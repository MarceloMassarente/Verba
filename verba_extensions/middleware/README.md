# 🔧 Middleware Components

Middleware components para observabilidade e monitoramento da API Verba.

## 📋 Componentes

### TelemetryMiddleware

**Arquivo:** `telemetry.py`

**Descrição:**
Middleware FastAPI que registra métricas de performance por request, incluindo latência, contagem de requests, erros e estatísticas por endpoint.

**Características:**
- ✅ Registra latência de cada request em milissegundos
- ✅ Calcula percentis automaticamente (p50, p95, p99)
- ✅ Log estruturado em JSON
- ✅ Métricas compartilhadas entre instâncias (singleton pattern)
- ✅ SLO checking (verifica se p95 < threshold)
- ✅ Rolling window (mantém últimas 1000 latências)

**Uso:**

```python
from verba_extensions.middleware.telemetry import TelemetryMiddleware
from fastapi import FastAPI

app = FastAPI()

# Adiciona middleware
app.add_middleware(TelemetryMiddleware, enable_logging=True)

# Endpoint opcional para stats
@app.get("/api/telemetry/stats")
async def get_telemetry_stats():
    return TelemetryMiddleware.get_shared_stats()

# Verificar SLO
@app.get("/api/telemetry/slo")
async def check_slo(threshold_ms: float = 350.0):
    is_ok, details = TelemetryMiddleware.check_shared_slo(threshold_ms)
    return {"is_ok": is_ok, **details}
```

**Métricas retornadas:**
- `requests`: Total de requests processados
- `errors`: Total de erros
- `latency_p50_ms`: Latência p50 (mediana)
- `latency_p95_ms`: Latência p95
- `latency_p99_ms`: Latência p99
- `by_endpoint`: Estatísticas por endpoint

**Headers adicionados:**
- `X-Request-Latency-MS`: Latência do request atual

**Logs:**
- `[TELEMETRY]`: Log estruturado de cada request (JSON)
- `[TELEMETRY_ERROR]`: Log de erros estruturados

**Documentação completa:** `GUIA_INTEGRACAO_RAG2_COMPONENTES.md`

---

## 📝 Notas

- Middleware é **thread-safe** (usa variáveis de classe compartilhadas)
- Mantém apenas últimas 1000 latências para evitar consumo excessivo de memória
- Logs são enviados para stdout (pode ser redirecionado para arquivo ou sistema de logs)

