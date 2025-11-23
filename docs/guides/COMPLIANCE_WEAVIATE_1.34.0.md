# Conformidade com Weaviate 1.34.0 - Named Vectors BYOV

## 📋 Resumo

Este documento valida se o sistema Verba segue as regras obrigatórias do Weaviate 1.34.0 para criação de schemas com named vectors em modo BYOV (Bring Your Own Vectors).

## ✅ Regras Obrigatórias (Weaviate 1.34.0)

### 1. **NÃO pode ter `vectorizer` no nível da classe**
- ❌ **Errado**: `{"class": "MyClass", "vectorizer": "none", "vectorConfig": {...}}`
- ✅ **Correto**: `{"class": "MyClass", "vectorConfig": {...}}`

### 2. **NÃO pode ter `vectorIndexType` / `vectorIndexConfig` no nível da classe**
- ❌ **Errado**: `{"class": "MyClass", "vectorIndexType": "hnsw", "vectorConfig": {...}}`
- ✅ **Correto**: `{"class": "MyClass", "vectorConfig": {...}}`

### 3. **Tudo deve ir dentro de `vectorConfig`**
- `vectorConfig` é um mapa de named vectors
- Cada named vector tem sua própria configuração

### 4. **`vectorizer` NÃO é string, é objeto**
- ❌ **Errado**: `"vectorizer": "none"` ou `"vectorizer": {}`
- ✅ **Correto**: `"vectorizer": {"none": {}}`

### 5. **Named vector `default` é obrigatório**
- Mesmo que não seja usado, deve existir em `vectorConfig`
- Pode ser preenchido com o mesmo vetor de outro named vector

### 6. **Formato completo de cada named vector**
```json
{
  "vectorConfig": {
    "default": {
      "vectorizer": {
        "none": {}
      },
      "vectorIndexType": "hnsw",
      "vectorIndexConfig": {
        "distance": "cosine"
      }
    },
    "concept_vec": {
      "vectorizer": {
        "none": {}
      },
      "vectorIndexType": "hnsw",
      "vectorIndexConfig": {
        "distance": "cosine"
      }
    }
  }
}
```

---

## 🔍 Análise do Sistema Verba

### ✅ **Conformidade: CORRIGIDA**

#### **Arquivo: `verba_extensions/integration/vector_config_builder.py`**

**Antes (❌ Não conforme):**
```python
base_vector_config = {
    "vectorIndexType": "hnsw",
    "vectorIndexConfig": {
        "distance": "cosine",
        **pq_config
    }
}

vector_config = {
    "concept_vec": {**base_vector_config},
    "sector_vec": {**base_vector_config},
    "company_vec": {**base_vector_config}
}
```

**Problemas:**
1. ❌ Faltava `vectorizer: {"none": {}}` em cada named vector
2. ❌ Faltava named vector `default` (obrigatório)

**Depois (✅ Conforme):**
```python
base_vector_config = {
    "vectorizer": {
        "none": {}  # BYOV mode - objeto, não string
    },
    "vectorIndexType": "hnsw",
    "vectorIndexConfig": {
        "distance": "cosine",
        **pq_config
    }
}

vector_config = {
    "default": {**base_vector_config},  # Obrigatório
    "concept_vec": {**base_vector_config},
    "sector_vec": {**base_vector_config},
    "company_vec": {**base_vector_config}
}
```

**Correções aplicadas:**
1. ✅ Adicionado `vectorizer: {"none": {}}` em cada named vector
2. ✅ Adicionado named vector `default` obrigatório
3. ✅ Validação atualizada para verificar formato correto do `vectorizer`

---

#### **Arquivo: `verba_extensions/integration/schema_updater.py`**

**Status: ✅ JÁ ESTAVA CORRETO**

O `schema_updater.py` cria o schema assim:
```python
schema_dict = {
    "class": collection_name,
    "description": "...",
    "vectorConfig": vector_config,  # Vem do vector_config_builder
    "properties": [...]
}
```

**Verificações:**
- ✅ **NÃO** adiciona `vectorizer` no nível da classe
- ✅ **NÃO** adiciona `vectorIndexType` no nível da classe
- ✅ Usa apenas `vectorConfig` (correto)
- ✅ Usa `create_from_dict()` para named vectors (correto)

---

## 📝 Validação Atualizada

A função `validate_vector_config()` foi atualizada para verificar:

1. ✅ `vectorizer` existe e é objeto `{"none": {}}`
2. ✅ `vectorIndexType` existe
3. ✅ `vectorIndexConfig` existe com `distance`
4. ✅ Named vector `default` existe

---

## 🎯 Schema Final Gerado

Quando `ENABLE_NAMED_VECTORS=true`, o sistema gera:

```json
{
  "class": "VERBA_Embedding_all_MiniLM_L6_v2",
  "description": "Collection com named vectors: concept_vec, sector_vec, company_vec",
  "vectorConfig": {
    "default": {
      "vectorizer": {
        "none": {}
      },
      "vectorIndexType": "hnsw",
      "vectorIndexConfig": {
        "distance": "cosine",
        "pq": {
          "enabled": false
        }
      }
    },
    "concept_vec": {
      "vectorizer": {
        "none": {}
      },
      "vectorIndexType": "hnsw",
      "vectorIndexConfig": {
        "distance": "cosine",
        "pq": {
          "enabled": false
        }
      }
    },
    "sector_vec": {
      "vectorizer": {
        "none": {}
      },
      "vectorIndexType": "hnsw",
      "vectorIndexConfig": {
        "distance": "cosine",
        "pq": {
          "enabled": false
        }
      }
    },
    "company_vec": {
      "vectorizer": {
        "none": {}
      },
      "vectorIndexType": "hnsw",
      "vectorIndexConfig": {
        "distance": "cosine",
        "pq": {
          "enabled": false
        }
      }
    }
  },
  "properties": [...]
}
```

---

## ⚠️ Importante: Named Vector `default`

O named vector `default` é **obrigatório** pelo Weaviate 1.34.0, mesmo que não seja usado nas queries.

**Recomendação:**
- Ao inserir objetos, você pode preencher `default` com o mesmo vetor de `concept_vec` (ou outro)
- Nas queries, use `targetVector: "concept_vec" | "sector_vec" | "company_vec"` para buscar nos named vectors especializados

**Exemplo de inserção:**
```python
vectors = {
    "default": embedding,  # Pode ser igual a concept_vec
    "concept_vec": embedding,
    "sector_vec": sector_embedding,
    "company_vec": company_embedding
}
```

---

## ✅ Checklist de Conformidade

- [x] **NÃO** tem `vectorizer` no nível da classe
- [x] **NÃO** tem `vectorIndexType` no nível da classe
- [x] **NÃO** tem `vectorIndexConfig` no nível da classe
- [x] `vectorConfig` é um mapa de named vectors
- [x] Cada named vector tem `vectorizer: {"none": {}}` (objeto, não string)
- [x] Cada named vector tem `vectorIndexType: "hnsw"`
- [x] Cada named vector tem `vectorIndexConfig` com `distance`
- [x] Named vector `default` existe em `vectorConfig`
- [x] Validação verifica formato correto

---

## 🔗 Referências

- [Weaviate Docs: Collection definition](https://docs.weaviate.io/weaviate/config-refs/collections)
- [Weaviate Docs: Vectorizer and vector index config](https://docs.weaviate.io/weaviate/manage-collections/vector-config)
- [Stack Overflow: How to use weaviate named vectors?](https://stackoverflow.com/questions/78886116/how-to-use-weaviate-named-vectors)

---

## 📅 Data da Validação

**Data:** 2025-11-XX  
**Versão Weaviate:** 1.34.0  
**Status:** ✅ **CONFORME** (após correções)

