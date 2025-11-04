# Named Vectors no Verba - Análise e Teste

## Problema Identificado

O Verba atualmente usa `weaviate-client v3.25.3`, mas **named vectors requerem weaviate-client v4+**.

### O que são Named Vectors?

Named vectors permitem que cada objeto no Weaviate tenha múltiplos vetores, cada um com seu próprio índice e configuração. Isso é útil para:

- **Separar representações semânticas**: Por exemplo, um chunk pode ter um vetor para "papéis/funções" e outro para "setores/indústrias"
- **Otimizar busca**: Buscar especificamente em um espaço vetorial específico
- **Melhorar relevância**: Diferentes queries podem usar diferentes vetores

### Limitação Atual

O Verba usa apenas o vetor "default" (um único vetor por chunk). Named vectors estão disponíveis no Weaviate desde a versão 1.24, mas requerem:

1. **Weaviate Server v1.24+** (pode já estar disponível)
2. **weaviate-client Python v4.0.0+** (atualmente v3.25.3)

## Teste Realizado

Criei um script de teste (`test_named_vectors.py`) que:

1. ✅ Detecta a versão do weaviate-client
2. ✅ Verifica se é v4+
3. ✅ Tenta criar collection com named vectors (BYOV - Bring Your Own Vector)
4. ✅ Testa inserção com múltiplos vetores
5. ✅ Testa queries usando `target_vector`

### Resultado do Teste

```
[WARN] weaviate-client v3 detectado. Named vectors requer v4+
[x] Named vectors requer weaviate-client v4+
[i] Para testar named vectors, atualize:
[i]   pip install --upgrade weaviate-client>=4.0.0
```

## Solução

### Opção 1: Atualizar weaviate-client (Recomendado)

```bash
pip install --upgrade weaviate-client>=4.0.0
```

**⚠️ AVISO**: Atualizar para v4 pode quebrar código existente se houver mudanças na API. É necessário testar cuidadosamente.

### Opção 2: Verificar Compatibilidade

Antes de atualizar, verificar:

1. **Weaviate Server**: Named vectors requerem Weaviate v1.24+
   ```bash
   # Verificar versão do Weaviate
   curl http://localhost:8080/v1/meta
   ```

2. **Código do Verba**: Verificar se há uso de APIs v3 que mudaram na v4

### Opção 3: Implementação Futura

Se não for possível atualizar agora, podemos:

1. Documentar named vectors como feature futura
2. Criar um plugin/extension que suporte named vectors quando v4 estiver disponível
3. Manter compatibilidade com v3 até migração completa

## Implementação Proposta (Quando v4 Estiver Disponível)

### 1. Modificar `WeaviateManager.verify_embedding_collection`

```python
async def verify_embedding_collection_with_named_vectors(
    self, 
    client: WeaviateAsyncClient, 
    embedder: str,
    named_vectors: Optional[Dict[str, Any]] = None
):
    """Cria collection com named vectors se configurado"""
    
    collection_name = self.embedding_table.get(embedder, f"VERBA_Embedding_{embedder}")
    
    if named_vectors:
        # Criar com named vectors
        await client.collections.create(
            name=collection_name,
            vectorizer_config=None,  # BYOV
            properties=[...],
            vector_config=[
                Configure.NamedVectors.vector(
                    name=name,
                    vector_index_config=Configure.VectorIndex.hnsw(...)
                )
                for name in named_vectors.keys()
            ]
        )
    else:
        # Criar normalmente (vetor default)
        await self.verify_collection(client, collection_name)
```

### 2. Modificar `import_document` para suportar múltiplos vetores

```python
async def import_document_with_named_vectors(
    self,
    client: WeaviateAsyncClient,
    document: Document,
    embedder: str,
    named_vector_config: Optional[Dict[str, Callable]] = None
):
    """Importa documento com named vectors"""
    
    # Gerar múltiplos vetores para cada chunk
    for chunk in document.chunks:
        vectors = {}
        
        if named_vector_config:
            for vector_name, embed_func in named_vector_config.items():
                # Gerar vetor específico
                text = getattr(chunk, f"{vector_name}_text", chunk.content)
                vectors[vector_name] = await embed_func(text)
        else:
            # Vetor default
            vectors = {"default": chunk.vector}
        
        await embedder_collection.data.insert(
            properties=chunk.to_json(),
            vector=vectors  # Dict de named vectors
        )
```

### 3. Modificar `hybrid_chunks_with_filter` para suportar `target_vector`

```python
async def hybrid_chunks_with_filter(
    self,
    client: WeaviateAsyncClient,
    embedder: str,
    query: str,
    vector: list[float],
    limit_mode: str,
    limit: int,
    labels: list[str],
    document_uuids: list[str],
    filters: "Filter" = None,
    alpha: float = 0.5,
    target_vector: Optional[str] = None,  # ← NOVO
):
    """Hybrid search com suporte a named vectors"""
    
    collection = client.collections.get(self.embedding_table[embedder])
    
    # Query híbrida com target_vector
    results = await collection.query.hybrid(
        query=query,
        vector=vector,
        target_vector=target_vector,  # ← Named vector
        alpha=alpha,
        limit=limit,
        filters=filters,
        return_metadata=MetadataQuery(distance=True, score=True)
    )
    
    return results.objects
```

## Comparação com RAG2

O RAG2 usa named vectors de forma sofisticada:

- **role_vec**: Vetorizado de `role_text` (papéis/funções) - 320 chars max
- **domain_vec**: Vetorizado de `domain_text` (setores/indústrias) - 280 chars max  
- **profile_bio_vec**: Vetorizado de `profile_bio` (resumo do perfil) - doc-level

No Verba, poderíamos implementar algo similar:

- **content_vec**: Vetor do conteúdo completo (default)
- **entity_vec**: Vetor apenas das entidades mencionadas (se disponível)
- **semantic_vec**: Vetor de conceitos semânticos extraídos (via LLM)

## Próximos Passos

1. ✅ **Teste criado** - `test_named_vectors.py` detecta versão e valida suporte
2. ⏳ **Atualizar weaviate-client** - Quando possível, testar upgrade para v4
3. ⏳ **Validar Weaviate Server** - Verificar se suporta named vectors
4. ⏳ **Implementar suporte** - Adicionar named vectors ao Verba quando v4 estiver disponível
5. ⏳ **Criar plugin** - Plugin opcional para named vectors (não quebra compatibilidade)

## Conclusão

Named vectors são uma feature poderosa que pode melhorar significativamente a qualidade do RAG, especialmente para separar diferentes aspectos semânticos do conteúdo. No entanto, requer atualização do `weaviate-client` para v4+, o que precisa ser feito com cuidado para não quebrar funcionalidades existentes.

**Recomendação**: Documentar como feature futura e planejar migração gradual para v4 quando possível.

