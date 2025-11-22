# Por Que Existem 2 Query Rewriters? (Ambos Usam LLM)

## 🎯 Resposta Direta

**Ambos usam LLM**, mas são versões diferentes:

1. **QueryBuilder** (novo, avançado) - Tenta primeiro
2. **QueryRewriter** (antigo, simples) - Fallback

Eles existem por **razões históricas** e **compatibilidade**.

---

## 📊 Comparação Rápida

| Aspecto | QueryRewriter | QueryBuilder |
|---------|---------------|-------------|
| **Usa LLM?** | ✅ SIM | ✅ SIM |
| **Quando foi criado?** | Mais antigo | Mais novo |
| **Conhece schema?** | ❌ NÃO | ✅ SIM |
| **Prioridade** | Fallback (2º) | Principal (1º) |
| **Complexidade** | Simples | Avançado |

---

## 🔄 Por Que Existem 2?

### História

1. **QueryRewriter foi criado primeiro** (baseado em RAG2)
   - Ferramenta simples de expansão semântica
   - Funciona bem, mas não conhece schema
   - Usado em produção

2. **QueryBuilder foi criado depois** (melhoria)
   - Mais inteligente, conhece schema
   - Pode gerar filtros baseados em estrutura
   - Melhor para queries complexas

3. **Mantidos ambos por compatibilidade**
   - QueryBuilder tenta primeiro (melhor)
   - QueryRewriter como fallback (se QueryBuilder falhar)
   - Garante que sistema sempre funciona

---

## 🔍 Como Funcionam no Código

### Fluxo Atual

```python
# verba_extensions/plugins/entity_aware_retriever.py (linha ~668)

# 1. TENTA QueryBuilder PRIMEIRO (mais inteligente)
try:
    from verba_extensions.plugins.query_builder import QueryBuilderPlugin
    builder = QueryBuilderPlugin(cache_ttl_seconds=cache_ttl)
    
    # Obtém schema do Weaviate
    schema_info = await builder.get_schema_info(client, collection_name)
    
    # Chama LLM COM schema completo
    strategy = await builder.build_query(
        query=query,
        schema_info=schema_info,  # ← Schema é passado para LLM!
        rag_config=rag_config
    )
    
    # QueryBuilder pode retornar filtros baseados em schema
    rewritten_query = strategy.get("semantic_query", query)
    filters = strategy.get("filters", {})  # ← Pode ter filtros!
    
except ImportError:
    # 2. FALLBACK para QueryRewriter (se QueryBuilder não disponível)
    if enable_query_rewriting:
        from verba_extensions.plugins.query_rewriter import QueryRewriterPlugin
        rewriter = QueryRewriterPlugin(cache_ttl_seconds=cache_ttl)
        
        # Chama LLM SEM schema (apenas expansão semântica)
        strategy = await rewriter.rewrite_query(query, use_cache=True)
        
        # QueryRewriter sempre retorna filters={} (vazio)
        rewritten_query = strategy.get("semantic_query", query)
        filters = {}  # ← Sempre vazio!
```

---

## 🤖 Como Cada Um Usa o LLM

### QueryRewriter (Simples)

**Prompt enviado ao LLM:**
```python
prompt = """Analise a query do usuário e retorne JSON com:
1. semantic_query: Query reescrita para busca semântica 
   (expandir sinônimos, conceitos relacionados, contexto)
2. keyword_query: Query otimizada para BM25
3. intent: "comparison" | "description" | "search"
4. filters: {} (vazio - para uso futuro)
5. alpha: Balance 0.0-1.0

Query original: "{query}"

Retorne apenas JSON válido:
{
    "semantic_query": "...",
    "keyword_query": "...",
    "intent": "...",
    "filters": {},  // ← SEMPRE VAZIO!
    "alpha": 0.6
}
"""
```

**O que o LLM recebe:**
- ✅ Query original do usuário
- ❌ NÃO recebe schema do Weaviate
- ❌ NÃO recebe informações sobre campos disponíveis

**O que o LLM retorna:**
- ✅ Query expandida (semantic_query)
- ✅ Query otimizada para BM25 (keyword_query)
- ✅ Intent (comparison/description/search)
- ✅ Alpha sugerido
- ❌ Filters sempre vazio `{}`

---

### QueryBuilder (Avançado)

**Prompt enviado ao LLM:**
```python
prompt = f"""
SCHEMA DA COLLECTION:
Collection: {collection_name}

Propriedades disponíveis:
  - content (text): Conteúdo do chunk
  - entities_local_ids (text[]): Entity IDs no chunk
  - section_title (text): Título da seção
  - chunk_lang (text): Idioma do chunk (pt, en, etc.)
  - chunk_date (text): Data do chunk (ISO format)
  - frameworks (text[]): Frameworks detectados
  - companies (text[]): Empresas detectadas
  - sectors (text[]): Setores detectados
  ...

Filtros disponíveis: entities_local_ids, section_title, chunk_lang, chunk_date, frameworks, companies, sectors, ...

Query do usuário: "{query}"

Analise a query e retorne JSON com:
1. semantic_query: Query expandida para busca semântica
2. keyword_query: Query para BM25
3. intent: "comparison" | "description" | "search"
4. filters: {{  // ← PODE preencher com filtros baseados em schema!
     "entities_local_ids": ["Apple"],  // Se query menciona entidade
     "chunk_lang": "pt",                // Se query é em português
     "chunk_date": {{"after": "2024-01-01"}}  // Se query menciona data
   }}
5. alpha: Balance 0.0-1.0
6. explanation: Explicação do que foi feito

Retorne apenas JSON válido:
{{
    "semantic_query": "...",
    "keyword_query": "...",
    "intent": "...",
    "filters": {{...}},  // ← PODE TER FILTROS!
    "alpha": 0.6,
    "explanation": "..."
}}
"""
```

**O que o LLM recebe:**
- ✅ Query original do usuário
- ✅ **Schema completo do Weaviate** (propriedades, tipos, descrições)
- ✅ **Lista de filtros disponíveis**
- ✅ **Informações sobre ETL** (se collection é ETL-aware)

**O que o LLM retorna:**
- ✅ Query expandida (semantic_query)
- ✅ Query otimizada para BM25 (keyword_query)
- ✅ Intent (comparison/description/search)
- ✅ Alpha sugerido
- ✅ **Filters baseados em schema** (pode preencher!)
- ✅ Explanation (explicação do que foi feito)

---

## 📋 Diferença Prática

### Exemplo: Query "Apple e inovação em português"

#### QueryRewriter (Simples)

**LLM recebe:**
```
Query original: "Apple e inovação em português"
```

**LLM retorna:**
```json
{
    "semantic_query": "Apple Inc, inovação tecnológica, desenvolvimento de produtos",
    "keyword_query": "Apple inovação",
    "intent": "search",
    "filters": {},  // ← VAZIO! Não sabe que pode filtrar por idioma
    "alpha": 0.6
}
```

**Resultado:**
- Query expandida ✅
- Mas não filtra por idioma ❌ (não conhece `chunk_lang`)

---

#### QueryBuilder (Avançado)

**LLM recebe:**
```
SCHEMA DA COLLECTION:
Propriedades disponíveis:
  - chunk_lang (text): Idioma do chunk (pt, en, etc.)
  - entities_local_ids (text[]): Entity IDs no chunk
  ...

Query original: "Apple e inovação em português"
```

**LLM retorna:**
```json
{
    "semantic_query": "Apple Inc, inovação tecnológica, desenvolvimento de produtos",
    "keyword_query": "Apple inovação",
    "intent": "search",
    "filters": {
        "entities_local_ids": ["Apple"],  // ← Detectou entidade!
        "chunk_lang": "pt"                 // ← Detectou idioma!
    },
    "alpha": 0.6,
    "explanation": "Query expandida e filtros aplicados: entidade 'Apple' e idioma 'pt'"
}
```

**Resultado:**
- Query expandida ✅
- Filtra por entidade ✅
- Filtra por idioma ✅ (conhece `chunk_lang`!)

---

## 🎯 Por Que Manter Ambos?

### Razões

1. **Compatibilidade**
   - QueryRewriter já está em produção
   - Não quebrar sistemas existentes
   - Fallback seguro se QueryBuilder falhar

2. **Simplicidade**
   - QueryRewriter é mais simples
   - Menos dependências
   - Funciona mesmo sem schema

3. **Gradual Migration**
   - Migração gradual de QueryRewriter para QueryBuilder
   - Usuários podem escolher qual usar
   - Sistema sempre funciona

4. **Fallback Robusto**
   - Se QueryBuilder falhar (erro, import, etc.)
   - QueryRewriter garante que sistema continua funcionando
   - Não quebra busca

---

## 🔧 Qual Usar?

### Use QueryBuilder (Recomendado)

✅ **Quando:**
- Queries complexas com múltiplos critérios
- Precisa de filtros baseados em schema
- Quer melhor qualidade de resultados
- Sistema tem schema ETL-aware

### Use QueryRewriter (Fallback)

✅ **Quando:**
- QueryBuilder não disponível (erro, import)
- Queries simples que só precisam de expansão
- Sistema não tem schema complexo
- Precisa de compatibilidade com versões antigas

---

## 📊 Resumo

| Pergunta | Resposta |
|----------|----------|
| **Ambos usam LLM?** | ✅ SIM - ambos usam LLM |
| **Qual a diferença?** | QueryBuilder conhece schema, QueryRewriter não |
| **Por que 2?** | QueryRewriter é antigo, QueryBuilder é novo (melhoria) |
| **Qual usar?** | QueryBuilder (tenta primeiro), QueryRewriter (fallback) |
| **Qual é melhor?** | QueryBuilder (mais inteligente, conhece schema) |

---

## 🎯 Conclusão

**Ambos usam LLM**, mas:
- **QueryRewriter**: LLM sem contexto de schema (expansão genérica)
- **QueryBuilder**: LLM com contexto completo de schema (mais inteligente)

Eles existem por **razões históricas** e **compatibilidade**. O sistema tenta usar **QueryBuilder primeiro** (melhor), e usa **QueryRewriter como fallback** (garante que sempre funciona).

**Em resumo**: São duas versões da mesma ideia (usar LLM para melhorar queries), mas QueryBuilder é a versão melhorada que conhece o schema.

