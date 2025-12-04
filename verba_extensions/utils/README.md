# 🛠️ Utility Modules

Utilitários de alto valor e baixa complexidade copiados do RAG2 para melhorar observabilidade, performance e qualidade do Verba.

## 📋 Componentes

### 1. Embeddings Cache ⭐ CRÍTICO

**Arquivo:** `embeddings_cache.py`

**Descrição:**
Cache in-memory determinístico de embeddings para evitar re-embedding redundante. Reduz drasticamente chamadas de APIs de embedding e melhora performance.

**Características:**
- ✅ Cache determinístico baseado em hash do texto
- ✅ Estatísticas de hit rate
- ✅ Thread-safe (cache global compartilhado)
- ✅ Opcional (pode ser desabilitado)

**Uso:**

```python
from verba_extensions.utils.embeddings_cache import (
    get_cached_embedding,
    get_cache_key,
    get_cache_stats,
    clear_cache
)

# Gerar chave de cache
cache_key = get_cache_key(
    text=chunk.text,
    doc_uuid=str(doc.uuid),
    parent_type="chunk"
)

# Obter embedding com cache
embedding, was_cached = get_cached_embedding(
    text=chunk.text,
    cache_key=cache_key,
    embed_fn=lambda t: self._call_embedding_api(t),
    enable_cache=True
)

# Verificar estatísticas
stats = get_cache_stats()
print(f"Hit rate: {stats['hit_rate']:.2f}%")
```

**Impacto esperado:**
- Redução de 50-90% em chamadas de embedding em re-uploads
- Economia de custo de APIs (OpenAI, Cohere, etc.)
- Melhoria de performance (especialmente em processamento batch)

---

### 2. Telemetry Collector

**Arquivo:** `telemetry.py`

**Descrição:**
Coletor de telemetria para métricas de normalização e cobertura. Identifica gaps em mapeamentos e gera relatórios para melhoria contínua.

**Características:**
- ✅ Rastreia métodos de normalização (títulos, skills, companies)
- ✅ Identifica termos não mapeados (gaps)
- ✅ Gera relatórios JSON
- ✅ Estatísticas de qualidade de chunks

**Uso:**

```python
from verba_extensions.utils.telemetry import get_telemetry

telemetry = get_telemetry()

# Registrar normalização de título
telemetry.record_title_normalization(
    method="regex",  # ou "llm", "none", etc.
    original_title="CEO"
)

# Registrar skill não mapeada
telemetry.record_skill_normalization(
    was_mapped=False,
    original_skill="Python"
)

# Registrar chunk filtrado por qualidade
telemetry.record_chunk_filtered_by_quality(
    parent_type="section",
    score=0.25,
    reason="LEN_V_SHORT:DENSITY_LOW"
)

# Gerar relatório
report = telemetry.generate_report()
telemetry.save_report("telemetry_report.json")
```

**Relatório inclui:**
- Cobertura de normalização de títulos por método
- Top 20 termos não mapeados
- Distribuição de proveniência de company_id
- Estatísticas de chunks filtrados por qualidade

---

### 3. UUID Determinístico

**Arquivo:** `uuid.py`

**Descrição:**
Gera UUIDs determinísticos (UUID v5) para garantir idempotência em re-uploads e upserts seguros.

**Características:**
- ✅ UUID v5 baseado em namespace + identificador
- ✅ Determinístico: mesmo input = mesmo UUID
- ✅ Idempotência garantida

**Uso:**

```python
from verba_extensions.utils.uuid import (
    generate_doc_uuid,
    generate_chunk_uuid,
    generate_chunk_uuid_by_type
)

# UUID para documento
doc_uuid = generate_doc_uuid(
    source_url=doc.meta.get("source_url"),
    public_identifier=doc.meta.get("public_id"),
    title=doc.title
)

# UUID para chunk
chunk_uuid = generate_chunk_uuid(
    doc_uuid=doc_uuid,
    chunk_id=f"{doc_uuid}:{chunk.chunk_id}"
)

# UUID para chunk com tipo (múltiplos vetores)
role_uuid = generate_chunk_uuid_by_type(
    doc_uuid=doc_uuid,
    vec_type="role",
    chunk_id=f"{doc_uuid}:{chunk.chunk_id}"
)
```

**Benefícios:**
- Re-uploads não criam duplicatas
- Upsert seguro (mesmo documento sempre tem mesmo UUID)
- Idempotência garantida

---

### 4. Text Preprocessing

**Arquivo:** `preprocess.py`

**Descrição:**
Utilitários para pré-processamento consistente de texto antes de embedding. Garante que texto embeddado é idêntico ao texto armazenado.

**Características:**
- ✅ Remove unicode invisível (zero-width spaces, etc.)
- ✅ Normaliza whitespace
- ✅ Truncamento semântico (preserva boundaries naturais)
- ✅ Validação de consistência

**Uso:**

```python
from verba_extensions.utils.preprocess import (
    prepare_for_embedding,
    validate_text_for_embedding,
    truncate_semantic
)

# Normalizar texto antes de embedding
text_for_embedding = prepare_for_embedding(chunk.text)

# Garantir consistência
is_valid, error = validate_text_for_embedding(
    text_stored=chunk.text,
    text_embedded=text_for_embedding
)

# Truncar semanticamente (preserva sentenças)
truncated = truncate_semantic(
    text="Texto muito longo...",
    max_chars=200,
    ellipsis="…"
)
```

**Benefícios:**
- Consistência entre texto armazenado e embeddado
- Melhor qualidade de embeddings (texto normalizado)
- Evita problemas de encoding

---

### 5. Quality Scoring

**Arquivo:** `quality.py`

**Descrição:**
Calcula score de qualidade de chunks para filtrar conteúdo de baixa qualidade automaticamente.

**Características:**
- ✅ Score de 0.0 a 1.0
- ✅ Type-aware (diferentes thresholds por tipo)
- ✅ Proteção de summaries (nunca descartados)
- ✅ Detecção de login walls e placeholders

**Uso:**

```python
from verba_extensions.utils.quality import compute_quality_score

# Calcular score
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

**Fatores considerados:**
- Comprimento do texto (200-3000 chars ideal)
- Densidade alfanumérica (>= 0.55 ideal)
- Detecção de login walls
- Detecção de placeholders
- Type-aware boost (experiências curtas são aceitas)

**Benefícios:**
- Filtragem automática de conteúdo de baixa qualidade
- Melhor qualidade de resultados de busca
- Redução de ruído nos resultados

---

### 6. Language Utils ⭐ NOVO (2025-01)

**Arquivo:** `language_utils.py`

**Descrição:**
Módulo utilitário comum que consolida código duplicado de detecção de idioma e NLP de múltiplos plugins. Elimina ~40% de código duplicado e fornece interface unificada.

**Características:**
- ✅ Detecção de idioma unificada (`detect_query_language()`)
- ✅ Cache global de modelos spaCy (`get_nlp()`)
- ✅ Stopwords PT/EN como constantes globais
- ✅ Lazy loading de modelos NLP
- ✅ Fallback gracioso se modelos não disponíveis

**Uso:**

```python
from verba_extensions.utils.language_utils import (
    detect_query_language,
    get_nlp,
    STOPWORDS_PT,
    STOPWORDS_EN,
    get_stopwords
)

# Detectar idioma
language = detect_query_language("O que é inovação?")
# Retorna: "pt"

# Carregar modelo NLP (com cache global)
nlp = get_nlp(language="pt")
if nlp:
    doc = nlp("Apple é uma empresa")
    entities = [ent.text for ent in doc.ents]

# Usar stopwords
stopwords = get_stopwords("pt")
filtered = [w for w in words if w not in stopwords]
```

**Plugins que usam:**
- `entity_aware_query_orchestrator.py`
- `a2_etl_hook.py`
- `bilingual_filter.py`
- `adaptive_entropy.py`
- `query_rewriter.py`

**Benefícios:**
- Elimina código duplicado em 5+ plugins
- Cache global eficiente (modelos carregados uma vez)
- Implementação consistente em todos os plugins
- Manutenção fácil (mudanças em um lugar)

**Documentação completa:** `docs/utils/LANGUAGE_UTILS.md`

---

## 📊 Comparação de Componentes

| Componente | Impacto Performance | Impacto Qualidade | Impacto Observabilidade | Complexidade |
|------------|---------------------|-------------------|-------------------------|--------------|
| Embeddings Cache | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐ |
| Telemetry Collector | ⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| UUID Determinístico | ⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ |
| Text Preprocessing | ⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐ |
| Quality Scoring | ⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐ |
| Language Utils | ⭐⭐ | ⭐⭐ | ⭐ | ⭐ |

---

## 🔗 Documentação Relacionada

- `ANALISE_RAG2_COMPONENTES_ALTO_VALOR.md` - Análise detalhada dos componentes
- `GUIA_INTEGRACAO_RAG2_COMPONENTES.md` - Guia de integração passo a passo
- `README_EXTENSOES.md` - Documentação geral das extensões

---

## ✅ Checklist de Integração

- [ ] Embeddings Cache integrado em embedders
- [ ] Text Preprocessing usado antes de embedding
- [ ] Quality Scoring usado em filtros (opcional)
- [ ] Telemetry Collector usado em plugins ETL (opcional)
- [ ] UUID Determinístico usado em imports (opcional)
- [ ] Testes realizados em ambiente de desenvolvimento

---

## 📝 Notas

- Todos os componentes são **opcionais** e podem ser integrados gradualmente
- **Embeddings Cache** tem maior impacto em performance
- Componentes são **independentes** - você pode usar apenas alguns
- **Sem dependências externas** - apenas bibliotecas padrão Python
- Componentes são **thread-safe** quando necessário

