# 🚀 Guia de Integração: Componentes RAG2 → Verba

Este guia mostra como integrar os componentes de alto valor copiados do RAG2 para o Verba.

---

## 📋 Componentes Disponíveis

1. ✅ **TelemetryMiddleware** - Observabilidade de API
2. ✅ **Embeddings Cache** - Cache de embeddings
3. ✅ **Telemetry Collector** - Métricas de ETL
4. ✅ **UUID Determinístico** - Idempotência
5. ✅ **Text Preprocessing** - Normalização de texto
6. ✅ **Quality Scoring** - Filtro de qualidade

---

## 1. TelemetryMiddleware (Observabilidade)

### O que faz
Middleware FastAPI que registra latência, contagem de requests e erros por endpoint.

### Como integrar

**Passo 1**: Adicionar middleware em `goldenverba/server/api.py`:

```python
from verba_extensions.middleware.telemetry import TelemetryMiddleware

# Adicionar ANTES de outras rotas
app.add_middleware(TelemetryMiddleware, enable_logging=True)
```

**Passo 2**: Adicionar endpoint para stats (opcional):

```python
from verba_extensions.middleware.telemetry import TelemetryMiddleware

@app.get("/api/telemetry/stats")
async def get_telemetry_stats():
    """Retorna estatísticas de telemetria da API"""
    return TelemetryMiddleware.get_shared_stats()

@app.get("/api/telemetry/slo")
async def check_slo(threshold_ms: float = 350.0):
    """Verifica se SLO está sendo atendido"""
    is_ok, details = TelemetryMiddleware.check_shared_slo(threshold_ms)
    return {
        "is_ok": is_ok,
        **details
    }
```

### Resultado
- Logs estruturados em JSON para cada request
- Métricas de latência (p50, p95, p99)
- Estatísticas por endpoint
- SLO checking automático

---

## 2. Embeddings Cache (Performance)

### O que faz
Cache in-memory determinístico de embeddings para evitar re-embedding redundante.

### Como integrar

**Passo 1**: Importar em embedders (ex: `goldenverba/components/embedding/OpenAIEmbedder.py`):

```python
from verba_extensions.utils.embeddings_cache import (
    get_cached_embedding,
    get_cache_key,
    get_cache_stats
)
```

**Passo 2**: Usar cache antes de chamar API de embedding:

```python
def embed(self, documents, client, logging):
    # ... código existente ...
    
    for doc in documents:
        for chunk in doc.chunks:
            # Gera chave de cache
            cache_key = get_cache_key(
                text=chunk.text,
                doc_uuid=str(doc.uuid),
                parent_type="chunk"
            )
            
            # Obtém embedding com cache
            embedding, was_cached = get_cached_embedding(
                text=chunk.text,
                cache_key=cache_key,
                embed_fn=lambda t: self._call_openai_api(t)  # Sua função de embedding
            )
            
            # Usa embedding normalmente
            # ... resto do código ...
```

**Passo 3** (Opcional): Adicionar endpoint para stats:

```python
from verba_extensions.utils.embeddings_cache import get_cache_stats

@app.get("/api/embeddings/cache/stats")
async def get_embeddings_cache_stats():
    """Retorna estatísticas do cache de embeddings"""
    return get_cache_stats()
```

### Resultado
- Redução de chamadas de embedding (especialmente em re-uploads)
- Economia de custo de APIs
- Melhor performance

---

## 3. Telemetry Collector (Métricas ETL)

### O que faz
Coleta métricas de normalização e cobertura para identificar gaps e melhorias.

### Como integrar

**Passo 1**: Usar em plugins de ETL (ex: `verba_extensions/plugins/llm_metadata_extractor.py`):

```python
from verba_extensions.utils.telemetry import get_telemetry

telemetry = get_telemetry()

# Ao normalizar título
telemetry.record_title_normalization(
    method="regex",  # ou "llm", "none", etc.
    original_title="CEO"
)

# Ao normalizar skill
telemetry.record_skill_normalization(
    was_mapped=True,
    original_skill="Python"
)

# Ao filtrar chunk por qualidade
telemetry.record_chunk_filtered_by_quality(
    parent_type="section",
    score=0.25,
    reason="LEN_V_SHORT:DENSITY_LOW"
)
```

**Passo 2**: Adicionar endpoint para relatório:

```python
from verba_extensions.utils.telemetry import get_telemetry

@app.get("/api/etl/telemetry")
async def get_etl_telemetry():
    """Retorna relatório de telemetria de ETL"""
    return get_telemetry().generate_report()

@app.post("/api/etl/telemetry/reset")
async def reset_etl_telemetry():
    """Reseta coletor de telemetria"""
    get_telemetry().reset()
    return {"status": "reset"}
```

### Resultado
- Identificação de gaps em normalização
- Métricas de cobertura
- Relatórios JSON para análise

---

## 4. UUID Determinístico (Idempotência)

### O que faz
Gera UUIDs determinísticos (UUID v5) para garantir idempotência em re-uploads.

### Como integrar

**Passo 1**: Usar em import de documentos:

```python
from verba_extensions.utils.uuid import generate_doc_uuid, generate_chunk_uuid

# Ao importar documento
doc_uuid = generate_doc_uuid(
    source_url=document.meta.get("source_url"),
    public_identifier=document.meta.get("public_id"),
    title=document.title
)

# Ao criar chunks
chunk_uuid = generate_chunk_uuid(
    doc_uuid=doc_uuid,
    chunk_id=f"{doc_uuid}:{chunk.chunk_id}"
)
```

**Resultado**
- Re-uploads não criam duplicatas
- Upsert seguro
- Idempotência garantida

---

## 5. Text Preprocessing (Consistência)

### O que faz
Normaliza texto antes de embedding para garantir consistência.

### Como integrar

**Passo 1**: Usar antes de embedding:

```python
from verba_extensions.utils.preprocess import prepare_for_embedding

# Antes de embed
text_for_embedding = prepare_for_embedding(chunk.text)

# Garante que texto embeddado = texto armazenado
assert chunk.text == text_for_embedding

# Agora faz embedding
embedding = embedder.embed(text_for_embedding)
```

**Resultado**
- Consistência entre texto armazenado e embeddado
- Melhor qualidade de embeddings

---

## 6. Quality Scoring (Filtro de Qualidade)

### O que faz
Calcula score de qualidade de chunks para filtrar conteúdo de baixa qualidade.

### Como integrar

**Passo 1**: Usar em chunkers ou filtros:

```python
from verba_extensions.utils.quality import compute_quality_score

# Ao processar chunk
score, reason = compute_quality_score(
    text=chunk.text,
    parent_type=chunk.meta.get("parent_type"),
    is_summary=chunk.meta.get("is_summary", False)
)

# Filtrar chunks de baixa qualidade
if score < 0.3:  # Threshold configurável
    # Opcional: registrar na telemetria
    from verba_extensions.utils.telemetry import get_telemetry
    get_telemetry().record_chunk_filtered_by_quality(
        parent_type=chunk.meta.get("parent_type", "unknown"),
        score=score,
        reason=reason
    )
    continue  # Pula chunk
```

**Resultado**
- Filtragem automática de conteúdo de baixa qualidade
- Melhor qualidade de resultados de busca

---

## 📊 Exemplo de Integração Completa

### `goldenverba/server/api.py`:

```python
from fastapi import FastAPI
from verba_extensions.middleware.telemetry import TelemetryMiddleware

app = FastAPI()

# Middleware de telemetria
app.add_middleware(TelemetryMiddleware, enable_logging=True)

# Endpoints de telemetria
@app.get("/api/telemetry/stats")
async def get_telemetry_stats():
    return TelemetryMiddleware.get_shared_stats()

@app.get("/api/embeddings/cache/stats")
async def get_embeddings_cache_stats():
    from verba_extensions.utils.embeddings_cache import get_cache_stats
    return get_cache_stats()

@app.get("/api/etl/telemetry")
async def get_etl_telemetry():
    from verba_extensions.utils.telemetry import get_telemetry
    return get_telemetry().generate_report()
```

### `goldenverba/components/embedding/OpenAIEmbedder.py`:

```python
from verba_extensions.utils.embeddings_cache import get_cached_embedding, get_cache_key
from verba_extensions.utils.preprocess import prepare_for_embedding

def embed(self, documents, client, logging):
    for doc in documents:
        for chunk in doc.chunks:
            # Normaliza texto
            text_for_embedding = prepare_for_embedding(chunk.text)
            
            # Cache key
            cache_key = get_cache_key(
                text=text_for_embedding,
                doc_uuid=str(doc.uuid),
                parent_type="chunk"
            )
            
            # Embed com cache
            embedding, was_cached = get_cached_embedding(
                text=text_for_embedding,
                cache_key=cache_key,
                embed_fn=lambda t: self._call_openai_api(t)
            )
            
            # ... resto do código ...
```

---

## ✅ Checklist de Integração

- [ ] TelemetryMiddleware adicionado em `api.py`
- [ ] Endpoints de telemetria criados
- [ ] Embeddings Cache integrado em embedders
- [ ] Text Preprocessing usado antes de embedding
- [ ] Quality Scoring usado em filtros (opcional)
- [ ] Telemetry Collector usado em plugins ETL (opcional)
- [ ] UUID Determinístico usado em imports (opcional)
- [ ] Testes realizados em ambiente de desenvolvimento

---

## 🔍 Verificação

Após integrar, verifique:

1. **TelemetryMiddleware**: Logs devem aparecer com `[TELEMETRY]`
2. **Embeddings Cache**: Stats devem mostrar `hit_rate > 0` em re-uploads
3. **Quality Scoring**: Chunks de baixa qualidade devem ser filtrados
4. **Text Preprocessing**: Textos devem estar normalizados

---

## 📝 Notas

- Todos os componentes são **opcionais** e podem ser integrados gradualmente
- **TelemetryMiddleware** e **Embeddings Cache** são os mais críticos
- Componentes são **independentes** - você pode usar apenas alguns
- **Sem dependências externas** - apenas bibliotecas padrão Python

---

**Próximos Passos**: 
1. Integrar TelemetryMiddleware (mais crítico)
2. Integrar Embeddings Cache (maior impacto em performance)
3. Adicionar outros componentes conforme necessidade

