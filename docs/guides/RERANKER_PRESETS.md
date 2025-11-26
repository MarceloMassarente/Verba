# Guia de Presets de Reranking

## Visão Geral

Os presets de reranking são configurações pré-otimizadas que combinam diferentes providers de reranking para diferentes cenários de uso. Eles simplificam a configuração e garantem performance e qualidade balanceadas.

## Presets Disponíveis

### 1. Production (Recomendado)

**Configuração:**
- Provider: ContextualAI
- Modelo: ctxl-rerank-v2-instruct-multilingual
- Instrução: "Prioritize recent and authoritative content."

**Características:**
- ⚡ Latência: ~500ms
- ⭐ Qualidade: Alta
- 💰 Custo: Baixo (1 API call)
- 📦 Requisitos: CONTEXTUAL_API_KEY

**Quando usar:**
- Uso geral em produção
- Quando você precisa de balanceamento entre velocidade e qualidade
- Quando você tem API key do ContextualAI disponível

**Como aplicar:**
```python
# Via código
reranker.apply_preset("production")

# Via frontend
# Selecione "Production" no seletor de presets
```

### 2. Max Quality

**Configuração:**
- Provider: Combined
- Mode: Hybrid
- Metadata Reranker: ✅ Habilitado
- Haystack Reranker: ✅ Habilitado
- ContextualAI Reranker: ✅ Habilitado
- Modelo: ctxl-rerank-v2-instruct-multilingual
- Instrução: "Prioritize internal documents and recent content."

**Características:**
- ⚡ Latência: ~1.5s
- ⭐ Qualidade: Muito Alta
- 💰 Custo: Médio (1 API call + processamento local)
- 📦 Requisitos: haystack-ai, CONTEXTUAL_API_KEY

**Quando usar:**
- Quando qualidade é mais importante que velocidade
- Para queries complexas que precisam de máxima precisão
- Quando você tem recursos disponíveis (Haystack + API key)

**Como aplicar:**
```python
# Via código
reranker.apply_preset("max_quality")

# Via frontend
# Selecione "Max Quality" no seletor de presets
```

### 3. Local Only

**Configuração:**
- Provider: Combined
- Mode: Parallel
- Metadata Reranker: ✅ Habilitado
- Haystack Reranker: ✅ Habilitado

**Características:**
- ⚡ Latência: ~500ms
- ⭐ Qualidade: Alta
- 💰 Custo: Zero (sem APIs)
- 📦 Requisitos: haystack-ai

**Quando usar:**
- Quando você não tem API keys disponíveis
- Para ambientes offline ou com restrições de rede
- Quando você quer evitar custos de API

**Como aplicar:**
```python
# Via código
reranker.apply_preset("local_only")

# Via frontend
# Selecione "Local Only" no seletor de presets
```

## Auto-Seleção

O preset "auto" analisa a query e os recursos disponíveis para selecionar automaticamente o melhor preset.

### Lógica de Seleção

1. **Latência crítica** (< 1s): Usa "production"
2. **Query precisa de instruções**: Usa "max_quality" (se recursos disponíveis)
3. **Sem APIs mas com Haystack**: Usa "local_only"
4. **Com APIs**: Usa "production" (balanceado)
5. **Apenas Haystack**: Usa "local_only"
6. **Fallback**: Usa "production" (sempre disponível via Metadata)

### Como usar Auto-Seleção

```python
# Via código
selected_preset = reranker.select_optimal_preset(
    query="inovação da Apple",
    has_api_keys=True,
    latency_budget=2.0
)
reranker.apply_preset(selected_preset)

# Via frontend
# Selecione "Auto" no seletor de presets
```

## Customização

Se você selecionar "Custom", pode configurar manualmente todas as opções do reranker através da interface ou código.

## Aplicando Presets

### Via Frontend

1. Acesse as configurações do Retriever
2. Na seção "Reranker Presets", selecione o preset desejado
3. O preset será aplicado automaticamente ao config do retriever

### Via Código

```python
from verba_extensions.plugins.reranker import RerankerPlugin

reranker = RerankerPlugin()

# Aplicar preset específico
reranker.apply_preset("production")

# Auto-seleção
preset = reranker.select_optimal_preset("sua query aqui")
reranker.apply_preset(preset)

# Obter metadados de todos os presets
presets = reranker.get_presets_metadata()
for preset in presets:
    print(f"{preset['name']}: {preset['description']}")
    print(f"  Disponível: {preset['available']}")
    print(f"  Latência: {preset['latency_estimate']}")
    print(f"  Qualidade: {preset['quality_estimate']}")
```

### Via API

```bash
# Obter lista de presets
curl -X POST http://localhost:8000/api/get_reranker_presets \
  -H "Content-Type: application/json" \
  -d '{"credentials": {...}}'

# Aplicar preset
curl -X POST http://localhost:8000/api/apply_reranker_preset \
  -H "Content-Type: application/json" \
  -d '{
    "preset_name": "production",
    "query": "inovação da Apple",
    "credentials": {...}
  }'
```

## Verificando Disponibilidade

Antes de aplicar um preset, você pode verificar se ele está disponível:

```python
from verba_extensions.plugins.reranker import RerankerPresets

reranker = RerankerPlugin()
availability = RerankerPresets.check_preset_availability("max_quality", reranker)

if availability["available"]:
    print("Preset disponível!")
    reranker.apply_preset("max_quality")
else:
    print(f"Preset não disponível: {availability['reason']}")
    print(f"Faltam: {availability['missing_requirements']}")
```

## Troubleshooting

### Preset não disponível

**Problema:** Preset mostra como "não disponível" no frontend.

**Soluções:**
1. Verifique se os requisitos estão instalados/configurados:
   - Para "max_quality": `pip install haystack-ai` e configure `CONTEXTUAL_API_KEY`
   - Para "local_only": `pip install haystack-ai`
   - Para "production": Configure `CONTEXTUAL_API_KEY`

2. Verifique as variáveis de ambiente:
   ```bash
   echo $CONTEXTUAL_API_KEY
   echo $COHERE_API_KEY
   ```

3. Reinicie o servidor após instalar dependências ou configurar variáveis.

### Preset aplicado mas não funciona

**Problema:** Preset foi aplicado mas o reranking não está usando a configuração.

**Soluções:**
1. Verifique se o preset foi salvo no RAG config
2. Verifique se o retriever está usando o Entity-Aware Retriever
3. Verifique os logs para erros de reranking

### Auto-seleção sempre escolhe o mesmo preset

**Problema:** Auto-seleção sempre retorna "production" mesmo com outros recursos disponíveis.

**Soluções:**
1. Verifique se os recursos estão realmente disponíveis (Haystack instalado, API keys configuradas)
2. Ajuste os parâmetros de `select_optimal_preset` se necessário:
   ```python
   preset = reranker.select_optimal_preset(
       query="query complexa",
       has_api_keys=True,
       latency_budget=3.0  # Aumenta orçamento de latência
   )
   ```

## Recomendações

### Para Produção

- Use **Production** preset para balanceamento ideal
- Configure `CONTEXTUAL_API_KEY` para melhor qualidade
- Monitore latência e ajuste se necessário

### Para Desenvolvimento

- Use **Local Only** para evitar custos de API
- Use **Custom** para testar configurações específicas

### Para Máxima Qualidade

- Use **Max Quality** quando qualidade é crítica
- Garanta que Haystack e ContextualAI estão disponíveis
- Aceite latência maior (~1.5s)

## Próximos Passos

- Veja [RERANKER_README.md](../plugins/RERANKER_README.md) para detalhes completos sobre providers
- Veja [ANALISE_CONFIG_RERANKER.md](./ANALISE_CONFIG_RERANKER.md) para análise de configurações
- Veja [TOP_K_PRE_POS_RERANK.md](./TOP_K_PRE_POS_RERANK.md) para entender Top K

