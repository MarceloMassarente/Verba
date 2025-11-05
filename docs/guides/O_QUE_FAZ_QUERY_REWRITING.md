# 🔄 O Que Faz o "Enable Query Rewriting"?

## ✅ **Resposta Direta**

O **Query Rewriting** usa um **LLM (Anthropic Claude)** para reescrever a query do usuário antes da busca, expandindo sinônimos e conceitos relacionados.

**⚠️ NÃO, ele NÃO tem conhecimento específico do schema do Weaviate.**

---

## 🎯 **O Que Ele Faz Exatamente**

### **1. Expansão Semântica da Query**

Quando você digita uma query, o LLM reescreve para melhorar a busca:

```
Query Original: "inovação da Apple"
    ↓
Query Rewritten: "inovação tecnológica, desenvolvimento de produtos, 
                  pesquisa e desenvolvimento, Apple Inc, 
                  avanços tecnológicos, inovação disruptiva"
```

**Benefícios:**
- ✅ Captura sinônimos (ex: "inovação" → "avanços tecnológicos")
- ✅ Expande conceitos relacionados (ex: "inovação" → "pesquisa e desenvolvimento")
- ✅ Adiciona contexto (ex: "Apple" → "Apple Inc")

### **2. Separação: Semantic Query vs Keyword Query**

O LLM retorna duas versões:

- **`semantic_query`**: Para busca vetorial (expandida, com sinônimos)
- **`keyword_query`**: Para BM25 (termos-chave, sem stopwords)

**Exemplo:**
```json
{
    "semantic_query": "inovação tecnológica, desenvolvimento de produtos, Apple Inc",
    "keyword_query": "inovação Apple",
    "intent": "search",
    "alpha": 0.6
}
```

### **3. Detecção de Intenção**

O LLM detecta o tipo de busca:
- **`comparison`**: Comparação entre entidades
- **`description`**: Descrição de algo
- **`search`**: Busca simples

### **4. Sugestão de Alpha**

O LLM sugere o balance entre keyword (0.0) e vector search (1.0):
- **0.0**: Apenas BM25 (keyword matching)
- **1.0**: Apenas vector search (semântica)
- **0.6**: Híbrido (60% semântica, 40% keyword)

---

## 🔍 **Como Funciona Técnicamente**

### **Fluxo Completo:**

```python
# verba_extensions/plugins/entity_aware_retriever.py (linha 176-200)

# 0. QUERY REWRITING (antes de parsing)
if enable_query_rewriting:
    from verba_extensions.plugins.query_rewriter import QueryRewriterPlugin
    rewriter = QueryRewriterPlugin(cache_ttl_seconds=cache_ttl)
    strategy = await rewriter.rewrite_query(query, use_cache=True)
    
    # Usa query reescrita para busca semântica
    rewritten_query = strategy.get("semantic_query", query)
    
    # Aplica alpha sugerido
    rewritten_alpha = strategy.get("alpha", 0.6)
```

### **Prompt para o LLM:**

```python
# verba_extensions/plugins/query_rewriter.py (linha 110-127)

prompt = """Analise a query do usuário e retorne JSON com:
1. semantic_query: Query reescrita para busca semântica 
   (expandir sinônimos, conceitos relacionados, contexto)
2. keyword_query: Query otimizada para BM25 
   (manter termos-chave, remover stopwords)
3. intent: "comparison" | "description" | "search"
4. filters: {} (vazio - para uso futuro)
5. alpha: Balance 0.0-1.0 (sugerir 0.4-0.7)

Query original: "{query}"

Retorne apenas JSON válido:
{
    "semantic_query": "...",
    "keyword_query": "...",
    "intent": "...",
    "filters": {},
    "alpha": 0.6
}
"""
```

**⚠️ Nota:** O prompt **NÃO menciona** campos do schema, propriedades do Weaviate, ou estrutura dos dados. Ele apenas pede expansão semântica genérica.

---

## ❌ **O Que Ele NÃO Faz**

### **1. Não Conhece o Schema**

O Query Rewriter **NÃO sabe**:
- ❌ Quais campos existem no Weaviate (`entities_local_ids`, `section_title`, etc.)
- ❌ Quais propriedades estão disponíveis
- ❌ Estrutura dos chunks
- ❌ Relações entre entidades

### **2. Não Aplica Filtros**

O campo `filters` no JSON retornado é **sempre vazio** (`{}`):
```json
{
    "filters": {}  // ← Sempre vazio, não usado
}
```

**Filtros são aplicados DEPOIS** pelo `EntityAwareRetriever` usando:
- Extração de entidades (SpaCy + Gazetteer)
- Filtros de idioma (BilingualFilterPlugin)
- Filtros temporais (TemporalFilterPlugin)

### **3. Não Usa Contexto dos Dados**

O LLM **não consulta** o Weaviate antes de reescrever. Ele apenas:
- Lê a query do usuário
- Expande usando conhecimento geral do LLM
- Retorna query expandida

---

## ✅ **O Que Ele Faz Bem**

### **1. Expansão Semântica Genérica**

Funciona bem para:
- ✅ Sinônimos comuns (ex: "inovação" → "avanço tecnológico")
- ✅ Conceitos relacionados (ex: "Apple" → "Apple Inc", "tecnologia Apple")
- ✅ Contexto geral (ex: "inovação" → "pesquisa e desenvolvimento")

### **2. Cache Inteligente**

- ✅ Cache LRU com TTL configurável (default: 1 hora)
- ✅ Queries similares retornam resultado cached
- ✅ Reduz chamadas ao LLM

### **3. Fallback Seguro**

Se o LLM falhar:
- ✅ Retorna query original
- ✅ Não quebra o fluxo
- ✅ Logs de erro para debug

---

## 📊 **Exemplos Práticos**

### **Exemplo 1: Query Simples**

```
Query Original: "inovação da Apple"

Query Rewritten:
  semantic_query: "inovação tecnológica, desenvolvimento de produtos, 
                    pesquisa e desenvolvimento, Apple Inc, 
                    avanços tecnológicos, inovação disruptiva"
  keyword_query: "inovação Apple"
  intent: "search"
  alpha: 0.6

Resultado: Busca encontra chunks sobre Apple que mencionam inovação, 
           avanços tecnológicos, desenvolvimento de produtos, etc.
```

### **Exemplo 2: Query com Comparação**

```
Query Original: "diferenças entre Apple e Microsoft"

Query Rewritten:
  semantic_query: "comparação entre Apple Inc e Microsoft Corporation, 
                    diferenças tecnológicas, estratégias distintas, 
                    modelos de negócio diferentes"
  keyword_query: "Apple Microsoft diferenças"
  intent: "comparison"
  alpha: 0.5  // Mais keyword para comparação

Resultado: Busca encontra chunks que comparam as duas empresas.
```

### **Exemplo 3: Query Ambígua**

```
Query Original: "o que é inovação"

Query Rewritten:
  semantic_query: "inovação, criatividade, desenvolvimento de novos 
                    produtos, avanços tecnológicos, mudança disruptiva, 
                    transformação digital"
  keyword_query: "inovação"
  intent: "description"
  alpha: 0.7  // Mais semântica para descrição

Resultado: Busca encontra chunks que explicam o conceito de inovação.
```

---

## ⚙️ **Configuração**

### **Habilitar/Desabilitar:**

Na UI do Verba → **Settings** → **Retriever**:
- **Enable Query Rewriting**: ✅ Ativado / ❌ Desativado

### **Cache TTL:**

- **Query Rewriter Cache TTL**: 3600 segundos (1 hora)
- Ajuste conforme necessário (mais cache = menos chamadas ao LLM)

---

## 🎯 **Quando Usar**

### **✅ Use Query Rewriting quando:**

- Queries curtas ou ambíguas
- Necessidade de capturar sinônimos
- Buscas que precisam de expansão conceitual
- Você tem LLM configurado (Anthropic)

### **❌ Não use quando:**

- Queries já são específicas e completas
- Você quer controle total sobre a query
- Não tem LLM configurado (fallback usa query original)
- Queries são muito técnicas (schema-specific)

---

## 🔄 **Fluxo Completo no EntityAwareRetriever**

```
1. Query Original: "inovação da Apple"
   ↓
2. Query Rewriting (se habilitado):
   → LLM reescreve: "inovação tecnológica, desenvolvimento de produtos, Apple Inc"
   → Sugere alpha: 0.6
   ↓
3. Parse Query:
   → Extrai entidades: Apple → entity_id="Q312"
   → Conceitos: "inovação tecnológica", "desenvolvimento de produtos"
   ↓
4. Aplica Filtros:
   → WHERE: entities_local_ids contains "Q312"
   ↓
5. Busca Híbrida:
   → Query: "inovação tecnológica, desenvolvimento de produtos, Apple Inc"
   → Vector: [0.123, -0.456, ...]
   → Alpha: 0.6
   → Filtros: entities = "Q312"
   ↓
6. Resultado: Chunks sobre Apple que mencionam inovação, 
              desenvolvimento de produtos, etc.
```

---

## 📋 **Resumo**

| Aspecto | Detalhes |
|---------|----------|
| **O que faz** | Reescreve query usando LLM para expansão semântica |
| **Conhece schema?** | ❌ NÃO - apenas expansão genérica |
| **Usa dados?** | ❌ NÃO - não consulta Weaviate |
| **Aplica filtros?** | ❌ NÃO - filtros são aplicados depois |
| **Cache** | ✅ SIM - LRU com TTL configurável |
| **Fallback** | ✅ SIM - retorna query original se falhar |
| **Alpha** | ✅ SIM - sugere balance keyword/vector |

---

## ✅ **Conclusão**

**Query Rewriting é uma ferramenta de expansão semântica genérica.**

- ✅ Funciona bem para **expansão de sinônimos e conceitos**
- ❌ **NÃO** conhece o schema específico do Weaviate
- ❌ **NÃO** aplica filtros baseados em schema
- ✅ **Simples e eficaz** para melhorar busca semântica

**Para filtros baseados em schema**, use:
- ✅ **Entity Filter** (entidades extraídas)
- ✅ **Language Filter** (idioma detectado)
- ✅ **Temporal Filter** (datas extraídas)

**Query Rewriting complementa** esses filtros, não os substitui! 🎉

