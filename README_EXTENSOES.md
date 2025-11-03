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

# Instala modelos spaCy (PT)
python -m spacy download pt_core_news_sm

# OU para melhor qualidade (mais pesado)
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

**Localização:** `ingestor/etl_a2.py`

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

