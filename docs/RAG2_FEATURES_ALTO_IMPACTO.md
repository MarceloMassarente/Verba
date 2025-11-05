# 🎯 RAG2: Features de Alto Impacto e Fáceis de Aplicar via Plugins

## 📊 Análise das Features do RAG2

Após análise detalhada do RAG2, identifiquei **3 features** que são:
- ✅ **Alto Impacto**: Melhoram significativamente qualidade/relevância
- ✅ **Fáceis de Implementar**: Podem ser plugins sem mudanças arquiteturais
- ✅ **Compatíveis**: Não dependem de named vectors ou outras features complexas

---

## 🥇 Feature #1: Roteamento Bilíngue (chunk_lang)

### **Impacto: ⭐⭐⭐⭐⭐ (Crítico)**

### **O que faz?**
- Detecta idioma da query (PT/EN)
- Filtra chunks por idioma (`chunk_lang`)
- Melhora recall em ambientes multilíngues

### **Como funciona no RAG2?**
```python
# RAG2: api/server.py
def _detect_query_lang(query: str) -> str:
    """Detecta idioma da query (PT/EN)"""
    pt_words = ["de", "da", "do", "em", "para", "com", "sem", "sobre", ...]
    en_words = ["the", "a", "an", "of", "in", "on", "at", "to", "for", ...]
    
    pt_count = sum(1 for word in pt_words if word in query)
    en_count = sum(1 for word in en_words if word in query)
    
    return "pt" if pt_count > en_count else "en"

# Filtro automático
filters = _to_weaviate_filters(req.filters, add_chunk_lang=query_lang)
# Adiciona: {"path": ["chunk_lang"], "operator": "Equal", "valueString": "pt"}
```

### **Por que é fácil?**
1. ✅ Verba já tem detecção de idioma (`detect_language` em `document.py`)
2. ✅ ETL A2 já adiciona `chunk_lang` nos chunks
3. ✅ Apenas precisa adicionar filtro no retriever
4. ✅ Zero mudanças arquiteturais

### **Implementação como Plugin**

**Plugin: `BilingualRetriever`** (ou extensão do `EntityAwareRetriever`)

```python
# verba_extensions/plugins/bilingual_retriever.py

from verba_extensions.plugins.entity_aware_retriever import EntityAwareRetriever
from weaviate.classes.query import Filter

class BilingualRetriever(EntityAwareRetriever):
    """Retriever que adiciona filtro de idioma automaticamente"""
    
    def _detect_query_language(self, query: str) -> str:
        """Detecta idioma da query (simplificado)"""
        query_lower = query.lower()
        
        # Palavras-chave PT
        pt_words = ["de", "da", "do", "em", "para", "com", "sem", "sobre", 
                   "como", "onde", "quando", "quem", "porque", "que", "este",
                   "está", "são", "faz", "trabalha", "experiência", "empresa"]
        # Palavras-chave EN
        en_words = ["the", "a", "an", "of", "in", "on", "at", "to", "for", "with",
                   "from", "by", "about", "as", "is", "are", "was", "were", "been",
                   "experience", "company", "work", "worked"]
        
        pt_count = sum(1 for word in pt_words if f" {word} " in f" {query_lower} ")
        en_count = sum(1 for word in en_words if f" {word} " in f" {query_lower} ")
        
        return "pt" if pt_count > en_count else "en"
    
    async def retrieve(
        self,
        queries: list[str],
        client: WeaviateAsyncClient,
        embedder: str,
        limit: int,
        filters: Optional[Filter] = None,
        **kwargs
    ) -> list[Chunk]:
        """Retrieve com filtro de idioma automático"""
        
        query = queries[0] if queries else ""
        
        # 1. Detectar idioma da query
        query_lang = self._detect_query_language(query)
        
        # 2. Criar filtro de idioma
        lang_filter = Filter.by_property("chunk_lang").equal(query_lang)
        
        # 3. Combinar com filtros existentes (entity filter, etc.)
        if filters:
            combined_filter = Filter.all_of([filters, lang_filter])
        else:
            combined_filter = lang_filter
        
        # 4. Chamar retrieve do EntityAwareRetriever com filtro combinado
        return await super().retrieve(
            queries=queries,
            client=client,
            embedder=embedder,
            limit=limit,
            filters=combined_filter,
            **kwargs
        )
```

### **Benefícios**
- ✅ **Melhora recall**: Evita chunks em idioma errado
- ✅ **Zero configuração**: Automático baseado na query
- ✅ **Compatível**: Funciona com EntityAwareRetriever
- ✅ **Fallback**: Se não detectar, pode usar ambos os idiomas

### **Próximos Passos**
1. ✅ Criar plugin `BilingualRetriever`
2. ✅ Testar com queries PT/EN
3. ✅ Validar melhoria de recall

---

## 🥈 Feature #2: Query Rewriting via LLM

### **Impacto: ⭐⭐⭐⭐⭐ (Crítico)**

### **O que faz?**
- Usa LLM para entender intenção da query
- Reescreve/expande query para melhor busca
- Extrai filtros e parâmetros automaticamente

### **Como funciona no RAG2?**
```python
# RAG2: agent/query_understander.py
class QueryUnderstander:
    def analyze(self, user_query: str) -> Dict[str, Any]:
        """Analisa query e retorna estratégia"""
        
        prompt = f"""
        Analise a query do usuário e retorne JSON:
        {{
            "intent": "comparison|description|search",
            "semantic_query": "query reescrita para busca semântica",
            "keyword_query": "query para BM25",
            "filters": {{"entity_ids": ["Q123"], "date_range": "2024-01-01"}},
            "query_params": {{"alpha": 0.6, "limit": 10}}
        }}
        """
        
        strategy = self.llm.generate_json([{"role": "user", "content": prompt}])
        return strategy
```

### **Por que é fácil?**
1. ✅ Verba já tem LLM generators (AnthropicGenerator, etc.)
2. ✅ Pode ser plugin de pré-processamento
3. ✅ Não requer mudanças no core
4. ✅ Cache pode ser adicionado depois

### **Implementação como Plugin**

**Plugin: `QueryRewriterPlugin`** (pré-processador de queries)

```python
# verba_extensions/plugins/query_rewriter.py

from typing import Dict, Any, Optional
from goldenverba.components.interfaces import Retriever
from goldenverba.components.generation.AnthrophicGenerator import AnthropicGenerator

class QueryRewriterPlugin:
    """Plugin que reescreve queries usando LLM para melhorar busca"""
    
    def __init__(self):
        self.generator = AnthropicGenerator()
        self.cache: Dict[str, Dict[str, Any]] = {}
    
    def rewrite_query(
        self, 
        original_query: str,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Reescreve query usando LLM.
        
        Returns:
        {
            "semantic_query": "query otimizada para busca semântica",
            "keyword_query": "query otimizada para BM25",
            "intent": "comparison|description|search",
            "filters": {"entity_ids": [...]},
            "alpha": 0.6  # Balance keyword/vector
        }
        """
        
        # Cache hit?
        if use_cache and original_query in self.cache:
            return self.cache[original_query]
        
        # Prompt para LLM
        prompt = f"""Analise a query do usuário e retorne JSON com:
1. semantic_query: Query reescrita para busca semântica (expandir sinônimos, conceitos)
2. keyword_query: Query para busca BM25 (manter termos-chave)
3. intent: "comparison" (comparação), "description" (descrição), "search" (busca)
4. filters: Extrair entidades, datas, etc. se mencionados
5. alpha: Balance entre keyword (0.0) e vector (1.0) - sugerir 0.4-0.7

Query original: "{original_query}"

Retorne apenas JSON válido:
{{
    "semantic_query": "...",
    "keyword_query": "...",
    "intent": "...",
    "filters": {{}},
    "alpha": 0.6
}}
"""
        
        try:
            # Chamar LLM
            response = self.generator.generate(
                messages=[{"role": "user", "content": prompt}],
                stream=False
            )
            
            # Parse JSON
            import json
            strategy = json.loads(response)
            
            # Cache
            if use_cache:
                self.cache[original_query] = strategy
            
            return strategy
            
        except Exception as e:
            # Fallback: retornar query original
            return {
                "semantic_query": original_query,
                "keyword_query": original_query,
                "intent": "search",
                "filters": {},
                "alpha": 0.6
            }
    
    def enhance_retriever_query(
        self,
        retriever: Retriever,
        query: str
    ) -> tuple[str, Dict[str, Any]]:
        """
        Integra com retriever para melhorar query.
        Retorna (query_otimizada, metadata)
        """
        strategy = self.rewrite_query(query)
        
        # Usar semantic_query para busca vetorial
        optimized_query = strategy.get("semantic_query", query)
        
        # Metadata para retriever
        metadata = {
            "intent": strategy.get("intent"),
            "alpha": strategy.get("alpha", 0.6),
            "filters": strategy.get("filters", {})
        }
        
        return optimized_query, metadata
```

### **Integração com EntityAwareRetriever**

```python
# verba_extensions/plugins/entity_aware_retriever.py

# Adicionar no início do método retrieve()
async def retrieve(self, queries: list[str], ...):
    query = queries[0] if queries else ""
    
    # ✨ NOVO: Query Rewriting (se plugin disponível)
    try:
        from verba_extensions.plugins.query_rewriter import QueryRewriterPlugin
        rewriter = QueryRewriterPlugin()
        optimized_query, metadata = rewriter.enhance_retriever_query(self, query)
        
        # Usar query otimizada
        query = optimized_query
        
        # Aplicar alpha sugerido
        if "alpha" in metadata:
            alpha = metadata["alpha"]
        
        # Aplicar filtros extras
        if "filters" in metadata:
            # Combinar com entity filters
            pass
    except:
        # Fallback: usar query original
        pass
    
    # ... resto do código
```

### **Benefícios**
- ✅ **Melhora relevância**: Query reescrita é mais precisa
- ✅ **Expansão automática**: Sinônimos e conceitos relacionados
- ✅ **Intenção detectada**: Ajusta estratégia de busca
- ✅ **Cache**: Reutiliza análises similares

### **Próximos Passos**
1. ✅ Criar plugin `QueryRewriterPlugin`
2. ✅ Integrar com EntityAwareRetriever
3. ✅ Adicionar cache LRU
4. ✅ Testar com queries complexas

---

## 🥉 Feature #3: Filtros Temporais (Date Range)

### **Impacto: ⭐⭐⭐⭐ (Alto para documentos temporais)**

### **O que faz?**
- Extrai faixas de datas de queries
- Aplica filtros temporais no Weaviate
- Útil para artigos, relatórios, notícias

### **Como funciona no RAG2?**
```python
# RAG2: Schema tem campos temporais
"exp_start_date": "date",
"exp_end_date": "date",
"last_company_change_date": "date"

# Query com filtro temporal
where: {
    path: ["exp_start_date"],
    operator: GreaterThan,
    valueDate: "2024-01-01"
}
```

### **Por que é fácil?**
1. ✅ Verba já tem campos de data nos chunks (via ETL)
2. ✅ Weaviate suporta filtros de data nativamente
3. ✅ Pode ser extensão do EntityAwareRetriever
4. ✅ Extração de datas pode usar regex ou LLM

### **Implementação como Plugin**

**Plugin: `TemporalFilterPlugin`** (extensão do retriever)

```python
# verba_extensions/plugins/temporal_filter.py

import re
from datetime import datetime
from typing import Optional, Tuple
from weaviate.classes.query import Filter

class TemporalFilterPlugin:
    """Plugin que extrai e aplica filtros temporais"""
    
    def extract_date_range(self, query: str) -> Optional[Tuple[str, str]]:
        """
        Extrai faixa de datas da query.
        
        Returns:
            (start_date, end_date) ou None
        """
        # Padrões de data
        patterns = [
            r"(\d{4})",  # "2024"
            r"(\d{1,2})/(\d{4})",  # "01/2024"
            r"(\d{1,2})-(\d{1,2})-(\d{4})",  # "01-01-2024"
            r"janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro",
            r"january|february|march|april|may|june|july|august|september|october|november|december"
        ]
        
        # Detectar anos
        years = re.findall(r"\b(20\d{2})\b", query)
        if years:
            min_year = min(years)
            max_year = max(years)
            return (f"{min_year}-01-01", f"{max_year}-12-31")
        
        # Detectar "em 2024", "desde 2023", "até 2024"
        if "desde" in query.lower() or "from" in query.lower():
            year = re.search(r"\b(20\d{2})\b", query)
            if year:
                return (f"{year.group(1)}-01-01", None)
        
        if "até" in query.lower() or "until" in query.lower() or "to" in query.lower():
            year = re.search(r"\b(20\d{2})\b", query)
            if year:
                return (None, f"{year.group(1)}-12-31")
        
        return None
    
    def build_temporal_filter(
        self,
        start_date: Optional[str],
        end_date: Optional[str],
        date_field: str = "chunk_date"  # Campo no Weaviate
    ) -> Optional[Filter]:
        """Constrói filtro temporal para Weaviate"""
        
        filters = []
        
        if start_date:
            filters.append(
                Filter.by_property(date_field).greater_or_equal(
                    datetime.fromisoformat(start_date)
                )
            )
        
        if end_date:
            filters.append(
                Filter.by_property(date_field).less_or_equal(
                    datetime.fromisoformat(end_date)
                )
            )
        
        if len(filters) == 1:
            return filters[0]
        elif len(filters) == 2:
            return Filter.all_of(filters)
        else:
            return None
```

### **Integração com EntityAwareRetriever**

```python
# verba_extensions/plugins/entity_aware_retriever.py

# Adicionar no método retrieve()
async def retrieve(self, queries: list[str], ...):
    query = queries[0] if queries else ""
    
    # ... entity filtering ...
    
    # ✨ NOVO: Filtros temporais
    try:
        from verba_extensions.plugins.temporal_filter import TemporalFilterPlugin
        temporal = TemporalFilterPlugin()
        date_range = temporal.extract_date_range(query)
        
        if date_range:
            start_date, end_date = date_range
            temporal_filter = temporal.build_temporal_filter(start_date, end_date)
            
            # Combinar com entity filter
            if entity_filter and temporal_filter:
                combined_filter = Filter.all_of([entity_filter, temporal_filter])
            elif temporal_filter:
                combined_filter = temporal_filter
            else:
                combined_filter = entity_filter
        else:
            combined_filter = entity_filter
    except:
        combined_filter = entity_filter
    
    # ... usar combined_filter na busca ...
```

### **Benefícios**
- ✅ **Melhora precisão**: Filtra por período relevante
- ✅ **Automatico**: Detecta datas na query
- ✅ **Útil para notícias**: Artigos, relatórios, eventos
- ✅ **Compatível**: Funciona com outros filtros

### **Próximos Passos**
1. ✅ Criar plugin `TemporalFilterPlugin`
2. ✅ Adicionar campo `chunk_date` no ETL (se não existir)
3. ✅ Integrar com EntityAwareRetriever
4. ✅ Testar com queries temporais

---

## 📊 Comparação das Features

| Feature | Impacto | Dificuldade | Tempo | Prioridade |
|---------|---------|-------------|-------|------------|
| **Roteamento Bilíngue** | ⭐⭐⭐⭐⭐ | ⭐ | 2-3h | 🥇 **ALTA** |
| **Query Rewriting** | ⭐⭐⭐⭐⭐ | ⭐⭐ | 4-6h | 🥈 **ALTA** |
| **Filtros Temporais** | ⭐⭐⭐⭐ | ⭐⭐ | 3-4h | 🥉 **MÉDIA** |

---

## 🚀 Plano de Implementação

### **Fase 1: Roteamento Bilíngue** (2-3 horas)
1. ✅ Criar `BilingualRetriever` plugin
2. ✅ Testar com queries PT/EN
3. ✅ Validar melhoria de recall

### **Fase 2: Query Rewriting** (4-6 horas)
1. ✅ Criar `QueryRewriterPlugin`
2. ✅ Integrar com EntityAwareRetriever
3. ✅ Adicionar cache LRU
4. ✅ Testar com queries complexas

### **Fase 3: Filtros Temporais** (3-4 horas)
1. ✅ Criar `TemporalFilterPlugin`
2. ✅ Adicionar campo `chunk_date` no ETL (se necessário)
3. ✅ Integrar com EntityAwareRetriever
4. ✅ Testar com queries temporais

---

## 💡 Conclusão

Essas 3 features do RAG2 são **ideais para implementar como plugins** porque:

1. ✅ **Alto impacto**: Melhoram significativamente qualidade/relevância
2. ✅ **Fáceis**: Não requerem mudanças arquiteturais grandes
3. ✅ **Compatíveis**: Funcionam com Verba atual
4. ✅ **Modulares**: Podem ser ativadas/desativadas independentemente

**Recomendação**: Começar pelo **Roteamento Bilíngue** (mais fácil e alto impacto), depois **Query Rewriting** (mais complexo mas crítico), e por último **Filtros Temporais** (útil mas específico).

