# Query Rewriter vs Query Builder: Qual a Diferença?

## 🎯 Resposta Direta

**Query Rewriter NÃO é um agente e NÃO conhece o schema em detalhes.**

Ele é uma ferramenta simples de **expansão semântica genérica** que usa LLM para reescrever queries, mas não tem conhecimento específico do schema do Weaviate.

**Query Builder** é mais avançado e **conhece o schema**, funcionando mais como um agente que pode construir queries estruturadas.

---

## 📊 Comparação Rápida

| Aspecto | Query Rewriter | Query Builder |
|---------|---------------|---------------|
| **Conhece Schema?** | ❌ NÃO | ✅ SIM |
| **É um Agente?** | ❌ NÃO (ferramenta simples) | ✅ SIM (mais próximo de agente) |
| **O que faz?** | Expansão semântica genérica | Constrói queries estruturadas com filtros |
| **Usa dados do Weaviate?** | ❌ NÃO | ✅ SIM (obtém schema dinamicamente) |
| **Aplica filtros?** | ❌ NÃO (filters sempre vazio) | ✅ SIM (gera filtros baseados em schema) |
| **Valida com usuário?** | ❌ NÃO | ✅ SIM (pode validar antes de executar) |

---

## 🔍 Query Rewriter (Simples)

### O que é?

Uma ferramenta que usa LLM para **reescrever queries** expandindo sinônimos e conceitos relacionados.

### Como Funciona?

1. **Recebe query original**: `"inovação da Apple"`

2. **Chama LLM com prompt genérico**:
   ```python
   prompt = """Analise a query do usuário e retorne JSON com:
   1. semantic_query: Query reescrita para busca semântica 
      (expandir sinônimos, conceitos relacionados, contexto)
   2. keyword_query: Query otimizada para BM25 
      (manter termos-chave, remover stopwords)
   3. intent: "comparison" | "description" | "search"
   4. filters: {} (vazio - para uso futuro)
   5. alpha: Balance 0.0-1.0 (sugerir 0.4-0.7)
   
   Query original: "{query}"
   """
   ```

3. **LLM retorna JSON**:
   ```json
   {
       "semantic_query": "inovação tecnológica, desenvolvimento de produtos, Apple Inc",
       "keyword_query": "inovação Apple",
       "intent": "search",
       "filters": {},  // ← Sempre vazio!
       "alpha": 0.6
   }
   ```

4. **Usa query expandida** na busca semântica

### ⚠️ Limitações

- ❌ **NÃO conhece schema**: Não sabe quais campos existem (`entities_local_ids`, `section_title`, etc.)
- ❌ **NÃO aplica filtros**: Campo `filters` sempre vazio `{}`
- ❌ **NÃO consulta Weaviate**: Não obtém informações sobre a collection
- ❌ **NÃO valida**: Não verifica se a query faz sentido com o schema
- ✅ **Apenas expansão semântica**: Funciona bem para melhorar busca, mas não é inteligente sobre estrutura

### Quando Usar?

✅ **Bom para**:
- Expansão de sinônimos e conceitos
- Melhorar Recall em busca semântica
- Queries simples que precisam de expansão

❌ **Não usar para**:
- Filtros baseados em schema
- Queries complexas com múltiplos critérios
- Validação de estrutura

---

## 🧠 Query Builder (Avançado - Mais Próximo de Agente)

### O que é?

Um **agente mais inteligente** que conhece o schema do Weaviate e pode construir queries estruturadas com filtros complexos.

### Como Funciona?

1. **Obtém Schema do Weaviate Dinamicamente**:
   ```python
   schema_info = await builder.get_schema_info(client, collection_name)
   
   # Retorna:
   {
       "collection_name": "VERBA_Embedding_all_MiniLM_L6_v2",
       "properties": [
           {"name": "content", "type": "text", "description": "Conteúdo do chunk"},
           {"name": "entities_local_ids", "type": "text[]", "description": "Entity IDs"},
           {"name": "section_title", "type": "text", "description": "Título da seção"},
           {"name": "chunk_lang", "type": "text", "description": "Idioma do chunk"},
           {"name": "chunk_date", "type": "text", "description": "Data do chunk"},
           ...
       ],
       "etl_aware": True,
       "available_filters": ["entities_local_ids", "section_title", "chunk_lang", "chunk_date", ...]
   }
   ```

2. **Chama LLM com Schema Completo**:
   ```python
   prompt = f"""
   SCHEMA DA COLLECTION:
   Propriedades disponíveis:
     - content (text): Conteúdo do chunk
     - entities_local_ids (text[]): Entity IDs no chunk
     - section_title (text): Título da seção
     - chunk_lang (text): Idioma do chunk (pt, en, etc.)
     - chunk_date (text): Data do chunk (ISO format)
     ...
   
   Filtros disponíveis: entities_local_ids, section_title, chunk_lang, chunk_date, ...
   
   Query do usuário: "{query}"
   
   Analise a query e retorne JSON com:
   1. semantic_query: Query expandida para busca semântica
   2. keyword_query: Query para BM25
   3. intent: "comparison" | "description" | "search"
   4. filters: {{  // ← PODE preencher com filtros baseados em schema!
       "entities_local_ids": ["Apple", "Microsoft"],
       "chunk_lang": "pt",
       "chunk_date": {{"after": "2024-01-01"}}
     }}
   5. alpha: Balance 0.0-1.0
   """
   ```

3. **LLM retorna JSON com Filtros**:
   ```json
   {
       "semantic_query": "inovação tecnológica, desenvolvimento de produtos",
       "keyword_query": "inovação Apple",
       "intent": "search",
       "filters": {
           "entities_local_ids": ["Apple"],
           "chunk_lang": "pt"
       },
       "alpha": 0.6
   }
   ```

4. **Valida e Aplica Filtros**:
   - Valida se os filtros fazem sentido com o schema
   - Pode validar com o usuário antes de executar
   - Aplica filtros na busca

### ✅ Vantagens

- ✅ **Conhece schema**: Sabe quais campos existem e como usá-los
- ✅ **Aplica filtros**: Pode gerar filtros baseados em schema
- ✅ **Consulta Weaviate**: Obtém informações sobre a collection dinamicamente
- ✅ **Valida queries**: Pode verificar se a query faz sentido
- ✅ **Mais inteligente**: Funciona como um agente que entende estrutura

### Quando Usar?

✅ **Bom para**:
- Queries complexas com múltiplos critérios
- Filtros baseados em schema
- Validação de estrutura
- Queries que precisam de conhecimento sobre dados

❌ **Não usar para**:
- Queries simples que só precisam de expansão semântica
- Quando não há necessidade de filtros complexos

---

## 🔄 Como São Usados no EntityAwareRetriever?

### Fluxo Atual

```python
# verba_extensions/plugins/entity_aware_retriever.py

# 1. TENTA QueryBuilder primeiro (se disponível)
try:
    from verba_extensions.plugins.query_builder import QueryBuilderPlugin
    builder = QueryBuilderPlugin(cache_ttl_seconds=cache_ttl)
    
    # Obtém schema e constrói query estruturada
    schema_info = await builder.get_schema_info(client, collection_name)
    strategy = await builder.build_query(
        query=query,
        schema_info=schema_info,
        rag_config=rag_config
    )
    
    rewritten_query = strategy.get("semantic_query", query)
    rewritten_alpha = strategy.get("alpha", 0.6)
    
    # QueryBuilder pode retornar filtros!
    query_filters = strategy.get("filters", {})
    
except:
    # 2. FALLBACK para QueryRewriter (mais simples)
    if enable_query_rewriting:
        from verba_extensions.plugins.query_rewriter import QueryRewriterPlugin
        rewriter = QueryRewriterPlugin(cache_ttl_seconds=cache_ttl)
        strategy = await rewriter.rewrite_query(query, use_cache=True)
        
        rewritten_query = strategy.get("semantic_query", query)
        rewritten_alpha = strategy.get("alpha", 0.6)
        
        # QueryRewriter sempre retorna filters={} (vazio)
```

### Prioridade

1. **QueryBuilder** (se disponível) - Mais inteligente, conhece schema
2. **QueryRewriter** (fallback) - Simples, apenas expansão semântica

---

## 📋 Resumo

### Query Rewriter

- ❌ **NÃO é um agente** - Ferramenta simples de expansão semântica
- ❌ **NÃO conhece schema** - Apenas expansão genérica
- ✅ **Simples e eficaz** - Funciona bem para melhorar busca
- ✅ **Cache** - TTL configurável (padrão: 1 hora)

### Query Builder

- ✅ **É mais próximo de agente** - Conhece estrutura e pode tomar decisões
- ✅ **Conhece schema** - Obtém dinamicamente do Weaviate
- ✅ **Mais inteligente** - Pode gerar filtros e validar queries
- ✅ **Validação** - Pode validar com usuário antes de executar

---

## 🎯 Conclusão

**Query Rewriter** é uma ferramenta simples que faz expansão semântica genérica. **NÃO é um agente** e **NÃO conhece o schema**.

**Query Builder** é mais avançado, conhece o schema e funciona mais como um agente que pode construir queries estruturadas.

No sistema atual, o **QueryBuilder é tentado primeiro** (se disponível), e o **QueryRewriter é usado como fallback** para compatibilidade.

