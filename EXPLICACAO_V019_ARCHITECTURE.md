# 🏗️ Arquitetura V019 - Explicação Completa

**Data:** 3 de Janeiro de 2025  
**Baseado em:** Análise do código em `verba_extensions/plugins/v019_markdown_reader.py`

---

## 🎯 O que é V019?

V019 é um **importer especializado para documentos ricos gerados por sistema de análise visual de slides** (consulting decks).

### Características Principais

✅ Processa **Markdown estruturado** com metadados ricos  
✅ **Um slide = uma seção H1** (# Slide X - Título)  
✅ Cada slide tem **metadados embarcados**:
- Frameworks detectados (BCG, SWOT, Porter, etc.)
- Stakeholders identificados
- Qualidade da ponte semântica (0.0-1.0)
- Posição no deck (opening, diagnostic, analysis, conclusion)
- Pattern genetics (componentes atômicos)
- Arquétipo visual (pyramid, matrix, flow)

✅ **Ativa automaticamente ETL A2** para enriquecimento adicional

---

## 📊 Arquitetura do V019

```
ENTRADA: Markdown com Estrutura V019
    ↓
┌─────────────────────────────────────────────────────────────┐
│  V019 Markdown Reader                                        │
│                                                               │
│  1. Decodifica base64 → conteúdo texto                       │
│  2. Extrai metadados por slide:                              │
│     - Divide em seções (H1 = Slide X)                        │
│     - Parse de metadata dentro de cada slide                 │
│     - Agrega frameworks/stakeholders globais                 │
│  3. Cria Document com:                                        │
│     - content: todo o markdown                               │
│     - meta: { slides_metadata[], frameworks[], ... }         │
│     - enable_etl: True (automático!)                         │
│                                                               │
│  SAÍDA: 1 Document com ALL slides + metadata rico            │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│  ETL PRE-CHUNKING (Automático - enable_etl=True)            │
│                                                               │
│  Extrai entidades do documento COMPLETO:                    │
│  - NER (Named Entity Recognition)                           │
│  - Armazena entity_spans em document.meta                   │
│  - Deduplicação e normalização                              │
│                                                               │
│  OBS: Aqui você poderia separar por slide, MAS VOCÊ ESCOLHE!
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│  CHUNKING (AQUI ESTÁ O PROBLEMA!)                           │
│                                                               │
│  ❓ Qual chunker? VOCÊ ESCOLHE LIVREMENTE NA UI:            │
│     - TokenChunker: Quebra por tokens                        │
│     - SentenceChunker: Quebra por sentenças                  │
│     - SemanticChunker: Quebra por similaridade              │
│     - SectionAwareChunker: Respeita seções (MAS TODAS!)      │
│     - EntitySemanticChunker: Híbrido                        │
│                                                               │
│  ❌ PROBLEMA: Nenhum respeita "1 slide = 1 chunk"           │
│  → Precisa de "V019ChunkingStrategy" específica!            │
│                                                               │
│  Resultado: ~93 chunks de múltiplos slides misturados        │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│  EMBEDDING                                                   │
│  (Gera vetores para busca semântica)                         │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│  IMPORT → WEAVIATE                                           │
│  (Salva chunks com metadata)                                 │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│  ETL PÓS-CHUNKING (Automático - enable_etl=True)           │
│                                                               │
│  Processa chunks INDIVIDUAIS:                               │
│  - NER por chunk                                             │
│  - Section Scope (identifica seção do chunk)                │
│  - Atualiza Weaviate com propriedades ETL                   │
│                                                               │
│  PROBLEMA: Já perdemos informação de "qual slide"           │
│  porque o chunking quebrou os slides!                       │
└─────────────────────────────────────────────────────────────┘
    ↓
RESULTADO: Chunks sem "slide_number", slide_title perdido
```

---

## ❓ Sua Pergunta: Por que não forçar "1 slide = 1 chunk"?

### A Resposta Curta:
**Você está 100% certo!** Os documentos V019 já vêm estruturados slide-por-slide, então deveria haver um chunker que respeita isso.

### Por Que Não Está Implementado?

1. **Flexibilidade**: Verba priorizou dar liberdade de escolha ao usuário
2. **Metadata Rich**: Os metadados DO SLIDE estão preservados em `document.meta["slides_metadata"]`
3. **ETL Compensa**: O ETL pós-chunking recupera parte da informação por chunk

### A Solução: V019 Chunking Strategy

Seria necessário criar:

```python
class V019ChunkingStrategy(Chunker):
    """
    Chunker especializado para documentos V019.
    
    Estratégia:
    1. Respeita seções de slide (H1)
    2. Cada slide = 1 ou mais chunks (baseado em tamanho/conteúdo)
    3. Preserva slide_number e slide_title em chunk.meta
    4. Agrupa blocos semânticos DENTRO de cada slide
    """
    
    def chunk(self, documents: list[Document]) -> list[Document]:
        # Para cada documento
        for doc in documents:
            # Se tem slides_metadata (V019)
            if "slides_metadata" in doc.meta:
                # 1. Divide conteúdo por slides (já sabemos as seções H1)
                # 2. Para cada slide:
                #    - Identifica sub-seções ou blocos semânticos
                #    - Cria chunks mas preserva slide_number
                # 3. Adiciona em chunk.meta:
                #    - slide_number
                #    - slide_title
                #    - frameworks (do slide)
                #    - stakeholders (do slide)
                #    - semantic_bridge_quality
                #    - position (opening, diagnostic, etc.)
```

---

## 📊 Comparação: Arquitetura Atual vs Ideal

### ❌ ATUAL (Flexível mas Perde Estrutura V019)

```
V019 Document
├─ meta.slides_metadata[0]: { slide_number: 1, title: "Executive Summary", frameworks: [...] }
├─ meta.slides_metadata[1]: { slide_number: 2, title: "Market Analysis", frameworks: [...] }
└─ meta.slides_metadata[2]: { slide_number: 3, title: "Conclusion", frameworks: [...] }

↓ Chunker GENÉRICO (TokenChunker, SemanticChunker, etc.)

Chunks Resultantes:
├─ chunk[0]: "Executive Summary. Market grew 15%..." (MIX de slides 1 e 2!)
├─ chunk[1]: "Market Analysis. Key competitors..." (de slide 2)
├─ chunk[2]: "Competition from..." (de slide 2)
└─ chunk[3]: "In conclusion..." (de slide 3)

❌ Perdeu informação: "qual slide? qual framework?", etc.
```

### ✅ IDEAL (Respeita Estrutura V019)

```
V019 Document com slides_metadata

↓ V019 Chunking Strategy

Chunks Resultantes:
├─ chunk[0]: "Executive Summary. Market grew..." 
│   meta: {
│     slide_number: 1,
│     slide_title: "Executive Summary",
│     frameworks: ["BCG Matrix"],
│     stakeholders: ["Company A", "Company B"],
│     semantic_bridge_quality: 0.92,
│     position: "opening"
│   }
├─ chunk[1]: "Key competitors in market..."
│   meta: {
│     slide_number: 2,
│     slide_title: "Market Analysis",
│     frameworks: ["Porter Five Forces"],
│     stakeholders: [...],
│     semantic_bridge_quality: 0.88,
│     position: "analysis"
│   }
└─ ...

✅ PRESERVA CONTEXTO: Cada chunk sabe seu slide, frameworks, posição no deck
```

---

## 🎯 O que Deveria Acontecer (Ideal)

### Opção 1: Forçar V019 Chunking Automático

```python
# Quando reader é V019MarkdownReader
# Automaticamente ativa V019ChunkingStrategy (não deixa escolher)

FileConfig:
├─ reader: "V019 Markdown Reader"  ← Detecta
├─ chunker: "V019 Chunking Strategy" ← Força automaticamente
├─ embedder: SentenceTransformers ← Livre de escolher
└─ enable_etl: True ← Força automaticamente
```

**Benefício:** Garante estrutura preservada  
**Desvantagem:** Menos flexível

### Opção 2: V019 Chunking Optional

```python
# UI oferece dropdown
Chunker:
├─ Standard options (Token, Sentence, Semantic, etc.)
├─ Section-Aware (genérico)
└─ ⭐ V019 Optimized (novo!) ← Usa slide_metadata

FileConfig:
├─ reader: "V019 Markdown Reader"
├─ chunker: "V019 Optimized" ← Recomendado, mas pode escolher outro
├─ embedder: SentenceTransformers
└─ enable_etl: True
```

**Benefício:** Oferece recomendação mas deixa flexível  
**Desvantagem:** Usuário pode não entender o impacto

### Opção 3: "Síntese Geral" Adicional

```python
# Você mencionou: "+ o chunk de síntese geral"

Chunks:
├─ Chunk 0: Síntese de toda a apresentação
│  meta: {
│    slide_number: 0,
│    slide_title: "DECK SUMMARY",
│    all_frameworks: [...],
│    all_stakeholders: [...]
│  }
├─ Chunk 1: Slide 1 (completo)
├─ Chunk 2: Slide 1 + Slide 2 (se muito pequeno, agrupa)
└─ ...

BENEFÍCIO: Queries genéricas encontram síntese primeiro
```

---

## 💡 Recomendação

### Para Resolver sua Questão:

**Criar `V019ChunkingStrategy` que:**

1. ✅ **Detecta slides** via `slides_metadata` no `document.meta`
2. ✅ **Preserva limite de slide**: Cada chunk DENTRO de um slide
3. ✅ **Agrupa semanticamente** dentro do slide (se > token_limit)
4. ✅ **Persiste metadata** em `chunk.meta`:
   ```python
   chunk.meta = {
       "slide_number": 1,
       "slide_title": "Executive Summary",
       "frameworks": ["BCG"],
       "stakeholders": [...],
       "semantic_bridge_quality": 0.92,
       "position": "opening",
       "chunk_within_slide": 1,  # 1º chunk deste slide
       "total_chunks_in_slide": 2  # Total chunks deste slide
   }
   ```

5. ✅ **Síntese global** (opcional):
   - Primeiro chunk = resumo de todas as frameworks
   - Facilita queries genéricas

6. ✅ **Automático ou Recomendado**:
   - Se reader é V019 → força V019ChunkingStrategy
   - Ou mostra como "Recomendado para V019"

---

## 🔄 Fluxo Melhorado

```
V019 Markdown Reader
├─ input: documento.md (structured)
├─ output: Document com slides_metadata[]
└─ meta.enable_etl = True

         ↓

ETL Pre-Chunking (genérico, funciona igual)

         ↓

V019 Chunking Strategy ⭐ NOVO
├─ input: Document com slides_metadata[]
├─ lógica:
│   For each slide in slides_metadata:
│      1. Extract slide content
│      2. Chunk semantically within slide boundary
│      3. Add slide metadata to chunk.meta
│      4. Preserve framework/stakeholder/position info
├─ output: List[Chunk] com structure preservada
└─ GARANTE: slide_number, slide_title em cada chunk

         ↓

Embedding (genérico)

         ↓

Import Weaviate (genérico)

         ↓

ETL Post-Chunking (genérico, agora com slide info!)
├─ NER por chunk (já tem contexto de slide)
├─ Section Scope (não perde slide)
└─ Update Weaviate com metadata enriquecido

         ↓

Multi-Vector Search Melhorado ✨
├─ Busca por framework: filtra slide_number + frameworks
├─ Busca por stakeholder: filtra stakeholders
├─ Busca por posição: "só quero análises" = position="analysis"
└─ Busca por slide específico: "slide 3" = slide_number=3
```

---

## 📋 Implementação Necessária

### Arquivo: `verba_extensions/plugins/v019_chunking_strategy.py`

```python
class V019ChunkingStrategy(Chunker):
    def __init__(self):
        self.name = "V019 Chunking Strategy"
        self.description = "Specialization for V019 consulting decks - preserves slide boundaries"
        
    def chunk(self, documents: list[Document]) -> list[Document]:
        """
        Chunks V019 documents respecting slide boundaries.
        Each chunk preserves its source slide metadata.
        """
        result = []
        
        for doc in documents:
            if "slides_metadata" not in doc.meta:
                # Not a V019 document, fallback to sentence chunking
                # ... fallback logic
                continue
            
            slides = doc.meta["slides_metadata"]
            processed_doc = Document(...)
            processed_doc.meta = doc.meta
            
            # Create summary chunk (all slides)
            summary_chunk = self._create_summary_chunk(slides, doc)
            processed_doc.chunks.append(summary_chunk)
            
            # Process each slide
            for slide in slides:
                slide_chunks = self._chunk_slide(
                    slide, 
                    doc,
                    max_tokens=self.max_chunk_size
                )
                processed_doc.chunks.extend(slide_chunks)
            
            result.append(processed_doc)
        
        return result
    
    def _chunk_slide(self, slide, doc, max_tokens):
        """Chunks a single slide, respecting boundaries"""
        # Extract content for this slide from doc.content
        # Chunk semantically within slide
        # Add slide metadata to each chunk
        pass
    
    def _create_summary_chunk(self, slides, doc):
        """Creates a summary chunk with all frameworks"""
        # Aggregates all frameworks, stakeholders, key info
        # Creates a synthetic summary
        pass
```

---

## ✅ Conclusão

**Sua observação está correta!** 

O V019 deveria ter um chunking strategy dedicado que:
- ✅ Respeita `1 slide = 1 ou mais chunks` (não mistura slides)
- ✅ Preserva metadata de slide em cada chunk
- ✅ Cria síntese geral como primeiro chunk
- ✅ Permite buscas granulares por slide/framework/stakeholder

**Status Atual:** ❌ Não implementado (usa chunkers genéricos)  
**Deve Ser:** ✅ Implementação prioritária para V019

---

**Próximas ações:**
1. Confirmar se você quer isso implementado
2. Criar V019ChunkingStrategy
3. Integrar na UI/API
4. Testar multi-vector search melhorado


