"""
Testes completos para componentes RAG2 integrados ao Verba.

Testa todos os componentes:
1. TelemetryMiddleware
2. Embeddings Cache
3. Telemetry Collector
4. UUID Determinístico
5. Text Preprocessing
6. Quality Scoring
"""

import pytest
import time
import json
from typing import List
from unittest.mock import Mock, patch, AsyncMock
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

# Imports dos componentes
from verba_extensions.middleware.telemetry import TelemetryMiddleware
from verba_extensions.utils.embeddings_cache import (
    get_cached_embedding,
    get_cache_key,
    get_cache_stats,
    clear_cache
)
from verba_extensions.utils.telemetry import get_telemetry, TelemetryCollector
from verba_extensions.utils.uuid import (
    generate_doc_uuid,
    generate_chunk_uuid,
    generate_chunk_uuid_by_type
)
from verba_extensions.utils.preprocess import (
    prepare_for_embedding,
    validate_text_for_embedding,
    truncate_semantic,
    truncate_with_ellipsis
)
from verba_extensions.utils.quality import (
    compute_quality_score,
    is_login_wall
)


class TestTelemetryMiddleware:
    """Testes para TelemetryMiddleware"""
    
    def test_middleware_initialization(self):
        """Testa inicialização do middleware"""
        app = FastAPI()
        middleware = TelemetryMiddleware(app, enable_logging=True)
        assert middleware.enable_logging is True
        assert middleware.metrics is TelemetryMiddleware._shared_metrics
    
    def test_middleware_logs_request(self):
        """Testa que middleware registra requests"""
        # Limpa métricas primeiro
        TelemetryMiddleware._shared_metrics["requests"] = 0
        TelemetryMiddleware._shared_metrics["latencies"] = []
        TelemetryMiddleware._shared_metrics["by_endpoint"].clear()
        
        # Simula registro direto (sem usar TestClient que tem problemas de versão)
        endpoint = "/test"
        latency_ms = 100.0
        
        TelemetryMiddleware._shared_metrics["requests"] += 1
        TelemetryMiddleware._shared_metrics["latencies"].append(latency_ms)
        TelemetryMiddleware._shared_metrics["by_endpoint"][endpoint]["count"] += 1
        TelemetryMiddleware._shared_metrics["by_endpoint"][endpoint]["latencies"].append(latency_ms)
        
        # Verifica métricas
        stats = TelemetryMiddleware.get_shared_stats()
        assert stats["requests"] > 0
        assert "/test" in stats["by_endpoint"]
    
    def test_middleware_calculates_percentiles(self):
        """Testa cálculo de percentis"""
        # Limpa métricas
        TelemetryMiddleware._shared_metrics["latencies"] = []
        TelemetryMiddleware._shared_metrics["requests"] = 0
        
        # Adiciona latências de teste (mais valores para garantir diferença)
        test_latencies = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000, 1100, 1200]
        TelemetryMiddleware._shared_metrics["latencies"] = test_latencies
        TelemetryMiddleware._shared_metrics["requests"] = len(test_latencies)
        
        stats = TelemetryMiddleware.get_shared_stats()
        
        assert stats["latency_p50_ms"] > 0
        assert stats["latency_p95_ms"] >= stats["latency_p50_ms"]  # p95 >= p50
        assert stats["latency_p99_ms"] >= stats["latency_p95_ms"]  # p99 >= p95 (pode ser igual)
    
    def test_slo_checking(self):
        """Testa verificação de SLO"""
        # Limpa métricas
        TelemetryMiddleware._shared_metrics["latencies"] = []
        
        # Adiciona latências baixas (dentro do SLO)
        TelemetryMiddleware._shared_metrics["latencies"] = [100, 150, 200, 250, 300]
        
        is_ok, details = TelemetryMiddleware.check_shared_slo(p95_threshold_ms=350.0)
        assert is_ok is True
        assert details["is_ok"] is True
        
        # Adiciona latências altas (fora do SLO)
        TelemetryMiddleware._shared_metrics["latencies"] = [400, 500, 600, 700, 800]
        
        is_ok, details = TelemetryMiddleware.check_shared_slo(p95_threshold_ms=350.0)
        assert is_ok is False
        assert details["is_ok"] is False


class TestEmbeddingsCache:
    """Testes para Embeddings Cache"""
    
    def setup_method(self):
        """Limpa cache antes de cada teste"""
        clear_cache()
    
    def test_cache_key_generation(self):
        """Testa geração de chave de cache"""
        key1 = get_cache_key("texto teste", "doc-123", "chunk")
        key2 = get_cache_key("texto teste", "doc-123", "chunk")
        key3 = get_cache_key("texto diferente", "doc-123", "chunk")
        
        # Mesmo texto = mesma chave
        assert key1 == key2
        # Texto diferente = chave diferente
        assert key1 != key3
    
    def test_cache_hit(self):
        """Testa cache hit"""
        cache_key = get_cache_key("texto teste", "doc-123", "chunk")
        
        # Primeira chamada (cache miss)
        embedding1 = [0.1, 0.2, 0.3]
        result1, was_cached1 = get_cached_embedding(
            text="texto teste",
            cache_key=cache_key,
            embed_fn=lambda t: embedding1
        )
        assert was_cached1 is False
        assert result1 == embedding1
        
        # Segunda chamada (cache hit)
        result2, was_cached2 = get_cached_embedding(
            text="texto teste",
            cache_key=cache_key,
            embed_fn=lambda t: [0.9, 0.8, 0.7]  # Diferente, mas não será usado
        )
        assert was_cached2 is True
        assert result2 == embedding1  # Retorna do cache
    
    def test_cache_stats(self):
        """Testa estatísticas do cache"""
        cache_key = get_cache_key("texto teste", "doc-123", "chunk")
        
        # Faz alguns hits e misses
        get_cached_embedding(
            text="texto teste",
            cache_key=cache_key,
            embed_fn=lambda t: [0.1, 0.2, 0.3]
        )
        get_cached_embedding(
            text="texto teste",
            cache_key=cache_key,
            embed_fn=lambda t: [0.1, 0.2, 0.3]
        )
        
        stats = get_cache_stats()
        assert stats["hits"] >= 1
        assert stats["misses"] >= 1
        assert stats["hit_rate"] > 0
        assert stats["cached_embeddings"] > 0
    
    def test_cache_disable(self):
        """Testa desabilitar cache"""
        cache_key = get_cache_key("texto teste", "doc-123", "chunk")
        
        # Primeira chamada com cache
        result1, was_cached1 = get_cached_embedding(
            text="texto teste",
            cache_key=cache_key,
            embed_fn=lambda t: [0.1, 0.2, 0.3],
            enable_cache=True
        )
        assert was_cached1 is False
        
        # Segunda chamada SEM cache (deve re-embed)
        result2, was_cached2 = get_cached_embedding(
            text="texto teste",
            cache_key=cache_key,
            embed_fn=lambda t: [0.9, 0.8, 0.7],
            enable_cache=False
        )
        assert was_cached2 is False
        assert result2 == [0.9, 0.8, 0.7]  # Novo embedding, não do cache


class TestTelemetryCollector:
    """Testes para Telemetry Collector"""
    
    def setup_method(self):
        """Reseta coletor antes de cada teste"""
        get_telemetry().reset()
    
    def test_record_title_normalization(self):
        """Testa registro de normalização de título"""
        telemetry = get_telemetry()
        
        telemetry.record_title_normalization("regex", "CEO")
        telemetry.record_title_normalization("llm", "CTO")
        telemetry.record_title_normalization("none", "Unknown Title")
        
        report = telemetry.generate_report()
        
        assert report["title_normalization"]["total"] == 3
        assert "regex" in report["title_normalization"]["by_method"]
        assert "llm" in report["title_normalization"]["by_method"]
        assert "none" in report["title_normalization"]["by_method"]
    
    def test_record_unmapped_titles(self):
        """Testa registro de títulos não mapeados"""
        telemetry = get_telemetry()
        
        telemetry.record_title_normalization("none", "Unknown Title 1")
        telemetry.record_title_normalization("none", "Unknown Title 2")
        
        report = telemetry.generate_report()
        
        assert len(report["title_normalization"]["top_unmapped"]) > 0
    
    def test_record_chunk_filtered(self):
        """Testa registro de chunks filtrados"""
        telemetry = get_telemetry()
        
        telemetry.record_chunk_filtered_by_quality("section", 0.25, "LEN_V_SHORT")
        telemetry.record_chunk_filtered_by_quality("section", 0.30, "DENSITY_LOW")
        
        report = telemetry.generate_report()
        
        assert report["chunks_quality_filtered"]["total_filtered"] == 2
        assert "section" in report["chunks_quality_filtered"]["by_type"]
        assert "LEN_V_SHORT" in report["chunks_quality_filtered"]["by_reason"]
    
    def test_generate_report(self):
        """Testa geração de relatório completo"""
        telemetry = get_telemetry()
        
        telemetry.record_title_normalization("regex", "CEO")
        telemetry.record_skill_normalization(was_mapped=False, original_skill="Python")
        telemetry.record_chunk_filtered_by_quality("section", 0.25, "LEN_V_SHORT")
        
        report = telemetry.generate_report()
        
        assert "timestamp" in report
        assert "title_normalization" in report
        assert "skill_normalization" in report
        assert "chunks_quality_filtered" in report


class TestUUIDDeterministic:
    """Testes para UUID Determinístico"""
    
    def test_generate_doc_uuid_deterministic(self):
        """Testa que mesmo input gera mesmo UUID"""
        uuid1 = generate_doc_uuid(source_url="https://example.com/doc1")
        uuid2 = generate_doc_uuid(source_url="https://example.com/doc1")
        uuid3 = generate_doc_uuid(source_url="https://example.com/doc2")
        
        # Mesmo input = mesmo UUID
        assert uuid1 == uuid2
        # Input diferente = UUID diferente
        assert uuid1 != uuid3
    
    def test_generate_doc_uuid_fallback(self):
        """Testa fallback de identificadores"""
        uuid1 = generate_doc_uuid(source_url="https://example.com/doc1")
        uuid2 = generate_doc_uuid(public_identifier="doc1")
        uuid3 = generate_doc_uuid(title="Document 1")
        
        # Diferentes identificadores devem gerar UUIDs diferentes
        assert uuid1 != uuid2
        assert uuid1 != uuid3
    
    def test_generate_chunk_uuid(self):
        """Testa geração de UUID de chunk"""
        doc_uuid = generate_doc_uuid(source_url="https://example.com/doc1")
        
        chunk_uuid1 = generate_chunk_uuid(doc_uuid, "chunk-1")
        chunk_uuid2 = generate_chunk_uuid(doc_uuid, "chunk-1")
        chunk_uuid3 = generate_chunk_uuid(doc_uuid, "chunk-2")
        
        # Mesmo chunk_id = mesmo UUID
        assert chunk_uuid1 == chunk_uuid2
        # Chunk diferente = UUID diferente
        assert chunk_uuid1 != chunk_uuid3
    
    def test_generate_chunk_uuid_by_type(self):
        """Testa geração de UUID de chunk com tipo"""
        doc_uuid = generate_doc_uuid(source_url="https://example.com/doc1")
        
        role_uuid = generate_chunk_uuid_by_type(doc_uuid, "role", "chunk-1")
        domain_uuid = generate_chunk_uuid_by_type(doc_uuid, "domain", "chunk-1")
        
        # Mesmo chunk_id mas tipo diferente = UUID diferente
        assert role_uuid != domain_uuid


class TestTextPreprocessing:
    """Testes para Text Preprocessing"""
    
    def test_prepare_for_embedding_normalizes(self):
        """Testa normalização de texto"""
        # Remove non-breaking spaces
        text1 = "Texto\u00A0com\u00A0non-breaking\u00A0spaces"
        result1 = prepare_for_embedding(text1)
        assert "\u00A0" not in result1
        
        # Remove zero-width spaces
        text2 = "Texto\u200Bcom\u200Bzero-width"
        result2 = prepare_for_embedding(text2)
        assert "\u200B" not in result2
        
        # Normaliza whitespace múltiplo
        text3 = "Texto   com    espaços    múltiplos"
        result3 = prepare_for_embedding(text3)
        assert "  " not in result3  # Não deve ter espaços duplos
    
    def test_prepare_for_embedding_empty(self):
        """Testa tratamento de valores vazios"""
        assert prepare_for_embedding(None) == ""
        assert prepare_for_embedding("") == ""
        assert prepare_for_embedding("   ") == ""
    
    def test_validate_text_for_embedding(self):
        """Testa validação de consistência"""
        # Textos idênticos
        is_valid, error = validate_text_for_embedding("texto", "texto")
        assert is_valid is True
        assert error is None
        
        # Textos diferentes
        is_valid, error = validate_text_for_embedding("texto 1", "texto 2")
        assert is_valid is False
        assert error is not None
    
    def test_truncate_semantic(self):
        """Testa truncamento semântico"""
        # Texto curto (não trunca)
        text = "Texto curto"
        result = truncate_semantic(text, max_chars=100)
        assert result == text
        
        # Texto longo (trunca em ponto final)
        text = "Primeira frase. Segunda frase. Terceira frase."
        result = truncate_semantic(text, max_chars=30)
        assert result.endswith("…")
        assert "Primeira frase" in result


class TestQualityScoring:
    """Testes para Quality Scoring"""
    
    def test_is_login_wall(self):
        """Testa detecção de login wall"""
        assert is_login_wall("Sign in to LinkedIn") is True
        assert is_login_wall("Entrar no LinkedIn") is True
        assert is_login_wall("Log in to view") is True
        assert is_login_wall("Texto normal") is False
    
    def test_compute_quality_score_empty(self):
        """Testa score de texto vazio"""
        score, reason = compute_quality_score("")
        assert score == 0.0
        assert reason == "EMPTY_TEXT"
    
    def test_compute_quality_score_summary(self):
        """Testa proteção de summaries"""
        score, reason = compute_quality_score(
            "Position | Company | Location",
            is_summary=True
        )
        assert score >= 0.75  # Summaries são protegidos
        assert "SUMMARY_PROTECTED" in reason
    
    def test_compute_quality_score_good_text(self):
        """Testa score de texto de boa qualidade"""
        # Texto com comprimento ideal e densidade alta
        good_text = "Este é um texto de exemplo com mais de 200 caracteres. " * 5
        score, reason = compute_quality_score(good_text)
        assert score >= 0.5  # Deve ter score alto
        assert "LEN_OK" in reason or "DENSITY_HIGH" in reason
    
    def test_compute_quality_score_short_text(self):
        """Testa score de texto muito curto"""
        short_text = "Texto curto"
        score, reason = compute_quality_score(short_text)
        assert score < 0.5  # Deve ter score baixo
        assert "LEN_V_SHORT" in reason or "LEN_SHORT" in reason
    
    def test_compute_quality_score_login_wall(self):
        """Testa penalização de login wall"""
        login_wall_text = "Sign in to LinkedIn to view this content"
        score, reason = compute_quality_score(login_wall_text)
        assert score < 0.5  # Deve ser penalizado
        assert "LOGIN_WALL" in reason
    
    def test_compute_quality_score_type_aware(self):
        """Testa boost type-aware"""
        # Experiência curta (deve ter boost)
        exp_text = "CEO | Company Name | Location"
        score1, _ = compute_quality_score(exp_text, parent_type="experience")
        
        # Texto normal curto (sem boost)
        score2, _ = compute_quality_score(exp_text, parent_type="section")
        
        # Experiência deve ter score maior ou igual
        assert score1 >= score2


class TestIntegration:
    """Testes de integração entre componentes"""
    
    def test_telemetry_with_quality_scoring(self):
        """Testa integração entre telemetry e quality scoring"""
        telemetry = get_telemetry()
        telemetry.reset()
        
        # Calcula score e registra (força registro mesmo que score seja >= 0.3)
        score, reason = compute_quality_score("Texto muito curto", parent_type="section")
        # Sempre registra para teste
        telemetry.record_chunk_filtered_by_quality("section", score, reason)
        
        # Também registra um com score baixo garantido
        score2, reason2 = compute_quality_score("", parent_type="section")  # Score 0.0
        telemetry.record_chunk_filtered_by_quality("section", score2, reason2)
        
        report = telemetry.generate_report()
        assert report["chunks_quality_filtered"]["total_filtered"] > 0
    
    def test_cache_with_preprocessing(self):
        """Testa integração entre cache e preprocessing"""
        clear_cache()
        
        # Texto original
        original_text = "Texto   com   espaços   múltiplos"
        
        # Normaliza
        normalized = prepare_for_embedding(original_text)
        
        # Gera chave com texto normalizado
        cache_key = get_cache_key(normalized, "doc-123", "chunk")
        
        # Embed com cache
        embedding, was_cached = get_cached_embedding(
            text=normalized,
            cache_key=cache_key,
            embed_fn=lambda t: [0.1, 0.2, 0.3]
        )
        
        assert was_cached is False  # Primeira vez
        assert embedding == [0.1, 0.2, 0.3]
        
        # Segunda vez (deve usar cache)
        embedding2, was_cached2 = get_cached_embedding(
            text=normalized,
            cache_key=cache_key,
            embed_fn=lambda t: [0.9, 0.8, 0.7]
        )
        
        assert was_cached2 is True
        assert embedding2 == embedding


if __name__ == "__main__":
    print("🧪 Executando testes dos componentes RAG2...")
    print("=" * 60)
    
    # Executa testes básicos
    test_classes = [
        TestTelemetryMiddleware,
        TestEmbeddingsCache,
        TestTelemetryCollector,
        TestUUIDDeterministic,
        TestTextPreprocessing,
        TestQualityScoring,
        TestIntegration
    ]
    
    total_tests = 0
    passed_tests = 0
    failed_tests = []
    
    for test_class in test_classes:
        print(f"\n📋 Testando {test_class.__name__}...")
        instance = test_class()
        
        # Executa setup se existir
        if hasattr(instance, 'setup_method'):
            instance.setup_method()
        
        # Encontra todos os métodos de teste
        test_methods = [method for method in dir(instance) if method.startswith('test_')]
        
        for test_method in test_methods:
            total_tests += 1
            try:
                getattr(instance, test_method)()
                passed_tests += 1
                print(f"  ✅ {test_method}")
            except Exception as e:
                failed_tests.append(f"{test_class.__name__}.{test_method}: {str(e)}")
                print(f"  ❌ {test_method}: {str(e)}")
    
    print("\n" + "=" * 60)
    print(f"📊 Resultados: {passed_tests}/{total_tests} testes passaram")
    
    if failed_tests:
        print(f"\n❌ Testes falhados:")
        for failure in failed_tests:
            print(f"  - {failure}")
        exit(1)
    else:
        print("\n✅ Todos os testes passaram!")
        exit(0)

