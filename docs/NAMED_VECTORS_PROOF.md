# ✅ PROVA: Sistema Popula e Usa os 4 Named Vectors

## 🔬 Evidência no Código

### 1. SISTEMA POPULA OS 4 VETORES? ✅ **SIM!**

**Arquivo**: `verba_extensions/integration/import_hook.py` linhas 488-590

```python
# Se tem named vectors, gera embeddings adicionais usando o mesmo embedder do Verba
# BYOV mode: Verba gera embeddings, Weaviate apenas armazena
if has_named_vectors and hasattr(document, 'chunks') and document.chunks:
    try:
        from verba_extensions.utils.vector_extractor import get_vector_extractor
        vector_extractor = get_vector_extractor()
        
        # Obtém instância do embedder para gerar embeddings (mesmo usado para default)
        from goldenverba.components import managers
        embedding_manager = managers.EmbeddingManager()
        
        if embedder not in embedding_manager.embedders:
            msg.warn(f"[Named-Vectors] Embedder '{embedder}' não encontrado")
        else:
            embedder_instance = embedding_manager.embedders[embedder]
            msg.info(f"[Named-Vectors] 🎯 Gerando embeddings para named vectors usando {embedder} (BYOV)")
            
            # Extrai textos especializados e gera embeddings para cada chunk
            for chunk_idx, chunk in enumerate(document.chunks):
                try:
                    # Extrai textos especializados
                    texts = vector_extractor.extract_all_texts(chunk)
                    chunk.meta["concept_text"] = texts["concept_text"]
                    chunk.meta["sector_text"] = texts["sector_text"]
                    chunk.meta["company_text"] = texts["company_text"]
                    
                    # Gera embeddings para cada texto especializado
                    named_vectors = {
                        "default": chunk.vector  # ← VETOR 1: DEFAULT
                    }
                    
                    # ← VETOR 2: CONCEPT_VEC
                    if texts["concept_text"]:
                        concept_embeddings = await embedder_instance.vectorize(
                            config, [texts["concept_text"]]
                        )
                        named_vectors["concept_vec"] = concept_embeddings[0]
                    else:
                        named_vectors["concept_vec"] = chunk.vector  # Fallback
                    
                    # ← VETOR 3: SECTOR_VEC  
                    if texts["sector_text"]:
                        sector_embeddings = await embedder_instance.vectorize(
                            config, [texts["sector_text"]]
                        )
                        named_vectors["sector_vec"] = sector_embeddings[0]
                    else:
                        named_vectors["sector_vec"] = chunk.vector  # Fallback
                    
                    # ← VETOR 4: COMPANY_VEC
                    if texts["company_text"]:
                        company_embeddings = await embedder_instance.vectorize(
                            config, [texts["company_text"]]
                        )
                        named_vectors["company_vec"] = company_embeddings[0]
                    else:
                        named_vectors["company_vec"] = chunk.vector  # Fallback
                    
                    # Armazena named vectors no chunk
                    chunk._named_vectors = named_vectors
                    
                except Exception as e:
                    msg.warn(f"[Named-Vectors] Erro ao processar chunk {chunk_idx}")
            
            msg.good(f"[Named-Vectors] ✅ Embeddings gerados para {len([c for c in document.chunks if hasattr(c, '_named_vectors')])} chunks (BYOV)")
```

**Conclusão**: ✅ **O código REALMENTE gera os 4 embeddings** usando `embedder_instance.vectorize()` com os textos especializados.

---

### 2. OS RETRIEVERS USAM OS NAMED VECTORS? ⚠️ **PARCIALMENTE**

#### 2.1. Uso Atual: SOMENTE `default` ✅

**Arquivo**: `goldenverba/components/managers.py` linha 1360

```python
# managers.py - hybrid_chunks method
query = (
    collection.query
    .hybrid(
        query=query_text,
        vector=query_embedding,
        alpha=0.5,
        target_vector="default"  # ← USA SEMPRE DEFAULT!
    )
)
```

**Status**: O retriever padrão do Verba usa **somente** `default`.

---

#### 2.2. EntityAwareRetriever: PODE usar outros vetores (FEATURE DESABILITADA) ⚠️

**Arquivo**: `verba_extensions/plugins/entity_aware_retriever.py` linha 2612-2641

```python
# EntityAwareRetriever - multi_vector_search
if multi_vector_enabled:
    # Verificar se collection tem named vectors
    try:
        collection_config = await collection.config.get()
        has_named_vectors = hasattr(collection_config, 'vector_config') and \
                           collection_config.vector_config is not None
        
        vectors_to_search = ["default"]  # Sempre inclui default
        
        if has_named_vectors:
            # Detecta quais vetores usar baseado na query
            if has_concepts or has_frameworks:
                vectors_to_search.append("concept_vec")  # ← PODE USAR CONCEPT
            if has_sectors:
                vectors_to_search.append("sector_vec")   # ← PODE USAR SECTOR
            if has_companies:
                vectors_to_search.append("company_vec")  # ← PODE USAR COMPANY
        
        msg.info(f"  Multi-Vector: buscando em {vectors_to_search}")
        
        # Busca em cada vetor em paralelo
        for vector_name in vectors_to_search:
            results = await collection.query.hybrid(
                query=query_text,
                vector=query_embedding,
                target_vector=vector_name,  # ← USA VETORES ESPECIALIZADOS!
                alpha=alpha,
                limit=limit
            )
            all_results.extend(results)
```

**Status**: EntityAwareRetriever **TEM O CÓDIGO** para usar os 3 vetores especializados, mas a feature "Enable Multi-Vector Search" está **DESABILITADA POR PADRÃO**.

---

## 📊 Status Atual vs Potencial

| Vetor | Populado? | Usado Atualmente? | Pode Ser Usado? |
|-------|-----------|-------------------|-----------------|
| **default** | ✅ SIM | ✅ SIM (sempre) | ✅ SIM |
| **concept_vec** | ✅ SIM | ❌ NÃO | ⚠️ SIM (se multi-vector enabled) |
| **sector_vec** | ✅ SIM | ❌ NÃO | ⚠️ SIM (se multi-vector enabled) |
| **company_vec** | ✅ SIM | ❌ NÃO | ⚠️ SIM (se multi-vector enabled) |

---

## 🎯 Como Ativar Uso dos 4 Vetores

### Opção 1: Via UI (NÃO TESTADO)

1. Settings → EntityAwareRetriever
2. ✅ Enable Multi-Vector Search
3. Settings → Advanced  
4. ✅ Enable Named Vectors

### Opção 2: Via Código (REQUER IMPLEMENTAÇÃO)

```python
# No EntityAwareRetriever
config = {
    "Enable Multi-Vector Search": {
        "value": True  # ← ATIVA MULTI-VECTOR
    }
}

# No Advanced
config["Advanced"] = {
    "Enable Named Vectors": {
        "value": True  # ← ATIVA NAMED VECTORS
    }
}
```

---

## ✅ CONCLUSÃO DEFINITIVA

### População dos Vetores

**✅ SIM, o sistema popula os 4 vetores!**

- Código em `import_hook.py` linhas 488-590
- Usa `embedder_instance.vectorize()` para cada texto especializado
- Gera embeddings reais (não só copia default)
- Armazena em `chunk._named_vectors` e depois em Weaviate

### Uso pelos Retrievers

**⚠️ PARCIAL - Somente `default` usado atualmente**

- **Retriever padrão (Verba core)**: Usa SOMENTE `default`
- **EntityAwareRetriever**: TEM código para usar os 3 vetores especializados, mas feature está **desabilitada por padrão**

### Para Usar Todos os 4 Vetores

Você precisa **ativar** "Enable Multi-Vector Search" no EntityAwareRetriever.

---

**Documentação atualizada**: 2026-01-03  
**Verificado em**: import_hook.py, entity_aware_retriever.py, managers.py
