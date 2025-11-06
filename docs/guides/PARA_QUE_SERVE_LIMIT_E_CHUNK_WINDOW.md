# Para que servem Limit e Chunk Window?

## Resumo Rápido

- **Limit (Limit/Sensitivity)**: Controla quantos chunks são **recuperados do Weaviate** na busca inicial
- **Chunk Window**: Adiciona chunks **adjacentes** aos chunks recuperados para dar mais contexto
- **Reranker Top K**: Controla quantos chunks são retornados **após o reranking**

## 1. Limit (Limit/Sensitivity) - Busca Inicial

### O que faz?
Controla quantos chunks são **recuperados do banco de dados (Weaviate)** na busca inicial.

### Como funciona?

#### **Autocut Mode** (Recomendado)
- O Weaviate decide automaticamente quantos chunks retornar baseado na **relevância**
- `Limit/Sensitivity` funciona como **sensibilidade**:
  - **Valor baixo (1-2)**: Mais restritivo → retorna apenas chunks muito relevantes (pode retornar 1-3 chunks)
  - **Valor alto (5-10)**: Menos restritivo → retorna mais chunks mesmo com relevância menor (pode retornar 5-15 chunks)
- **Exemplo**: Com `Limit/Sensitivity=1` e `Autocut`, o Weaviate pode retornar 1-5 chunks dependendo da relevância

#### **Fixed Mode**
- Retorna **exatamente** o número especificado em `Limit/Sensitivity`
- **Exemplo**: Com `Limit/Sensitivity=5` e `Fixed`, sempre retorna exatamente 5 chunks

### Por que é importante?
- **Limita o custo**: Menos chunks = menos processamento
- **Foca na relevância**: Com Autocut, só retorna chunks realmente relevantes
- **É o "filtro inicial"**: Todos os chunks que vêm depois dependem do que foi recuperado aqui

## 2. Chunk Window - Contexto Adjacente

### O que faz?
Adiciona chunks **adjacentes** (antes e depois) aos chunks recuperados para dar mais contexto.

### Como funciona?

```
Documento original:
[Chunk 1] [Chunk 2] [Chunk 3] [Chunk 4] [Chunk 5] [Chunk 6] [Chunk 7]

Busca inicial recupera: Chunk 3 (relevante)

Com Chunk Window = 1:
- Chunk 2 (antes)
- Chunk 3 (recuperado)
- Chunk 4 (depois)

Com Chunk Window = 2:
- Chunk 1 (2 antes)
- Chunk 2 (1 antes)
- Chunk 3 (recuperado)
- Chunk 4 (1 depois)
- Chunk 5 (2 depois)
```

### Por que é útil?
- **Contexto completo**: Chunks relevantes podem estar no meio de uma seção
- **Evita fragmentação**: Garante que o LLM veja o contexto completo
- **Não aumenta busca**: Não precisa buscar mais chunks do Weaviate, apenas pega os adjacentes

### Limitação
- Só funciona se os chunks adjacentes **já existem no documento**
- Não adiciona contexto de **outros documentos**

## 3. Reranker Top K - Pós-Reranking

### O que faz?
Controla quantos chunks são retornados **após o reranking**.

### Como funciona?
1. Busca inicial recupera N chunks (controlado por `Limit`)
2. Chunk Window adiciona chunks adjacentes (se configurado)
3. Reranker reordena todos os chunks por relevância
4. Reranker Top K limita quantos chunks são retornados

### Por que é importante?
- **Qualidade sobre quantidade**: Reranker escolhe os melhores chunks
- **Limita o contexto final**: Evita enviar muitos chunks ao LLM
- **É o "filtro final"**: Última chance de controlar quantos chunks vão para o LLM

## Fluxo Completo

```
1. QUERY DO USUÁRIO
   ↓
2. BUSCA INICIAL (Weaviate)
   ├─ Limit Mode: Autocut/Fixed
   ├─ Limit/Sensitivity: 1-10
   └─ Retorna: N chunks (ex: 5 chunks)
   ↓
3. CHUNK WINDOW (se configurado)
   ├─ Chunk Window: 1-10
   └─ Adiciona chunks adjacentes (ex: 5 chunks → 7 chunks)
   ↓
4. RERANKING
   ├─ Recebe: M chunks (N + adjacentes)
   ├─ Reordena por relevância
   ├─ Reranker Top K: 5
   └─ Retorna: min(M, Reranker Top K) chunks (ex: 5 chunks)
   ↓
5. CONTEXTO PARA LLM
   └─ 5 chunks finais enviados ao LLM
```

## Exemplo Prático

### Configuração:
- **Limit Mode**: Autocut
- **Limit/Sensitivity**: 2
- **Chunk Window**: 1
- **Reranker Top K**: 5

### O que acontece:

1. **Busca inicial**: Weaviate retorna 3 chunks relevantes (Autocut com sensitivity=2)
2. **Chunk Window**: Adiciona chunks adjacentes → 3 chunks viram 5 chunks (cada um tem 1 antes + 1 depois)
3. **Reranking**: Reordena os 5 chunks por relevância
4. **Reranker Top K**: Retorna os 5 melhores chunks (todos, porque temos 5 e top_k=5)
5. **LLM recebe**: 5 chunks finais

## Quando Aumentar Cada Parâmetro?

### Aumentar Limit/Sensitivity quando:
- ✅ Queries retornam poucos chunks
- ✅ Precisa de mais opções para o reranker escolher
- ✅ Documentos têm muitos chunks relevantes

### Aumentar Chunk Window quando:
- ✅ Chunks recuperados estão fragmentados
- ✅ Precisa de mais contexto ao redor dos chunks relevantes
- ✅ Documentos têm estrutura sequencial (capítulos, seções)

### Aumentar Reranker Top K quando:
- ✅ Precisa de mais contexto para o LLM
- ✅ Queries são complexas e precisam de múltiplos chunks
- ✅ Documentos têm informações distribuídas

## Recomendações

### Para Queries Gerais
- **Limit Mode**: Autocut
- **Limit/Sensitivity**: 3-5
- **Chunk Window**: 1-2
- **Reranker Top K**: 5-10

### Para Queries Específicas (com entidades)
- **Limit Mode**: Fixed
- **Limit/Sensitivity**: 5-10
- **Chunk Window**: 0-1
- **Reranker Top K**: 5-10

### Para Queries que Precisam de Contexto Completo
- **Limit Mode**: Autocut
- **Limit/Sensitivity**: 2-3
- **Chunk Window**: 2-3
- **Reranker Top K**: 5-10

## Resumo Visual

```
┌─────────────────────────────────────────────────────────┐
│ LIMIT (Limit/Sensitivity)                               │
│ ─────────────────────────────────────────────────────── │
│ Controla: Quantos chunks são RECUPERADOS do Weaviate    │
│ Quando usar: Para controlar custo e foco inicial         │
│ Impacto: ALTO - afeta tudo que vem depois                │
└─────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ CHUNK WINDOW                                             │
│ ─────────────────────────────────────────────────────── │
│ Controla: Quantos chunks ADJACENTES são adicionados      │
│ Quando usar: Para dar contexto completo aos chunks      │
│ Impacto: MÉDIO - adiciona contexto sem buscar mais      │
└─────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ RERANKER TOP K                                           │
│ ─────────────────────────────────────────────────────── │
│ Controla: Quantos chunks são RETORNADOS após reranking   │
│ Quando usar: Para limitar contexto final ao LLM        │
│ Impacto: ALTO - afeta o que o LLM recebe                 │
└─────────────────────────────────────────────────────────┘
```

## Conclusão

- **Limit**: "Quantos chunks buscar do banco?"
- **Chunk Window**: "Quantos chunks adjacentes adicionar?"
- **Reranker Top K**: "Quantos chunks enviar ao LLM?"

Cada um tem um propósito diferente e trabalham juntos para otimizar a recuperação e o contexto enviado ao LLM.

