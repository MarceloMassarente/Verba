# ✅ Sistema Integrado no Verba - Tudo pela UI Original

## 🎯 Solução Final

**Tudo roda pela UI original do Verba, sem serviços paralelos!**

### Componentes como Plugins:

1. ✅ **A2 Readers** → Plugin (aparecem na lista de Readers)
   - "A2 URL Ingestor" - para ingerir URLs
   - "A2 Results Ingestor" - para ingerir JSON results

2. ✅ **ETL A2** → Hook automático (executa após import)
   - Não precisa chamar manualmente
   - Ativado via checkbox "Enable ETL" no Reader

3. ✅ **Entity-Aware Retriever** → Plugin (aparece na lista de Retrievers)
   - Selecionável normalmente na UI

## 🚀 Quick Start

### 1. Instalação

```bash
# Dependências extras (só para os plugins)
pip install httpx trafilatura

# Se usar ETL (opcional)
pip install spacy
python -m spacy download pt_core_news_sm en_core_web_sm
```

### 2. Inicialização

```python
# No início do seu script, ANTES de importar Verba
import verba_extensions.startup

# Agora importa normalmente
from goldenverba.server.api import app
```

**OU** modifique o CLI do Verba para auto-carregar.

### 3. Uso na UI

#### Importar URLs

1. Abra Verba UI (`localhost:8000`)
2. Vá em **"Import Data"**
3. Selecione Reader: **"A2 URL Ingestor"**
4. Configure:
   - **URLs**: Cole URLs (uma por linha)
   - **Language Hint**: pt, en, etc.
   - **Enable ETL**: ✅ (marca para rodar ETL automaticamente)
5. Clique em **Import**

**Resultado:**
- ✅ Documento importado
- ✅ ETL executado automaticamente em background
- ✅ Metadados entity-aware no Weaviate

#### Usar Entity-Aware Retriever

1. Vá em **"Config"** no Verba
2. Selecione Retriever: **"EntityAware"**
3. Use normalmente no Chat
4. Sistema filtra automaticamente por entidades

## 📁 Estrutura Simplificada

```
verba_extensions/
├── plugins/
│   ├── a2_reader.py              ← Readers integrados
│   ├── a2_etl_hook.py            ← ETL automático
│   └── entity_aware_retriever.py ← Retriever entity-aware
├── integration/
│   └── import_hook.py            ← Hook no import_document
└── startup.py                     ← Auto-inicialização
```

## 💡 Vantagens

### ✅ Simplicidade
- **Um serviço** ao invés de dois
- **Uma interface** ao invés de duas
- **Zero configuração** de serviços paralelos

### ✅ Upgrade Automático
- **Plugins isolados** - Não afetam core do Verba
- **Compatibilidade automática** - Version checker detecta mudanças
- **Upgrade simples** - `pip install --upgrade goldenverba`

### ✅ UX Nativa
- **Experiência familiar** - Usa UI padrão do Verba
- **Configuração integrada** - Tudo no mesmo lugar
- **Zero aprendizado** - Usuário não precisa saber de plugins

## 🔄 Fluxo Integrado

```
Usuário na UI do Verba
  ↓
Seleciona Reader "A2 URL Ingestor"
  ↓
Configura URLs + Enable ETL ✅
  ↓
Clica Import
  ↓
Verba processa:
  - Reader.load() → Documents
  - Chunker.chunk()
  - Embedder.vectorize()
  - Import no Weaviate
  ↓
Hook dispara ETL automaticamente (background)
  ↓
✅ Documento pronto com metadados entity-aware
```

## 📊 Comparação

| Aspecto | Separado | **Integrado (Atual)** |
|---------|----------|----------------------|
| Serviços | 2 | **1** ✅ |
| Portas | 2 | **1** ✅ |
| Interfaces | 2 | **1** ✅ |
| Upgrade | Complexo | **Simples** ✅ |
| UX | Fragmentada | **Nativa** ✅ |

## ✅ Resultado

**Tudo funciona pela UI original do Verba:**
- ✅ Importação de URLs/Results → Readers plugins
- ✅ ETL automático → Hook transparente
- ✅ Entity-aware → Retriever plugin

**Zero serviços paralelos, upgrade simples, UX nativa!** 🎉

## 📚 Documentação

- `README_INTEGRADO.md` - Guia completo integrado
- `GUIA_UPGRADE_AUTOMATICO.md` - Como fazer upgrades
- `GUIA_COMPARACAO.md` - Separado vs Integrado
- `RESUMO_REFATORACAO.md` - O que mudou
- **`API_GUIDE.md`** - Guia completo de uso da API externa ✨ **NOVO**

## 🎯 Named Vectors (Multi-Vector)

O sistema suporta **múltiplos vetores** por chunk no Weaviate:

- **`default`**: Vetor principal para busca semântica geral ✅ (automático)
- **`company_vec`**: Vetor especializado para empresas
- **`concept_vec`**: Vetor para conceitos de negócio
- **`sector_vec`**: Vetor para setores/indústrias

### Como Funciona

✅ **Automático** - O código já usa `targetVector: "default"` por padrão  
✅ **Auto-fallback** - Encontra collection com dados automaticamente  
✅ **Schema Rico** - 44 campos ETL-aware incluindo entities, frameworks, companies, sectors

Veja detalhes completos em [`API_GUIDE.md`](../API_GUIDE.md).

## 🌐 API Externa

### Quick Start

```python
import requests

BASE_URL = "https://verba-production.railway.app"

# 1. Get config
config = requests.post(
    f"{BASE_URL}/api/get_rag_config",
    headers={"Content-Type": "application/json", "Origin": BASE_URL},
    json={"deployment": "Custom", "url": "weaviate.railway.internal", "key": ""}
).json()["rag_config"]

# 2. Fix Advanced (obrigatório!)
if "Advanced" in config:
    adv = config["Advanced"]
    config["Advanced"] = {
        "selected": "Default",
        "components": {
            "Default": {
                "name": "Default",
                "variables": [],
                "library": [],
                "description": "Default Advanced Settings",
                "config": adv,
                "type": "",
                "available": True
            }
        }
    }

# 3. Query
result = requests.post(
    f"{BASE_URL}/api/query",
    headers={"Content-Type": "application/json", "Origin": BASE_URL},
    json={
        "query": "sua busca",
        "labels": [],
        "documentFilter": [],
        "credentials": {"deployment": "Custom", "url": "weaviate-url", "key": ""},
        "RAG": config
    }
).json()

print(f"Chunks encontrados: {len(result['documents'])}")
```

### Documentação Completa

Veja [`API_GUIDE.md`](../API_GUIDE.md) para:
- Estrutura completa de payload
- Exemplos com filtros
- Troubleshooting de erros 422/403/502
- Named vectors em detalhe
- Scripts funcionais

## ✨ Melhorias Recentes (2026-01-03)

### Auto-Fallback Inteligente
- ✅ Busca automaticamente collections com dados
- ✅ Funciona mesmo se embedder configurado diferir do usado na ingestão
- ✅ Logs detalhados mostram qual collection está sendo usada

### Multi-Vector Support
- ✅ Suporte completo a named vectors do Weaviate
- ✅ Usa `targetVector: 'default'` automaticamente
- ✅ Schema com 44 campos ETL-aware

### API Externa Funcional
- ✅ Endpoints documentados
- ✅ Exemplos práticos
- ✅ Guia de troubleshooting completo

