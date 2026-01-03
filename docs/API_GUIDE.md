# Verba API - Guia Completo

## 📋 Índice
- [Named Vectors (Multi-Vector)](#named-vectors-multi-vector)
- [Como Usar a API](#como-usar-a-api)
- [Estrutura do Payload](#estrutura-do-payload)
- [Exemplos Práticos](#exemplos-práticos)
- [Troubleshooting](#troubleshooting)

---

## 🎯 Named Vectors (Multi-Vector)

### O que são Named Vectors?

Weaviate suporta **múltiplos vetores** por objeto. A collection `VERBA_Embedding_all_MiniLM_L6_v2` usa 4 vetores:

- **`default`**: Vetor principal para busca semântica geral ✅ (PADRÃO)
- **`company_vec`**: Vetor específico para nomes de empresas
- **`concept_vec`**: Vetor para conceitos de negócio
- **`sector_vec`**: Vetor para setores/indústrias

### Como Funciona

Quando você faz uma query, o Verba **automaticamente usa** `targetVector: "default"`:

```python
# Em managers.py linha 1323
async def hybrid_chunks(
    self,
    ...
    target_vector: str = "default",  # ← PADRÃO AUTOMÁTICO
):
```

**Você não precisa fazer nada!** O código já está configurado corretamente.

### Schema Multi-Vector

#### Campos Principais
- `content`: Texto do chunk (substituiu `text`)
- `title`: Título do documento (substituiu `doc_name`)
- `doc_uuid`: ID do documento
- `chunk_id`: ID do chunk
- `frameworks`: Lista de frameworks mencionados
- `companies`: Lista de empresas mencionadas
- `sectors`: Lista de setores mencionados

#### Campos ETL Avançados (44 total)
- `concept_text`, `sector_text`, `company_text`: Textos específicos para cada vetor
- `entities_local_ids`, `parent_entities`: Referências de entidades
- `section_*`: Campos de contexto de seção
- E mais 30+ campos especializados

---

## 🚀 Como Usar a API

### Endpoint Base
```
https://verba-production-c347.up.railway.app
```

### Fluxo Básico

```
1. GET /api/get_rag_config  → Obter configuração
2. Fix RAG config           → Adicionar campos obrigatórios
3. POST /api/query          → Executar busca
```

### 1. Obter RAG Config

```python
import requests

BASE_URL = "https://verba-production-c347.up.railway.app"

headers = {
    "Content-Type": "application/json",
    "Origin": BASE_URL,
    "Referer": f"{BASE_URL}/"
}

# Get config
response = requests.post(
    f"{BASE_URL}/api/get_rag_config",
    headers=headers,
    json={
        "deployment": "Custom",
        "url": "weaviate.railway.internal",
        "key": ""
    },
    timeout=30
)

rag_config = response.json()["rag_config"]
```

### 2. Fix Advanced Structure

**CRÍTICO**: O RAG config retornado precisa ser ajustado antes de usar:

```python
# Fix Advanced component - adicionar campos obrigatórios
if "Advanced" in rag_config:
    adv = rag_config["Advanced"]
    
    # Converter para estrutura completa
    rag_config["Advanced"] = {
        "selected": "Default",
        "components": {
            "Default": {
                "name": "Default",
                "variables": [],
                "library": [],
                "description": "Default Advanced Settings",
                "config": adv,  # Settings vão aqui
                "type": "",
                "available": True
            }
        }
    }
```

### 3. Executar Query

```python
# Montar payload
query_payload = {
    "query": "caminhoes a gas GNL",
    "labels": [],                    # Filtrar por labels (opcional)
    "documentFilter": [],            # Filtrar por doc UUIDs (opcional)
    "credentials": {
        "deployment": "Custom",
        "url": "weaviate.railway.internal",
        "key": ""
    },
    "RAG": rag_config                # Config ajustado
}

# Executar query
response = requests.post(
    f"{BASE_URL}/api/query",
    headers=headers,
    json=query_payload,
    timeout=60
)

# Processar resultados
result = response.json()
documents = result.get("documents", [])

print(f"Encontrados {len(documents)} chunks!")
for doc in documents:
    print(f"- {doc.get('doc_name')}: {doc.get('score')}")
```

---

## 📦 Estrutura do Payload

### RAG Config Structure

```json
{
  "Reader": {
    "selected": "Universal A2 (Arquivos + URLs)",
    "components": { ... }
  },
  "Chunker": {
    "selected": "Entity-Semantic",
    "components": { ... }
  },
  "Embedder": {
    "selected": "SentenceTransformers",
    "components": { ... }
  },
  "Retriever": {
    "selected": "EntityAware",
    "components": { ... }
  },
  "Generator": {
    "selected": "UpstageGenerator",
    "components": { ... }
  },
  "Advanced": {
    "selected": "Default",
    "components": {
      "Default": {
        "name": "Default",
        "variables": [],
        "library": [],
        "description": "Default Advanced Settings",
        "config": {
          "Enable Named Vectors": {
            "type": "bool",
            "value": true,
            "description": "Enable named vectors...",
            "values": []
          }
        },
        "type": "",
        "available": true
      }
    }
  }
}
```

### Campos Obrigatórios - Advanced Component

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `name` | string | Nome do componente |
| `variables` | array | Lista de variáveis (pode ser vazia) |
| `library` | array | Lista de bibliotecas (pode ser vazia) |
| `description` | string | Descrição do componente |
| `config` | object | Configurações (settings do Advanced) |
| `type` | string | Tipo (pode ser vazio) |
| `available` | boolean | Se está disponível |

---

## 💡 Exemplos Práticos

### Exemplo 1: Busca Simples

```python
def simple_search(query_text):
    """Busca simples retornando chunks."""
    # Get config
    config_resp = requests.post(
        f"{BASE_URL}/api/get_rag_config",
        headers=headers,
        json={"deployment":"Custom", "url":"weaviate.railway.internal", "key":""}
    )
    rag_config = config_resp.json()["rag_config"]
    
    # Fix Advanced
    if "Advanced" in rag_config:
        adv = rag_config["Advanced"]
        rag_config["Advanced"] = {
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
    
    # Query
    result = requests.post(
        f"{BASE_URL}/api/query",
        headers=headers,
        json={
            "query": query_text,
            "labels": [],
            "documentFilter": [],
            "credentials": {
                "deployment": "Custom",
                "url": "weaviate.railway.internal",
                "key": ""
            },
            "RAG": rag_config
        }
    )
    
    return result.json()

# Usar
results = simple_search("caminhoes a gas")
print(f"Encontrados: {len(results['documents'])} chunks")
```

### Exemplo 2: Busca com Filtros

```python
def filtered_search(query_text, labels=None, doc_uuids=None):
    """Busca com filtros de labels e documentos."""
    # ... (mesmo código get_config e fix) ...
    
    result = requests.post(
        f"{BASE_URL}/api/query",
        headers=headers,
        json={
            "query": query_text,
            "labels": labels or [],              # Ex: ["financial", "tech"]
            "documentFilter": doc_uuids or [],   # Ex: ["uuid-123", "uuid-456"]
            "credentials": {...},
            "RAG": rag_config
        }
    )
    
    return result.json()

# Usar
results = filtered_search(
    "energia renovável",
    labels=["sustainability"],
    doc_uuids=["abc-123"]
)
```

### Exemplo 3: Script Completo Reutilizável

Veja `test_api_working.py` para script completo funcional.

---

## 🔧 Troubleshooting

### Erro 422: "Field required"

**Causa**: RAG config incompleto, faltam campos em Advanced

**Solução**: Aplicar o fix do Advanced (veja seção 2)

```python
# SEMPRE fazer isso antes de usar!
if "Advanced" in rag_config:
    adv = rag_config["Advanced"]
    rag_config["Advanced"] = {
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
```

### Erro 403: "Not allowed"

**Causa**: Headers CORS faltando

**Solução**: Adicionar headers corretos

```python
headers = {
    "Content-Type": "application/json",
    "Origin": BASE_URL,
    "Referer": f"{BASE_URL}/"
}
```

### Erro 502: "Application failed to respond"

**Causa**: Railway reiniciando ou timeout

**Solução**: Aguardar 30s e tentar novamente

### Zero Chunks Retornados

**Possíveis causas**:

1. **Query muito específica** - tente termos mais gerais
2. **Embedder errado** - auto-fallback deve resolver automaticamente
3. **Collection vazia** - verifique via Weaviate console

**Debug**:
```python
# Ver qual collection está sendo usada
# Logs do Railway mostram:
# "🎯 AUTO-FALLBACK: Using VERBA_Embedding_all_MiniLM_L6_v2 with 16 objects"
```

---

## 📚 Referências

### Código Relevante

- **managers.py linha 729-776**: Auto-fallback logic
- **managers.py linha 1323**: Default target_vector
- **managers.py linha 1360-1367**: targetVector application
- **graphql_builder.py linha 189**: GraphQL targetVector syntax

### Collections no Weaviate

```
VERBA_DOCUMENTS              → 2 objects (metadata dos docs)
VERBA_Embedding_all_MiniLM_L6_v2 → 16 objects (CHUNKS - USAR ESTA) ✅
VERBA_Embedding_SentenceTransformers → 0 objects (vazia)
```

### Named Vectors Disponíveis

Sempre use **`default`** para busca regular. Os outros vetores são para casos especializados:

- `default` ✅ - Busca semântica geral
- `company_vec` - Matching específico de empresas
- `concept_vec` - Matching de conceitos
- `sector_vec` - Matching de setores

---

## ✅ Quick Start

```python
import requests

BASE_URL = "https://verba-production-c347.up.railway.app"
headers = {
    "Content-Type": "application/json",
    "Origin": BASE_URL,
    "Referer": f"{BASE_URL}/"
}

# 1. Get config
config = requests.post(
    f"{BASE_URL}/api/get_rag_config",
    headers=headers,
    json={"deployment":"Custom", "url":"weaviate.railway.internal", "key":""}
).json()["rag_config"]

# 2. Fix Advanced
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
    headers=headers,
    json={
        "query": "sua busca aqui",
        "labels": [],
        "documentFilter": [],
        "credentials": {"deployment":"Custom", "url":"weaviate.railway.internal", "key":""},
        "RAG": config
    }
).json()

print(f"Chunks: {len(result['documents'])}")
```

---

**Documentação atualizada em**: 2026-01-03  
**Versão da API**: Railway Production  
**Status**: ✅ Funcionando
