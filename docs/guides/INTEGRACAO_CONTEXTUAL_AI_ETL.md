# Integração Contextual.ai com ETL

## 📋 Visão Geral

O **Contextual.ai** se integra perfeitamente com o sistema ETL do Verba através de dois componentes:

1. **Contextual.ai Reader** (separado) - Reader simples que retorna Document sem chunks
2. **Contextual.ai Ingestor Integrado** ⭐ NOVO - Reader + Chunker integrado com chunking otimizado hardcoded

**Fluxo completo (Ingestor Integrado):**
```
Contextual.ai Parse → Chunking Otimizado (hardcoded) → Document com chunks + enable_etl=True → Embedding → Import → ETL Pós-Chunking
```

**Fluxo completo (Reader separado):**
```
Contextual.ai Parse → Document com enable_etl=True → Chunking (chunker escolhido) → Embedding → Import → ETL Pós-Chunking
```

---

## 🔄 Fluxo de Integração

### **FASE 1: Contextual.ai Reader Carrega Documento**

```python
# verba_extensions/plugins/contextual_ai_reader.py

async def load(self, config: dict, fileConfig: FileConfig) -> List[Document]:
    # 1. Faz parse via API Contextual.ai
    result = await self._parse_with_contextual_ai(fileConfig)
    
    # 2. Extrai conteúdo (Markdown com descrições de gráficos)
    content = self._extract_content(result)
    
    # 3. Cria Document
    document = create_document(content, fileConfig)
    
    # 4. ⭐ CRÍTICO: Marca para ETL
    if not hasattr(document, 'meta') or document.meta is None:
        document.meta = {}
    
    document.meta["enable_etl"] = True  # ← ETL será executado automaticamente
    document.meta["language"] = "pt"  # ou detectado automaticamente
    document.meta["source_api"] = "contextual.ai"
    
    # 5. Preserva metadados do Contextual.ai
    if "hierarchy" in result:
        document.meta["document_hierarchy"] = result["hierarchy"]
    if "figures" in result:
        document.meta["figure_descriptions"] = result["figures"]
    
    return [document]
```

**Resultado:**
- ✅ Document criado com conteúdo parseado (Markdown com descrições de gráficos)
- ✅ `enable_etl=True` → ETL será executado automaticamente
- ✅ Metadados preservados (hierarchy, figure_descriptions)

---

### **FASE 2: ETL Pré-Chunking (Opcional, se habilitado)**

**Quando acontece:** Antes do chunking, se `ENABLE_ETL_PRE_CHUNKING=true`

```python
# goldenverba/verba_manager.py (via hook)

if enable_etl and ENABLE_ETL_PRE_CHUNKING:
    from verba_extensions.integration.chunking_hook import apply_etl_pre_chunking
    document = apply_etl_pre_chunking(document, enable_etl=True)
```

**O que faz:**
1. Extrai entidades (ORG + PERSON) do documento completo via spaCy
2. Armazena em `document.meta["entity_spans"]`
3. Usado pelo chunker para não cortar entidades no meio

**Resultado:**
- ✅ `document.meta["entity_spans"]` preenchido
- ✅ Chunker entity-aware pode usar para respeitar entidades

---

### **FASE 3: Chunking**

```python
# VerbaManager.process_single_document()

# Chunker divide documento em chunks
chunks = await chunker.chunk(document, config)
```

**O que acontece:**
- Documento é dividido em chunks
- Se `entity_spans` disponível, chunker respeita entidades (não corta no meio)
- Cada chunk mantém referência ao documento pai

**Resultado:**
- ✅ Múltiplos chunks criados
- ✅ Cada chunk tem texto + metadados do documento

---

### **FASE 4: Embedding**

```python
# Embedder gera vetores para cada chunk
vectors = await embedder.vectorize(chunks)
```

**O que acontece:**
- Cada chunk é convertido em vetor numérico
- Vetores serão usados para busca semântica

**Resultado:**
- ✅ Cada chunk tem vetor de embedding

---

### **FASE 5: Import no Weaviate**

```python
# WeaviateManager.import_document() (patched via import_hook.py)

# 1. Insere documento na collection VERBA_Document
doc_uuid = await document_collection.data.insert(document_obj)

# 2. Insere chunks na collection de embedding
chunk_response = await embedder_collection.data.insert_many(chunks_with_vectors)

# 3. ⭐ Hook detecta enable_etl=True e prepara ETL pós-chunking
if enable_etl:
    passage_uuids = [chunk.uuid for chunk in chunks]
    # Dispara hook 'import.after' em background
    await global_hooks.trigger('import.after', 
        client=client,
        document_uuid=doc_uuid,
        passage_uuids=passage_uuids,
        enable_etl=True,
        collection_name=embedder_collection_name
    )
```

**Resultado:**
- ✅ Documento e chunks armazenados no Weaviate
- ✅ Hook registrado para executar ETL pós-chunking

---

### **FASE 6: ETL Pós-Chunking (Background)** ⭐ PRINCIPAL

```python
# verba_extensions/plugins/a2_etl_hook.py

async def run_etl_on_passages(
    client,
    passage_uuids: List[str],
    collection_name: str
):
    """
    Executa ETL A2 inteligente em cada chunk:
    - Extrai entidades (NER) via spaCy
    - Detecta seções (Section Scope)
    - Atualiza chunks no Weaviate
    """
    
    for chunk_uuid in passage_uuids:
        # 1. Busca chunk do Weaviate
        chunk = await collection.get(uuid=chunk_uuid)
        chunk_text = chunk.properties["text"]
        
        # 2. ⭐ NOVO: Detecção de idioma (PT, EN ou PT-EN)
        language, stats = detect_language_mix(chunk_text)
        # Exemplo: "O cash flow da Apple" → language = "pt-en"
        
        # 3. Extrai entidades via spaCy (bilíngue se necessário)
        entities = []
        for lang in get_language_list(language):  # ["pt", "en"]
            nlp = get_nlp_for_language(lang)
            doc = nlp(chunk_text)
            for ent in doc.ents:
                if ent.label_ in ("ORG", "PERSON", "PER"):
                    entities.append({
                        "text": ent.text,
                        "label": ent.label_,
                        "confidence": 0.95
                    })
        
        # 4. Detecta seção (título, primeiro parágrafo, entidades da seção)
        section_title = detect_section_title(chunk, document)
        section_entity_ids = extract_section_entities(section_title)
        
        # 5. Atualiza chunk no Weaviate
        await collection.data.update(
            uuid=chunk_uuid,
            properties={
                # ⭐ NOVO: entity_mentions (modo inteligente)
                "entity_mentions": json.dumps(entities),
                "chunk_lang": language,  # "pt", "en", "pt-en", etc.
                
                # Modo legado (se gazetteer disponível):
                "entities_local_ids": normalize_via_gazetteer(entities),
                
                # Section scope:
                "section_title": section_title,
                "section_entity_ids": section_entity_ids,
                "section_scope_confidence": 0.85,
                
                "etl_version": "entity_scope_intelligent_v2"
            }
        )
```

**Resultado:**
- ✅ Cada chunk tem metadados de entidades (`entity_mentions`, `entities_local_ids`)
- ✅ Cada chunk tem metadados de seção (`section_title`, `section_entity_ids`)
- ✅ Chunks prontos para busca entity-aware

---

## 🎯 Integração Específica: Descrições de Gráficos

### **Como Descrições de Gráficos são Preservadas**

O Contextual.ai gera descrições detalhadas de gráficos quando `figure_caption_mode=detailed`. Essas descrições são preservadas no fluxo ETL:

#### **1. Durante Parse (Contextual.ai Reader)**

```python
# Contextual.ai retorna Markdown com descrições de gráficos incorporadas
content = """
# Título do Documento

Texto do documento...

![Gráfico 1: Vendas por trimestre](figure_1.png)
**Descrição detalhada:** Este gráfico mostra as vendas da Apple por trimestre em 2024.
O Q1 teve $95 bilhões, Q2 teve $81 bilhões, Q3 teve $81.8 bilhões, e Q4 teve $89.5 bilhões.
Observa-se uma tendência de crescimento no final do ano.

Mais texto...
"""
```

#### **2. Durante Chunking**

```python
# Chunker divide o documento, preservando descrições de gráficos nos chunks

Chunk 1:
"""
# Título do Documento

Texto do documento...

![Gráfico 1: Vendas por trimestre](figure_1.png)
**Descrição detalhada:** Este gráfico mostra as vendas da Apple por trimestre em 2024.
O Q1 teve $95 bilhões, Q2 teve $81 bilhões, Q3 teve $81.8 bilhões, e Q4 teve $89.5 bilhões.
Observa-se uma tendência de crescimento no final do ano.
"""
```

#### **3. Durante ETL Pós-Chunking**

```python
# ETL extrai entidades do chunk (incluindo descrições de gráficos)

chunk_text = """
![Gráfico 1: Vendas por trimestre](figure_1.png)
**Descrição detalhada:** Este gráfico mostra as vendas da Apple por trimestre em 2024.
O Q1 teve $95 bilhões, Q2 teve $81 bilhões, Q3 teve $81.8 bilhões, e Q4 teve $89.5 bilhões.
Observa-se uma tendência de crescimento no final do ano.
"""

# spaCy NER detecta "Apple" na descrição do gráfico
entities = [
    {"text": "Apple", "label": "ORG", "confidence": 0.95}
]

# ETL salva no chunk
await collection.data.update(
    uuid=chunk_uuid,
    properties={
        "entity_mentions": json.dumps(entities),  # ← "Apple" detectado
        "entities_local_ids": ["Q312"],  # ← Apple Inc (se gazetteer disponível)
        "section_entity_ids": ["Q312"],  # ← Entidades da seção
        # ... outros metadados
    }
)
```

**Resultado:**
- ✅ Descrições de gráficos são preservadas no texto do chunk
- ✅ Entidades mencionadas nas descrições são extraídas pelo ETL
- ✅ Chunks com gráficos podem ser encontrados via busca entity-aware

---

## 🚀 Ingestor Integrado (Reader + Chunker Otimizado) ⭐ NOVO

### **Componente: ContextualAIIngestor**

O **Contextual.ai Ingestor Integrado** é um componente único que combina Reader + Chunker otimizado especificamente para o formato Contextual.ai.

**Localização:** `verba_extensions/plugins/contextual_ai_ingestor.py`

**Características:**
- ✅ Parse via API Contextual.ai
- ✅ Chunking hardcoded otimizado (não configurável via UI)
- ✅ PPTX: 1 slide = 1 chunk
- ✅ PDF/DOCX: Respeita hierarquia Markdown (H1/H2/H3)
- ✅ Preserva descrições de gráficos completas
- ✅ ETL automático (`enable_etl=True`)

### **Fluxo do Ingestor Integrado**

```python
# verba_extensions/plugins/contextual_ai_ingestor.py

async def load(self, config: dict, fileConfig: FileConfig) -> List[Document]:
    # 1. Parse via API Contextual.ai
    result = await self._parse_with_contextual_ai(fileConfig, config)
    
    # 2. Extrai conteúdo
    content = self._extract_content(result)
    
    # 3. Detecta tipo (pptx, document, markdown)
    doc_type = self._detect_document_type(fileConfig, result)
    
    # 4. Chunking otimizado (hardcoded)
    if doc_type == 'pptx':
        chunks = self._chunk_pptx(content, result)  # 1 slide = 1 chunk
    else:
        chunks = self._chunk_with_hierarchy(content, result)  # Respeita H1/H2/H3
    
    # 5. Cria Document com chunks já preenchidos
    document = create_document(content, fileConfig)
    document.chunks = chunks  # ← Chunks já criados!
    
    # 6. Marca para ETL
    document.meta["enable_etl"] = True
    document.meta["chunking_strategy"] = doc_type
    
    return [document]
```

### **Como Funciona o Chunking Hardcoded**

#### **Para PPTX (1 slide = 1 chunk):**

1. **Estratégia 1:** Se resultado tem estrutura de slides explícita (`result['slides']`)
2. **Estratégia 2:** Se tem hierarquia com slides (`result['hierarchy']['slides']`)
3. **Estratégia 3:** Fallback - divide por marcadores no Markdown (`---`, `## Slide`, etc.)

#### **Para PDF/DOCX (Hierarquia):**

1. **Estratégia 1:** Se tem hierarquia estruturada (`result['hierarchy']['sections']`)
2. **Estratégia 2:** Parse Markdown detectando headers (`#`, `##`, `###`)
3. Cada seção (H1/H2/H3) vira um chunk ou múltiplos chunks respeitando a seção

### **Integração com ETL**

O ingestor integrado funciona exatamente como o Reader separado:

1. ✅ Marca `enable_etl=True` automaticamente
2. ✅ Chunks já existem quando chegam no VerbaManager
3. ✅ Chunker padrão detecta chunks existentes e pula chunking (`if len(document.chunks) > 0: continue`)
4. ✅ ETL pré-chunking ainda executa (extrai entidades do documento completo)
5. ✅ ETL pós-chunking executa normalmente (processa chunks individuais)

### **Vantagens do Ingestor Integrado**

- ✅ **Chunking otimizado:** Específico para formato Contextual.ai
- ✅ **1 slide = 1 chunk:** Ideal para apresentações
- ✅ **Hierarquia preservada:** Chunks respeitam estrutura do documento
- ✅ **Descrições preservadas:** Gráficos não são cortados no meio
- ✅ **Sem configuração:** Chunking é hardcoded, não precisa escolher chunker

### **Quando Usar**

**Use o Ingestor Integrado se:**
- ✅ Você tem PPTX e quer 1 slide = 1 chunk
- ✅ Você quer chunking otimizado automaticamente
- ✅ Você não quer escolher chunker manualmente

**Use o Reader separado se:**
- ✅ Você quer escolher o chunker manualmente
- ✅ Você quer usar chunkers customizados (Entity-Semantic, etc.)

---

## 🔍 Busca Entity-Aware com Descrições de Gráficos

### **Cenário: Buscar Gráficos sobre Apple**

```python
# Query: "gráficos sobre vendas da Apple"

# 1. Query Builder detecta entidade
entities = ["Apple"]

# 2. Entity-Aware Retriever busca chunks
results = await collection.query.hybrid(
    query="gráficos sobre vendas",
    vector=query_vector,
    filters=Filter.by_property("section_entity_ids").contains_any(["Apple"]),
    limit=10
)

# 3. Retorna chunks que:
#    - Mencionam "Apple" (detectado pelo ETL)
#    - Contêm texto sobre "gráficos" ou "vendas"
#    - Incluem descrições de gráficos do Contextual.ai
```

**Resultado:**
- ✅ Chunks com descrições de gráficos sobre Apple são retornados
- ✅ Descrições detalhadas estão no texto do chunk
- ✅ LLM pode usar descrições para gerar respostas precisas

---

## 📊 Exemplo Completo: Fluxo End-to-End

### **Input: PDF com Gráficos**

```
artigo_apple.pdf:
- Texto sobre Apple
- Gráfico 1: Vendas por trimestre
- Gráfico 2: Market share
- Texto sobre produtos
```

### **FASE 1: Contextual.ai Parse**

```markdown
# Artigo sobre Apple

A Apple é uma das maiores empresas de tecnologia...

![Gráfico 1: Vendas por trimestre](figure_1.png)
**Descrição detalhada:** Este gráfico mostra as vendas da Apple por trimestre em 2024.
O Q1 teve $95 bilhões, Q2 teve $81 bilhões, Q3 teve $81.8 bilhões, e Q4 teve $89.5 bilhões.
Observa-se uma tendência de crescimento no final do ano.

![Gráfico 2: Market share](figure_2.png)
**Descrição detalhada:** Este gráfico compara o market share da Apple, Microsoft e Google
no mercado de smartphones. Apple tem 27%, Microsoft tem 3%, e Google tem 71%.

A Apple continua inovando...
```

### **FASE 2: Chunking**

```
Chunk 1:
"A Apple é uma das maiores empresas de tecnologia..."

Chunk 2:
"![Gráfico 1: Vendas por trimestre](figure_1.png)
**Descrição detalhada:** Este gráfico mostra as vendas da Apple por trimestre em 2024.
O Q1 teve $95 bilhões, Q2 teve $81 bilhões, Q3 teve $81.8 bilhões, e Q4 teve $89.5 bilhões.
Observa-se uma tendência de crescimento no final do ano."

Chunk 3:
"![Gráfico 2: Market share](figure_2.png)
**Descrição detalhada:** Este gráfico compara o market share da Apple, Microsoft e Google
no mercado de smartphones. Apple tem 27%, Microsoft tem 3%, e Google tem 71%."

Chunk 4:
"A Apple continua inovando..."
```

### **FASE 3: ETL Pós-Chunking**

```
Chunk 1:
- entity_mentions: [{"text": "Apple", "label": "ORG"}]
- entities_local_ids: ["Q312"]
- section_entity_ids: ["Q312"]

Chunk 2 (com gráfico):
- entity_mentions: [{"text": "Apple", "label": "ORG"}]
- entities_local_ids: ["Q312"]
- section_entity_ids: ["Q312"]
- text: "[...descrição detalhada do gráfico...]"

Chunk 3 (com gráfico):
- entity_mentions: [
    {"text": "Apple", "label": "ORG"},
    {"text": "Microsoft", "label": "ORG"},
    {"text": "Google", "label": "ORG"}
  ]
- entities_local_ids: ["Q312", "Q2283", "Q95"]
- section_entity_ids: ["Q312", "Q2283", "Q95"]

Chunk 4:
- entity_mentions: [{"text": "Apple", "label": "ORG"}]
- entities_local_ids: ["Q312"]
- section_entity_ids: ["Q312"]
```

### **FASE 4: Busca Entity-Aware**

```python
# Query: "gráficos sobre vendas da Apple"

# Entity-Aware Retriever:
# - Filtra por section_entity_ids CONTAINS "Apple"
# - Busca semântica por "gráficos sobre vendas"

# Resultado:
# - Chunk 2 (gráfico de vendas) ← Retornado (relevante + entidade correta)
# - Chunk 3 (gráfico de market share) ← Retornado (relevante + entidade correta)
# - Chunk 1 ← Não retornado (não tem gráfico)
# - Chunk 4 ← Não retornado (não tem gráfico)
```

### **FASE 5: Resposta do LLM**

```
"Com base nos gráficos do documento, as vendas da Apple por trimestre em 2024 foram:
- Q1: $95 bilhões
- Q2: $81 bilhões
- Q3: $81.8 bilhões
- Q4: $89.5 bilhões

Observa-se uma tendência de crescimento no final do ano."
```

---

## ✅ Checklist de Integração

### **No Contextual.ai Reader:**

- [x] Marcar `enable_etl=True` no `document.meta`
- [x] Preservar metadados do Contextual.ai (`hierarchy`, `figure_descriptions`)
- [x] Extrair conteúdo (Markdown ou JSON)
- [x] Retornar `Document` compatível com Verba

### **ETL Automático (via hooks):**

- [x] Hook detecta `enable_etl=True` automaticamente
- [x] ETL pré-chunking (opcional, se habilitado)
- [x] ETL pós-chunking executa em background
- [x] Entidades extraídas de descrições de gráficos
- [x] Metadados salvos no Weaviate

### **Busca Entity-Aware:**

- [x] Entity-Aware Retriever usa metadados do ETL
- [x] Filtros por entidade funcionam com chunks de gráficos
- [x] Descrições de gráficos preservadas no texto do chunk

---

## 🎯 Vantagens da Integração

### **1. Descrições de Gráficos Preservadas**

- ✅ Contextual.ai gera descrições detalhadas
- ✅ Descrições são preservadas no texto do chunk
- ✅ LLM pode usar descrições para respostas precisas

### **2. Entidades Extraídas de Gráficos**

- ✅ ETL detecta entidades mencionadas nas descrições
- ✅ Chunks com gráficos podem ser filtrados por entidade
- ✅ Busca entity-aware funciona com gráficos

### **3. Estrutura Hierárquica Preservada**

- ✅ `enable_document_hierarchy=true` preserva TOC
- ✅ Section scope detecta seções corretamente
- ✅ Metadados de hierarquia disponíveis para busca

### **4. Integração Transparente**

- ✅ Mesmo fluxo dos outros readers
- ✅ ETL executa automaticamente
- ✅ Sem configuração adicional necessária

---

## ⚠️ Pontos de Atenção

### **1. Tamanho dos Chunks**

**Problema:** Descrições detalhadas de gráficos podem aumentar tamanho dos chunks.

**Solução:**
- Chunker respeita limites de tamanho
- Descrições são preservadas, mas podem ser divididas se necessário
- Considerar chunker específico para documentos com muitos gráficos

### **2. Entidades em Descrições**

**Problema:** Entidades mencionadas apenas em descrições de gráficos podem não ser detectadas se chunk não contém texto adjacente.

**Solução:**
- ETL processa todo o texto do chunk (incluindo descrições)
- Entidades em descrições são detectadas normalmente
- Se necessário, ajustar chunker para incluir mais contexto

### **3. Performance**

**Problema:** Documentos com muitos gráficos podem ter muitos chunks grandes.

**Solução:**
- ETL executa em background (não bloqueia interface)
- Considerar processamento em lote se muitos documentos

---

## 📚 Referências

- [Análise Contextual.ai Integration](./ANALISE_CONTEXTUAL_AI_INTEGRATION.md) - Análise completa da API
- [Explicação Fluxo Completo ETL](../guides/EXPLICACAO_FLUXO_COMPLETO_ETL.md) - Fluxo detalhado do ETL
- [Como ETL Funciona por Chunker](../guides/COMO_ETL_FUNCIONA_POR_CHUNKER.md) - ETL e chunkers
- [README Extensões](../README_EXTENSOES.md) - Sistema de extensões

---

**Última atualização**: Janeiro 2025  
**Status**: Documentação de integração  
**Compatibilidade**: Verba 2.1.x + ETL A2 Inteligente

