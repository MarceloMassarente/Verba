# 🔍 Framework Detection System

## Visão Geral

O sistema de detecção de frameworks identifica automaticamente frameworks de negócio, empresas e setores em textos, permitindo filtros precisos e buscas semânticas melhoradas.

## Arquitetura

### Componentes Principais

1. **Framework Detector** (`verba_extensions/utils/framework_detector.py`)
   - Classe principal que detecta frameworks, empresas e setores
   - Usa Gliner (NER) quando disponível, com fallback para keyword matching
   - Carrega frameworks de arquivo JSON com aliases PT/EN

2. **Frameworks Database** (`verba_extensions/resources/frameworks.json`)
   - JSON com 71+ frameworks e seus aliases
   - Suporte a português e inglês
   - Categorização por área (Estratégia, Marketing, Operações, etc.)

3. **Script de Geração** (`scripts/generate_framework_aliases.py`)
   - Gera aliases automaticamente a partir do CSV
   - Cria variações PT/EN para cada framework

## Como Funciona

### 1. Detecção Durante Chunking

```python
from verba_extensions.utils.framework_detector import get_framework_detector

detector = get_framework_detector()
result = await detector.detect_frameworks(texto_do_chunk)

# Retorna:
# {
#   "frameworks": ["SWOT Analysis", "Porter's Five Forces"],
#   "companies": ["Apple", "Microsoft"],
#   "sectors": ["technology", "retail"],
#   "confidence": 0.85
# }
```

### 2. Detecção Durante Busca

O `EntityAwareRetriever` detecta automaticamente frameworks mencionados na query:

```python
# Query: "descreva o que se fala sobre SWOT e Porter"
# Detecta: ["SWOT Analysis", "Porter's Five Forces"]
# Aplica filtro: WHERE frameworks CONTAINS ["SWOT Analysis", "Porter's Five Forces"]
```

### 3. Armazenamento no Weaviate

Frameworks detectados são armazenados como propriedades:

```python
{
  "frameworks": ["SWOT Analysis", "Porter's Five Forces"],
  "companies": ["Apple"],
  "sectors": ["technology"],
  "framework_confidence": 0.85
}
```

## Frameworks Suportados

### Total: 71+ Frameworks

Categorias:
- **Estratégia Corporativa**: GE-McKinsey Matrix, Three Horizons, Founder's Mentality, etc.
- **Cliente & Marketing**: NPS, Consumer Decision Journey, Elements of Value, etc.
- **Organização & Pessoas**: 7-S Framework, OHI, RAPID, Talent to Value, etc.
- **Operações & Performance**: ZBR, ZBB, Lean Management, Economic Profit, etc.
- **Inovação & Tecnologia**: Engine 1 vs Engine 2, Rule of 40, Digital Quotient, etc.
- **Metodologia & Cognição**: MECE, Pyramid Principle, SCQA, 80/20 Rule, etc.
- **Ferramentas Clássicas**: SWOT, Porter's Five Forces, BCG Matrix, PESTEL, etc.

### Aliases PT/EN

Cada framework tem múltiplos aliases para detecção em ambos os idiomas:

**Exemplo: Porter's Five Forces**
- EN: "Porter", "Five Forces", "5 Forces", "Porter Forces", "Porter's Five Forces"
- PT: "5 Forças", "Cinco Forças", "Forças de Porter"

**Exemplo: SWOT Analysis**
- EN: "SWOT", "SWOT Analysis"
- PT: "Análise SWOT"

**Exemplo: Balanced Scorecard**
- EN: "Balanced Scorecard", "BSC", "Scorecard"
- PT: "Indicadores Balanceados"

## Estrutura de Arquivos

```
verba_extensions/
├── utils/
│   └── framework_detector.py          # Detector principal
├── resources/
│   └── frameworks.json                # Database de frameworks (71+ frameworks, 336+ aliases)
└── ...

scripts/
└── generate_framework_aliases.py       # Script para gerar aliases do CSV

frameworks.csv                          # Fonte de dados (70 frameworks)
```

## Como Adicionar Novos Frameworks

### Opção 1: Via CSV (Recomendado)

1. Edite `frameworks.csv`:
```csv
Macro Área;Nome do Framework;Elementos Principais
1. Estratégia Corporativa;OKR;Objetivos e Resultados-Chave para alinhamento estratégico
```

2. Execute o script:
```bash
python scripts/generate_framework_aliases.py
```

3. O JSON será atualizado automaticamente com aliases PT/EN

### Opção 2: Editar JSON Diretamente

Edite `verba_extensions/resources/frameworks.json`:

```json
{
  "name": "OKR",
  "aliases": ["OKR", "Objectives and Key Results", "Objetivos e Resultados-Chave"],
  "category": "1. Estratégia Corporativa",
  "description": "Objetivos e Resultados-Chave para alinhamento estratégico"
}
```

## Uso Programático

### Detectar Frameworks em Texto

```python
from verba_extensions.utils.framework_detector import get_framework_detector

detector = get_framework_detector()

# Texto em português
result = await detector.detect_frameworks(
    "Aplicamos SWOT e as 5 Forças de Porter na análise"
)
# result["frameworks"] = ["SWOT Analysis", "Porter's Five Forces"]

# Texto em inglês
result = await detector.detect_frameworks(
    "We used SWOT analysis and Porter's Five Forces"
)
# result["frameworks"] = ["SWOT Analysis", "Porter's Five Forces"]
```

### Listar Frameworks Disponíveis

```python
detector = get_framework_detector()

# Listar todos os frameworks
for name, data in detector.frameworks_by_name.items():
    print(f"{name}: {data['category']}")
    print(f"  Aliases: {', '.join(data['aliases'][:5])}...")
```

## Integração com EntityAwareRetriever

O `EntityAwareRetriever` usa automaticamente o detector:

```python
# Query: "o que se fala sobre SWOT e Apple?"
# 
# 1. Detecta frameworks: ["SWOT Analysis"]
# 2. Detecta empresas: ["Apple"]
# 3. Aplica filtros:
#    WHERE frameworks CONTAINS ["SWOT Analysis"]
#    AND companies CONTAINS ["Apple"]
# 4. Busca semântica dentro dos resultados filtrados
```

## Modelos Utilizados

### Gliner (Opcional)
- Modelo: `urchade/gliner_small-v2.1`
- Uso: Detecção de frameworks via NER
- Labels: `["framework", "business model", "strategic framework"]`
- Fallback: Keyword matching se não disponível

### spaCy (Opcional)
- Modelos: `pt_core_news_sm` ou `en_core_web_sm`
- Uso: Detecção de empresas (entidades ORG/PERSON)
- Fallback: Keyword matching se não disponível

## Performance

- **Frameworks carregados**: 71
- **Aliases disponíveis**: 336+
- **Média de aliases por framework**: 7.3
- **Taxa de detecção**: ~83% (testes automatizados)
- **Suporte a idiomas**: Português e Inglês

## Testes

Execute os testes:

```bash
python scripts/test_framework_detector.py
```

Testes incluem:
- Detecção em português
- Detecção em inglês
- Múltiplos frameworks
- Abreviações (NPS, BSC, etc.)
- Aliases variados

## Troubleshooting

### Frameworks não detectados

1. Verifique se o framework está no JSON:
```bash
grep -i "nome_do_framework" verba_extensions/resources/frameworks.json
```

2. Verifique se os aliases estão corretos:
```python
detector = get_framework_detector()
print(detector.frameworks_by_name.get("Nome do Framework", {}).get("aliases", []))
```

3. Adicione aliases se necessário (edite JSON ou CSV)

### JSON não carregado

O sistema usa fallback para lista hardcoded se JSON não for encontrado. Verifique:
- Caminho: `verba_extensions/resources/frameworks.json`
- Encoding: UTF-8
- Formato JSON válido

## Referências

- **Gliner**: https://github.com/urchade/gliner
- **spaCy**: https://spacy.io/
- **Documentação Weaviate**: https://weaviate.io/developers/weaviate

## Changelog

### 2025-01-XX
- ✅ Integração de 71 frameworks do CSV
- ✅ Geração automática de aliases PT/EN
- ✅ Suporte a 336+ aliases
- ✅ Detecção melhorada com Gliner + keyword matching
- ✅ Testes automatizados

