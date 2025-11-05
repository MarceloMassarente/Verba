# Como Configurar Quantidade de Chunks e Mix Semântico/Léxico

## Onde Configurar

### 1. Configuração no Retriever

Os parâmetros são configurados no **EntityAwareRetriever** (ou outros retrievers):

**Arquivo**: `verba_extensions/plugins/entity_aware_retriever.py` (linhas 71-94)

```python
self.config["Limit Mode"] = InputConfig(
    type="dropdown",
    value="Autocut",  # ← Modo padrão
    description="Method for limiting results",
    values=["Autocut", "Fixed"],
)

self.config["Limit/Sensitivity"] = InputConfig(
    type="number",
    value=1,  # ← Valor padrão
    description="Limit value or sensitivity",
    values=[],
)

self.config["Alpha"] = InputConfig(
    type="text",
    value="0.6",  # ← Valor padrão (60% semântico, 40% léxico)
    description="Hybrid search alpha (0.0=keyword, 1.0=vector)",
    values=[],
)
```

### 2. Como Funciona na Busca

**Arquivo**: `goldenverba/components/managers.py` (linhas 1095-1226)

```python
async def hybrid_chunks_with_filter(
    self,
    client: WeaviateAsyncClient,
    embedder: str,
    query: str,
    vector: list[float],
    limit_mode: str,      # ← "Autocut" ou "Fixed"
    limit: int,            # ← Número de chunks ou sensibilidade
    filters: Filter = None,
    alpha: float = 0.5,    # ← Mix semântico/léxico
):
    # ...
    
    if limit_mode == "Autocut":
        chunks = await embedder_collection.query.hybrid(
            query=query,
            vector=vector,
            alpha=alpha,           # ← Mix configurado aqui
            auto_limit=limit,      # ← Sensibilidade (1-10)
            filters=apply_filters,
        )
    else:  # Fixed
        chunks = await embedder_collection.query.hybrid(
            query=query,
            vector=vector,
            alpha=alpha,           # ← Mix configurado aqui
            limit=limit,           # ← Número fixo de chunks
            filters=apply_filters,
        )
```

## Parâmetros Detalhados

### 1. Limit Mode (Modo de Limitação)

#### **"Autocut"** (Padrão)
- **O que faz**: Weaviate decide automaticamente quantos chunks retornar
- **Como funciona**: Usa `auto_limit` que é uma sensibilidade (1-10)
  - `auto_limit=1`: Mais conservador (menos chunks, mais relevantes)
  - `auto_limit=10`: Mais agressivo (mais chunks, pode incluir menos relevantes)
- **Quando usar**: Quando você quer que o sistema encontre automaticamente o "corte natural" de relevância

#### **"Fixed"**
- **O que faz**: Retorna um número fixo de chunks
- **Como funciona**: Usa `limit` como número exato de chunks
  - `limit=5`: Retorna exatamente 5 chunks
  - `limit=20`: Retorna exatamente 20 chunks
- **Quando usar**: Quando você precisa de um número específico de chunks

### 2. Limit/Sensitivity (Valor do Limit)

#### **Com Autocut**
- Valor: 1-10 (sensibilidade)
- Padrão: `1`
- Significado:
  - `1`: Muito conservador, apenas chunks muito relevantes
  - `5`: Moderado, balance entre quantidade e relevância
  - `10`: Agressivo, mais chunks incluídos

#### **Com Fixed**
- Valor: Número inteiro (quantidade de chunks)
- Padrão: `1`
- Exemplos:
  - `5`: Retorna 5 chunks
  - `10`: Retorna 10 chunks
  - `20`: Retorna 20 chunks

### 3. Alpha (Mix Semântico/Léxico)

**Range**: 0.0 a 1.0
**Padrão**: `0.6`

#### **Como Funciona**

```
alpha = 0.0  → 100% Busca Léxica (BM25/Keyword)
              → Busca por palavras exatas na query
              → Melhor para: termos específicos, nomes próprios

alpha = 0.5  → 50% Semântico + 50% Léxico
              → Balance entre significado e palavras exatas
              → Melhor para: queries gerais

alpha = 0.6  → 60% Semântico + 40% Léxico (PADRÃO)
              → Prefere significado, mas considera palavras
              → Melhor para: maioria dos casos

alpha = 1.0  → 100% Busca Semântica (Vector)
              → Busca apenas por significado
              → Melhor para: conceitos abstratos, sinônimos
```

#### **Fórmula de Combinação**

```
score_final = (alpha × score_semantico) + ((1 - alpha) × score_lexico)
```

**Exemplos**:
- `alpha=0.6`: `score = 0.6×semantic + 0.4×lexical`
- `alpha=0.0`: `score = 0.0×semantic + 1.0×lexical = lexical` (apenas BM25)
- `alpha=1.0`: `score = 1.0×semantic + 0.0×lexical = semantic` (apenas vector)

## Como Ajustar Dinamicamente

### 1. Via QueryBuilder (Recomendado)

O QueryBuilder pode ajustar o alpha automaticamente baseado na query:

```python
# QueryBuilder analisa a query e sugere alpha
strategy = await builder.build_query(
    user_query="inovação e tecnologia",
    ...
)

# QueryBuilder pode sugerir:
# - alpha=0.8 para queries conceituais
# - alpha=0.4 para queries com termos específicos
```

**Arquivo**: `verba_extensions/plugins/query_builder.py`

### 2. Via Configuração do Retriever

No frontend ou configuração, você pode ajustar:

```python
# No EntityAwareRetriever
config = {
    "Limit Mode": "Fixed",        # ou "Autocut"
    "Limit/Sensitivity": 10,      # Número fixo ou sensibilidade
    "Alpha": "0.7",               # Mix semântico/léxico
}
```

### 3. Via API

```python
# Chamada à API
POST /api/query
{
    "query": "inovação",
    "retriever_config": {
        "limit_mode": "Fixed",
        "limit": 10,
        "alpha": 0.7
    }
}
```

## Exemplos Práticos

### Exemplo 1: Busca Específica (Termos Exatos)

```python
# Query: "Apple iPhone 15"
# Queremos: Termos exatos, não sinônimos
config = {
    "Limit Mode": "Fixed",
    "Limit/Sensitivity": 5,      # Apenas 5 chunks
    "Alpha": "0.3",               # 30% semântico, 70% léxico
}
```

**Resultado**: Poucos chunks, prioriza menções exatas de "Apple iPhone 15"

### Exemplo 2: Busca Conceitual (Sinônimos)

```python
# Query: "inovação e criatividade"
# Queremos: Conceitos, não palavras exatas
config = {
    "Limit Mode": "Autocut",
    "Limit/Sensitivity": 5,      # Sensibilidade moderada
    "Alpha": "0.8",               # 80% semântico, 20% léxico
}
```

**Resultado**: Múltiplos chunks, captura sinônimos e conceitos relacionados

### Exemplo 3: Busca Balanceada (Padrão)

```python
# Query: "Apple e inovação"
# Queremos: Balance entre entidade específica e conceito
config = {
    "Limit Mode": "Autocut",
    "Limit/Sensitivity": 3,      # Sensibilidade conservadora
    "Alpha": "0.6",               # 60% semântico, 40% léxico (padrão)
}
```

**Resultado**: Chunks relevantes sobre Apple que mencionam inovação

### Exemplo 4: Busca Abrangente (Muitos Chunks)

```python
# Query: "tecnologia"
# Queremos: Todos chunks relevantes
config = {
    "Limit Mode": "Fixed",
    "Limit/Sensitivity": 20,     # 20 chunks
    "Alpha": "0.7",               # 70% semântico
}
```

**Resultado**: 20 chunks mais relevantes sobre tecnologia

## Como o Sistema Decide Automaticamente

### QueryBuilder com Auto-Detecção

O QueryBuilder pode ajustar automaticamente baseado na query:

```python
# Query: "descreva Apple"
# → QueryBuilder detecta: query descritiva/conceitual
# → Sugere: alpha=0.7 (mais semântico)

# Query: "Apple iPhone preço"
# → QueryBuilder detecta: termos específicos
# → Sugere: alpha=0.4 (mais léxico)
```

**Arquivo**: `verba_extensions/plugins/query_builder.py` (linhas 230-238)

## Locais Importantes no Código

### 1. Definição dos Parâmetros

```python
# verba_extensions/plugins/entity_aware_retriever.py
# Linhas 71-94: Configuração dos InputConfigs
# - Limit Mode (linha 71)
# - Limit/Sensitivity (linha 77)
# - Alpha (linha 89)
```

### 2. Uso dos Parâmetros

```python
# verba_extensions/plugins/entity_aware_retriever.py
# Linha 165: limit_mode = config["Limit Mode"].value
# Linha 166: limit = int(config["Limit/Sensitivity"].value)
# Linha 168: alpha = float(config["Alpha"].value)
```

### 3. Execução da Busca

```python
# goldenverba/components/managers.py
# Linhas 1095-1146: hybrid_chunks() - agora aceita alpha como parâmetro
# Linhas 1147-1226: hybrid_chunks_with_filter() - aceita alpha como parâmetro
# Linhas 1208-1225: Lógica de Autocut vs Fixed
```

**Nota**: Ambos os métodos agora respeitam o parâmetro `alpha` configurado. Anteriormente, `hybrid_chunks()` tinha alpha hardcoded como 0.5, mas foi corrigido para aceitar o parâmetro.

## Resumo

| Parâmetro | Onde Configurar | Padrão | Range | Uso |
|-----------|----------------|--------|-------|-----|
| **Limit Mode** | `entity_aware_retriever.py:71` | `"Autocut"` | `["Autocut", "Fixed"]` | Como limitar resultados |
| **Limit/Sensitivity** | `entity_aware_retriever.py:77` | `1` | `1-10` (Autocut) ou `1-N` (Fixed) | Quantos chunks retornar |
| **Alpha** | `entity_aware_retriever.py:89` | `"0.6"` | `"0.0"` - `"1.0"` | Mix semântico/léxico |

## Recomendações

### Para Busca com Entidades (Entity-Aware)
- **Limit Mode**: `"Autocut"` (deixa sistema decidir)
- **Limit/Sensitivity**: `3-5` (sensibilidade moderada)
- **Alpha**: `0.6` (padrão, balance entre semântica e palavras)

### Para Busca Genérica
- **Limit Mode**: `"Fixed"` (controle preciso)
- **Limit/Sensitivity**: `10-20` (quantidade razoável)
- **Alpha**: `0.7` (mais semântico para capturar sinônimos)

### Para Busca Específica (Termos Exatos)
- **Limit Mode**: `"Fixed"` 
- **Limit/Sensitivity**: `5` (poucos chunks)
- **Alpha**: `0.3-0.4` (mais léxico, prioriza palavras exatas)

