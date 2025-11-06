# Entity-Semantic Chunking - Explicação Detalhada

## 🎯 O Que É?

O **Entity-Semantic Chunking** é uma estratégia híbrida de divisão de documentos que combina **três técnicas** para criar chunks de alta qualidade:

1. **Section-Aware** (Delimitação por Seções)
2. **Entity Guardrails** (Proteção de Entidades)
3. **Semantic Breakpoints** (Quebras Semânticas)

---

## 📊 Comparação Visual: Problema vs Solução

### ❌ Problema: Chunking Simples (Token/Sentence)

```
Documento: Artigo sobre 3 empresas

[Chunk 1: 500 tokens]
"A Empresa A desenvolve soluções inovadoras. 
A Empresa B também tem tecnologia avançada.
A Empresa C está crescendo rapidamente."

[Chunk 2: 500 tokens]
"A Empresa A lançou novo produto.
A Empresa B expandiu para novos mercados.
A Empresa C recebeu investimento."
```

**Problemas:**
- ❌ Chunks misturam informações de múltiplas empresas
- ❌ Busca por "Empresa A e inovação" pode retornar chunks com Empresa B/C
- ❌ Entidades podem ser cortadas no meio ("Apple Inc" → "Apple" e "Inc")
- ❌ Quebras arbitrárias ignoram contexto semântico

### ✅ Solução: Entity-Semantic Chunking

```
Documento: Artigo sobre 3 empresas

[Seção 1: "Empresa A - Tecnologia"]
  [Chunk 1.1: Semântico]
  "A Empresa A desenvolve soluções inovadoras..."
  
  [Chunk 1.2: Semântico]
  "A Empresa A lançou novo produto..."

[Seção 2: "Empresa B - Expansão"]
  [Chunk 2.1: Semântico]
  "A Empresa B também tem tecnologia avançada..."
  
  [Chunk 2.2: Semântico]
  "A Empresa B expandiu para novos mercados..."

[Seção 3: "Empresa C - Crescimento"]
  [Chunk 3.1: Semântico]
  "A Empresa C está crescendo rapidamente..."
  
  [Chunk 3.2: Semântico]
  "A Empresa C recebeu investimento..."
```

**Benefícios:**
- ✅ Chunks delimitados por seção (sem contaminação entre empresas)
- ✅ Entidades preservadas (não cortadas no meio)
- ✅ Quebras respeitam similaridade semântica
- ✅ Busca mais precisa (filtra por seção/entidade)

---

## 🔧 Como Funciona: Os 3 Componentes

### 1️⃣ Section-Aware (Delimitação por Seções)

**Objetivo:** Evitar contaminação entre assuntos/empresas diferentes.

**Como funciona:**
```python
# Detecta seções automaticamente
sections = detect_sections(text)
# Retorna: [
#   {"title": "Empresa A", "start": 0, "end": 500},
#   {"title": "Empresa B", "start": 500, "end": 1000},
#   {"title": "Empresa C", "start": 1000, "end": 1500}
# ]

# Processa cada seção separadamente
for section in sections:
    sentences = filter_sentences_in_section(all_sentences, section)
    # Chunking acontece DENTRO da seção
```

**Heurísticas de detecção:**
- Quebras duplas/triplas de linha (`\n\n\n`)
- Linhas curtas que parecem títulos (< 100 chars, sem ponto final)
- Padrões markdown (`# Título`, `## Subtítulo`)
- Linhas numeradas (`1. Título`, `1) Título`)

**Exemplo:**
```
Texto:
"EMPRESA A - TECNOLOGIA

A empresa desenvolve soluções inovadoras..."

↓ detect_sections()

Seções:
[
  {title: "EMPRESA A - TECNOLOGIA", start: 0, end: 200},
  {title: "EMPRESA B - EXPANSÃO", start: 200, end: 400}
]
```

---

### 2️⃣ Entity Guardrails (Proteção de Entidades)

**Objetivo:** Evitar cortar entidades (nomes próprios, empresas) no meio.

**Como funciona:**
```python
# 1. ETL Pré-Chunking extrai entity_spans ANTES do chunking
entity_spans = [
    {"text": "Apple Inc", "start": 100, "end": 109, "entity_id": "Q312"},
    {"text": "Steve Jobs", "start": 250, "end": 260, "entity_id": "Q2283"}
]

# 2. Quando breakpoint semântico propõe cortar entidade:
proposed_boundary = 105  # Entre "Apple" e "Inc"

# 3. Verifica se cruza entidade
if entity_crosses_boundary(entity_spans, proposed_boundary):
    # 4. Ajusta boundary para não cortar
    adjusted_boundary = adjust_boundary_with_entities(
        sentences, proposed_boundary, entity_spans
    )
    # Tenta avançar 1 sentença, se não funcionar, recua 1 sentença
```

**Algoritmo de ajuste:**
```
1. Boundary proposto: posição 105 (meio de "Apple Inc")
   ↓
2. Detecta que cruza entidade "Apple Inc" (start: 100, end: 109)
   ↓
3. Tenta avançar 1 sentença → posição 120
   - Verifica: não cruza entidade? ✅
   - Usa: boundary = 120
   ↓
4. Se não funcionar, tenta recuar 1 sentença → posição 90
   - Verifica: não cruza entidade? ✅
   - Usa: boundary = 90
```

**Exemplo visual:**
```
Texto: "...trabalhou na Apple Inc durante 10 anos..."

❌ Boundary ruim (corta entidade):
Chunk 1: "...trabalhou na Apple"
Chunk 2: "Inc durante 10 anos..."

✅ Boundary ajustado (preserva entidade):
Chunk 1: "...trabalhou na Apple Inc"
Chunk 2: "durante 10 anos..."
```

---

### 3️⃣ Semantic Breakpoints (Quebras Semânticas)

**Objetivo:** Quebrar chunks em pontos de mudança de assunto (dentro da seção).

**Como funciona:**
```python
# 1. Gera embeddings de sentenças adjacentes
embeddings = [
    embed("A empresa desenvolve soluções inovadoras."),  # [0.1, 0.2, ...]
    embed("A empresa lançou novo produto."),              # [0.3, 0.4, ...]
    embed("O mercado está em expansão."),                # [0.8, 0.9, ...] ← MUDANÇA!
]

# 2. Calcula similaridade entre sentenças adjacentes
similarities = [
    cosine_similarity(embeddings[0], embeddings[1]),  # 0.85 (similar)
    cosine_similarity(embeddings[1], embeddings[2]),  # 0.35 (diferente!) ← BREAKPOINT
]

# 3. Converte para distâncias
distances = [1.0 - sim for sim in similarities]  # [0.15, 0.65]

# 4. Define threshold pelo percentil (ex: 80%)
threshold = percentile(distances, 80)  # 0.65

# 5. Quebra onde distância > threshold
breakpoints = [i for i, d in enumerate(distances) if d >= threshold]
# Resultado: [1] → quebra entre sentença 1 e 2
```

**Exemplo visual:**
```
Sentenças:
1. "A empresa desenvolve soluções inovadoras."     [embedding: similar]
2. "A empresa lançou novo produto."                [embedding: similar]
3. "O mercado está em expansão."                   [embedding: DIFERENTE] ← BREAKPOINT
4. "Investidores estão otimistas."                [embedding: similar]

Similaridades:
- Sent 1 ↔ Sent 2: 0.85 (alta) → MESMO CHUNK
- Sent 2 ↔ Sent 3: 0.35 (baixa) → BREAKPOINT! ✅
- Sent 3 ↔ Sent 4: 0.82 (alta) → MESMO CHUNK

Chunks resultantes:
[Chunk 1: Sent 1-2] "A empresa desenvolve... lançou novo produto."
[Chunk 2: Sent 3-4] "O mercado está... Investidores estão otimistas."
```

**Configuração:**
- **Breakpoint Percentile Threshold** (padrão: 80)
  - Menor (ex: 70) → mais breakpoints → chunks menores
  - Maior (ex: 90) → menos breakpoints → chunks maiores

---

## 🔄 Fluxo Completo de Processamento

```
┌─────────────────────────────────────────────────────────────┐
│ 1. DOCUMENTO COMPLETO                                       │
│    "Artigo sobre 3 empresas..."                            │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. ETL PRÉ-CHUNKING (se enable_etl=True)                   │
│    - Extrai entity_spans do documento                        │
│    - Armazena em document.meta["entity_spans"]             │
│    Resultado: [                                             │
│      {text: "Apple Inc", start: 100, end: 109},            │
│      {text: "Steve Jobs", start: 250, end: 260}            │
│    ]                                                        │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. DETECÇÃO DE SEÇÕES                                       │
│    sections = detect_sections(text)                         │
│    Resultado: [                                             │
│      {title: "Empresa A", start: 0, end: 500},             │
│      {title: "Empresa B", start: 500, end: 1000}           │
│    ]                                                        │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. PARA CADA SEÇÃO:                                         │
│                                                              │
│    a) Filtra sentenças dentro da seção                     │
│       sentences = filter_sentences_in_section(...)          │
│                                                              │
│    b) Gera embeddings das sentenças                          │
│       embeddings = await embedder.vectorize(sentences)       │
│                                                              │
│    c) Calcula breakpoints semânticos                        │
│       - Similaridade entre sentenças adjacentes              │
│       - Threshold pelo percentil                            │
│       - Define breakpoints onde distância > threshold       │
│                                                              │
│    d) Ajusta breakpoints para não cortar entidades          │
│       - Verifica se breakpoint cruza entity_spans           │
│       - Ajusta avançando/recuando sentenças                  │
│                                                              │
│    e) Aplica cap por tamanho máximo (fallback)               │
│       - Se chunk > max_sentences_per_chunk, quebra           │
│                                                              │
│    f) Cria chunks respeitando:                              │
│       - Limites de seção                                    │
│       - Guard-rails de entidade                             │
│       - Breakpoints semânticos                              │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. CHUNKS FINAIS                                            │
│    [                                                         │
│      Chunk(id=0, section="Empresa A", content="..."),       │
│      Chunk(id=1, section="Empresa A", content="..."),       │
│      Chunk(id=2, section="Empresa B", content="..."),       │
│      ...                                                     │
│    ]                                                        │
└─────────────────────────────────────────────────────────────┘
```

---

## ⚙️ Configuração

### Parâmetros Disponíveis

| Parâmetro | Tipo | Padrão | Descrição |
|-----------|------|--------|-----------|
| **Breakpoint Percentile Threshold** | number | 80 | Percentil do drop de similaridade para split (menor → mais splits) |
| **Max Sentences Per Chunk** | number | 20 | Máximo de sentenças por chunk (fallback/capping) |
| **Overlap** | number | 0 | Overlap em sentenças entre chunks (opcional) |

### Recomendações

**Para chunks menores (mais precisos):**
```json
{
  "Breakpoint Percentile Threshold": 75,
  "Max Sentences Per Chunk": 15,
  "Overlap": 0
}
```

**Para chunks maiores (mais contexto):**
```json
{
  "Breakpoint Percentile Threshold": 85,
  "Max Sentences Per Chunk": 25,
  "Overlap": 2
}
```

**Para documentos com muitas entidades:**
```json
{
  "Breakpoint Percentile Threshold": 80,
  "Max Sentences Per Chunk": 20,
  "Overlap": 1  // Overlap ajuda a preservar contexto de entidades
}
```

---

## 🎯 Quando Usar?

### ✅ Ideal Para:

1. **Artigos/URLs com múltiplas empresas**
   - Análises de mercado
   - Comparações de produtos
   - Relatórios setoriais

2. **Documentos com estrutura hierárquica**
   - Títulos de seção claros
   - Múltiplos assuntos/entidades
   - Relatórios anuais

3. **Documentos onde contaminação é crítica**
   - Busca precisa por empresa + tema
   - Evitar resultados de empresas erradas

### ❌ Não Ideal Para:

1. **Documentos sem estrutura de seções**
   - Texto corrido sem títulos
   - Use: Section-Aware ou Semantic puro

2. **Documentos muito pequenos**
   - < 500 palavras
   - Overhead pode não valer a pena

3. **Documentos técnicos específicos**
   - Código, JSON, Markdown estruturado
   - Use: CodeChunker, JSONChunker, etc.

---

## 📈 Performance

### Benchmarks Esperados

| Métrica | Valor |
|---------|-------|
| **Tempo de chunking** (documento médio) | 2-5s |
| **Overhead vs Section-Aware** | +0.5-1s (cálculo de embeddings) |
| **Overhead vs Semantic** | +0.3-0.5s (detecção de seções + entity guardrails) |

**Nota:** Overhead é aceitável considerando os benefícios de evitar contaminação.

---

## 🔍 Exemplo Prático

### Documento de Entrada

```
EMPRESA A - TECNOLOGIA

A Empresa A desenvolve soluções inovadoras para o mercado.
A empresa lançou novo produto no último trimestre.
O produto recebeu feedback positivo dos clientes.

EMPRESA B - EXPANSÃO

A Empresa B expandiu para novos mercados internacionais.
A empresa também investiu em tecnologia.
Os resultados financeiros foram positivos.
```

### Processamento

1. **ETL Pré-Chunking:**
   - Extrai: `entity_spans = [{"text": "Empresa A", start: 0, end: 10}, ...]`

2. **Detecção de Seções:**
   - Seção 1: "EMPRESA A - TECNOLOGIA" (0-200 chars)
   - Seção 2: "EMPRESA B - EXPANSÃO" (200-400 chars)

3. **Para Seção 1:**
   - Sentenças: 3 sentenças
   - Embeddings: calculados
   - Breakpoints semânticos: nenhum (todas similares)
   - Entity guardrails: verifica, não precisa ajustar
   - **Chunk 1:** "A Empresa A desenvolve... feedback positivo dos clientes."

4. **Para Seção 2:**
   - Sentenças: 3 sentenças
   - Embeddings: calculados
   - Breakpoints semânticos: nenhum (todas similares)
   - Entity guardrails: verifica, não precisa ajustar
   - **Chunk 2:** "A Empresa B expandiu... resultados financeiros foram positivos."

### Resultado Final

```
Chunks:
- Chunk 0: "A Empresa A desenvolve... feedback positivo dos clientes." (Seção: EMPRESA A)
- Chunk 1: "A Empresa B expandiu... resultados financeiros foram positivos." (Seção: EMPRESA B)
```

**Benefício:** Busca por "Empresa A e tecnologia" retorna apenas Chunk 0, sem contaminação de Empresa B.

---

## 🆚 Comparação com Outros Chunkers

| Chunker | Seções | Entidades | Semântica | Contaminação | Qualidade |
|---------|--------|-----------|-----------|---------------|-----------|
| **Entity-Semantic** ⭐ | ✅ | ✅ | ✅ | ✅ Baixa | ⭐⭐⭐⭐⭐ |
| **Section-Aware** | ✅ | ✅ | ❌ | ✅ Baixa | ⭐⭐⭐⭐ |
| **Semantic** | ❌ | ❌ | ✅ | ⚠️ Média | ⭐⭐⭐⭐ |
| **Token/Sentence** | ❌ | ❌ | ❌ | ⚠️ Alta | ⭐⭐⭐ |

---

## 📚 Referências

- `verba_extensions/plugins/entity_semantic_chunker.py` - Implementação
- `docs/guides/ENTITY_SEMANTIC_CHUNKER.md` - Guia completo
- `docs/guides/COMO_ETL_FUNCIONA_POR_CHUNKER.md` - Integração com ETL
- `docs/guides/SOLUCAO_CONTAMINACAO_ENTRE_EMPRESAS.md` - Solução de contaminação

---

**Última atualização:** Janeiro 2025

