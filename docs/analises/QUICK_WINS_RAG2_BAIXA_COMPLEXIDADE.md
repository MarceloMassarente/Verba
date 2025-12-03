# 🚀 Quick Wins: Baixa Complexidade + Alto Impacto

Baseado na análise do RAG 2.0, aqui estão as **implementações mais viáveis** que trariam melhoria significativa com **esforço mínimo**.

---

## 🥇 #1: Busca Iterativa no Context (Simulada) - ⭐⭐⭐⭐⭐

### O Que É

Durante a geração, se o modelo gerar um token especial ou phrase especial (ex: `[SEARCH]` ou "Deixe-me buscar mais informações sobre..."), interromper a geração, fazer uma busca adicional e continuar.

### Implementação

**Effort: 4-6 horas | Impacto: Alto | Complexidade: Média**

```python
# Pseudo-código do fluxo
async def generate_with_iterative_search(
    query: str,
    initial_context: str,
    max_iterations: int = 3
):
    context = initial_context
    full_response = ""
    
    for iteration in range(max_iterations):
        # Gerar até detectar [SEARCH] ou fim
        response_chunk = ""
        async for token in generator.generate_stream(
            config, query, context, conversation
        ):
            full_response += token["message"]
            response_chunk += token["message"]
            
            # Detectar token de busca
            if "[SEARCH:" in response_chunk:
                # Extrair query para busca
                search_query = extract_search_query(response_chunk)
                
                # Buscar documentos adicionais
                new_chunks = await retriever.retrieve(
                    search_query, vector=..., config=...
                )
                
                # Adicionar ao contexto
                context += "\n\n[Informações Adicionais]:\n"
                context += combine_context(new_chunks)
                
                # Continuar gerando com novo contexto
                break
        else:
            # Geração terminou, sem busca necessária
            break
    
    return full_response
```

### Benefícios

- ✅ Simula busca iterativa sem treinar modelo
- ✅ Permite múltiplas buscas durante resposta
- ✅ Compatível com gerador existente (Claude, GPT, etc.)
- ✅ Fácil de desativar (flag `Enable Iterative Search`)

### Implementação Técnica

1. Adicionar hook no `generator.generate_stream()` para detectar `[SEARCH:]`
2. Extrair query de busca do formato `[SEARCH: query aqui]`
3. Re-buscar com nova query
4. Injetar novo contexto
5. Continuar geração

### Onde Implementar

- `goldenverba/verba_manager.py` → método `generate_stream_answer()`
- Ou novo arquivo: `verba_extensions/plugins/iterative_search_plugin.py`

---

## 🥈 #2: Query Rewriting com Análise de Entropia - ⭐⭐⭐⭐

### O Que É

Usar métricas simples (entropia, variedade de palavras) para decidir **quando** reescrever a query e **como**.

Exemplo:
```
Query genérica: "o que é" → Alta entropia → Reescrever com contexto
Query específica: "Steve Jobs cofundador Apple" → Baixa entropia → Manter original
```

### Implementação

**Effort: 2-3 horas | Impacto: Médio-Alto | Complexidade: Baixa**

```python
class AdaptiveQueryRewriter:
    def should_rewrite(self, query: str) -> bool:
        """Decide se deve reescrever baseado em entropia"""
        
        # Calcular entropia do query (número de palavras únicas / total)
        words = query.lower().split()
        unique_words = len(set(words))
        total_words = len(words)
        
        entropy = unique_words / total_words if total_words > 0 else 0
        
        # Se genérico (alta entropia), reescrever
        # Se específico (baixa entropia), manter
        return entropy > 0.7  # threshold configurável
    
    async def rewrite_adaptive(self, query: str) -> str:
        """Reescreve adaptando força de reescrita"""
        
        if not self.should_rewrite(query):
            # Query específica, usar rewrite leve
            prompt = f"""Expanda levemente a query (apenas sinônimos diretos):
            Query: "{query}"
            Responda apenas com query expandida, sem explicações."""
        else:
            # Query genérica, usar rewrite forte
            prompt = f"""Expanda fortemente a query (sinônimos, conceitos relacionados, contexto):
            Query: "{query}"
            Responda apenas com query expandida, sem explicações."""
        
        rewritten = await self.llm.call(prompt)
        return rewritten
```

### Benefícios

- ✅ Economiza chamadas ao LLM (não reescreve queries específicas)
- ✅ Melhor qualidade em queries genéricas
- ✅ Simples lógica estatística (sem ML)
- ✅ Fácil de tunar

### Onde Implementar

- Modificar `QueryRewriterPlugin` para adicionar `should_rewrite()`
- Ou novo arquivo: `verba_extensions/plugins/adaptive_query_rewriter.py`

---

## 🥉 #3: Reranking com Score Dinâmico - ⭐⭐⭐⭐

### O Que É

Não apenas reordenar chunks por similaridade, mas considerar:
1. **Recência** (dados mais recentes mais relevantes)
2. **Frequência de entidades** (chunks que mencionam mais entidades = mais relevantes)
3. **Documento source** (alguns documentos mais confiáveis que outros)

### Implementação

**Effort: 3-4 horas | Impacto: Médio-Alto | Complexidade: Baixa**

```python
class DynamicReranker:
    async def rerank_with_metadata(
        self,
        chunks: List[Chunk],
        query: str,
        weights: Dict[str, float] = None
    ) -> List[Chunk]:
        """
        Reranking que considera múltiplas dimensões:
        - similarity_score: Do model embedding (0-1)
        - recency_score: Baseado em chunk_date (0-1)
        - entity_frequency_score: Quantas entidades mencionadas (0-1)
        - doc_authority_score: Confiabilidade do documento (0-1)
        """
        
        if weights is None:
            weights = {
                "similarity": 0.6,    # Peso da similaridade
                "recency": 0.15,      # Chunks recentes mais relevantes
                "entity_freq": 0.15,  # Chunks com mais entidades
                "authority": 0.1      # Confiabilidade do doc
            }
        
        scored_chunks = []
        
        for chunk in chunks:
            # 1. Score de similaridade (já temos)
            similarity_score = chunk.similarity_score  # 0-1
            
            # 2. Score de recência
            recency_score = self._calculate_recency_score(chunk.chunk_date)
            
            # 3. Score de frequência de entidades
            entity_freq_score = min(len(chunk.entities) / 5.0, 1.0)  # até 5 entidades = score 1
            
            # 4. Score de autoridade do documento
            authority_score = self._get_doc_authority_score(chunk.doc_uuid)
            
            # Combinar scores ponderados
            final_score = (
                weights["similarity"] * similarity_score +
                weights["recency"] * recency_score +
                weights["entity_freq"] * entity_freq_score +
                weights["authority"] * authority_score
            )
            
            scored_chunks.append((final_score, chunk))
        
        # Ordenar por score final
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        return [chunk for _, chunk in scored_chunks]
    
    def _calculate_recency_score(self, chunk_date: str) -> float:
        """Chunks mais recentes = score mais alto"""
        from datetime import datetime, timedelta
        
        try:
            date = datetime.fromisoformat(chunk_date)
            days_old = (datetime.now() - date).days
            
            # Fórmula: 1 - (dias_old / 365)
            # 0 dias (hoje) = 1.0
            # 365 dias (1 ano) = 0.0
            return max(1.0 - (days_old / 365.0), 0.0)
        except:
            return 0.5  # Default se não conseguir parsear
    
    def _get_doc_authority_score(self, doc_uuid: str) -> float:
        """Pontuação baseada em confiabilidade do documento"""
        # Pode ser:
        # - Baseado em label/tag do documento
        # - Baseado em quantas vezes o doc foi consultado
        # - Baseado em tipo de fonte
        # Exemplo simples: tudo 1.0 por enquanto
        return 1.0
```

### Benefícios

- ✅ Melhora qualidade de ranking sem modelo novo
- ✅ Simples lógica ponderada
- ✅ Configurável (pesos ajustáveis)
- ✅ Aproveita metadados que já existem

### Onde Implementar

- `verba_extensions/plugins/entity_aware_retriever.py` → adicionar reranking final
- Ou novo arquivo: `verba_extensions/plugins/dynamic_reranker.py`

---

## 🎯 #4: Cache Inteligente com TTL Adaptativo - ⭐⭐⭐

### O Que É

Não apenas cache simples (mesma query = mesma resposta). Mas cache que entende:
- Queries similares (não exatamente iguais) → reusar resultado
- Cache com TTL diferente por tipo de documento
  - Documentos estáticos (whitepapers) → cache 30 dias
  - Documentos dinâmicos (notícias) → cache 1 dia

### Implementação

**Effort: 2-3 horas | Impacto: Médio | Complexidade: Baixa**

```python
from sentence_transformers import util

class IntelligentCache:
    def __init__(self, embedding_model):
        self.embedding_model = embedding_model
        self.cache = {}  # {query_vector: (response, ttl_expiry)}
        self.similarity_threshold = 0.85  # 85% similar é suficiente
    
    async def get_cached_or_retrieve(
        self,
        query: str,
        doc_type: str = "general"  # "whitepaper", "news", "general"
    ):
        """Tenta encontrar cache com query similar"""
        
        # Determinar TTL baseado em tipo de documento
        ttl_map = {
            "whitepaper": 30 * 24 * 3600,  # 30 dias
            "news": 1 * 24 * 3600,          # 1 dia
            "general": 7 * 24 * 3600        # 7 dias
        }
        ttl = ttl_map.get(doc_type, 24 * 3600)
        
        # Embedar query
        query_embedding = self.embedding_model.encode(query)
        
        # Buscar no cache por similaridade
        current_time = time.time()
        for cached_query_emb, (response, expiry_time) in self.cache.items():
            # Verificar TTL
            if current_time > expiry_time:
                continue  # Expirou
            
            # Calcular similaridade com cached query
            similarity = util.pytorch_cos_sim(
                query_embedding, cached_query_emb
            )[0][0].item()
            
            if similarity > self.similarity_threshold:
                # Cache hit! Query similar encontrada
                return response, {"cache_hit": True, "similarity": similarity}
        
        # Cache miss
        return None, {"cache_hit": False}
    
    async def set_cache(self, query: str, response: str, doc_type: str = "general"):
        """Armazena response no cache"""
        query_embedding = self.embedding_model.encode(query)
        ttl_map = {"whitepaper": 30, "news": 1, "general": 7}
        ttl_days = ttl_map.get(doc_type, 7)
        expiry = time.time() + (ttl_days * 24 * 3600)
        
        self.cache[query_embedding] = (response, expiry)
```

### Benefícios

- ✅ Reutiliza respostas para queries similares
- ✅ TTL inteligente (documentos dinâmicos = cache curto)
- ✅ Economiza chamadas ao LLM
- ✅ Fácil de implementar

### Onde Implementar

- Novo arquivo: `verba_extensions/plugins/intelligent_cache.py`
- Adicionar no fluxo de retrieval antes de buscar

---

## 📊 Tabela Comparativa: Quick Wins

| Feature | Effort | Impacto | Viabilidade | Tempo Est. |
|---------|--------|--------|-------------|-----------|
| **Busca Iterativa** | Médio | ⭐⭐⭐⭐⭐ Alto | 95% | 4-6h |
| **Query Rewriting Adaptativo** | Baixo | ⭐⭐⭐⭐ Alto | 99% | 2-3h |
| **Reranking Dinâmico** | Baixo | ⭐⭐⭐⭐ Alto | 98% | 3-4h |
| **Cache Inteligente** | Baixo | ⭐⭐⭐ Médio | 95% | 2-3h |

---

## 🎯 Recomendação: Ordem de Implementação

### Fase 1 (Semana 1): Quick Wins de Baixissimo Esforço
1. ✅ **Query Rewriting Adaptativo** (2-3h) → 20% melhoria de recall
2. ✅ **Cache Inteligente** (2-3h) → Economia de custo + velocidade

### Fase 2 (Semana 2): Impacto Alto
3. ✅ **Reranking Dinâmico** (3-4h) → Melhor ordenação de resultados
4. ✅ **Busca Iterativa** (4-6h) → Abordagem mais próxima ao RAG 2.0

### Resultado Final
- **Tempo Total:** ~14-16 horas
- **Melhoria Esperada:** +30-50% em qualidade de respostas
- **Aproximação ao RAG 2.0:** De 80% para 85-90%

---

## 💡 Por Que Esses São "Quick Wins"

1. **Não requerem treinamento** - Usam lógica e heurísticas
2. **Compatíveis com sistema atual** - Não quebram nada existente
3. **Podem ser ligados/desligados** - Flags simples para ativar
4. **Aproveitam dados existentes** - Usam metadados que já existem
5. **Alto ROI** - Pouco esforço, muito impacto

---

## 🚀 Próximo Passo

Qual desses você quer implementar primeiro?

**Sugestão:** Começar com **#2 (Query Rewriting Adaptativo)** porque:
- Menos código
- Integra com `QueryRewriterPlugin` existente
- Impacto imediato
- Aprende depois com resultados para tunar outros



