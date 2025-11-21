# 🚀 Sistema de Extensões Verba - Guia Completo

## 📋 Visão Geral

Sistema completo de extensões para o Verba que permite:
- ✅ **RAG Entity-Aware** (anti-contaminação)
- ✅ **ETL externo** (NER + Section Scope)
- ✅ **Minisserviço de ingestão** FastAPI
- ✅ **Upgrade automático** do Verba sem perder extensões

## 🏗️ Arquitetura

```
┌─────────────────┐
│   Verba Core    │ ← Atualizado via pip/git
└────────┬────────┘
         │
    ┌────▼────────────────────────┐
    │  Plugin Manager              │ ← Carrega extensões
    │  Version Checker            │ ← Verifica compatibilidade
    │  Hooks System               │ ← Injeta comportamento
    └────┬────────────────────────┘
         │
    ┌────▼────────────────────────┐
    │  Extensões                  │
    │  - EntityAware Retriever    │
    │  - ETL A2                   │
    │  - Custom Components        │
    └─────────────────────────────┘

┌─────────────────────────────────┐
│  Ingestor FastAPI               │ ← Minisserviço separado
│  - POST /ingest/urls            │
│  - POST /ingest/results         │
│  - POST /etl/patch              │
└─────────────────────────────────┘
```

## 🚀 Quick Start

### 1. Instalação

```bash
# Instala dependências de extensões
pip install -r requirements-extensions.txt

# Instala modelos spaCy (PT + EN para code-switching)
python -m spacy download pt_core_news_sm en_core_web_sm

# OU para melhor qualidade (mais pesado em PT)
python -m spacy download pt_core_news_lg
```

### 2. Configuração

```bash
# .env
WEAVIATE_URL=http://weaviate:8080
WEAVIATE_TENANT=news_v1
WEAVIATE_API_KEY=  # vazio se sem auth
ETL_ON_INGEST=true
SPACY_MODEL=pt_core_news_sm
VERBA_PLUGINS_DIR=verba_extensions/plugins
```

### 3. Inicialização

#### Opção A: Auto-load (Recomendado)

```python
# No início do seu script, ANTES de importar Verba
import verba_extensions.startup
# Agora importa Verba normalmente
from goldenverba.server.api import app
```

#### Opção B: Manual

```python
from verba_extensions.startup import initialize_extensions
plugin_manager, version_checker = initialize_extensions()
```

### 4. Criar Schema Weaviate

```python
# scripts/create_schema.py
python scripts/create_schema.py
```

### 5. Rodar Ingestor

```bash
# Terminal 1: Ingestor
cd ingestor
uvicorn app:app --host 0.0.0.0 --port 8001

# Terminal 2: Verba (com extensões)
verba start
```

## 📦 Componentes

### 1. Entity-Aware Retriever

**Localização:** `verba_extensions/plugins/entity_aware_retriever.py`

**Funcionalidade:**
- Filtros entity-aware via Weaviate `where`
- Pre-filter antes do ANN/HNSW
- Anti-contaminação automática

**Uso no Verba:**
1. Plugin carregado automaticamente
2. Aparece como "EntityAware" no seletor de retriever
3. Configuração via UI do Verba

### 2. ETL A2

**Localização:** `verba_extensions/etl/etl_a2.py`

**Funcionalidade:**
- NER com spaCy
- Section Scope (heading > first_para > parent)
- Normalização via gazetteer
- Patch automático no Weaviate

**Execução:**
```bash
# Automático durante ingestão
POST /ingest/urls {"run_etl": true}

# Manual em lote
POST /etl/patch {"tenant": "news_v1", "limit": 500}
```

### 2.1. Google Drive Reader (ETL A2 Integrado) ⭐ NOVO

**Localização:** `verba_extensions/plugins/google_drive_reader.py`

**Funcionalidade:**
- Importa arquivos diretamente do Google Drive
- Suporta Service Account e OAuth 2.0
- Lista arquivos de pastas/compartilhamentos
- Baixa arquivos automaticamente
- **ETL A2 automático** - NER + Section Scope em todos os arquivos
- Suporte recursivo a subpastas
- Múltiplos formatos (PDF, DOCX, TXT, MD, XLSX, PPTX, etc.)

**Configuração:**
```bash
# Service Account (recomendado)
export GOOGLE_DRIVE_CREDENTIALS="/caminho/para/service-account-key.json"

# OAuth 2.0 (alternativa)
export GOOGLE_DRIVE_CREDENTIALS="/caminho/para/token.json"
```

**Uso no Verba:**
1. Plugin carregado automaticamente
2. Aparece como "Google Drive (ETL A2)" no seletor de readers tipo "URL"
3. Configure Folder ID ou File IDs na interface
4. Arquivos são importados com ETL A2 habilitado automaticamente

**Documentação completa:** `verba_extensions/plugins/GOOGLE_DRIVE_README.md`

### 3. Minisserviço de Ingestão

**Endpoints:**
- `GET /` - UI simples (HTML form)
- `POST /ingest/urls` - Ingesta URLs
- `POST /ingest/results` - Ingesta conteúdo já extraído
- `POST /etl/patch` - Reprocessa ETL em lote
- `GET /status` - Status e estatísticas

**Exemplo de Uso:**
```bash
curl -X POST http://localhost:8001/ingest/results \
  -H 'Content-Type: application/json' \
  -d '{
    "results": [{
      "url": "https://exemplo.com/artigo",
      "content": "Conteúdo do artigo...",
      "title": "Título",
      "metadata": {"language": "pt"}
    }],
    "tenant": "news_v1",
    "run_etl": true,
    "batch_tag": "manual_2024"
  }'
```

---

## 🆕 Componentes RAG2 (Alto Valor, Baixa Complexidade)

Componentes copiados do RAG2 para melhorar observabilidade, performance e qualidade:

### 4. TelemetryMiddleware ⭐ CRÍTICO

**Localização:** `verba_extensions/middleware/telemetry.py`

**Funcionalidade:**
- Middleware FastAPI para observabilidade de API
- Registra latência, contagem de requests e erros por endpoint
- Calcula percentis (p50, p95, p99) automaticamente
- Log estruturado em JSON
- SLO checking (verifica se p95 < threshold)

**Integração:**
```python
# Em goldenverba/server/api.py
from verba_extensions.middleware.telemetry import TelemetryMiddleware

app.add_middleware(TelemetryMiddleware, enable_logging=True)

# Endpoint opcional para stats
@app.get("/api/telemetry/stats")
async def get_telemetry_stats():
    return TelemetryMiddleware.get_shared_stats()
```

**Documentação:** `GUIA_INTEGRACAO_RAG2_COMPONENTES.md`

---

### 5. Embeddings Cache ⭐ CRÍTICO

**Localização:** `verba_extensions/utils/embeddings_cache.py`

**Funcionalidade:**
- Cache in-memory determinístico de embeddings
- Evita re-embedding de textos idênticos
- Estatísticas de hit rate
- Reduz custo de APIs e melhora performance

**Integração:**
```python
from verba_extensions.utils.embeddings_cache import get_cached_embedding, get_cache_key

cache_key = get_cache_key(text=chunk.text, doc_uuid=str(doc.uuid))
embedding, was_cached = get_cached_embedding(
    text=chunk.text,
    cache_key=cache_key,
    embed_fn=lambda t: self._call_embedding_api(t)
)
```

**Documentação:** `GUIA_INTEGRACAO_RAG2_COMPONENTES.md`

---

### 6. Telemetry Collector

**Localização:** `verba_extensions/utils/telemetry.py`

**Funcionalidade:**
- Coleta métricas de normalização e cobertura
- Rastreia gaps em mapeamentos
- Gera relatórios JSON para melhoria contínua

**Uso:**
```python
from verba_extensions.utils.telemetry import get_telemetry

telemetry = get_telemetry()
telemetry.record_title_normalization(method="regex", original_title="CEO")
telemetry.record_chunk_filtered_by_quality(parent_type="section", score=0.25, reason="LEN_V_SHORT")
```

---

### 7. UUID Determinístico

**Localização:** `verba_extensions/utils/uuid.py`

**Funcionalidade:**
- Gera UUIDs determinísticos (UUID v5) para idempotência
- Permite re-uploads sem duplicatas
- Upsert seguro

**Uso:**
```python
from verba_extensions.utils.uuid import generate_doc_uuid, generate_chunk_uuid

doc_uuid = generate_doc_uuid(source_url=doc.meta.get("source_url"), title=doc.title)
chunk_uuid = generate_chunk_uuid(doc_uuid=doc_uuid, chunk_id=f"{doc_uuid}:{chunk.chunk_id}")
```

---

### 8. Text Preprocessing

**Localização:** `verba_extensions/utils/preprocess.py`

**Funcionalidade:**
- Normaliza texto antes de embedding
- Garante consistência entre texto armazenado e embeddado
- Remove unicode invisível e normaliza whitespace

**Uso:**
```python
from verba_extensions.utils.preprocess import prepare_for_embedding

text_for_embedding = prepare_for_embedding(chunk.text)
embedding = embedder.embed(text_for_embedding)
```

---

### 9. Quality Scoring

**Localização:** `verba_extensions/utils/quality.py`

**Funcionalidade:**
- Calcula score de qualidade de chunks (0.0-1.0)
- Filtra conteúdo de baixa qualidade automaticamente
- Type-aware scoring (diferentes thresholds por tipo)

**Uso:**
```python
from verba_extensions.utils.quality import compute_quality_score

score, reason = compute_quality_score(
    text=chunk.text,
    parent_type=chunk.meta.get("parent_type"),
    is_summary=chunk.meta.get("is_summary", False)
)

if score < 0.3:  # Threshold configurável
    # Filtrar chunk
    continue
```

**Documentação completa:** `GUIA_INTEGRACAO_RAG2_COMPONENTES.md` e `ANALISE_RAG2_COMPONENTES_ALTO_VALOR.md`

## 🔄 Upgrade Automático

### Processo

1. **Atualiza Verba:**
   ```bash
   pip install --upgrade goldenverba
   ```

2. **Sistema verifica automaticamente:**
   - ✅ Compatibilidade de interfaces
   - ✅ Mudanças em assinaturas
   - ✅ Novos métodos obrigatórios

3. **Logs informativos:**
   ```
   ℹ️ Verba version: 2.1.3
   ✅ Extensões compatíveis
   ✅ 2 plugins carregados
   ```

### Compatibilidade

O sistema detecta automaticamente:
- ✅ Mudanças em interfaces (Retriever, Generator, etc.)
- ✅ Novos métodos obrigatórios
- ✅ Mudanças em assinaturas

Se incompatível, mostra warnings:
```
⚠️ Incompatibilidade em Retriever: Método retrieve mudou
💡 Sugestão: Atualize plugin entity_aware_retriever
```

## 📝 Criando Novos Plugins

### Template Básico

```python
# verba_extensions/plugins/meu_plugin.py

from goldenverba.components.interfaces import Retriever  # ou Generator, Reader, etc.
from goldenverba.components.types import InputConfig

class MeuComponente(Retriever):
    def __init__(self):
        super().__init__()
        self.name = "MeuComponente"
        self.description = "Descrição do componente"
        # Configuração
        self.config["Minha Config"] = InputConfig(
            type="text",
            value="default",
            description="Descrição",
            values=[]
        )
    
    async def retrieve(self, client, query, vector, config, weaviate_manager, embedder, labels, document_uuids):
        # Sua lógica aqui
        pass

def register():
    return {
        'name': 'meu_plugin',
        'version': '1.0.0',
        'description': 'Plugin customizado',
        'retrievers': [MeuComponente()],  # ou generators, readers, etc.
        'compatible_verba_version': '>=2.1.0'
    }
```

### Plugin com Hooks

```python
from verba_extensions.hooks import global_hooks

def before_retrieve(query, **kwargs):
    # Modifica query antes da busca
    return f"query modificado: {query}"

# Registra hook
global_hooks.register_hook('retrieve.before', before_retrieve, priority=50)
```

## 🧪 Testes

### Verificar Compatibilidade

```python
from verba_extensions.version_checker import VersionChecker

vc = VersionChecker()
info = vc.get_version_info()
checks = vc.check_api_changes()

for component, status in checks.items():
    print(f"{component}: {'✅' if status['compatible'] else '❌'}")
```

### Testar Plugin

```python
from verba_extensions.plugin_manager import PluginManager

pm = PluginManager()
pm.load_plugin("verba_extensions/plugins/meu_plugin.py")
print(pm.list_plugins())
```

## 📊 Monitoramento

### Logs Automáticos

O sistema loga:
- ✅ Plugins carregados
- ✅ Compatibilidade verificada
- ⚠️ Warnings de incompatibilidade
- ❌ Erros de carregamento

### Status Endpoint

```bash
GET /status
# Retorna:
{
  "tenant": "news_v1",
  "weaviate_url": "http://weaviate:8080",
  "etl_on_ingest": true,
  "jobs": [...],
  "last": {...},
  "queue_size": 0
}
```

## 🛠️ Troubleshooting

### Plugin não carrega

1. Verifica que tem função `register()`
2. Verifica compatibilidade: `python -c "from verba_extensions.version_checker import VersionChecker; VersionChecker().check_api_changes()"`
3. Verifica logs do Verba

### Extensões não aparecem no Verba

1. Verifica que `VERBA_AUTO_INIT_EXTENSIONS=true`
2. Verifica que plugins estão em `VERBA_PLUGINS_DIR`
3. Reinicia o Verba

### ETL não roda

1. Verifica conexão Weaviate
2. Verifica que schema foi criado (Article/Passage)
3. Verifica modelos spaCy: `python -m spacy info pt_core_news_sm`

## 📚 Documentação Adicional

- `GUIA_UPGRADE_AUTOMATICO.md` - Guia detalhado de upgrades
- `SOLUCAO_RAILWAY.md` - Solução para Railway sem API key
- `ANALISE_PROJETO.md` - Análise completa do projeto Verba

## ✅ Checklist de Deploy

- [ ] Schema Weaviate criado
- [ ] Modelos spaCy instalados
- [ ] Variáveis de ambiente configuradas
- [ ] Plugins na pasta correta
- [ ] Verifica compatibilidade
- [ ] Testa ingestão
- [ ] Testa ETL
- [ ] Testa retriever entity-aware

---

**Resultado:** Sistema completo de extensões que funciona com qualquer versão do Verba! 🎉

