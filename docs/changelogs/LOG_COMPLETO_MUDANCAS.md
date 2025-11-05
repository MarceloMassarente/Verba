# 📋 Log Completo de Mudanças no Verba

## 🎯 Objetivo

Este documento lista **TODAS as mudanças** feitas no código do Verba para permitir replicação em atualizações futuras.

---

## 📁 Estrutura de Arquivos Criados

### **Novos Diretórios (Não Modificam Core):**

```
verba_extensions/           # Sistema de plugins/extensões
├── __init__.py
├── plugin_manager.py      # Gerencia plugins
├── version_checker.py     # Verifica compatibilidade
├── hooks.py               # Sistema de hooks
├── startup.py              # Auto-inicialização
├── plugins/                # Plugins customizados
│   ├── entity_aware_retriever.py
│   ├── a2_reader.py
│   ├── a2_etl_hook.py
│   ├── universal_reader.py
│   ├── section_aware_chunker.py
│   └── entity_aware_query_orchestrator.py
├── compatibility/          # Compatibilidade Weaviate v3/v4
│   ├── weaviate_v3_adapter.py
│   ├── weaviate_v3_patch.py
│   ├── weaviate_version_detector.py
│   └── weaviate_imports.py
├── integration/           # Integrações com core
│   └── import_hook.py     # Hook no import_document
└── resources/
    └── gazetteer.json

scripts/
├── pdf_to_a2_json.py      # Conversor PDF → JSON A2
├── create_schema.py       # Schema Article/Passage Weaviate
└── check_dependencies.py
```

**✅ Nenhum desses arquivos modifica código core!**

---

## 🔧 Mudanças no Código Core do Verba

### **1. `goldenverba/server/api.py`**

**Linha ~44-55**: Carregamento de extensões no startup

```python
# ANTES (código original):
load_dotenv()

# DEPOIS (nossa mudança):
load_dotenv()

# Carrega extensões ANTES de criar managers
try:
    import verba_extensions.startup
    from verba_extensions.startup import initialize_extensions
    plugin_manager, version_checker = initialize_extensions()
    if plugin_manager:
        msg.good(f"Extensoes carregadas: {len(plugin_manager.list_plugins())} plugins")
except ImportError:
    msg.info("Extensoes nao disponiveis (continuando sem extensoes)")
except Exception as e:
    msg.warn(f"Erro ao carregar extensoes: {str(e)} (continuando sem extensoes)")
```

**Localização**: Logo após `load_dotenv()`, antes de criar `VerbaManager`

---

### **2. `goldenverba/server/api.py`**

**Linha ~72-85**: CORS Middleware - Permitir origens do Railway

```python
# ANTES (código original):
def check_same_origin(request: Request):
    # ... código original ...

# DEPOIS (nossa mudança):
def check_same_origin(request: Request):
    """Verifica se requisição vem do mesmo origin, com suporte a Railway"""
    origin = request.headers.get("origin")
    if not origin:
        return
    
    # Normaliza URLs (ignora http/https)
    def normalize_url(url: str) -> str:
        return url.replace("https://", "").replace("http://", "").lower().rstrip("/")
    
    # Permite origens do Railway automaticamente
    if ".railway.app" in origin.lower():
        return
    
    # Permite ALLOWED_ORIGINS do env
    allowed_origins = os.getenv("ALLOWED_ORIGINS", "").split(",")
    allowed_origins = [o.strip() for o in allowed_origins if o.strip()]
    
    # ... resto do código original ...
```

**Localização**: Dentro da função `check_same_origin` no middleware

---

### **3. `goldenverba/components/managers.py`**

**Linha ~105**: Adicionar SentenceTransformersEmbedder

```python
# ANTES (código original):
embedders = [
    OllamaEmbedder(),
    WeaviateEmbedder(),
    UpstageEmbedder(),
    VoyageAIEmbedder(),
    CohereEmbedder(),
    OpenAIEmbedder(),
]

# DEPOIS (nossa mudança):
embedders = [
    OllamaEmbedder(),
    SentenceTransformersEmbedder(),  # ← ADICIONADO
    WeaviateEmbedder(),
    UpstageEmbedder(),
    VoyageAIEmbedder(),
    CohereEmbedder(),
    OpenAIEmbedder(),
]
```

**Localização**: Lista `embedders` quando `production != "Production"`

---

### **4. `goldenverba/components/managers.py`**

**Método `connect_to_cluster()`**: Priorização de configuração PaaS explícita

**Arquivo**: `goldenverba/components/managers.py`
**Método**: `WeaviateManager.connect_to_cluster()` (linha ~170-258 aprox)

**Mudanças Principais**:
1. Priorização de configuração PaaS explícita (WEAVIATE_HTTP_HOST/GRPC_HOST)
2. Suporte a portas HTTP/gRPC separadas para PaaS
3. Fallback para métodos originais (WCS, URL-based)

**Código Adicionado (no início da função):**
```python
# PRIORIDADE 1: Verificar se há configuração PaaS explícita (Railway, etc.)
http_host = os.getenv("WEAVIATE_HTTP_HOST")
grpc_host = os.getenv("WEAVIATE_GRPC_HOST")

if http_host and grpc_host:
    # Configuração PaaS explícita - usar connect_to_custom com portas separadas
    # ... lógica completa de conexão PaaS ...
    return client
# Continua para métodos originais...
```

**Localização**: Logo após verificação de URL, antes de qualquer outra lógica

**Documentação**: Ver `PATCHES_VERBA_WEAVIATE_V4.md` (linha 13-82) para detalhes completos

---

### **5. `goldenverba/components/managers.py`**

**Método `connect_to_custom()`**: Lógica completa para Railway/Weaviate v3

**Arquivo**: `goldenverba/components/managers.py`
**Método**: `WeaviateManager.connect_to_custom()` (linha ~271-460 aprox)

**Mudanças Principais**:
1. Detecção de Railway domains (`.railway.app`, `.railway.internal`)
2. Mapeamento correto de portas (8080 interno vs 443 externo)
3. Suporte a Weaviate v3 via adapter
4. Fallback automático v4 → v3
5. Tratamento de HTTPS/HTTP
6. Priorização de `connect_to_custom()` para HTTPS (mais confiável)

**⚠️ MÉTODO COMPLETO MODIFICADO** (~200 linhas reescritas)

**Documentação**: Ver `PATCHES_VERBA_WEAVIATE_V4.md` (linha 92-246) para detalhes completos

---

### **6. `goldenverba/components/generation/OpenAIGenerator.py`**

**Método `get_models()`**: Filtro melhorado para incluir todos modelos de chat

**Arquivo**: `goldenverba/components/generation/OpenAIGenerator.py`
**Método**: `OpenAIGenerator.get_models()` (linha ~127-146 aprox)

**Mudança**:
```python
# ANTES (código original):
# Filtro básico que pode excluir modelos de chat

# DEPOIS (nossa mudança):
# Filtro melhorado que inclui todos modelos de chat disponíveis
# Verifica se modelo é de chat (gpt-*, o1-*, etc.) e inclui todos
```

**Localização**: Dentro do método `get_models()`, na lógica de filtro de modelos

**Motivação**: Garantir que todos modelos de chat disponíveis apareçam na UI, não apenas um subset

---

## 📝 Arquivos de Documentação Criados

### **Guias e Documentação:**

```
ANALISE_PROJETO.md
SOLUCAO_RAILWAY.md
GUIA_UPGRADE_AUTOMATICO.md
README_EXTENSOES.md
GUIA_DOCKER.md
GUIA_SENTENCE_TRANSFORMERS.md
FOCO_PLUGINS.md
GUIA_QUAL_INGESTOR_USAR.md
GUIA_CONVERTER_PDF_PARA_JSON.md
GUIA_INGESTOR_UNIVERSAL.md
EXPLICACAO_FLUXO_COMPLETO_ETL.md
ANALISE_ORDEM_FLUXO_ETL.md
GUIA_USO_ENTITY_AWARE_RETRIEVER.md
VERBA_QUERIES_AVANCADAS.md
EXPLICACAO_MODELOS_OPENAI.md
ONDE_SELECIONAR_RETRIEVER_CUSTOMIZADO.md
```

---

## 🔄 Dependências Adicionadas

### **`requirements-extensions.txt`**:

```txt
httpx>=0.27.0
trafilatura>=1.12.0
spacy>=3.7.0
nltk>=3.9.0
sentence-transformers>=2.2.0
pypdf>=3.0.0
```

### **`Dockerfile`**:

```dockerfile
# Adicionado:
RUN pip install --no-cache-dir -r requirements-extensions.txt || true
RUN pip install --no-cache-dir sentence-transformers || true
RUN python -c "import nltk; nltk.download('punkt', quiet=True)" || true
```

---

## 🎯 Resumo de Mudanças Core

| Arquivo | Linha(s) | Tipo | Descrição |
|---------|----------|------|-----------|
| `goldenverba/server/api.py` | ~44-55 | **Adição** | Carregamento de extensões no startup |
| `goldenverba/server/api.py` | ~72-150 | **Modificação** | CORS middleware para Railway |
| `goldenverba/components/managers.py` | ~105 | **Adição** | SentenceTransformersEmbedder na lista |
| `goldenverba/components/managers.py` | ~170-258 | **Modificação** | Método `connect_to_cluster()` - Priorização PaaS explícita |
| `goldenverba/components/managers.py` | ~271-460 | **Modificação Completa** | Método `connect_to_custom()` - Railway/v3/v4 |
| `goldenverba/components/generation/OpenAIGenerator.py` | ~127-146 | **Modificação** | Método `get_models()` - Filtro melhorado para incluir todos modelos de chat |
| `goldenverba/components/generation/AnthropicGenerator.py` | ~24-94 | **Melhoria** | Adicionado método `get_models()` para listar todos modelos Claude disponíveis (incluindo 3.5) ao invés de apenas 1 hardcoded |
| `verba_extensions/compatibility/__init__.py` | **Novo** | **Criação** | Arquivo __init__.py faltando - necessário para Python reconhecer como pacote |
| `verba_extensions/integration/__init__.py` | **Novo** | **Criação** | Arquivo __init__.py faltando - necessário para Python reconhecer como pacote |
| `verba_extensions/plugins/__init__.py` | **Novo** | **Criação** | Arquivo __init__.py faltando - necessário para Python reconhecer como pacote |
| `verba_extensions/plugins/entity_aware_retriever.py` | ~47-52 | **Correção** | InputConfig Alpha: mudado de `type="number" value=0.6` para `type="text" value="0.6"` (InputConfig não aceita float) |
| `verba_extensions/plugins/entity_aware_retriever.py` | ~81-83 | **Correção** | Adicionada conversão de string para float ao usar Alpha value |
| `verba_extensions/integration/import_hook.py` | ~39-68 | **Melhoria** | Adicionado tratamento de exceções para tentar recuperar doc_uuid mesmo após erro de conexão durante Weaviating |

---

## ✅ Arquivos Que NÃO Modificam Core

Todos estes são **adicionados**, não modificam código existente:

- ✅ `verba_extensions/` (todos os arquivos)
- ✅ `scripts/` (todos os arquivos)
- ✅ Documentação (todos os `.md`)
- ✅ `Dockerfile` (apenas adiciona comandos)
- ✅ `docker-compose.yml` (apenas adiciona env vars)
- ✅ `requirements-extensions.txt` (novo arquivo)

---

## 🚨 Atenção Especial

### **Mudança Complexa: `connect_to_custom()`**

Este método foi **completamente reescrito** (~200 linhas). Ao atualizar Verba:

1. **Mantenha a lógica original** (se houver melhorias no Verba)
2. **Adicione nossa lógica** de Railway/v3
3. **Teste cuidadosamente** após merge

**Recomendação**: Salve versão atual como `connect_to_custom_backup.py` antes de atualizar.

---

## 📋 Checklist para Aplicar em Update

- [ ] Backup do código atual
- [ ] Baixar nova versão do Verba
- [ ] Aplicar mudança 1: Carregamento extensões (`api.py`)
- [ ] Aplicar mudança 2: CORS Railway (`api.py`)
- [ ] Aplicar mudança 3: SentenceTransformers (`managers.py`)
- [ ] Aplicar mudança 4: `connect_to_cluster()` - PaaS (`managers.py`)
- [ ] Aplicar mudança 5: `connect_to_custom()` - Railway/v3 (`managers.py`)
- [ ] Aplicar mudança 6: `get_models()` OpenAI (`OpenAIGenerator.py`)
- [ ] Aplicar mudança 7: `get_models()` Anthropic (`AnthropicGenerator.py`)
- [ ] Copiar `verba_extensions/` completo
- [ ] Copiar `scripts/` completo
- [ ] Atualizar `requirements-extensions.txt` se necessário
- [ ] Atualizar `Dockerfile` se necessário
- [ ] Testar conexão Weaviate
- [ ] Testar plugins
- [ ] Testar ETL

---

**Próximo**: Criar script de patch automático? 🛠️

