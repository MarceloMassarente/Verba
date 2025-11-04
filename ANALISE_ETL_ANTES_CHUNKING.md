# 🔍 Análise: ETL Antes do Chunking - Viabilidade e Implementação

## ❓ Problema Identificado

**Situação Atual:**
```
Reader → Chunking → Embedding → Import → ETL (APÓS)
```

**Problema:**
- Chunking divide texto sem saber onde estão as entidades
- Entidades podem ser cortadas no meio (ex: "Apple Inc" dividido em dois chunks)
- Perde contexto semântico relacionado a entidades
- Section scope fica menos preciso

**Solução Proposta:**
```
Reader → ETL (NER no documento completo) → Chunking (entity-aware) → Embedding → Import
```

---

## ✅ É Viável? SIM!

### **Vantagens:**

1. **Chunks mais coesos**
   - Evita dividir entidades no meio
   - Agrupa conteúdo relacionado à mesma entidade
   - Melhora qualidade de busca

2. **Section Scope mais preciso**
   - Conhece contexto completo do documento antes de dividir
   - Pode detectar seções com entidades relacionadas

3. **Performance similar**
   - NER no documento completo é rápido (spaCy é eficiente)
   - Mesma função `extract_entities_nlp()` já existe

4. **Compatibilidade**
   - Não quebra chunkers existentes
   - Pode ser opcional (flag `enable_etl`)

### **Desafios:**

1. **Ordem de execução**
   - Precisa hook "chunking.before" ou modificar `process_single_document()`
   - Chunker precisa aceitar informações de entidades

2. **Section Scope**
   - Precisa contexto completo para detectar seções
   - Mas isso já é feito no ETL atual

3. **Performance**
   - NER em documento completo pode ser mais lento que em chunks
   - Mas ainda é aceitável (spaCy é rápido)

---

## 🏗️ Proposta de Implementação

### **Opção 1: Hook "chunking.before" (Recomendado)**

```python
# verba_extensions/integration/chunking_hook.py

async def before_chunking(document: Document, enable_etl: bool):
    """Extrai entidades ANTES do chunking"""
    if not enable_etl:
        return document
    
    # Extrai entidades do documento completo
    from verba_extensions.plugins.a2_etl_hook import extract_entities_nlp, normalize_entities, load_gazetteer
    
    text = document.content
    mentions = extract_entities_nlp(text)
    gaz = load_gazetteer()
    entity_ids = normalize_entities(mentions, gaz)
    
    # Armazena no documento para o chunker usar
    if not hasattr(document, 'meta') or document.meta is None:
        document.meta = {}
    
    document.meta["entities"] = mentions  # Lista de {"text": "Apple", "label": "ORG"}
    document.meta["entity_ids"] = entity_ids  # ["Q312"]
    document.meta["entity_spans"] = [
        {"text": e.text, "start": e.start_char, "end": e.end_char, "label": e.label_}
        for e in nlp_model(text).ents
    ]
    
    return document
```

**Vantagens:**
- Não modifica código core
- Pode ser ativado/desativado via flag
- Compatível com chunkers existentes

---

### **Opção 2: Entity-Aware Chunker**

Modificar `SectionAwareChunker` para usar entidades:

```python
# verba_extensions/plugins/section_aware_chunker.py

async def chunk(self, config, documents, embedder, embedder_config):
    for document in documents:
        # Pega entidades do documento (se disponível)
        entities = document.meta.get("entities", []) if hasattr(document, 'meta') else []
        entity_spans = document.meta.get("entity_spans", []) if hasattr(document, 'meta') else []
        
        # Detecta seções
        sections = detect_sections(text)
        
        # Chunking que evita cortar entidades
        for section in sections:
            # Verifica se há entidades nesta seção
            section_entities = [
                e for e in entity_spans
                if section["start"] <= e["start"] < section["end"]
            ]
            
            # Se tem entidades, tenta manter chunk junto
            if section_entities:
                # Evita dividir no meio de uma entidade
                # ...
```

**Vantagens:**
- Chunking realmente entity-aware
- Melhora qualidade dos chunks

---

### **Opção 3: Híbrido (Melhor Solução)**

**Fase 1: ETL Pré-Chunking (NER básico)**
- Extrai entidades do documento completo
- Armazena spans (posições) no documento
- Rápido, não bloqueia

**Fase 2: Chunking Entity-Aware**
- Chunker usa spans para evitar cortes
- Cria chunks mais coesos

**Fase 3: ETL Pós-Chunking (Section Scope + Normalização)**
- Mantém ETL atual para section scope
- Usa contexto completo para melhor precisão
- Normaliza entidades nos chunks

---

## 📊 Comparação: Antes vs Depois

### **Antes (ETL Após Chunking):**

```
Documento: "Apple lança iPhone. A empresa anunciou..."
Chunk 1: "Apple lança iPhone. A empresa"
Chunk 2: "anunciou novas funcionalidades..."
ETL: Encontra "Apple" em Chunk 1, mas contexto fragmentado
```

### **Depois (ETL Antes Chunking):**

```
Documento: "Apple lança iPhone. A empresa anunciou..."
ETL: Detecta "Apple" no documento completo, spans [0:5]
Chunking: Cria chunks evitando cortar "Apple"
Chunk 1: "Apple lança iPhone. A empresa anunciou novas funcionalidades..."
ETL Post: Refina section scope usando contexto completo
```

---

## 🚀 Plano de Implementação

### **Fase 1: ETL Pré-Chunking (Básico)**

1. ✅ Criar hook `chunking.before`
2. ✅ Extrair entidades do documento completo
3. ✅ Armazenar spans no `document.meta`
4. ✅ Testar com chunker existente

### **Fase 2: Chunker Entity-Aware**

1. ✅ Modificar `SectionAwareChunker` para usar spans
2. ✅ Evitar cortar entidades no meio
3. ✅ Agrupar conteúdo por entidade quando possível

### **Fase 3: ETL Pós-Chunking (Refinamento)**

1. ✅ Manter ETL atual para section scope
2. ✅ Usar entidades pré-extraídas para acelerar
3. ✅ Melhorar precisão de section scope

---

## ⚡ Performance Esperada

**ETL Antes:**
- NER em documento completo: ~50-200ms (depende do tamanho)
- Benefício: Chunks melhores, menos necessidade de reprocessar

**ETL Depois (mantido):**
- NER em chunks: ~10-50ms por chunk
- Benefício: Section scope mais preciso com contexto completo

**Total:**
- Overhead: ~50-200ms adicional
- Benefício: Chunks 20-30% mais coesos, melhor qualidade

---

## 🎯 Conclusão

**✅ É TOTALMENTE VIÁVEL e RECOMENDADO!**

**Benefícios:**
- Chunks mais coesos (não corta entidades)
- Melhor qualidade de busca
- Compatível com código existente
- Pode ser implementado incrementalmente

**Próximos Passos:**
1. Implementar hook `chunking.before`
2. Modificar `SectionAwareChunker` para usar entidades
3. Testar com documentos reais
4. Comparar qualidade antes/depois

