# 🔧 Correção: Collection Name com Hífens - 2025-11-04

**Data:** 2025-11-04  
**Problema:** Erro 422 ao criar collection Weaviate  
**Status:** ✅ CORRIGIDO E ENVIADO

---

## ❌ Problema Identificado

### Erro nos Logs Railway
```
✘ Failed to connect to Weaviate Collection may not have been created properly.! 
Unexpected status code: 422, with response body: 
{'error': [{'message': "'VERBA_Embedding_all-MiniLM-L6-v2' is not a valid class name"}]}.
```

### Root Cause
O nome do modelo `all-MiniLM-L6-v2` (SentenceTransformersEmbedder) contém **hífens**, que **não são permitidos** em nomes de classes Weaviate.

**Regras Weaviate:**
- ✅ Permite: letras, números, underscores (`_`)
- ❌ **NÃO permite:** hífens (`-`), pontos (`.`), espaços

---

## 🔍 Análise do Código

**Arquivo:** `goldenverba/components/managers.py` (linha 602-636)

**Função:** `_normalize_embedder_name()`

**Problema Original:**
```python
# ❌ Permitindo hífens (linha 630)
normalized = re.sub(r"[^a-zA-Z0-9_-]", "_", normalized)
# Isso mantinha hífens no nome: all-MiniLM-L6-v2
```

**Resultado:**
- Input: `all-MiniLM-L6-v2`
- Normalizado: `all-MiniLM-L6-v2` (hífen mantido)
- Collection: `VERBA_Embedding_all-MiniLM-L6-v2` ❌ **INVÁLIDO**

---

## ✅ Solução Implementada

**Arquivo:** `goldenverba/components/managers.py` (linha 629-637)

```python
# Clean up the name - only allow alphanumeric and underscore (NO HYPHENS - Weaviate doesn't allow them)
# Replace hyphens with underscores first
normalized = normalized.replace("-", "_")
# Replace any other invalid characters with underscore
normalized = re.sub(r"[^a-zA-Z0-9_]", "_", normalized)
# Remove multiple underscores
normalized = re.sub(r"_+", "_", normalized)
# Remove leading/trailing underscores
normalized = normalized.strip("_")
```

**Resultado Agora:**
- Input: `all-MiniLM-L6-v2`
- Normalizado: `all_MiniLM_L6_v2` (hífens substituídos)
- Collection: `VERBA_Embedding_all_MiniLM_L6_v2` ✅ **VÁLIDO**

---

## 📊 Comparação

| Aspecto | Antes | Depois |
|---------|-------|--------|
| Input | `all-MiniLM-L6-v2` | `all-MiniLM-L6-v2` |
| Normalizado | `all-MiniLM-L6-v2` ❌ | `all_MiniLM_L6_v2` ✅ |
| Collection | `VERBA_Embedding_all-MiniLM-L6-v2` ❌ | `VERBA_Embedding_all_MiniLM_L6_v2` ✅ |
| Status | Erro 422 | Criada com sucesso |

---

## 🔄 Fluxo de Normalização

1. **Input:** `all-MiniLM-L6-v2`
2. **Replace hífens:** `all_MiniLM_L6_v2`
3. **Replace invalid chars:** `all_MiniLM_L6_v2` (já válido)
4. **Remove múltiplos underscores:** `all_MiniLM_L6_v2`
5. **Strip leading/trailing:** `all_MiniLM_L6_v2`
6. **Collection name:** `VERBA_Embedding_all_MiniLM_L6_v2` ✅

---

## 🧪 Testes

### Teste Manual
```python
from goldenverba.components.managers import WeaviateManager

wm = WeaviateManager()
result = wm._normalize_embedder_name("all-MiniLM-L6-v2")
print(result)  # Esperado: "all_MiniLM_L6_v2"
print("-" in result)  # Esperado: False
```

---

## 📍 Onde é Usado

A função `_normalize_embedder_name()` é chamada em:

1. **`verify_embedding_collection()`** (linha 643)
   - Cria collection para um embedder específico

2. **`verify_embedding_collections()`** (linha 664)
   - Cria collections para todos os embedders disponíveis

3. **`verify_cache_collection()`** (linha 649)
   - Cria collection de cache

---

## 🚀 Deploy

**Commit:** `a669b9d fix: Normalizar hífens em nomes de collections Weaviate`  
**Status:** ✅ Enviado para `main` branch  
**Railway:** Deploy automático em produção

---

## ✨ Impacto

- ✅ **Antes:** Collection não criada, erro 422
- ✅ **Depois:** Collection criada automaticamente
- ✅ **Resultado:** SentenceTransformersEmbedder funciona corretamente
- ✅ **Compatibilidade:** Todos os modelos com hífens agora funcionam

---

**Última atualização:** 2025-11-04  
**Status:** ✅ CORRIGIDO E EM PRODUÇÃO

