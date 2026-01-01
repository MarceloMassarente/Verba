# Verba API: Preset Parameter

## Visão Geral

O parâmetro `preset` permite aplicar configurações de busca predefinidas diretamente via API,
sem necessidade de acessar a UI. Isso possibilita controle **stateless** e **explícito** de
qual preset usar em cada requisição.

## Endpoint

```
POST /api/query
```

## Payload

```json
{
  "query": "frameworks de gestão estratégica",
  "RAG": { ... },
  "labels": [],
  "documentFilter": [],
  "credentials": {
    "deployment": "Custom",
    "url": "weaviate.railway.internal",
    "key": ""
  },
  "preset": "consulting_frameworks"  // ← NOVO (opcional)
}
```

## Parâmetro `preset`

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| preset | string | Não | Nome do preset a aplicar. Sobrescreve configurações do EntityAware Retriever |

### Presets Disponíveis

| Nome do Preset | Descrição | Uso Recomendado |
|----------------|-----------|-----------------|
| `consulting_frameworks` | Otimizado para frameworks (SWOT, Porter, BCG) | Buscas por metodologias |
| `company_research` | Prioriza documentos por empresa | Pesquisa de empresas específicas |
| `sector_analysis` | Foco em análises setoriais | Relatórios de mercado |
| `speed` | Prioriza velocidade | Demos e testes rápidos |
| `max_quality` | Máxima precisão | Buscas críticas |
| `balanced` | Equilíbrio velocidade/qualidade | Uso geral |
| `offline` | Sem APIs externas | Ambientes sem internet |

## Comportamento

1. **Com `preset`**: Backend carrega o preset especificado e aplica suas configurações ao EntityAware Retriever antes de executar a busca.

2. **Sem `preset`**: Usa a configuração do `RAG` passado no payload normalmente.

3. **Preset inválido**: Loga warning no backend e continua com a configuração original.

## Resposta

```json
{
  "error": "",
  "documents": [...],
  "context": "...",
  "preset_applied": "consulting_frameworks"  // Presente apenas se preset foi aplicado
}
```

## Exemplos

### Python

```python
import requests

response = requests.post(
    "https://verba-production-c347.up.railway.app/api/query",
    json={
        "query": "análise SWOT da empresa X",
        "RAG": rag_config,  # RAGConfig carregado anteriormente
        "labels": [],
        "documentFilter": [],
        "credentials": {
            "deployment": "Custom",
            "url": "weaviate.railway.internal",
            "key": ""
        },
        "preset": "consulting_frameworks"
    }
)

result = response.json()
print(f"Preset aplicado: {result.get('preset_applied', 'nenhum')}")
print(f"Documentos: {len(result['documents'])}")
```

### cURL

```bash
curl -X POST https://verba-production-c347.up.railway.app/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "empresas do setor de educação",
    "RAG": {...},
    "labels": [],
    "documentFilter": [],
    "credentials": {
      "deployment": "Custom",
      "url": "weaviate.railway.internal",
      "key": ""
    },
    "preset": "company_research"
  }'
```

## Log do Backend

Quando um preset é usado, o backend loga:

```
ℹ️ 🎯 Preset especificado: consulting_frameworks
✅ Preset 'consulting_frameworks' aplicado com sucesso
```

## Fluxo Interno

```
1. POST /api/query chega com preset="consulting_frameworks"
2. Backend verifica se preset foi especificado
3. Carrega preset da classe RerankerPresets
4. Aplica configurações ao EntityAware:
   - Alpha, Top K, Query Expansion, etc.
5. Muda retriever selecionado para "EntityAware"
6. Executa busca com config modificado
7. Retorna resultados com "preset_applied" na resposta
```

## Vantagens

- ✅ **Stateless**: Cada request especifica qual preset usar
- ✅ **Explícito**: Sabe-se exatamente qual configuração foi usada
- ✅ **Auditável**: Resposta indica qual preset foi aplicado
- ✅ **Flexível**: Pode variar preset por requisição
- ✅ **Robusto**: Não depende de estado salvo ou UI
