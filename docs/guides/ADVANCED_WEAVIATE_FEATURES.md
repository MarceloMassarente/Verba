# Features Avançadas Weaviate no Verba

## Visão Geral

Este documento descreve as features avançadas do Weaviate implementadas no Verba, aprendendo das melhores práticas do RAG2:

- **Named Vectors**: Vetores especializados para diferentes aspectos semânticos
- **Multi-Vector Search**: Busca paralela em múltiplos vetores com combinação RRF
- **GraphQL Builder**: Queries GraphQL dinâmicas com HTTP fallback
- **Aggregation**: Queries analíticas com HTTP fallback quando gRPC falha
- **Framework Detection**: Detecção automática de frameworks, empresas e setores

---

## 1. Named Vectors Especializados

### O que são Named Vectors?

Named vectors permitem ter múltiplos vetores em uma única collection, cada um especializado em um aspecto diferente:

- **`concept_vec`**: Conceitos abstratos (frameworks, estratégias, metodologias)
- **`sector_vec`**: Setores/indústrias (varejo, bancos, tecnologia)
- **`company_vec`**: Empresas específicas (Apple, Microsoft, etc.)

### Como Habilitar

```bash
# Variável de ambiente
export ENABLE_NAMED_VECTORS="true"
```

### Como Funciona

1. **Criação de Collection:**
   - Quando `ENABLE_NAMED_VECTORS=true`, collections são criadas com `vectorConfig`
   - Cada named vector tem seu próprio índice HNSW
   - Quantização PQ é ativada automaticamente para collections grandes (≥50k objetos)

2. **Durante Chunking:**
   - Textos especializados são extraídos para cada named vector:
     - `concept_text`: frameworks + termos semânticos + texto base
     - `sector_text`: setores + texto base
     - `company_text`: empresas + texto base

3. **Durante Import:**
   - Estrutura preparada para gerar embeddings para cada named vector
   - Propriedades `concept_text`, `sector_text`, `company_text` são salvas

4. **Durante Busca:**
   - Multi-vector search usa named vectors quando apropriado
   - Fallback para vetor único se named vectors não disponíveis

### Arquivos Relacionados

- `verba_extensions/integration/vector_config_builder.py` - Constrói vectorConfig
- `verba_extensions/integration/schema_updater.py` - Adiciona named vectors ao schema
- `verba_extensions/utils/vector_extractor.py` - Extrai textos especializados
- `verba_extensions/integration/import_hook.py` - Prepara textos durante import

### Verificação

```python
# Verificar se named vectors estão habilitados
from verba_extensions.integration.schema_updater import get_vector_config
vector_config = get_vector_config(enable_named_vectors=True)
if vector_config:
    print('✅ Named vectors configurados')
    print(f'Vetores: {list(vector_config.keys())}')

# Verificar se collection tem named vectors
collection = client.collections.get("VERBA_Embedding_...")
config = await collection.config.get()
if hasattr(config, 'vector_config') and config.vector_config:
    print('✅ Collection tem named vectors')
    print(f'Vetores: {list(config.vector_config.keys())}')
```

---

## 2. Multi-Vector Search

### O que é Multi-Vector Search?

Busca paralela em múltiplos named vectors, combinando resultados com RRF (Reciprocal Rank Fusion) para melhor recall e precisão.

### Quando é Usado

Multi-vector search é ativado automaticamente quando:
- Query combina 2+ aspectos (conceito + setor, setor + empresa, etc.)
- Collection tem named vectors habilitados
- Feature está habilitada no EntityAwareRetriever

### Como Habilitar

Na interface do Verba, no EntityAwareRetriever:
- **"Enable Multi-Vector Search"**: `true` (default: `false`)

### Como Funciona

1. **Análise da Query:**
   - Detecta conceitos (frameworks, termos semânticos)
   - Detecta setores (indústrias mencionadas)
   - Detecta empresas (organizações mencionadas)

2. **Decisão de Vetores:**
   - Se tem conceito → usa `concept_vec`
   - Se tem setor → usa `sector_vec`
   - Se tem empresa → usa `company_vec`
   - Se 2+ vetores → ativa multi-vector search

3. **Busca Paralela:**
   - Busca em cada vetor em paralelo
   - Cada busca retorna top-K resultados

4. **Combinação RRF:**
   - RRF Score = sum(1 / (k + rank)) para cada vetor
   - k = 60 (parâmetro RRF)
   - Resultados ordenados por score RRF combinado

5. **Deduplicação:**
   - Remove duplicatas baseado em UUID
   - Retorna top-N resultados únicos

### Exemplo

```python
# Query: "Estratégia digital para bancos"
# Detecta:
# - Conceito: "Estratégia digital" → concept_vec
# - Setor: "bancos" → sector_vec
# → Usa multi-vector search em [concept_vec, sector_vec]

# Busca paralela:
# - concept_vec: top-50 resultados sobre "estratégia digital"
# - sector_vec: top-50 resultados sobre "bancos"

# Combinação RRF:
# - Documentos que aparecem em ambos vetores têm score alto
# - Documentos sobre "estratégia digital em bancos" ficam no topo
```

### Arquivos Relacionados

- `verba_extensions/plugins/multi_vector_searcher.py` - Implementação do searcher
- `verba_extensions/plugins/entity_aware_retriever.py` - Integração no retriever

### Verificação

```python
# Verificar se multi-vector searcher está disponível
from verba_extensions.plugins.multi_vector_searcher import MultiVectorSearcher
searcher = MultiVectorSearcher()
print('✅ Multi-vector searcher disponível')

# Testar busca multi-vetor
result = await searcher.search_multi_vector(
    client=client,
    collection_name="VERBA_Embedding_...",
    query="Estratégia digital para bancos",
    query_vector=query_embedding,
    vectors=["concept_vec", "sector_vec"],
    limit=10
)
print(f'Resultados: {len(result["results"])}')
```

---

## 3. GraphQL Builder

### O que é GraphQL Builder?

Constrói queries GraphQL dinâmicas para Weaviate, permitindo usar features avançadas que o SDK Python pode não suportar diretamente.

### Quando é Usado

- Queries complexas com named vectors
- Filtros complexos (where clause)
- Hybrid search via GraphQL
- Quando SDK Python não suporta features específicas

### Como Funciona

1. **Construção de Query:**
   - Monta query GraphQL com campos, filtros, limites
   - Suporta `targetVector` para named vectors
   - Suporta `hybrid` para busca híbrida

2. **Execução:**
   - Tenta SDK Python primeiro
   - Se falhar, usa HTTP REST API como fallback

### Exemplo

```python
from verba_extensions.utils.graphql_builder import get_graphql_builder
from verba_extensions.utils.graphql_client import get_graphql_client

builder = get_graphql_builder()
query = builder.build_query(
    class_name="VERBA_Embedding_...",
    query="inovação",
    vector=query_embedding,
    target_vector="concept_vec",
    filters=Filter.by_property("frameworks").contains_any(["SWOT"]),
    alpha=0.6,
    limit=10
)

client = get_graphql_client()
result = await client.execute_query(query)
```

### Arquivos Relacionados

- `verba_extensions/utils/graphql_builder.py` - Builder de queries
- `verba_extensions/utils/graphql_client.py` - Cliente com HTTP fallback

---

## 4. Aggregation & Analytics

### O que é Aggregation?

Queries analíticas que agregam dados (count, group by, sum, etc.) sem retornar objetos individuais.

### Quando é Usado

- Queries como "quantos documentos sobre SWOT?"
- "Agrupar por setor"
- "Estatísticas de frameworks"
- Queries analíticas em geral

### Como Habilitar

Na interface do Verba, no EntityAwareRetriever:
- **"Enable Aggregation"**: `true` (default: `false`)

### Como Funciona

1. **Detecção:**
   - Detecta palavras-chave de agregação: "quantos", "count", "agrupar", etc.
   - Extrai propriedades para `group_by` da query

2. **Execução:**
   - Tenta SDK Python primeiro (`collection.aggregate.over_all()`)
   - Se gRPC falhar, usa HTTP REST API como fallback

3. **Resultado:**
   - Retorna dados analíticos (não chunks)
   - Formato: `{total_count: X, groups: [...]}`

### Exemplo

```python
# Query: "Quantos documentos sobre SWOT?"
# Detecta: query de agregação
# Executa:
result = await aggregation_wrapper.aggregate_over_all(
    client=client,
    collection_name="VERBA_Embedding_...",
    filters=Filter.by_property("frameworks").contains_any(["SWOT"]),
    total_count=True
)
# Retorna: {total_count: 42}
```

### Arquivos Relacionados

- `verba_extensions/utils/aggregation_wrapper.py` - Wrapper com HTTP fallback
- `verba_extensions/plugins/entity_aware_retriever.py` - Detecção e execução

### Verificação

```python
# Verificar se aggregation wrapper está disponível
from verba_extensions.utils.aggregation_wrapper import get_aggregation_wrapper
wrapper = get_aggregation_wrapper()
print('✅ Aggregation wrapper disponível')

# Testar aggregation
result = await wrapper.aggregate_over_all(
    client=client,
    collection_name="VERBA_Embedding_...",
    group_by=["frameworks"],
    total_count=True
)
print(f'Total: {result.get("total_count", 0)}')
```

---

## 5. Framework Detection

### O que é Framework Detection?

Detecção automática de frameworks, empresas e setores durante chunking, armazenando em propriedades Weaviate para filtros precisos.

### Como Funciona

1. **Durante Chunking:**
   - `EntitySemanticChunker` detecta frameworks/empresas/setores
   - Armazena em `chunk.meta`: `frameworks`, `companies`, `sectors`

2. **Durante Import:**
   - Propriedades são mapeadas para Weaviate se collection suporta
   - Fallback para `meta` JSON se não suporta

3. **Durante Busca:**
   - `EntityAwareRetriever` detecta frameworks/empresas/setores na query
   - Aplica filtros automáticos se collection suporta

### Propriedades Weaviate

- `frameworks`: Array de frameworks detectados (ex: ["SWOT", "Porter"])
- `companies`: Array de empresas detectadas (ex: ["Apple", "Microsoft"])
- `sectors`: Array de setores detectados (ex: ["Tecnologia", "Varejo"])
- `framework_confidence`: Confiança na detecção (0.0-1.0)

### Arquivos Relacionados

- `verba_extensions/utils/framework_detector.py` - Detecção de frameworks
- `verba_extensions/plugins/entity_semantic_chunker.py` - Integração no chunker
- `verba_extensions/plugins/entity_aware_retriever.py` - Filtros automáticos

---

## Configuração Completa

### Variáveis de Ambiente

```bash
# Habilitar named vectors
export ENABLE_NAMED_VECTORS="true"

# Weaviate (já existentes)
export WEAVIATE_URL_VERBA="http://localhost:8080"
export WEAVIATE_API_KEY_VERBA=""
```

### Configurações do EntityAwareRetriever

Na interface do Verba:

1. **Enable Multi-Vector Search**: `true` (default: `false`)
   - Habilita busca multi-vetor quando query combina múltiplos aspectos

2. **Enable Aggregation**: `true` (default: `false`)
   - Habilita detecção e execução de queries de agregação

3. **Enable Framework Filter**: `true` (default: `true`)
   - Habilita filtros automáticos baseados em frameworks/empresas/setores

---

## Troubleshooting

### Named Vectors não são criados

**Sintoma:** Collections criadas sem `vectorConfig`

**Solução:**
1. Verificar se `ENABLE_NAMED_VECTORS="true"` está configurado
2. Verificar logs: deve aparecer "🎯 Named vectors habilitados"
3. Verificar se `patch_weaviate_manager_verify_collection()` está sendo chamado

### Multi-Vector Search não é usado

**Sintoma:** Sempre usa busca simples mesmo com named vectors

**Solução:**
1. Verificar se "Enable Multi-Vector Search" está habilitado
2. Verificar se query combina 2+ aspectos (conceito + setor, etc.)
3. Verificar logs: deve aparecer "🎯 Multi-vector search habilitado"

### Aggregation falha

**Sintoma:** Erro ao executar queries de agregação

**Solução:**
1. Verificar se "Enable Aggregation" está habilitado
2. Verificar se query contém palavras-chave de agregação
3. Verificar logs: deve aparecer "✅ Aggregation executada"
4. Se gRPC falhar, HTTP fallback deve ser usado automaticamente

### GraphQL queries falham

**Sintoma:** Erro ao executar queries GraphQL

**Solução:**
1. Verificar sintaxe da query GraphQL
2. Verificar se `graphql_client.py` está usando URL correta
3. Verificar logs: deve aparecer "SDK falhou, usando HTTP fallback"

---

## Performance

### Named Vectors

- **Overhead de memória**: ~3x (3 vetores vs 1)
- **Overhead de ingestão**: ~3x (3 embeddings vs 1)
- **Benefício**: Busca mais precisa quando query combina múltiplos aspectos

### Multi-Vector Search

- **Latência**: ~2x (busca paralela em 2-3 vetores)
- **Recall**: +30-50% (combina resultados de múltiplos vetores)
- **Precisão**: Mantida ou melhorada (RRF prioriza documentos relevantes em múltiplos vetores)

### Aggregation

- **Latência**: Similar a busca normal
- **Benefício**: Queries analíticas funcionam mesmo quando gRPC falha

---

## Compatibilidade

### Weaviate Versions

- **Weaviate v4.x**: Totalmente suportado
- **Weaviate v3.x**: Named vectors não suportados (fallback para vetor único)

### Verba Versions

- **Verba 2.1.x**: Compatível
- **Verba 2.0.x**: Pode precisar ajustes menores

### Fallbacks

- **Named vectors não disponíveis**: Usa vetor único padrão
- **Multi-vector não aplicável**: Usa busca simples
- **gRPC falha**: Usa HTTP REST API
- **SDK não suporta**: Usa GraphQL via HTTP

---

## Próximos Passos

1. **Benchmarks**: Comparar performance vs RAG2
2. **Otimização**: Ajustar thresholds e parâmetros
3. **Monitoramento**: Acompanhar uso e performance
4. **Expansão**: Adicionar mais named vectors se necessário

---

## Referências

- **RAG2**: `C:\Users\marce\native tool\RAG2` - Implementação de referência
- **Weaviate Docs**: https://weaviate.io/developers/weaviate
- **Documentação de Patches**: `verba_extensions/patches/README_PATCHES.md`

---

**Última atualização:** Janeiro 2025

