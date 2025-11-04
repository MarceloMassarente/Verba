# 🔌 Integração de Plugins no Verba - Documentação

**Data:** 2025-11-04  
**Status:** ✅ Integrado e Funcional

---

## 📋 Visão Geral

O sistema de plugins foi integrado ao fluxo de ingestão do Verba para permitir enriquecimento automático de chunks durante a indexação.

### Pipeline Completo

```
Documento → Reader → Chunker → ✨ PLUGINS → Embedder → Weaviate
                              ↑
                    LLMMetadataExtractor
                    (e outros futuros plugins)
```

---

## 🏗️ Arquitetura

### Componentes Criados

1. **PluginManager** (`verba_extensions/plugins/plugin_manager.py`)
   - Carrega plugins automaticamente
   - Processa chunks em batch
   - Gerencia ciclo de vida dos plugins

2. **Chunk.meta** (atualizado em `goldenverba/components/chunk.py`)
   - Campo `meta` adicionado para armazenar metadata enriquecido
   - Campo `uuid` adicionado para identificação
   - `to_json()` e `from_json()` atualizados para serializar meta

3. **Integração no VerbaManager** (`goldenverba/verba_manager.py`)
   - Hook após chunking e antes de vectorization
   - Processamento não-blocking e fault-tolerant

---

## 🔄 Fluxo de Execução

### 1. Durante Indexação

```python
# Em VerbaManager.process_single_document():

# 1. Chunking (como antes)
chunked_documents = await chunker_manager.chunk(...)

# 2. ✨ NOVO: Plugin Enrichment
if PLUGINS_AVAILABLE:
    plugin_manager = get_plugin_manager()
    for doc in chunked_documents:
        doc = await plugin_manager.process_document_chunks(doc)
        # Agora doc.chunks tem metadata enriquecido em chunk.meta

# 3. Vectorization (como antes)
vectorized_documents = await embedder_manager.vectorize(...)

# 4. Import to Weaviate (metadata enriquecido é salvo automaticamente)
await weaviate_manager.import_document(...)
```

### 2. O Que Acontece com Cada Chunk

```python
# Chunk antes do plugin:
chunk.meta = {}

# Chunk depois do LLMMetadataExtractor:
chunk.meta = {
    "enriched": {
        "companies": ["Apple", "Microsoft"],
        "key_topics": ["AI", "Innovation"],
        "sentiment": "positive",
        "summary": "Apple's AI strategy...",
        "keywords": ["apple", "ai"],
        "entities_relationships": [...],
        "confidence_score": 0.92
    }
}

# Salvo no Weaviate:
chunk.to_json() → {
    "content": "...",
    "meta": '{"enriched": {...}}',  # JSON serializado
    ...
}
```

---

## 🔌 Plugins Disponíveis

### LLMMetadataExtractor

**Status:** ✅ Funcional  
**Localização:** `verba_extensions/plugins/llm_metadata_extractor.py`

**O que faz:**
- Enriquece chunks com metadata estruturado via LLM
- Extrai: empresas, tópicos, sentimento, relações, resumos
- Batch processing para eficiência
- Cache automático

**Configuração:**
- Requer `ANTHROPIC_API_KEY` (opcional - funciona sem LLM)
- Processa automaticamente durante indexação

**Documentação:** Ver `LLM_METADATA_EXTRACTOR_README.md`

---

## 📊 Estrutura de Metadata

### Chunk.meta Format

```python
chunk.meta = {
    # Metadata padrão (já existente)
    "source": "documento.pdf",
    "section": "Introduction",
    
    # Metadata enriquecido por plugins
    "enriched": {
        "companies": ["Apple", "Microsoft"],
        "key_topics": ["AI", "Innovation"],
        "sentiment": "positive",
        "summary": "Resumo do chunk...",
        "keywords": ["apple", "ai"],
        "entities_relationships": [
            {
                "entity": "Microsoft",
                "relationship_type": "competitor",
                "confidence": 0.95
            }
        ],
        "confidence_score": 0.92
    }
}
```

### Serialização no Weaviate

```python
# Em Chunk.to_json():
"meta": json.dumps(chunk.meta)  # String JSON

# Em Weaviate (salvo como propriedade):
chunk.properties["meta"] = '{"enriched": {...}}'
```

---

## 🚀 Como Usar

### Para Usuários Finais

**Automático!** Os plugins são carregados automaticamente durante a indexação.

Se você tem `ANTHROPIC_API_KEY` configurada:
- ✅ Chunks são enriquecidos automaticamente
- ✅ Metadata salvo no Weaviate
- ✅ Disponível para retrieval e reranking

Se você não tem `ANTHROPIC_API_KEY`:
- ✅ Indexação funciona normalmente
- ⚠️ Chunks não são enriquecidos (mas não quebra nada)

### Para Desenvolvedores

**Adicionar Novo Plugin:**

1. Criar arquivo em `verba_extensions/plugins/seu_plugin.py`
2. Implementar interface:
   ```python
   class SeuPlugin:
       async def process_chunk(chunk, config) -> Chunk:
           # Enriquecer chunk
           chunk.meta["seu_enriquecimento"] = {...}
           return chunk
       
       async def process_batch(chunks, config) -> List[Chunk]:
           # Processar em batch
           return [await self.process_chunk(c) for c in chunks]
   ```
3. Criar factory:
   ```python
   def create_seu_plugin():
       return SeuPlugin()
   ```
4. Adicionar em `plugin_manager.py`:
   ```python
   known_plugins = [
       "llm_metadata_extractor",
       "seu_plugin",  # Adicionar aqui
   ]
   ```

---

## 🔍 Verificação e Debug

### Verificar Plugins Carregados

```python
from verba_extensions.plugins.plugin_manager import get_plugin_manager

pm = get_plugin_manager()
print(pm.get_enabled_plugins())
# ['llm_metadata_extractor']

print(pm.get_plugin_configs())
# {
#     'LLMMetadataExtractor': {
#         'name': 'LLMMetadataExtractor',
#         'has_llm': True,
#         'cache_size': 0,
#         ...
#     }
# }
```

### Verificar Metadata em Chunks

```python
# Após indexação, buscar chunk do Weaviate:
chunk = await weaviate_manager.get_chunk(...)

# Verificar metadata:
if "enriched" in chunk.meta:
    print("✅ Chunk enriquecido!")
    print(chunk.meta["enriched"])
else:
    print("⚠️ Chunk não enriquecido")
```

### Logs

Os plugins logam suas atividades:

```
[INFO] Loaded plugin: llm_metadata_extractor
[INFO] Applying 1 plugin(s) to enrich chunks
[INFO] Processing batch of 10 chunks
[GOOD] Chunks enriched with ['llm_metadata_extractor']
```

---

## ⚠️ Considerações Importantes

### Performance

- **Latência:** ~2-3s por chunk com LLM
- **Batch:** Processa em paralelo (batch_size=5)
- **Cache:** Evita reprocessamento de chunks idênticos
- **Impacto:** Adiciona ~20-30s para documentos com 10 chunks

### Fault Tolerance

- Plugins **nunca quebram** a indexação
- Se um plugin falhar, indexação continua
- Logs de erro são registrados mas não interrompem processo

### Storage

- Metadata enriquecido é salvo no Weaviate
- Campo `meta` serializado como JSON string
- ~1-2KB por chunk enriquecido

---

## 🎯 Próximos Passos

### Plugins Planejados

1. ✅ **LLMMetadataExtractor** - Implementado
2. ⏭️ **Reranker Plugin** - Week 4
3. ⏭️ **RecursiveDocumentSplitter** - Week 3

### Melhorias Futuras

- [ ] Persistent cache (Redis/SQLite)
- [ ] Plugin configuration via UI
- [ ] Metrics collection (latency, cost)
- [ ] Hot-reload de plugins
- [ ] Plugin dependencies

---

## 📞 Suporte

**Documentação:** Este arquivo  
**Código:** `verba_extensions/plugins/`  
**Issues:** Verificar logs com `logger.info()` habilitado

---

## ✅ Checklist de Validação

- [x] Chunk.meta adicionado e serializado
- [x] PluginManager criado e funcional
- [x] Integração no VerbaManager
- [x] LLMMetadataExtractor integrado
- [x] Fault tolerance implementado
- [x] Logs configurados
- [x] Documentação completa
- [ ] Testes end-to-end (Week 5)

---

**Status:** ✅ Sistema de plugins integrado e pronto para uso!

