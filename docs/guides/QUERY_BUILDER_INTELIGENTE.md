# 🧠 Query Builder Inteligente - Conhece Schema e Valida

## ✅ Problema Resolvido

O `QueryRewriter` antigo só fazia expansão semântica genérica, **não conhecia o schema** e **não validava com o usuário**.

Agora temos um **`QueryBuilder`** que:
- ✅ **Conhece o schema do Weaviate** (obtém dinamicamente)
- ✅ **Gera queries complexas** com filtros, entidades, datas
- ✅ **Valida com o usuário** antes de executar
- ✅ **Usa LLM** para entender o prompt e extrair informações

---

## 🎯 O Que Foi Criado

### **1. QueryBuilderPlugin** (`verba_extensions/plugins/query_builder.py`)

**Features:**
- Obtém schema do Weaviate dinamicamente
- Conhece todas as propriedades disponíveis
- Detecta se collection é ETL-aware
- Usa LLM para entender prompt do usuário
- Gera query estruturada com filtros complexos

**Diferença do QueryRewriter:**
- QueryRewriter: Expansão semântica genérica (não conhece schema)
- QueryBuilder: Constrói query estruturada conhecendo schema

---

## 🔧 Como Funciona

### **1. Obtém Schema do Weaviate**

```python
schema_info = await builder.get_schema_info(client, collection_name)

# Retorna:
{
    "collection_name": "VERBA_Embedding_all_MiniLM_L6_v2",
    "properties": [
        {"name": "content", "type": "text", ...},
        {"name": "entities_local_ids", "type": "text[]", ...},
        {"name": "section_title", "type": "text", ...},
        ...
    ],
    "etl_aware": True,
    "available_filters": ["entities_local_ids", "section_title", "chunk_lang", ...]
}
```

### **2. Usa LLM com Schema**

O LLM recebe:
- ✅ Schema completo da collection
- ✅ Propriedades disponíveis
- ✅ Filtros disponíveis
- ✅ Se é ETL-aware

**Prompt inteligente:**
```
SCHEMA DA COLLECTION:
Propriedades disponíveis:
  - content (text): Conteúdo do chunk
  - entities_local_ids (text[]): Entity IDs no chunk
  - section_title (text): Título da seção
  ...

Filtros disponíveis: entities_local_ids, section_title, chunk_lang, chunk_date, ...

QUERY DO USUÁRIO: "mostre inovação da Apple em 2024"

Sua tarefa:
1. Analisar a query e entender o que o usuário quer
2. Extrair entidades (Apple → Q312)
3. Identificar filtros (entidade, data)
4. Gerar query estruturada
```

### **3. Gera Query Estruturada**

```json
{
    "semantic_query": "inovação tecnológica, desenvolvimento de produtos, Apple Inc, avanços tecnológicos",
    "keyword_query": "inovação Apple",
    "intent": "search",
    "filters": {
        "entities": ["Q312"],  // Apple
        "entity_property": "entities_local_ids",
        "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
        "language": null,
        "labels": [],
        "section_title": ""
    },
    "alpha": 0.6,
    "explanation": "Query filtra por entidade Apple (Q312) e data 2024, busca semântica por 'inovação tecnológica'",
    "requires_validation": true
}
```

---

## 🚀 Endpoints Criados

### **1. `/api/query/validate`** - Validar Query Antes de Executar

```python
POST /api/query/validate
{
    "query": "mostre inovação da Apple em 2024",
    "RAG": {...},
    "credentials": {...}
}

Response:
{
    "error": "",
    "query_plan": {
        "semantic_query": "...",
        "filters": {...},
        "explanation": "...",
        "requires_validation": true
    }
}
```

**Uso:**
1. Frontend chama `/api/query/validate` antes de executar
2. Mostra query plan para o usuário validar
3. Usuário confirma ou ajusta
4. Executa query

### **2. `/api/query/execute`** - Executar Query Validada

```python
POST /api/query/execute
{
    "query": "mostre inovação da Apple em 2024",
    "RAG": {...},
    "credentials": {...}
}

Response:
{
    "error": "",
    "documents": [...],
    "context": "..."
}
```

---

## 🔄 Integração no EntityAwareRetriever

O `EntityAwareRetriever` agora:

1. **Tenta QueryBuilder primeiro** (conhece schema)
2. **Fallback para QueryRewriter** se não disponível
3. **Usa filtros do builder** (entidades, datas, idioma)
4. **Combina com outros filtros** automaticamente

**Fluxo:**
```python
# 0. Query Builder (conhece schema)
strategy = await builder.build_query(query, client, collection_name)

# 1. Extrai filtros
entities = strategy["filters"]["entities"]
date_range = strategy["filters"]["date_range"]
language = strategy["filters"]["language"]

# 2. Aplica filtros
entity_filter = Filter.by_property("entities_local_ids").contains_any(entities)
temporal_filter = TemporalFilterPlugin().build_temporal_filter(...)
lang_filter = BilingualFilterPlugin().build_language_filter(language)

# 3. Combina filtros
combined_filter = Filter.all_of([entity_filter, temporal_filter, lang_filter])

# 4. Busca híbrida
chunks = await hybrid_chunks_with_filter(
    query=strategy["semantic_query"],
    filters=combined_filter,
    alpha=strategy["alpha"]
)
```

---

## 📋 Exemplo de Uso

### **Query do Usuário:**
```
"mostre inovação da Apple em 2024"
```

### **Query Builder Gera:**
```json
{
    "semantic_query": "inovação tecnológica, desenvolvimento de produtos, Apple Inc, avanços tecnológicos, pesquisa e desenvolvimento",
    "keyword_query": "inovação Apple",
    "intent": "search",
    "filters": {
        "entities": ["Q312"],  // Apple
        "entity_property": "entities_local_ids",
        "date_range": {
            "start": "2024-01-01",
            "end": "2024-12-31"
        },
        "language": null,
        "labels": [],
        "section_title": ""
    },
    "alpha": 0.6,
    "explanation": "Query filtra por entidade Apple (Q312) e período 2024, busca semântica expandida por 'inovação tecnológica' e conceitos relacionados",
    "requires_validation": true
}
```

### **Validação com Usuário:**
```
Frontend mostra:
┌─────────────────────────────────────────┐
│ Query Planejada:                         │
│                                          │
│ Busca: "inovação tecnológica, Apple..."  │
│ Filtros:                                 │
│   • Entidade: Apple (Q312)              │
│   • Data: 2024-01-01 até 2024-12-31    │
│                                          │
│ [✅ Executar] [✏️ Editar] [❌ Cancelar] │
└─────────────────────────────────────────┘
```

---

## 🎯 Próximos Passos (Frontend)

Para completar a integração, você pode:

1. **Adicionar validação no frontend:**
   - Chamar `/api/query/validate` antes de executar
   - Mostrar query plan para o usuário
   - Permitir edição antes de executar

2. **UI de validação:**
   - Modal mostrando query estruturada
   - Botões: Executar, Editar, Cancelar
   - Edição de filtros antes de executar

---

## ✅ Benefícios

1. **Conhece Schema:**
   - Sabe quais propriedades existem
   - Sabe quais filtros pode usar
   - Sabe se collection é ETL-aware

2. **Queries Complexas:**
   - Extrai entidades automaticamente
   - Extrai datas e períodos
   - Combina múltiplos filtros

3. **Validação:**
   - Usuário vê query antes de executar
   - Pode editar se necessário
   - Evita queries incorretas

4. **Transparência:**
   - Explicação clara do que será buscado
   - Filtros visíveis
   - Entidades mostradas

---

## 📝 Configuração

**No EntityAwareRetriever:**
- `Enable Query Rewriting`: Ativa QueryBuilder (se disponível)
- QueryBuilder é usado automaticamente se disponível
- Fallback para QueryRewriter se não disponível

**Cache:**
- Schema cache: 5 minutos
- Query cache: 1 hora (configurável)

---

## ✅ Conclusão

**QueryBuilder criado e integrado!**

- ✅ Conhece schema do Weaviate
- ✅ Gera queries complexas com filtros
- ✅ Extrai entidades, datas, idioma
- ✅ Valida com usuário (endpoint criado)
- ✅ Integrado no EntityAwareRetriever

**Próximo passo:** Adicionar UI de validação no frontend (opcional)

---

**Última atualização:** 2025-01-XX  
**Versão:** 1.0

