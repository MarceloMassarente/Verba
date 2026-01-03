# 🏗️ Design: Specialized Hybrid Ingestion & Retrieval

Este documento detalha o plano de implementação para o sistema "Hybrid Multi-Embedder" e "Cascade Retriever", visando **redução de custo de 75%** e manutenção da qualidade.

## 1. Arquitetura Proposta

### Componentes Principais

1.  **HybridMultiEmbedder**: Embedder customizado que roteia otimamente:
    *   `default` -> Voyage 3.5 (Premium, 1024 dims)
    *   `concept_vec`, `company_vec`, `sector_vec` -> Modelos Locais (BGE-M3/MiniLM, 384/1024 dims)
2.  **Smart Import Hook**: Modificação no `import_hook.py` para suportar `vectorize_named`, permitindo que o embedder saiba *qual* vetor está gerando.
3.  **Cascade Retriever**: Lógica de retrieval em dois estágios (Recall Rápido -> Rerank Premium).

---

## 2. Implementação do Ingestor (Hybrid Embedder)

### 2.1 Mudança na Interface e Hook

Precisamos permitir que o `Embedder` saiba o *destino* do vetor.

**Arquivo**: `verba_extensions/integration/import_hook.py`

```python
# MUDANÇA PROPOSTA:
# Em vez de chamar vectorize() cegamente, passamos o contexto

# Antes:
# vec = await embedder_instance.vectorize(config, [text])

# Depois:
if hasattr(embedder_instance, 'vectorize_named'):
    # Embedder inteligente sabe lidar com vetores específicos
    vec = await embedder_instance.vectorize_named(config, [text], vector_name="company_vec")
else:
    # Fallback para embedders normais
    vec = await embedder_instance.vectorize(config, [text])
```

### 2.2 Classe `HybridMultiEmbedder`

**Arquivo**: `verba_extensions/embedders/hybrid_embedder.py`

```python
class HybridMultiEmbedder(Embedder):
    def __init__(self):
        super().__init__()
        self.name = "HybridMultiEmbedder"
        # Inicializa Voyage e SentenceTransformers
        
    async def vectorize(self, config, content):
        # Default behavior (para vetor principal)
        return await self.voyage_client.embed(content, model="voyage-3.5")

    async def vectorize_named(self, config, content, vector_name="default"):
        if vector_name == "default":
            # Premium
            return await self.vectorize(config, content)
            
        elif vector_name == "concept_vec":
            # BGE-M3 (Conceitos)
            return self.bge_m3.encode(content)
            
        elif vector_name in ["company_vec", "sector_vec"]:
            # MiniLM (Entidades - Rápido)
            return self.minilm.encode(content)
            
        return await self.vectorize(config, content)
```

### 2.3 Schema e Dimensões

**Desafio**: Weaviate aceita dimensões mistas?
**Solução**: Sim, desde que cada *property* (target vector) tenha sua dimensão consistente.
*   `default`: 1024d
*   `concept_vec`: 1024d (BGE-M3)
*   `company_vec`: 384d (MiniLM)

Como `vector_config_builder.py` usa `vectorizer: none` (BYOV), o Weaviate valida a dimensão no **primeiro insert**. Não precisamos mudar o código de criação de schema, apenas garantir que o primeiro insert tenha as dimensões corretas.

---

## 3. Implementação do Retrieval (Cascade)

### 3.1 EntityAwareRetriever Update

O `EntityAwareRetriever` precisa ser atualizado para suportar a lógica Cascade se o preset "Cascade" estiver ativo.

**Lógica nova no `search()`:**

1.  **Stage 1 (Recall)**:
    *   Usa Embedder Local (rápido) para embeddar query.
    *   Faz query no Weaviate usando `target_vector="company_vec"` (ou outro secundário).
    *   Limit: 100 documentos.
    
2.  **Stage 2 (Rerank)**:
    *   Pega UUIDs dos 100 candidatos.
    *   Usa Embedder Voyage (premium) para embeddar query.
    *   Faz query no Weaviate usando `target_vector="default"` + filtro `id in [UUIDs]`.
    *   Limit: 10 documentos finais.

---

## 4. Plano de Ação

### Fase 1: Ingestion (Prioridade)
1.  [ ] Criar `HybridMultiEmbedder` em `verba_extensions/embedders`.
2.  [ ] Patchear `import_hook.py` para usar `vectorize_named`.
3.  [ ] Testar ingestão de 1 documento e verificar dimensões no Weaviate.

### Fase 2: Retrieval
1.  [ ] Adicionar lógica Cascade no `EntityAwareRetriever`.
2.  [ ] Atualizar Presets para usar Cascade Mode.

### Requisitos
*   Chave API Voyage funcionando.
*   Modelo BGE-M3 e MiniLM baixados localmente (cache).

---

## 6. Integração com Visual Semantic Ingestion

A estratégia híbrida é **altamente recomendada** para o fluxo "Visual Semantic" (Slides):

1.  **Chunker**: `SlidesSemanticaVisualChunker` (já existente).
    *   Extrai metadados ricos: `visual_archetype`, `slide_position`, `pattern_genetics`.
    *   Popula `meta['frameworks']` e `meta['companies']`.

2.  **Hybrid Embedder (Integração)**:
    *   O `HybridMultiEmbedder` usará automaticamente os metadados extraídos pelo chunker visual.
    *   **Texto do Slide** -> Voyage 3.5 (`default`)
    *   **Frameworks Visuais** -> MiniLM (`framework_vec`)
    *   **Empresas nos Slides** -> MiniLM (`company_vec`)

Isso garante que a busca visual ("mostre slides de matriz SWOT da Apple") funcione com precisão máxima e custo zero para os vetores secundários.
