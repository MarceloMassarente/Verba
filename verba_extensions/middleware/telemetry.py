"""
Middleware de telemetria para observabilidade de performance (SLO).

Registra latência, custo e métricas operacionais por request da API Verba.
Adaptado do RAG2 para Verba.

Features:
- Registra latência de cada request em milissegundos
- Calcula percentis automaticamente (p50, p95, p99)
- Log estruturado em JSON
- Métricas compartilhadas entre instâncias (singleton pattern)
- SLO checking (verifica se p95 < threshold)
- Rolling window (mantém últimas 1000 latências)

Uso:
    from verba_extensions.middleware.telemetry import TelemetryMiddleware
    from fastapi import FastAPI
    
    app = FastAPI()
    app.add_middleware(TelemetryMiddleware, enable_logging=True)
    
    # Endpoint opcional para stats
    @app.get("/api/telemetry/stats")
    async def get_telemetry_stats():
        return TelemetryMiddleware.get_shared_stats()

Exemplo de log:
    [TELEMETRY] {"timestamp": "2024-11-04T10:00:00Z", "method": "GET", 
                 "endpoint": "/api/query", "status_code": 200, 
                 "latency_ms": 123.45}

Exemplo de stats:
    {
        "requests": 1000,
        "errors": 5,
        "latency_p50_ms": 120.0,
        "latency_p95_ms": 350.0,
        "latency_p99_ms": 500.0,
        "by_endpoint": {
            "/api/query": {
                "count": 500,
                "errors": 2,
                "latency_p50_ms": 110.0,
                "latency_p95_ms": 300.0
            }
        }
    }

Documentação completa: GUIA_INTEGRACAO_RAG2_COMPONENTES.md
"""
import time
import json
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from collections import defaultdict
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class TelemetryMiddleware(BaseHTTPMiddleware):
    """
    Middleware que registra métricas de performance por request.
    Usa variáveis de classe para compartilhar métricas entre instâncias.
    """
    # Variáveis de classe compartilhadas (singleton pattern)
    _shared_metrics = {
        "requests": 0,
        "errors": 0,
        "latencies": [],
        "by_endpoint": defaultdict(lambda: {
            "count": 0,
            "latencies": [],
            "errors": 0
        })
    }
    
    def __init__(self, app, enable_logging: bool = True):
        super().__init__(app)
        self.enable_logging = enable_logging
        # Usa as métricas compartilhadas da classe
        self.metrics = TelemetryMiddleware._shared_metrics
    
    async def dispatch(self, request: Request, call_next):
        """
        Intercepta request, mede latência e registra métricas.
        """
        start_time = time.time()
        endpoint = request.url.path
        
        try:
            response = await call_next(request)
            
            # Mede latência em ms
            latency_ms = (time.time() - start_time) * 1000
            
            # Registra métricas
            self.metrics["requests"] += 1
            self.metrics["latencies"].append(latency_ms)
            self.metrics["by_endpoint"][endpoint]["count"] += 1
            self.metrics["by_endpoint"][endpoint]["latencies"].append(latency_ms)
            
            # Mantém apenas últimas 1000 latências (rolling window)
            if len(self.metrics["latencies"]) > 1000:
                self.metrics["latencies"] = self.metrics["latencies"][-1000:]
            
            # Log estruturado (JSON)
            if self.enable_logging:
                self._log_request(request, response, latency_ms)
            
            # Adiciona header com métricas se necessário
            response.headers["X-Request-Latency-MS"] = f"{latency_ms:.2f}"
            
            return response
            
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self.metrics["errors"] += 1
            self.metrics["by_endpoint"][endpoint]["errors"] += 1
            
            if self.enable_logging:
                self._log_error(request, e, latency_ms)
            
            raise
    
    def _log_request(self, request: Request, response: Response, latency_ms: float):
        """
        Log estruturado de request (JSON).
        """
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "method": request.method,
            "endpoint": request.url.path,
            "status_code": response.status_code,
            "latency_ms": round(latency_ms, 2),
            "query_params": dict(request.query_params) if request.query_params else None
        }
        
        print(f"[TELEMETRY] {json.dumps(log_entry)}")
    
    def _log_error(self, request: Request, error: Exception, latency_ms: float):
        """
        Log de erro estruturado.
        """
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "method": request.method,
            "endpoint": request.url.path,
            "error": str(error),
            "error_type": type(error).__name__,
            "latency_ms": round(latency_ms, 2)
        }
        
        print(f"[TELEMETRY_ERROR] {json.dumps(log_entry)}")
    
    @classmethod
    def get_shared_stats(cls) -> Dict[str, Any]:
        """
        Método de classe para obter estatísticas sem precisar de instância.
        """
        latencies = cls._shared_metrics["latencies"]
        
        if not latencies:
            return {
                "requests": 0,
                "errors": 0,
                "latency_p50_ms": 0.0,
                "latency_p95_ms": 0.0,
                "latency_p99_ms": 0.0,
                "by_endpoint": {}
            }
        
        sorted_latencies = sorted(latencies)
        n = len(sorted_latencies)
        
        def percentile(p: float) -> float:
            idx = int(n * p)
            return sorted_latencies[min(idx, n - 1)]
        
        stats = {
            "requests": cls._shared_metrics["requests"],
            "errors": cls._shared_metrics["errors"],
            "latency_p50_ms": round(percentile(0.50), 2),
            "latency_p95_ms": round(percentile(0.95), 2),
            "latency_p99_ms": round(percentile(0.99), 2),
            "by_endpoint": {}
        }
        
        # Stats por endpoint
        for endpoint, data in cls._shared_metrics["by_endpoint"].items():
            endpoint_latencies = data["latencies"]
            if endpoint_latencies:
                sorted_ep = sorted(endpoint_latencies)
                ep_n = len(sorted_ep)
                ep_p50 = sorted_ep[int(ep_n * 0.50)] if ep_n > 0 else 0
                ep_p95 = sorted_ep[int(ep_n * 0.95)] if ep_n > 0 else 0
                
                stats["by_endpoint"][endpoint] = {
                    "count": data["count"],
                    "errors": data["errors"],
                    "latency_p50_ms": round(ep_p50, 2),
                    "latency_p95_ms": round(ep_p95, 2)
                }
        
        return stats
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Retorna estatísticas agregadas (usa método de classe).
        """
        return TelemetryMiddleware.get_shared_stats()
    
    @classmethod
    def check_shared_slo(cls, p95_threshold_ms: float = 350.0) -> tuple[bool, Dict[str, Any]]:
        """
        Verifica se SLO está sendo atendido (método de classe).
        
        Args:
            p95_threshold_ms: Limiar de p95 em ms (padrão 350ms)
            
        Returns:
            Tuple: (is_ok: bool, details: dict)
        """
        stats = cls.get_shared_stats()
        p95 = stats.get("latency_p95_ms", 0.0)
        
        is_ok = p95 < p95_threshold_ms
        
        details = {
            "p95_ms": p95,
            "threshold_ms": p95_threshold_ms,
            "is_ok": is_ok,
            "alert": not is_ok
        }
        
        return is_ok, details

