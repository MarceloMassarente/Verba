#!/usr/bin/env python3
"""
Verba API Client - Acesso Externo Completo
===========================================

Este cliente permite acesso completo à API do Verba para integração
com sistemas externos, mantendo todas as capacidades avançadas de
retrieval e reranking.

IMPORTANTE: O header 'Origin' é obrigatório para bypass do CORS.
"""

import requests
from typing import Optional, List, Dict, Any

# =============================================================================
# CONFIGURAÇÃO
# =============================================================================

BASE_URL = "https://verba-production-c347.up.railway.app"

# O header Origin é OBRIGATÓRIO - sem ele você recebe 403 Forbidden
HEADERS = {
    "Content-Type": "application/json",
    "Origin": BASE_URL,
}

# Credenciais - 'Local' usa as env vars do Railway
CREDENTIALS = {
    "deployment": "Weaviate",
    "url": "http://weaviate.railway.internal:8080",
    "key": ""  # Leave empty if no auth is configured on internal network
}


# =============================================================================
# FUNÇÕES DA API
# =============================================================================

def health_check() -> dict:
    """Verifica se a API está online."""
    response = requests.get(
        f"{BASE_URL}/api/health",
        headers=HEADERS,
        timeout=10
    )
    response.raise_for_status()
    return response.json()


def get_rag_config() -> dict:
    """Obtém a configuração RAG atual."""
    response = requests.post(
        f"{BASE_URL}/api/get_rag_config",
        headers=HEADERS,
        json=CREDENTIALS,
        timeout=30
    )
    response.raise_for_status()
    return response.json()


def get_presets() -> dict:
    """Obtém a lista de presets disponíveis."""
    response = requests.post(
        f"{BASE_URL}/api/get_reranker_presets",
        headers=HEADERS,
        json={"credentials": CREDENTIALS},
        timeout=30
    )
    response.raise_for_status()
    return response.json()


def search(
    query: str,
    preset: Optional[str] = None,
    labels: Optional[List[str]] = None,
    document_filter: Optional[List[Dict[str, str]]] = None
) -> dict:
    """
    Executa uma busca usando o endpoint /api/external/query.
    
    Este endpoint usa o RAG config do servidor e mantém todas as
    capacidades avançadas do EntityAware Retriever.
    
    Args:
        query: Texto da busca
        preset: (Optional) Preset a aplicar:
                - speed: Busca rápida
                - balanced: Equilíbrio velocidade/qualidade
                - max_quality: Máxima qualidade
                - consulting_frameworks: Foco em frameworks consultoria
                - company_research: Pesquisa de empresas
                - sector_analysis: Análise setorial
        labels: (Optional) Labels para filtrar documentos
        document_filter: (Optional) Lista de {title, uuid} para filtrar
    
    Returns:
        documents: Lista de documentos/chunks encontrados
        context: Contexto agregado para RAG
        preset_applied: Nome do preset aplicado (se houver)
        error: Mensagem de erro (se houver)
    """
    payload = {
        "query": query,
        "credentials": CREDENTIALS
    }
    
    if preset:
        payload["preset"] = preset
    if labels:
        payload["labels"] = labels
    if document_filter:
        payload["documentFilter"] = document_filter
    
    response = requests.post(
        f"{BASE_URL}/api/external/query",
        headers=HEADERS,
        json=payload,
        timeout=120
    )
    response.raise_for_status()
    return response.json()


# =============================================================================
# EXEMPLO DE USO
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("VERBA API - TESTE DE ACESSO EXTERNO COMPLETO")
    print("=" * 60)
    
    # 1. Health check
    print("\n[1] Health Check...")
    try:
        health = health_check()
        print(f"    ✅ API online!")
    except Exception as e:
        print(f"    ❌ Erro: {e}")
        exit(1)
    
    # 2. Get Presets
    print("\n[2] Presets disponíveis:")
    try:
        data = get_presets()
        presets = data.get("presets", [])
        if isinstance(presets, list):
            for p in presets[:6]:
                name = p.get("name") if isinstance(p, dict) else p
                display = p.get("display_name", name) if isinstance(p, dict) else name
                print(f"    - {name}: {display}")
        else:
            for name in list(presets.keys())[:6]:
                print(f"    - {name}")
    except Exception as e:
        print(f"    ❌ Erro: {e}")
    
    # 3. Busca simples
    print("\n[3] Busca simples (sem preset)...")
    try:
        result = search("agronegocio qualificacoes")
        docs = result.get("documents", [])
        print(f"    ✅ Encontrados {len(docs)} documentos")
        for doc in docs[:3]:
            score = doc.get("score", 0)
            text = doc.get("text", "")[:50].replace("\n", " ")
            print(f"    [{score:.3f}] {text}...")
    except Exception as e:
        print(f"    ❌ Erro: {e}")
    
    # 4. Busca com preset
    print("\n[4] Busca com preset 'balanced'...")
    try:
        result = search("agronegocio", preset="balanced")
        docs = result.get("documents", [])
        preset_applied = result.get("preset_applied")
        print(f"    ✅ Encontrados {len(docs)} documentos")
        print(f"    Preset aplicado: {preset_applied}")
    except Exception as e:
        print(f"    ❌ Erro: {e}")
    
    # 5. Busca com diferentes presets
    print("\n[5] Testando diferentes presets...")
    for preset in ["speed", "max_quality", "consulting_frameworks"]:
        try:
            result = search("estrategia", preset=preset)
            docs = result.get("documents", [])
            print(f"    - {preset}: {len(docs)} docs")
        except Exception as e:
            print(f"    - {preset}: Erro - {e}")
    
    print("\n" + "=" * 60)
    print("ACESSO EXTERNO COMPLETO FUNCIONANDO!")
    print(f"Endpoint: {BASE_URL}/api/external/query")
    print("=" * 60)
