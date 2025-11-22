# Como o Verba Faz a Vetorização

## ✅ Resposta Direta

**SIM, o Verba faz a vetorização!** O Verba usa **embedders** (componentes de vetorização) para gerar os vetores dos documentos e queries, e então envia esses vetores já prontos para o Weaviate.

---

## 🔍 Como Funciona

### 1. **Verba Gera os Vetores (BYOV - Bring Your Own Vectors)**

O Verba **não depende** do Weaviate para gerar vetores. Ele usa seus próprios **embedders**:

```python
# goldenverba/components/managers.py

embedders = [
    OpenAIEmbedder(),           # Usa API OpenAI
    SentenceTransformersEmbedder(),  # Usa HuggingFace (local)
    CohereEmbedder(),           # Usa API Cohere
    VoyageAIEmbedder(),         # Usa API VoyageAI
    UpstageEmbedder(),          # Usa API Upstage
    OllamaEmbedder(),           # Usa Ollama (local)
    WeaviateEmbedder(),         # Usa Weaviate (se configurado)
]
```

### 2. **Processo de Vetorização**

#### **Durante o Import:**

```python
# 1. Documento é lido e chunked
documents = await reader_manager.load(...)
documents = await chunker_manager.chunk(..., documents, embedder)

# 2. EmbeddingManager vetoriza os chunks
documents = await embedding_manager.vectorize(embedder, fileConfig, documents, logger)

# 3. Cada chunk recebe seu vetor
for chunk in document.chunks:
    chunk.vector = [0.123, -0.456, 0.789, ...]  # Vetor gerado pelo embedder

# 4. Vetores são enviados para Weaviate
await weaviate_manager.import_document(client, document, embedder)
```

#### **Durante a Query:**

```python
# 1. Query é vetorizada com o mesmo embedder
vector = await embedding_manager.vectorize_query(embedder, query, rag_config)

# 2. Busca no Weaviate usando o vetor
results = await weaviate_manager.hybrid_chunks(
    query=query,
    vector=vector,  # Vetor já gerado pelo Verba
    ...
)
```

---

## 📊 Exemplo: OpenAIEmbedder

```python
# goldenverba/components/embedding/OpenAIEmbedder.py

async def vectorize(self, config: dict, content: List[str]) -> List[List[float]]:
    """Vectorize usando API OpenAI"""
    model = config.get("Model").value  # ex: "text-embedding-3-small"
    api_key = get_environment(config, "API Key", "OPENAI_API_KEY", ...)
    
    # Chama API OpenAI para gerar vetores
    payload = {"input": content, "model": model}
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{base_url}/embeddings",
            headers={"Authorization": f"Bearer {api_key}"},
            data=json.dumps(payload),
        ) as response:
            data = await response.json()
            embeddings = [item["embedding"] for item in data["data"]]
            return embeddings  # Retorna vetores prontos
```

**O que acontece:**
1. ✅ Verba chama API OpenAI
2. ✅ OpenAI retorna vetores
3. ✅ Verba armazena vetores nos chunks
4. ✅ Verba envia chunks + vetores para Weaviate

---

## 🎯 Por Que BYOV (Bring Your Own Vectors)?

### **Vantagens:**

1. **Flexibilidade**: Escolha qualquer embedder (OpenAI, Cohere, local, etc.)
2. **Performance**: Vetorização pode ser feita em batch antes de enviar ao Weaviate
3. **Custo**: Controle sobre qual serviço usar (pode ser local com SentenceTransformers)
4. **Cache**: Verba pode cachear embeddings (implementado em `verba_extensions/utils/embeddings_cache.py`)
5. **Independência**: Não depende de módulos do Weaviate

### **Weaviate em Modo BYOV:**

```dockerfile
# Dockerfile.weaviate
ENV ENABLE_MODULES=""  # Sem módulos de vetorização
ENV DEFAULT_VECTORIZER_MODULE="none"  # BYOV mode
```

**O Weaviate apenas:**
- ✅ Armazena os vetores (já gerados pelo Verba)
- ✅ Faz busca vetorial (similarity search)
- ✅ Faz BM25 (keyword search nativo)
- ✅ Faz hybrid search (combina BM25 + vector)

**O Weaviate NÃO:**
- ❌ Gera vetores (isso é feito pelo Verba)
- ❌ Precisa de módulos de vetorização (text2vec-openai, etc.)

---

## 📋 Embedders Disponíveis

### **Cloud (APIs Externas)**
- **OpenAIEmbedder**: `text-embedding-3-small`, `text-embedding-3-large`, etc.
- **CohereEmbedder**: Modelos Cohere
- **VoyageAIEmbedder**: Modelos VoyageAI
- **UpstageEmbedder**: Modelos Upstage

### **Local**
- **SentenceTransformersEmbedder**: HuggingFace (ex: `all-MiniLM-L6-v2`)
- **OllamaEmbedder**: Modelos Ollama locais

### **Weaviate (Opcional)**
- **WeaviateEmbedder**: Usa módulos do Weaviate (se configurado)

---

## 🔄 Fluxo Completo

### **Import de Documento:**

```
1. Documento → Reader → Texto
2. Texto → Chunker → Chunks
3. Chunks → Embedder → Vetores  ← VERBA FAZ AQUI
4. Chunks + Vetores → Weaviate → Armazenado
```

### **Query:**

```
1. Query → Embedder → Vetor  ← VERBA FAZ AQUI
2. Vetor + Query → Weaviate → Busca híbrida (BM25 + Vector)
3. Weaviate → Retorna chunks relevantes
4. Chunks → Generator → Resposta final
```

---

## 💡 Por Que Isso Importa?

### **Para o Dockerfile.weaviate:**

Como o Verba faz a vetorização, o Weaviate pode rodar em **modo BYOV** (sem módulos):

```dockerfile
ENV ENABLE_MODULES=""  # Sem módulos necessários
ENV DEFAULT_VECTORIZER_MODULE="none"  # BYOV
```

**Benefícios:**
- ✅ Weaviate mais leve (sem módulos)
- ✅ Menos dependências
- ✅ Mais rápido (sem overhead de módulos)
- ✅ Mais flexível (mude embedder sem reconfigurar Weaviate)

---

## 🎯 Resumo

| Componente | Responsabilidade |
|------------|------------------|
| **Verba (Embedders)** | ✅ Gera vetores (BYOV) |
| **Weaviate** | ✅ Armazena vetores<br>✅ Busca vetorial<br>✅ BM25 (keyword)<br>✅ Hybrid search |

**O Verba é responsável pela vetorização, o Weaviate apenas armazena e busca!**

---

## 📚 Referências

- [Embedder: Import vs Query](./EMBEDDER_IMPORT_VS_QUERY.md)
- [Dockerfile.weaviate Railway Guide](./DOCKERFILE_WEAVIATE_RAILWAY.md)
- [SentenceTransformers Guide](./GUIA_SENTENCE_TRANSFORMERS.md)

---

**Última atualização:** Novembro 2025

