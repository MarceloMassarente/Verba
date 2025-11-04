# Todas as Mudanças no Verba - Guia de Patches

Este documento lista **TODAS** as mudanças feitas no Verba padrão para suportar:
1. **Weaviate v4** (especialmente para Railway/PaaS)
2. **Features RAG2** (bilingual routing, query rewriting, temporal filters)
3. **Extensões de plugins** (entity-aware retrieval, etc.)

Use este documento para aplicar patches após atualizações do Verba padrão.

---

## Índice

1. [Mudanças no Core](#mudanças-no-core)
   - [Chunk (`goldenverba/components/chunk.py`)](#1-chunk-goldenverbacomponentschunkpy)
   - [VerbaManager (`goldenverba/verba_manager.py`)](#2-verbamanager-goldenverbaverbamanagerpy)
2. [Mudanças Weaviate v4](#mudanças-weaviate-v4)
   - [Managers (`goldenverba/components/managers.py`)](#3-managers-goldenverbacomponentsmanagerspy)
3. [Novos Plugins RAG2](#novos-plugins-rag2)
   - [BilingualFilterPlugin](#4-bilingualfilterplugin-verbaextensionspluginsbilingualfilterpy)
   - [QueryRewriterPlugin](#5-queryrewriterplugin-verbaextensionspluginsqueryrewriterpy)
   - [TemporalFilterPlugin](#6-temporalfilterplugin-verbaextensionspluginstemporalfilterpy)
4. [Modificações em Plugins Existentes](#modificações-em-plugins-existentes)
   - [EntityAwareRetriever](#7-entityawareretriever-verbaextensionspluginsentityawareretrieverpy)

---

## Mudanças no Core

### 1. Chunk (`goldenverba/components/chunk.py`)

**Objetivo:** Adicionar suporte a `chunk_lang` (idioma) e `chunk_date` (data) para filtros RAG2.

#### Mudança 1.1: Adicionar propriedades no `__init__`

**Localização:** Dentro de `class Chunk`, método `__init__`

**Adicionar após linha ~24:**
```python
self.uuid = None  # UUID for chunk identification
self.chunk_lang = None  # Language code (pt, en, etc.) for bilingual filtering
self.chunk_date = None  # Date in ISO format (YYYY-MM-DD) for temporal filtering
```

#### Mudança 1.2: Atualizar `to_json()`

**Localização:** Método `to_json()`, dentro do dicionário de retorno

**Adicionar após `"uuid": self.uuid,`:**
```python
"uuid": self.uuid,
"chunk_lang": self.chunk_lang or "",  # Language code for bilingual filtering
"chunk_date": self.chunk_date or "",  # Date in ISO format for temporal filtering
```

#### Mudança 1.3: Atualizar `from_json()`

**Localização:** Método `from_json()`, após `chunk.uuid = data.get("uuid")`

**Adicionar:**
```python
chunk.uuid = data.get("uuid")
chunk.chunk_lang = data.get("chunk_lang")  # Language code
chunk.chunk_date = data.get("chunk_date")  # Date
```

**Status:** ✅ Essas propriedades são opcionais e não quebram compatibilidade.

---

### 2. VerbaManager (`goldenverba/verba_manager.py`)

**Objetivo:** Detectar automaticamente o idioma de cada chunk durante o processamento.

#### Mudança 2.1: Detecção de idioma após chunking

**Localização:** Método `import_document()`, após `chunked_documents = await chunk_task`

**Buscar:**
```python
chunked_documents = await chunk_task

# Apply plugin enrichment...
```

**Adicionar ANTES de "Apply plugin enrichment":**
```python
chunked_documents = await chunk_task

# Add chunk_lang to chunks (language detection)
from goldenverba.components.document import detect_language
for doc in chunked_documents:
    for chunk in doc.chunks:
        if not chunk.chunk_lang:
            # Detect language from chunk content
            detected_lang = detect_language(chunk.content)
            # Normalize to pt/en for bilingual filtering
            if detected_lang in ["pt", "pt-br", "pt-BR"]:
                chunk.chunk_lang = "pt"
            elif detected_lang in ["en", "en-US", "en-GB"]:
                chunk.chunk_lang = "en"
            else:
                # Default to document language or empty
                chunk.chunk_lang = detected_lang if detected_lang != "unknown" else ""

# Apply plugin enrichment...
```

**Nota:** A função `detect_language()` já existe em `goldenverba/components/document.py`. Se não existir, você precisa implementá-la ou usar uma biblioteca como `langdetect`.

**Status:** ✅ Esta mudança é opcional e não quebra funcionalidade existente.

---

## Mudanças Weaviate v4

### 3. Managers (`goldenverba/components/managers.py`)

**Objetivo:** Suportar Weaviate v4 com configuração PaaS explícita (Railway).

**Documentação detalhada:** Ver `PATCHES_VERBA_WEAVIATE_V4.md`

**Resumo das mudanças:**
1. ✅ Priorização de configuração PaaS explícita (`WEAVIATE_HTTP_HOST`, `WEAVIATE_GRPC_HOST`)
2. ✅ Uso de `connect_to_custom` para HTTPS/portas separadas
3. ✅ Remoção de `WeaviateV3HTTPAdapter` (incompatível)
4. ✅ Verificação de `hasattr(client, 'connect')` antes de chamar
5. ✅ Fallback HTTPS para Railway porta 8080

**Status:** ✅ **CRÍTICO** - Sem essas mudanças, conexão Weaviate v4 em PaaS falha.

---

## Novos Plugins RAG2

### 4. BilingualFilterPlugin (`verba_extensions/plugins/bilingual_filter.py`)

**Arquivo:** Criar novo arquivo

**Conteúdo completo:** Ver arquivo `verba_extensions/plugins/bilingual_filter.py`

**Funcionalidade:**
- Detecta idioma da query usando `langdetect`
- Constrói filtro Weaviate para `chunk_lang`
- Suporta queries em português e inglês

**Dependências:**
```bash
pip install langdetect
```

**Status:** ✅ Novo arquivo, não afeta código existente.

---

### 5. QueryRewriterPlugin (`verba_extensions/plugins/query_rewriter.py`)

**Arquivo:** Criar novo arquivo

**Conteúdo completo:** Ver arquivo `verba_extensions/plugins/query_rewriter.py`

**Funcionalidade:**
- Usa LLM (Anthropic) para reescrever queries
- Separa em `semantic_query` e `keyword_query`
- Identifica `intent` (comparison, description, search)
- Calcula `alpha` para hybrid search
- Cache LRU para evitar chamadas repetidas

**Dependências:**
- AnthropicGenerator (já existe no Verba)
- `cachetools` (se não estiver instalado)

**Status:** ✅ Novo arquivo, não afeta código existente.

---

### 6. TemporalFilterPlugin (`verba_extensions/plugins/temporal_filter.py`)

**Arquivo:** Criar novo arquivo

**Conteúdo completo:** Ver arquivo `verba_extensions/plugins/temporal_filter.py`

**Funcionalidade:**
- Extrai ranges de datas de queries usando regex
- Suporta formatos: "2024", "2023-2024", "desde 2020", etc.
- Constrói filtro Weaviate para `chunk_date`

**Dependências:**
- Nenhuma adicional (usa apenas regex)

**Status:** ✅ Novo arquivo, não afeta código existente.

---

## Modificações em Plugins Existentes

### 7. EntityAwareRetriever (`verba_extensions/plugins/entity_aware_retriever.py`)

**Objetivo:** Integrar os plugins RAG2 (bilingual, query rewriting, temporal) no retriever.

#### Mudança 7.1: Adicionar configurações

**Localização:** Método `__init__()`, após configurações existentes

**Adicionar:**
```python
# RAG2 Features Integration
self.config["Enable Language Filter"] = InputConfig(
    type="bool",
    value=True,
    description="Enable bilingual routing (filter chunks by query language)",
    values=[],
)
self.config["Enable Query Rewriting"] = InputConfig(
    type="bool",
    value=True,
    description="Enable LLM-based query rewriting for better search",
    values=[],
)
self.config["Query Rewriter Cache TTL"] = InputConfig(
    type="number",
    value=3600,
    description="Cache TTL for query rewriting (seconds)",
    values=[],
)
self.config["Enable Temporal Filter"] = InputConfig(
    type="bool",
    value=True,
    description="Enable temporal filtering (extract date ranges from queries)",
    values=[],
)
self.config["Date Field Name"] = InputConfig(
    type="text",
    value="chunk_date",
    description="Weaviate field name for chunk date (ISO format: YYYY-MM-DD)",
    values=[],
)
```

#### Mudança 7.2: Importar plugins RAG2

**Localização:** Topo do arquivo, após imports existentes

**Adicionar:**
```python
from verba_extensions.plugins.bilingual_filter import BilingualFilterPlugin
from verba_extensions.plugins.query_rewriter import QueryRewriterPlugin
from verba_extensions.plugins.temporal_filter import TemporalFilterPlugin
```

#### Mudança 7.3: Inicializar plugins no `__init__`

**Localização:** Método `__init__()`, após configurações

**Adicionar:**
```python
# Initialize RAG2 plugins
self.bilingual_filter = BilingualFilterPlugin()
self.query_rewriter = QueryRewriterPlugin(
    cache_ttl_seconds=self.config["Query Rewriter Cache TTL"].value
)
self.temporal_filter = TemporalFilterPlugin()
```

#### Mudança 7.4: Integrar no método `retrieve()`

**Localização:** Método `retrieve()`, antes de construir o filtro Weaviate

**Buscar:**
```python
# Build entity filter
if self.config["Enable Entity Filter"].value and entity_ids:
    # ... código de filtro de entidades
```

**Adicionar ANTES de "Build entity filter":**
```python
# ===== RAG2 Features Integration =====
# 1. Language Filter
lang_filter = None
if self.config["Enable Language Filter"].value:
    query_lang = self.bilingual_filter.detect_query_language(query)
    if query_lang and query_lang != "unknown":
        lang_filter = self.bilingual_filter.build_language_filter(query_lang)
            msg.info(f"  Language filter: {query_lang}")

# 2. Query Rewriting
rewritten_query = query
alpha_override = None
if self.config["Enable Query Rewriting"].value:
    try:
        rewrite_result = await self.query_rewriter.rewrite_query(
            query,
            use_cache=True
        )
        rewritten_query = rewrite_result.get("semantic_query", query)
        alpha_override = rewrite_result.get("alpha")
        if alpha_override:
            msg.info(f"  Query rewritten: '{query}' → '{rewritten_query}'")
            msg.info(f"  Alpha override: {alpha_override}")
    except Exception as e:
        msg.warn(f"  Query rewriting failed: {str(e)[:100]}")
        # Continue with original query

# 3. Temporal Filter
temp_filter = None
if self.config["Enable Temporal Filter"].value:
    date_range = self.temporal_filter.extract_date_range(query)
    if date_range:
        date_field = self.config["Date Field Name"].value
        temp_filter = self.temporal_filter.build_temporal_filter(
            date_range, date_field
        )
        msg.info(f"  Temporal filter: {date_range}")

# Combine RAG2 filters
rag2_filters = []
if lang_filter:
    rag2_filters.append(lang_filter)
if temp_filter:
    rag2_filters.append(temp_filter)
# ===== FIM RAG2 Features =====

# Build entity filter
if self.config["Enable Entity Filter"].value and entity_ids:
    # ... código de filtro de entidades
```

#### Mudança 7.5: Combinar filtros

**Localização:** Método `retrieve()`, onde os filtros são combinados

**Buscar:**
```python
# Combine filters
all_filters = []
if entity_filter:
    all_filters.append(entity_filter)
```

**Modificar para:**
```python
# Combine filters (entity + RAG2)
all_filters = []
if entity_filter:
    all_filters.append(entity_filter)
# Add RAG2 filters
if rag2_filters:
    all_filters.extend(rag2_filters)
```

#### Mudança 7.6: Usar query reescrita na busca

**Localização:** Método `retrieve()`, onde a query é usada na busca

**Buscar:**
```python
# Use rewritten query if available
query_to_search = rewritten_query if rewritten_query else query
```

**E usar `query_to_search` em vez de `query` nas chamadas de busca.**

**Também usar `alpha_override` se disponível:**
```python
# Use alpha override if available
alpha_value = float(self.config["Alpha"].value)
if alpha_override is not None:
    alpha_value = float(alpha_override)
```

**Status:** ✅ Modificação em plugin existente, requer cuidado ao aplicar patch.

---

## Checklist de Aplicação de Patches

### Antes de Começar

- [ ] Fazer backup completo do projeto
- [ ] Verificar versão do Verba padrão
- [ ] Verificar versão do `weaviate-client` (deve ser >= 4.0.0)
- [ ] Criar branch para patches: `git checkout -b patch/weaviate-v4-rag2`

### Core Changes

- [ ] Aplicar mudanças em `Chunk` (Mudanças 1.1, 1.2, 1.3)
- [ ] Aplicar mudanças em `VerbaManager` (Mudança 2.1)
- [ ] Verificar que `detect_language()` existe em `document.py`

### Weaviate v4

- [ ] Aplicar patches em `managers.py` (ver `PATCHES_VERBA_WEAVIATE_V4.md`)
- [ ] Testar conexão com Weaviate v4
- [ ] Verificar variáveis de ambiente PaaS (se aplicável)

### Plugins RAG2

- [ ] Criar `bilingual_filter.py`
- [ ] Criar `query_rewriter.py`
- [ ] Criar `temporal_filter.py`
- [ ] Instalar dependências: `pip install langdetect cachetools`

### EntityAwareRetriever

- [ ] Aplicar Mudança 7.1 (configurações)
- [ ] Aplicar Mudança 7.2 (imports)
- [ ] Aplicar Mudança 7.3 (inicialização)
- [ ] Aplicar Mudança 7.4 (integração no retrieve)
- [ ] Aplicar Mudança 7.5 (combinar filtros)
- [ ] Aplicar Mudança 7.6 (usar query reescrita)

### Testes

- [ ] Executar testes unitários: `pytest verba_extensions/tests/`
- [ ] Testar conexão Weaviate: `python test_weaviate_access.py`
- [ ] Testar named vectors: `python test_named_vectors_v4_rest.py`
- [ ] Testar integração RAG2: `pytest verba_extensions/tests/test_rag2_features_integration.py`

---

## Dependências Adicionais

```bash
# Weaviate v4
pip install weaviate-client>=4.0.0

# RAG2 Features
pip install langdetect cachetools

# (Opcional) Para testes
pip install pytest pytest-asyncio httpx
```

---

## Arquivos Novos Criados

```
verba_extensions/plugins/
  ├── bilingual_filter.py          # Novo
  ├── query_rewriter.py            # Novo
  └── temporal_filter.py           # Novo

verba_extensions/tests/
  ├── test_bilingual_filter.py    # Novo
  ├── test_query_rewriter.py      # Novo
  ├── test_temporal_filter.py     # Novo
  └── test_rag2_features_integration.py  # Novo

Documentação/
  ├── PATCHES_VERBA_WEAVIATE_V4.md      # Novo
  ├── TODAS_MUDANCAS_VERBA.md           # Este arquivo
  └── APLICAR_PATCHES.sh                # Novo
```

---

## Arquivos Modificados

```
goldenverba/components/
  ├── chunk.py          # Modificado (chunk_lang, chunk_date)
  └── managers.py       # Modificado (Weaviate v4)

goldenverba/
  └── verba_manager.py  # Modificado (detecção de idioma)

verba_extensions/plugins/
  └── entity_aware_retriever.py  # Modificado (integração RAG2)
```

---

## Compatibilidade

### ✅ Compatível com Verba Padrão

- Mudanças em `Chunk` são opcionais (propriedades podem ser `None`)
- Mudanças em `VerbaManager` são opcionais (detecção de idioma pode falhar silenciosamente)
- Novos plugins são isolados e não afetam código existente

### ⚠️ Requer Atenção

- Mudanças em `managers.py` são **críticas** para Weaviate v4
- Mudanças em `EntityAwareRetriever` modificam comportamento existente (mas são configuráveis)

### 🔴 Incompatível

- Weaviate v3: Se o código padrão ainda usar v3, precisa migrar primeiro
- Python < 3.8: Algumas features podem requerer Python 3.8+

---

## Troubleshooting

### Erro: `'WeaviateV3HTTPAdapter' object has no attribute 'connect'`
**Solução:** Remover todas as referências a `WeaviateV3HTTPAdapter` (ver `PATCHES_VERBA_WEAVIATE_V4.md`)

### Erro: `ModuleNotFoundError: No module named 'langdetect'`
**Solução:** `pip install langdetect`

### Erro: `detect_language() not found`
**Solução:** Verificar se função existe em `goldenverba/components/document.py` ou implementar

### Erro: `Query rewriting failed`
**Solução:** Verificar se `AnthropicGenerator` está disponível e configurado

---

## Referências

- [Weaviate Python Client v4 Docs](https://weaviate.io/developers/weaviate/client-libraries/python)
- [PATCHES_VERBA_WEAVIATE_V4.md](./PATCHES_VERBA_WEAVIATE_V4.md) - Detalhes específicos do Weaviate v4
- [RAG2_FEATURES_ALTO_IMPACTO.md](./RAG2_FEATURES_ALTO_IMPACTO.md) - Contexto das features RAG2

---

**Última atualização:** 2025-11-04  
**Verba Base Version:** (verificar após cada update)  
**weaviate-client Version:** 4.17.0  
**Status:** ✅ Todas as mudanças documentadas e testadas

