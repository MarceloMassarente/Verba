# Análise aprofundada dos mecanismos de pesquisa na base vetorizada (Verba)

Data: 2026-04-24

## Objetivo desta versão

Aprofundar especificamente:
1. **quais mecanismos de busca existem** hoje sobre a base já vetorizada;
2. **quando usar cada mecanismo** para melhor qualidade/custo/latência;
3. **como o chat decide e aplica** (ou não) esses mecanismos na prática.

---

## 1) Mapa do fluxo de pesquisa sobre base vetorizada

## Fluxo real (código)

1. O backend recebe query e RAG config.
2. `VerbaManager.retrieve_chunks(...)` escolhe `Retriever` e `Embedder` ativos, registra sugestão e gera embedding da query.
3. `RetrieverManager.retrieve(...)` chama o retriever selecionado (normalmente `EntityAware`).
4. O retriever executa a estratégia de busca e retorna `(documents, context[, debug_info])`.

## Implicações
- O motor de busca não está hardcoded no chat: **é dirigido por configuração de retriever**.
- O chat usa "tools" de pesquisa principalmente **via pipeline do retriever**, não por function-calling explícito de ferramentas externas.

---

## 2) Quais mecanismos de pesquisa existem hoje

Abaixo, os mecanismos efetivamente implementados para consultar base vetorizada no Weaviate.

## 2.1 Hybrid Search (BM25 + vector)

**O que é:** busca híbrida com `query` textual + `vector` da query + `alpha`.

**Onde aparece:**
- `WeaviateManager.hybrid_chunks(...)`
- `WeaviateManager.hybrid_chunks_with_filter(...)`

**Parâmetros-chave:**
- `alpha` (peso lexical vs semântico)
- `limit_mode` (`Autocut` ou `Fixed`)
- `target_vector` (quando named vectors estão ativos)
- `query_properties` (boost BM25)
- `fusion_type` (Relative Score quando suportado)

**Quando usar melhor:**
- default para maioria dos casos;
- ideal para perguntas misturando termos específicos + conceito semântico.

---

## 2.2 Hybrid Search com filtros compostos (entity-aware)

**O que é:** mesma busca híbrida, mas com `WHERE` antes da ordenação final (entidades, labels, doc_uuid, temporal etc.).

**Força:** reduz “contaminação” de contexto entre entidades semelhantes.

**Quando usar melhor:**
- perguntas com **empresa/pessoa/setor explícitos**;
- cenários com coleção heterogênea e risco de falso positivo sem filtro.

---

## 2.3 Entity Filter modes (strict / boost / adaptive / hybrid)

O `EntityAwareRetriever` expõe múltiplos modos de uso de entidade:
- **strict**: filtro duro;
- **boost**: sem filtro duro, reforça termos;
- **adaptive**: tenta estratégia mais restritiva e recua em fallback;
- **hybrid**: combinação orientada pela sintaxe/intenção.

**Quando usar melhor:**
- `strict`: precisão máxima (risco de recall menor);
- `boost`: recall maior com entidade como sinal fraco;
- `adaptive`: melhor default em produção multi-domínio;
- `hybrid`: útil com queries ambíguas e mistas.

---

## 2.4 Two-Phase Search (subespaço por entidade → busca semântica)

**O que é:**
1. Fase 1: filtra subespaço (chunk-level ou document-level);
2. Fase 2: busca semântica/multivetor dentro do subespaço.

**Modos:**
- `enabled`, `auto`, `disabled`.
- Nível de filtro: `chunk` ou `document`.

**Quando usar melhor:**
- consultas com entidades claras e necessidade de precisão contextual;
- `document-level` quando quer evitar fragmentação e preservar contexto completo.

---

## 2.5 Named vectors e target vector único

Se a collection tiver `vector_config`, o sistema pode consultar vetor específico:
- `default`
- `concept_vec`
- `sector_vec`
- `company_vec`

**Quando usar melhor:**
- `concept_vec`: frameworks/metodologias/temas abstratos;
- `sector_vec`: perguntas por indústria;
- `company_vec`: perguntas focadas em organização específica.

Se apenas 1 dimensão é dominante, usar target vector único tende a dar melhor custo/latência que multi-vector.

---

## 2.6 Multi-Vector Search (experimental)

Busca paralela em múltiplos vetores especializados, com combinação (RRF/Relative Score fallback).

**Status atual:** explicitamente marcado como **EXPERIMENTAL**.

**Quando usar melhor:**
- queries multiaspecto (empresa + setor + conceito) e coleção madura com named vectors bem preenchidos;
- benchmarking controlado, não como default global em produção sensível a latência.

---

## 2.7 Query Builder (schema-aware)

**Função:** montar estratégia de busca com consciência de schema, filtros, vetores-alvo, alpha e até agregações.

**Papel no pipeline:** executa antes do parsing principal e pode:
- reescrever query semântica;
- sugerir `alpha`;
- definir `target_vectors`;
- definir `two_phase_mode` e `filter_level`;
- detectar agregação.

**Quando usar melhor:**
- ambientes com schema rico e queries complexas;
- quando quer reduzir tuning manual de knobs.

---

## 2.8 Query Rewriter (fallback semântico)

Se Query Builder não está disponível/funciona, o sistema usa rewriter adaptativo por entropia.

**Força:** melhora semântica sem depender de schema detalhado.

**Limitação:** menos preciso que Query Builder em cenários de filtros estruturados.

---

## 2.9 Query Expansion

Expande variações de tema antes da busca normal (quando habilitado e Two-Phase não resolve).

**Quando usar melhor:**
- perguntas curtas/genéricas;
- casos com vocabulário rico/sinônimos variados.

---

## 2.10 Aggregation queries

Existe caminho de detecção e execução de agregações (inclusive por Query Builder), retornando contexto analítico em vez de chunks tradicionais.

**Quando usar melhor:**
- perguntas de contagem/distribuição/listagem analítica;
- exploração de metadados, não de passagem textual para resposta discursiva.

---

## 2.11 Cascade Mode + Reranking

Duas fases: recall mais amplo primeiro, depois reranking premium e corte por `Reranker Top K`.

**Quando usar melhor:**
- quando custo extra de rerank compensa ganho de precisão final;
- queries críticas (relatórios executivos, comparação fina de evidências).

---

## 2.12 Chunk Window + Relevance Gate

- **Chunk Window**: expande chunks vizinhos para enriquecer contexto.
- **Relevance Gate** (`Retrieval Threshold` + `Retrieval Margin`): bloqueia respostas quando sinais de relevância são fracos/ambíguos.

**Quando usar melhor:**
- Window: documentos segmentados onde contexto local importa;
- Gate: produção com risco de perguntas fora de domínio.

---

## 2.13 Intelligent Cache + Dynamic Score Enrichment

- cache semântico para reaproveitar retrieval;
- enriquecimento de score (recência/frequência de entidade) antes do reranker principal.

**Quando usar melhor:**
- alto volume de queries repetidas ou similares;
- necessidade de estabilidade de latência.

---

## 3) Como usar melhor cada mecanismo (guia prático)

## Perfil A — Base geral sem schema ETL completo

**Ative:** Hybrid padrão + Query Rewriting + Gate leve.
**Evite inicialmente:** Entity strict, Two-Phase agressivo, Multi-Vector.

Por quê: sem ETL/schema consistente, filtros entity-aware podem degradar recall.

## Perfil B — Base corporativa com entidades bem extraídas

**Ative:** Entity Filter `adaptive` + Two-Phase `auto` + filtros temporal/framework + reranker moderado.

Por quê: equilíbrio forte entre precisão sem “zero result” frequente.

## Perfil C — Coleção madura com named vectors confiáveis

**Ative:** target vector seletivo e, quando necessário, Multi-Vector em queries multiaspecto.
**Controle:** latência e custo por tipo de pergunta.

## Perfil D — Assistente executivo (qualidade máxima)

**Ative:** Cascade + Reranker Top K adequado + Gate calibrado + observabilidade de debug.
**Tradeoff:** maior custo e tempo por resposta.

---

## 4) Como o chat “sabe usar” essas ferramentas hoje

## 4.1 O que funciona bem

1. O retriever recebe **rag_config completo** (não apenas query + vetor).
2. O `EntityAwareRetriever` decide dinamicamente entre:
   - busca normal híbrida,
   - two-phase,
   - named vector único,
   - multi-vector (se habilitado),
   - query builder/rewriter,
   - agregação.
3. O retriever retorna `debug_info` detalhando decisões (modo, filtros, alpha, gate etc.).

**Resumo:** o chat “sabe usar” por **orquestração interna do retriever**, não por agente de tools explícito.

## 4.2 Gap importante

No websocket `/ws/generate_stream`, mesmo quando "iterative search" é marcado como habilitado, o código atual continua no fluxo `generate_stream_answer(...)` (padrão) em vez de chamar o caminho iterativo completo.

**Efeito prático:** capacidade de busca iterativa existe na base, mas ainda não está totalmente acionada no fluxo principal de streaming do chat.

---

## 5) Robustez específica da camada de pesquisa

## Pontos fortes

- múltiplos mecanismos reais de recuperação, não só “vector top-k” simples;
- fallback defensivo quando schema não suporta filtros ETL;
- compatibilidade com named vectors e collections sem named vectors;
- guardrails de relevância e pós-processamento.

## Pontos de risco

- complexidade alta concentrada em um único retriever grande;
- comportamento pode variar bastante conforme combinação de flags;
- multi-vector ainda experimental;
- contract de retorno ainda com compatibilidade 2/3 elementos.

---

## 6) Plano objetivo para melhorar “o chat sabe usar”

1. **P0**: no websocket principal, quando iterative search=true, chamar `generate_stream_answer_iterative(...)` com client e filtros.
2. **P0**: normalizar contrato de retorno dos retrievers para sempre incluir `debug_info` (mesmo vazio).
3. **P1**: extrair orquestração do `EntityAwareRetriever` em módulos (`query_understanding`, `filter_planner`, `search_executor`, `post_processor`).
4. **P1**: criar "Search Trace" estruturado por query (json persistível) para auditoria e tuning.
5. **P2**: hardening e promoção gradual de Multi-Vector de experimental para estável com benchmark e SLO.

---

## 7) Conclusão executiva

A base vetorizada do Verba já suporta um **ecossistema avançado de pesquisa**: hybrid, filtros entity-aware, two-phase, named vectors, query intelligence, reranking e guardrails. O sistema não sofre de “falta de mecanismos”; o principal desafio é **governar complexidade** e **garantir que o fluxo de chat principal acione consistentemente os modos avançados planejados**.

Em outras palavras: a capacidade técnica existe; o próximo salto de qualidade vem de orquestração previsível, observabilidade estruturada e simplificação de runtime.
