# 🎯 Verba Extensions - Tudo Integrado na UI Original

## ✨ Vantagens da Abordagem Integrada

✅ **Uma única interface** - Tudo via UI do Verba  
✅ **Zero serviços paralelos** - Tudo roda no mesmo processo  
✅ **Upgrade mais simples** - Plugins isolados, compatibilidade automática  
✅ **UX nativa** - Usuário não percebe diferença  

## 🏗️ Arquitetura Simplificada

```
┌─────────────────────────────┐
│   Verba UI Original         │ ← Interface única
└────────────┬────────────────┘
             │
    ┌────────▼────────────────────┐
    │  Plugin System              │
    │  - A2 Readers (URL/Results) │ ← Aparecem como Readers normais
    │  - EntityAware Retriever    │ ← Aparece como Retriever normal
    │  - ETL Hook                 │ ← Executa automaticamente
    └─────────────────────────────┘
             │
    ┌────────▼────────────────────┐
    │  Verba Core                 │ ← Atualizado via pip/git
    │  - Reader.load()            │
    │  - Chunker.chunk()          │
    │  - Embedder.vectorize()     │
    │  - Import + ETL Hook        │ ← ETL dispara aqui
    └─────────────────────────────┘
```

## 📦 Componentes Integrados

### 1. A2 Readers (Plugin)

**Arquivo:** `verba_extensions/plugins/a2_reader.py`

**Funcionalidade:**
- Aparece como **"A2 URL Ingestor"** na lista de Readers
- Aparece como **"A2 Results Ingestor"** na lista de Readers
- Usuário seleciona como qualquer outro Reader do Verba
- Configuração via UI normal do Verba

**Uso na UI:**
1. Vá em "Import Data"
2. Selecione Reader "A2 URL Ingestor"
3. Cole URLs (uma por linha)
4. Configure "Enable ETL" se quiser
5. Clique em importar

### 2. Entity-Aware Retriever (Plugin)

**Arquivo:** `verba_extensions/plugins/entity_aware_retriever.py`

**Funcionalidade:**
- Aparece como **"EntityAware"** na lista de Retrievers
- Usuário seleciona no Config do Verba
- Funciona como qualquer retriever padrão

### 3. ETL A2 (Hook Automático)

**Arquivo:** `verba_extensions/plugins/a2_etl_hook.py`

**Funcionalidade:**
- Executa **automaticamente** após importação
- Não precisa configuração manual
- Roda se `enable_etl=true` no documento

**Fluxo:**
```
Import → Chunking → Embedding → Import no Weaviate → [Hook ETL] → Patch
```

## 🚀 Quick Start

### 1. Instalação

```bash
# Dependências
pip install -r requirements-extensions.txt

# Modelo spaCy (opcional, só se usar ETL)
python -m spacy download pt_core_news_sm
```

### 2. Configuração

```bash
# .env (opcional)
SPACY_MODEL=pt_core_news_sm
VERBA_PLUGINS_DIR=verba_extensions/plugins
VERBA_AUTO_INIT_EXTENSIONS=true
WEAVIATE_TENANT=news_v1  # Se usar tenantização
```

### 3. Inicialização

**Opção A: Auto-load (Recomendado)**
```python
# No início do script, ANTES de importar Verba
import verba_extensions.startup
from goldenverba.server.api import app
```

**Opção B: Via CLI do Verba**
```bash
# Modifica o CLI do Verba para auto-carregar
# Ou cria wrapper
verba start --with-extensions
```

### 4. Uso na UI

#### Ingestão de URLs

1. Abra Verba UI (localhost:8000)
2. Vá em **"Import Data"**
3. Selecione Reader: **"A2 URL Ingestor"**
4. Configure:
   - **URLs**: Cole URLs (uma por linha)
   - **Language Hint**: pt, en, etc.
   - **Enable ETL**: ✅ (marca para rodar ETL)
5. Clique em **Import**

#### Ingestão de Results JSON

1. Abra Verba UI
2. Vá em **"Import Data"**
3. Selecione Reader: **"A2 Results Ingestor"**
4. Configure:
   - **Results JSON**: Cole JSON com `{"results": [...]}`
   - **Enable ETL**: ✅
5. Clique em **Import**

#### Uso do Entity-Aware Retriever

1. Vá em **"Config"** no Verba
2. Selecione **Retriever**: "EntityAware"
3. Configure filtros (se necessário)
4. Use normalmente no Chat

## 📊 Fluxo Completo Integrado

### Cenário: Importar URL com ETL

```
1. Usuário seleciona "A2 URL Ingestor" na UI
   ↓
2. Verba chama: A2URLReader.load()
   ↓
3. Retorna: list[Document] com doc_meta["enable_etl"] = True
   ↓
4. Verba processa normalmente:
   - Chunker.chunk()
   - Embedder.vectorize()
   ↓
5. VerbaManager.import_document()
   ↓
6. Hook "import.after" dispara automaticamente
   ↓
7. ETL A2 roda e faz patch no Weaviate
   ↓
8. Documento pronto com metadados entity-aware
```

### Cenário: Consulta Entity-Aware

```
1. Usuário faz pergunta no Chat
   ↓
2. Verba usa EntityAware Retriever
   ↓
3. Retriever constrói filtros where (entity_ids)
   ↓
4. Busca híbrida COM pre-filter
   ↓
5. Retorna chunks relevantes (zero contaminação)
   ↓
6. Generator cria resposta
```

## 🔧 Configuração Avançada

### Schema Weaviate

**Importante:** Se usar Article/Passage schema customizado, precisa criar antes:

```python
# scripts/create_schema.py
python scripts/create_schema.py
```

**OU** usar schema padrão do Verba (funciona sem schema customizado também).

### ETL Opcional

O ETL só roda se:
- ✅ `enable_etl=True` no documento (config do Reader)
- ✅ spaCy instalado e modelo disponível
- ✅ Gazetteer encontrado (opcional, funciona sem)

### Gazetteer Customizado

Crie `verba_extensions/resources/gazetteer.json`:

```json
[
  {
    "entity_id": "ent:org:google",
    "aliases": ["Google", "Alphabet", "GCP"]
  }
]
```

## 🎯 Comparação: Integrado vs Separado

### ✅ Integrado (Atual)

- Uma única interface
- Sem serviços paralelos
- Upgrade simples
- UX nativa
- Plugins isolados

### ❌ Separado (Anterior)

- Duas interfaces (Verba + Ingestor)
- Dois serviços para gerenciar
- Upgrade mais complexo
- UX fragmentada

## 🚨 Troubleshooting

### Reader não aparece na UI

1. Verifica que plugins foram carregados:
   ```python
   from verba_extensions.plugin_manager import PluginManager
   pm = PluginManager()
   print(pm.list_plugins())
   ```

2. Verifica logs do Verba ao iniciar

### ETL não executa

1. Verifica que `enable_etl=True` no Reader
2. Verifica que spaCy está instalado
3. Verifica logs: procura "ETL A2: X passages atualizados"

### Entity-Aware não filtra

1. Verifica que ETL rodou (passages têm `entities_local_ids`)
2. Verifica que orquestrador está gerando entity_ids da query
3. Verifica filtros `where` no retriever

## 📝 Exemplo Completo

### 1. Importar URL com ETL

```python
# Via UI do Verba:
# 1. Import Data
# 2. Reader: "A2 URL Ingestor"
# 3. URLs: "https://exemplo.com/artigo"
# 4. Enable ETL: ✅
# 5. Import
```

### 2. Consultar com Entity-Aware

```python
# Via UI do Verba:
# 1. Config → Retriever: "EntityAware"
# 2. Chat → Pergunta: "Análises sobre Google"
# 3. Sistema filtra automaticamente por entity_ids
```

## ✅ Checklist de Uso

- [ ] Plugins carregados (logs mostram "X plugins carregados")
- [ ] Readers aparecem na UI ("A2 URL Ingestor", "A2 Results Ingestor")
- [ ] Retriever aparece ("EntityAware")
- [ ] ETL executa (logs mostram "ETL A2: X passages atualizados")
- [ ] Passages têm metadados (`entities_local_ids`, etc.)
- [ ] Consultas funcionam com filtros entity-aware

---

**Resultado:** Tudo integrado na UI original do Verba, zero serviços paralelos! 🎉

