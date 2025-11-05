# 📋 Descrição Completa do Sistema Verba

## 🎯 Visão Geral

**Verba** (The Golden RAGtriever) é uma aplicação open-source de **Retrieval-Augmented Generation (RAG)** desenvolvida pela Weaviate. É um assistente personalizado totalmente customizável que utiliza RAG para consultar e interagir com dados, permitindo resolver questões sobre documentos, fazer referências cruzadas e obter insights de bases de conhecimento.

### Informações Técnicas
- **Versão Backend**: 2.1.3 (Python)
- **Versão Frontend**: 2.1.0 (Next.js)
- **Python**: >=3.10.0,<3.13.0
- **Arquitetura**: Full-stack (Python FastAPI + Next.js React)
- **Banco de Dados**: Weaviate (banco vetorial)

---

## 🏗️ Arquitetura do Sistema

### Estrutura de Diretórios

```
Verba/
├── goldenverba/              # Backend Python (Core)
│   ├── components/           # Componentes RAG modulares
│   │   ├── reader/           # Leitura de documentos
│   │   ├── chunking/         # Divisão de documentos
│   │   ├── embedding/        # Geração de embeddings
│   │   ├── retriever/        # Recuperação de chunks
│   │   └── generation/       # Geração de respostas (LLMs)
│   ├── server/               # API FastAPI
│   │   ├── api.py           # Endpoints REST
│   │   ├── helpers.py       # Utilitários
│   │   └── types.py         # Tipos de dados
│   └── verba_manager.py      # Gerenciador principal
│
├── verba_extensions/         # Sistema de Extensões (Custom)
│   ├── plugins/              # Plugins customizados
│   ├── compatibility/        # Compatibilidade Weaviate v3/v4
│   ├── integration/          # Hooks de integração
│   └── plugin_manager.py     # Gerenciador de plugins
│
├── frontend/                 # Frontend Next.js/React
│   └── app/                  # Componentes React
│
├── ingestor/                 # Minisserviço de Ingestão (Opcional)
│   ├── app.py               # API FastAPI para ingestão
│   ├── etl_a2.py            # ETL com NER + Section Scope
│   └── chunker.py           # Divisão de documentos
│
└── scripts/                  # Scripts utilitários
```

---

## 🔧 Módulos Principais

### 1. Backend Core (`goldenverba/`)

#### **VerbaManager** (`verba_manager.py`)
- **Função**: Orquestrador principal do sistema
- **Responsabilidades**:
  - Gerencia conexão com Weaviate
  - Coordena importação de documentos
  - Processa queries e geração de respostas
  - Gerencia configurações RAG

#### **WeaviateManager** (`components/managers.py`)
- **Função**: Gerenciamento do banco vetorial Weaviate
- **Responsabilidades**:
  - Conexão com Weaviate (Local, Docker, Cloud, Custom)
  - Criação e verificação de collections
  - Importação de documentos e chunks
  - Queries e agregações
  - Gerenciamento de embeddings

#### **Managers de Componentes**

1. **ReaderManager**
   - Gerencia leitura de documentos
   - Suporta múltiplos formatos: PDF, DOCX, TXT, JSON, CSV, HTML, etc.
   - Readers disponíveis:
     - `BasicReader`: Arquivos básicos (PDF, DOCX, TXT, etc.)
     - `HTMLReader`: Páginas HTML
     - `GitReader`: Repositórios Git/GitLab
     - `UnstructuredReader`: Via API Unstructured
     - `FirecrawlReader`: Web scraping via Firecrawl
     - `AssemblyAIReader`: Áudio/vídeo via AssemblyAI
     - `UpstageDocumentParse`: Parse de documentos via Upstage

2. **ChunkerManager**
   - Gerencia divisão de documentos em chunks
   - Chunkers disponíveis:
     - `TokenChunker`: Por tokens (spaCy)
     - `SentenceChunker`: Por sentenças (spaCy)
     - `RecursiveChunker`: Recursivo baseado em regras
     - `SemanticChunker`: Agrupa por similaridade semântica
     - `HTMLChunker`: Específico para HTML
     - `MarkdownChunker`: Específico para Markdown
     - `CodeChunker`: Específico para código
     - `JSONChunker`: Específico para JSON

3. **EmbeddingManager**
   - Gerencia geração de embeddings vetoriais
   - Embedders disponíveis:
     - `OpenAIEmbedder`: OpenAI embeddings
     - `CohereEmbedder`: Cohere embeddings
     - `OllamaEmbedder`: Embeddings locais via Ollama
     - `SentenceTransformersEmbedder`: HuggingFace (local)
     - `WeaviateEmbedder`: Embeddings via Weaviate
     - `VoyageAIEmbedder`: VoyageAI embeddings
     - `UpstageEmbedder`: Upstage embeddings

4. **RetrieverManager**
   - Gerencia recuperação de chunks relevantes
   - Retrievers disponíveis:
     - `WindowRetriever`: Recupera chunks com janela de contexto

5. **GeneratorManager**
   - Gerencia geração de respostas via LLMs
   - Generators disponíveis:
     - `OpenAIGenerator`: GPT-4, GPT-3.5, etc.
     - `AnthropicGenerator`: Claude (Anthropic)
     - `CohereGenerator`: Cohere Command R+
     - `OllamaGenerator`: Modelos locais (Llama3, Mistral, etc.)
     - `GroqGenerator`: Groq (LPU inference)
     - `NovitaGenerator`: Novita AI
     - `UpstageGenerator`: Upstage Solar

### 2. Sistema de Extensões (`verba_extensions/`)

#### **PluginManager**
- **Função**: Gerencia plugins customizados sem modificar o core
- **Recursos**:
  - Carregamento automático de plugins
  - Injeção de componentes no sistema
  - Verificação de compatibilidade

#### **Plugins Customizados Disponíveis**

1. **Entity-Aware Retriever** (`entity_aware_retriever.py`)
   - Filtros baseados em entidades (NER)
   - Anti-contaminação (evita chunks de empresas erradas)
   - Pre-filter via Weaviate `where` antes do ANN/HNSW

2. **Universal Reader** (`universal_reader.py`)
   - Leitor universal que aceita qualquer formato
   - Aplica ETL A2 automaticamente
   - Garante `enable_etl=True` em todos os documentos

3. **Query Rewriter** (`query_rewriter.py`)
   - Reescreve queries para melhor recuperação
   - Usa LLM para expandir termos de busca

4. **Reranker** (`reranker.py`)
   - Reordena resultados por relevância
   - Melhora precisão da recuperação

5. **Temporal Filter** (`temporal_filter.py`)
   - Filtra chunks por data/tempo
   - Útil para documentos com timestamps

6. **Bilingual Filter** (`bilingual_filter.py`)
   - Filtra por idioma
   - Suporta múltiplos idiomas

7. **Section-Aware Chunker** (`section_aware_chunker.py`)
   - Chunking baseado em seções do documento
   - Preserva contexto hierárquico

8. **LLM Metadata Extractor** (`llm_metadata_extractor.py`)
   - Extrai metadados usando LLM
   - Enriquece chunks com informações estruturadas

9. **A2 ETL Hook** (`a2_etl_hook.py`)
   - Executa ETL (NER + Section Scope) após chunking
   - Processa entidades nomeadas
   - Normaliza entidades via gazetteer

### 3. Frontend (`frontend/`)

#### **Tecnologias**
- **Framework**: Next.js 14.2.25 + React 18.3.1
- **UI**: TailwindCSS + DaisyUI
- **Visualização 3D**: Three.js (para visualização de vetores)
- **Animações**: Framer Motion

#### **Views Principais**

1. **LoginView**
   - Configuração inicial
   - Seleção de deployment (Local, Docker, Weaviate Cloud, Custom)
   - Configuração de API keys

2. **IngestionView**
   - Importação de dados
   - Configuração de Readers, Chunkers, Embedders
   - Upload de arquivos, diretórios ou URLs

3. **ChatView**
   - Interface de chat
   - Configuração de RAG pipeline
   - Visualização de chunks retornados

4. **DocumentView**
   - Explorador de documentos
   - Visualização de chunks
   - Visualização vetorial 3D

5. **SettingsView**
   - Configurações gerais
   - API keys
   - Configurações de componentes

### 4. API Server (`goldenverba/server/api.py`)

#### **Endpoints Principais**

- `POST /api/connect`: Conecta ao Weaviate
- `POST /api/disconnect`: Desconecta do Weaviate
- `POST /api/import`: Importa documentos
- `POST /api/query`: Executa queries RAG
- `POST /api/generate`: Gera respostas
- `GET /api/documents`: Lista documentos
- `GET /api/metadata`: Metadados do Weaviate
- `POST /api/delete`: Deleta documentos
- `WebSocket /api/stream`: Stream de respostas

---

## 🔌 Como o Verba Acessa o Weaviate

### Tipos de Conexão

O Verba suporta **4 modos de deployment** do Weaviate:

#### 1. **Local Deployment** (Weaviate Embedded)
```python
# Usa Weaviate Embedded (roda localmente)
client = weaviate.use_async_with_embedded(
    additional_config=AdditionalConfig(
        timeout=Timeout(init=60, query=300, insert=300)
    )
)
```
- **Características**:
  - Roda diretamente no processo Python
  - Não requer instalação separada
  - Dados armazenados em `~/.local/share/weaviate`
  - **Não suportado no Windows** (experimental)

#### 2. **Docker Deployment**
```python
# Conecta via Docker network
client = await weaviate.connect_to_local(
    host="weaviate",  # Nome do serviço no docker-compose
    port=8080,
    grpc_port=50051
)
```
- **Características**:
  - Weaviate roda em container Docker
  - Comunicação via rede Docker
  - Ideal para desenvolvimento

#### 3. **Weaviate Cloud (WCS)**
```python
# Conecta a cluster WCS
client = await weaviate.connect_to_wcs(
    cluster_url=w_url,
    auth_credentials=AuthApiKey(w_key)
)
```
- **Características**:
  - Cluster gerenciado na nuvem
  - Requer API key
  - Escalável e gerenciado

#### 4. **Custom Deployment**
```python
# Conecta a instância customizada
client = await weaviate.connect_to_custom(
    http_host=host,
    http_port=port,
    http_secure=secure,
    grpc_host=host,
    grpc_port=grpc_port,
    grpc_secure=grpc_secure,
    auth_credentials=AuthApiKey(api_key) if api_key else None
)
```
- **Características**:
  - Conecta a qualquer instância Weaviate
  - Suporta HTTP e gRPC separados
  - Útil para PaaS (Railway, etc.)

### Fluxo de Conexão

1. **VerbaManager.connect()** → Chama `WeaviateManager.connect()`
2. **WeaviateManager.connect()** → Seleciona método baseado em `deployment`:
   - `"Local"` → `connect_to_embedded()`
   - `"Docker"` → `connect_to_docker()`
   - `"Weaviate"` → `connect_to_cluster()` (WCS)
   - `"Custom"` → `connect_to_custom()`
3. **Verificação**: `client.is_ready()` confirma conexão
4. **Verificação de Collections**: Cria collections necessárias se não existirem

### Collections no Weaviate

O Verba cria e gerencia as seguintes collections:

1. **`VERBA_DOCUMENTS`**
   - Armazena metadados dos documentos
   - Propriedades: `title`, `content`, `extension`, `labels`, `source`, `meta`, etc.

2. **`VERBA_Embedding_<modelo>`**
   - Uma collection por modelo de embedding usado
   - Armazena chunks com vetores
   - Propriedades: `content`, `doc_uuid`, `chunk_id`, `title`, `labels`, `vector`, etc.

3. **`VERBA_CONFIGURATION`**
   - Armazena configurações RAG
   - Configurações de tema, usuário, etc.

4. **`VERBA_SUGGESTIONS`**
   - Armazena sugestões de autocomplete

### Compatibilidade Weaviate v3/v4

O sistema possui **detecção automática** de versão:

- **Weaviate v4** (padrão):
  - Usa `weaviate-client v4.9.6`
  - API moderna com `collections`, `use_async_with_*`
  - Suporte completo a named vectors

- **Weaviate v3** (fallback):
  - Detecta automaticamente via `weaviate_version_detector.py`
  - Usa adapter `WeaviateV3HTTPAdapter` (httpx)
  - Compatível com API REST v3

### Operações Principais no Weaviate

#### **Importação de Documentos**
```python
# 1. Insere documento na collection VERBA_DOCUMENTS
doc_uuid = await document_collection.data.insert(document_obj)

# 2. Insere chunks na collection de embedding
chunk_response = await embedder_collection.data.insert_many(
    [DataObject(properties=chunk.to_json(), vector=chunk.vector) 
     for chunk in document.chunks]
)
```

#### **Query/RAG**
```python
# 1. Busca semântica (vector search)
results = await embedder_collection.query.near_vector(
    near_vector=query_vector,
    limit=top_k,
    filters=Filter.by_property("doc_uuid").equal(doc_uuid),
    return_metadata=MetadataQuery(distance=True)
)

# 2. Hybrid search (vector + keyword)
results = await embedder_collection.query.hybrid(
    query=query_text,
    vector=query_vector,
    alpha=0.7,  # 0.7 = 70% semântico, 30% keyword
    limit=top_k
)
```

#### **Filtros (Entity-Aware)**
```python
# Filtro por entidades (anti-contaminação)
filter = Filter.any_of([
    Filter.by_property("entities").contains_any(["Empresa A"]),
    Filter.by_property("entities").contains_any(["Organização X"])
])
results = await embedder_collection.query.near_vector(
    near_vector=query_vector,
    filters=filter,
    limit=top_k
)
```

---

## ✨ Features Principais

### 1. **RAG Pipeline Completo**
- ✅ **Hybrid Search**: Combina busca semântica + keyword
- ✅ **Autocomplete**: Sugestões de queries
- ✅ **Filtering**: Filtros por documento, tipo, labels, etc.
- ✅ **Metadata Customizável**: Controle total sobre metadados
- ✅ **Async Ingestion**: Ingestão assíncrona para velocidade

### 2. **Suporte a Múltiplos Formatos**
- ✅ PDF, DOCX, TXT, MD
- ✅ CSV, XLSX, JSON
- ✅ HTML, URLs (via Firecrawl)
- ✅ Git/GitLab repositories
- ✅ Áudio/Vídeo (via AssemblyAI)

### 3. **Modelos de LLM**
- ✅ OpenAI (GPT-4, GPT-3.5)
- ✅ Anthropic (Claude)
- ✅ Cohere (Command R+)
- ✅ Ollama (local: Llama3, Mistral, etc.)
- ✅ Groq (LPU inference)
- ✅ Novita AI
- ✅ Upstage (Solar)

### 4. **Embeddings**
- ✅ OpenAI embeddings
- ✅ Cohere embeddings
- ✅ Ollama (local)
- ✅ SentenceTransformers (HuggingFace local)
- ✅ Weaviate embeddings
- ✅ VoyageAI embeddings
- ✅ Upstage embeddings

### 5. **Técnicas de Chunking**
- ✅ Token-based (spaCy)
- ✅ Sentence-based (spaCy)
- ✅ Semantic chunking
- ✅ Recursive chunking
- ✅ Format-specific (HTML, Markdown, Code, JSON)

### 6. **Features Avançadas (Extensões)**
- ✅ **Entity-Aware RAG**: Filtros baseados em entidades
- ✅ **ETL A2**: NER + Section Scope automático
- ✅ **Query Rewriting**: Expansão de queries via LLM
- ✅ **Reranking**: Reordenação de resultados
- ✅ **Temporal Filtering**: Filtros por data
- ✅ **Bilingual Support**: Suporte multi-idioma

### 7. **Visualização**
- ✅ **Vector Viewer 3D**: Visualização de vetores em 3D (Three.js)
- ✅ **Chunk Explorer**: Exploração de chunks
- ✅ **Document Viewer**: Visualização de documentos

---

## 🔄 Fluxo de Funcionamento

### 1. **Importação de Documentos**

```
Arquivo → Reader → Documento → Chunker → Chunks → Embedder → Weaviate
```

1. **Reader** carrega arquivo → `Document` object
2. **Chunker** divide em chunks
3. **ETL Hook** (opcional) processa entidades
4. **Embedder** gera vetores para cada chunk
5. **WeaviateManager** importa:
   - Documento na `VERBA_DOCUMENTS`
   - Chunks na `VERBA_Embedding_<modelo>`

### 2. **Query/RAG**

```
Query → Embedder → Vector → Retriever → Chunks → Generator → Resposta
```

1. **Query** do usuário
2. **Embedder** gera vetor da query
3. **Retriever** busca chunks similares no Weaviate:
   - Vector search (semântico)
   - Hybrid search (semântico + keyword)
   - Filtros (entity-aware, temporal, etc.)
4. **Generator (LLM)** gera resposta com contexto dos chunks
5. **Resposta** retornada ao usuário

### 3. **Streaming**

- WebSocket para streaming de respostas
- Respostas geradas incrementalmente
- Feedback em tempo real

---

## 📊 Estrutura de Dados

### Document Object
```python
{
    "title": "string",
    "content": "string",
    "extension": "string",
    "fileSize": number,
    "labels": ["string"],
    "source": "string",
    "meta": {
        "enable_etl": bool,
        "language": "pt",
        ...
    },
    "metadata": "string"
}
```

### Chunk Object
```python
{
    "content": "string",
    "content_without_overlap": "string",
    "doc_uuid": "uuid",
    "chunk_id": number,
    "title": "string",
    "labels": ["string"],
    "vector": [float],  # Embedding vector
    "entities": ["string"],  # ETL A2
    "section_scope": "string",  # ETL A2
    ...
}
```

---

## 🚀 Deploy e Configuração

### Opções de Deploy

1. **pip install**: `pip install goldenverba`
2. **From Source**: `git clone` + `pip install -e .`
3. **Docker**: `docker compose up -d`

### Variáveis de Ambiente

Principais variáveis:
- `WEAVIATE_URL_VERBA`: URL do cluster Weaviate
- `WEAVIATE_API_KEY_VERBA`: API key do Weaviate
- `OPENAI_API_KEY`: OpenAI API key
- `ANTHROPIC_API_KEY`: Anthropic API key
- `OLLAMA_URL`: URL do Ollama (local)
- `DEFAULT_DEPLOYMENT`: Deployment padrão (Local/Docker/Weaviate/Custom)

---

## 📝 Conclusão

O Verba é um sistema completo de RAG que oferece:
- ✅ Interface user-friendly
- ✅ Arquitetura modular e extensível
- ✅ Suporte a múltiplos LLMs e embeddings
- ✅ Integração robusta com Weaviate
- ✅ Sistema de extensões para features customizadas
- ✅ Deploy flexível (local, Docker, cloud)

O sistema é projetado para ser **modular**, **extensível** e **fácil de usar**, permitindo que usuários configurem pipelines RAG complexos através de uma interface simples, enquanto desenvolvedores podem estender funcionalidades através do sistema de plugins.

