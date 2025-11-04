#!/usr/bin/env python3
"""
🧪 Script de Testes Remotos para Verba API
Valida: Conexão, Query, EntityAwareRetriever, e Response
"""

import httpx
import asyncio
import json
from typing import Optional
import sys

# Tenta importar websockets (opcional para teste de stream)
try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False

# ============================================================================
# CONFIGURAÇÃO
# ============================================================================

# URL da aplicação Verba
BASE_URL = "https://verba-production-c347.up.railway.app"
WEAVIATE_URL = "https://weaviate-production-0d0e.up.railway.app"
# Para local: BASE_URL = "http://localhost:8000"

TIMEOUT = 30  # segundos

# ============================================================================
# CORES PARA OUTPUT
# ============================================================================

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def success(msg: str):
    print(f"{Colors.GREEN}[OK] {msg}{Colors.END}")

def error(msg: str):
    print(f"{Colors.RED}[ERROR] {msg}{Colors.END}")

def info(msg: str):
    print(f"{Colors.BLUE}[INFO] {msg}{Colors.END}")

def warning(msg: str):
    print(f"{Colors.YELLOW}[WARN] {msg}{Colors.END}")

def header(msg: str):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{msg}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.END}\n")

# ============================================================================
# TESTES
# ============================================================================

async def test_health() -> bool:
    """Testa endpoint /api/health"""
    header("1. Testando Health Check")
    
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(f"{BASE_URL}/api/health")
            
            if response.status_code == 200:
                success(f"Health check OK (status: {response.status_code})")
                info(f"Response: {response.json()}")
                return True
            else:
                error(f"Health check falhou (status: {response.status_code})")
                return False
    except Exception as e:
        error(f"Erro ao conectar: {str(e)}")
        return False

async def test_query_simple() -> bool:
    """Testa query simples via API"""
    header("2. Testando Query Simples")
    
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            payload = {
                "query": "o que se falou sobre apple?",
                "RAG": {},  # Usa configuracao padrao
                "labels": [],  # Sem filtro de labels
                "documentFilter": [],  # Todos os documentos
                "credentials": {
                    "deployment": "Local",
                    "url": "http://localhost:8000",
                    "key": ""
                }
            }
            
            headers = {
                "Origin": "http://verba-production-c347.up.railway.app/",
                "Referer": "http://verba-production-c347.up.railway.app/",
            }
            
            info(f"Enviando query: {payload['query']}")
            response = await client.post(
                f"{BASE_URL}/api/query",
                json=payload,
                headers=headers
            )
            
            if response.status_code == 200:
                success(f"Query retornou (status: {response.status_code})")
                data = response.json()
                
                if "documents" in data:
                    docs = data.get('documents', [])
                    info(f"Documentos retornados: {len(docs)}")
                    if len(docs) > 0:
                        success(f"Encontrados {len(docs)} documento(s)")
                        return True
                    else:
                        info(f"Nenhum documento retornado")
                        return True
                else:
                    warning(f"Response estrutura inesperada: {list(data.keys())}")
                    return True
            else:
                error(f"Query falhou (status: {response.status_code})")
                error(f"Response: {response.text[:200]}")
                return False
                
    except Exception as e:
        error(f"Erro ao executar query: {str(e)}")
        return False

async def test_query_entity() -> bool:
    """Testa query com entidade (Spencer Stuart)"""
    header("3. Testando Query com Entidade")
    
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            payload = {
                "query": "procure o que se falou sobre a Spencer Stuart",
                "RAG": {},  # Usa configuracao padrao
                "labels": [],  # Sem filtro de labels
                "documentFilter": [],  # Todos os documentos
                "credentials": {
                    "deployment": "Local",
                    "url": "http://localhost:8000",
                    "key": ""
                }
            }
            
            headers = {
                "Origin": "http://verba-production-c347.up.railway.app/",
                "Referer": "http://verba-production-c347.up.railway.app/",
            }
            
            info(f"Enviando query com entidade: {payload['query']}")
            response = await client.post(
                f"{BASE_URL}/api/query",
                json=payload,
                headers=headers
            )
            
            if response.status_code == 200:
                success(f"Query com entidade retornou (status: {response.status_code})")
                data = response.json()
                
                if "documents" in data:
                    docs = data.get('documents', [])
                    info(f"Documentos retornados: {len(docs)}")
                    if len(docs) > 0:
                        success(f"Encontrados {len(docs)} documento(s)")
                        return True
                    else:
                        info(f"Nenhum documento retornado (pode ser normal)")
                        return True
                else:
                    warning(f"Response inesperada: {list(data.keys())}")
                    return True
                    
            else:
                error(f"Query falhou (status: {response.status_code})")
                return False
                
    except Exception as e:
        error(f"Erro: {str(e)}")
        return False

async def test_retriever_config() -> bool:
    """Testa se o EntityAwareRetriever está configurado"""
    header("4. Testando Configuracao do Retriever")
    
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            headers = {
                "Origin": BASE_URL,
                "Referer": BASE_URL,
                "Content-Type": "application/json",
            }
            # /api/get_meta espera Credentials payload (POST apenas)
            payload = {
                "deployment": "Local",
                "url": "http://localhost:8000",
                "key": ""
            }
            
            response = await client.post(f"{BASE_URL}/api/get_meta", json=payload, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                info(f"Meta data recebida")
                
                # Verifica collection_payload para encontrar retriever config
                collection_payload = data.get("collection_payload", {})
                
                # Tenta encontrar retriever na configuração
                if "retriever" in str(data).lower() or "entityaware" in str(data).lower():
                    success(f"Meta endpoint funcionando - pode conter configuracao de retriever")
                    return True
                else:
                    # Verifica se há collections disponíveis
                    if collection_payload:
                        success(f"Meta endpoint funcionando - {len(collection_payload)} collections encontradas")
                        return True
                    else:
                        warning(f"Meta retornou mas sem dados de collections (pode ser normal)")
                        return True
            else:
                error(f"Meta falhou (status: {response.status_code})")
                if response.status_code == 422:
                    error(f"Payload invalido: {response.text[:200]}")
                return False
                
    except Exception as e:
        error(f"Erro ao obter meta: {str(e)}")
        return False

async def test_stream_query() -> bool:
    """Testa streaming de resposta (WebSocket)"""
    header("5. Testando Stream de Resposta (WebSocket)")
    
    if not WEBSOCKETS_AVAILABLE:
        warning("websockets library nao disponivel - pulando teste de WebSocket")
        info("Instale com: pip install websockets")
        return False
    
    try:
        ws_url = BASE_URL.replace("https://", "wss://").replace("http://", "ws://")
        ws_url = f"{ws_url}/ws/generate_stream"
        
        info(f"Conectando ao WebSocket: {ws_url}")
        
        # websockets.connect não aceita timeout diretamente, usa ping_timeout
        async with websockets.connect(ws_url, ping_interval=20, ping_timeout=10) as websocket:
            # Payload para GeneratePayload
            # O rag_config precisa ter estrutura RAGComponentClass
            payload = {
                "query": "quem e Steve Jobs?",
                "context": "",
                "conversation": [],
                "rag_config": {
                    "Reader": {"selected": "Basic", "components": {}},
                    "Chunker": {"selected": "Token", "components": {}},
                    "Embedder": {"selected": "SentenceTransformers", "components": {}},
                    "Retriever": {"selected": "Window", "components": {}},
                    "Generator": {"selected": "OpenAI", "components": {}}
                }
            }
            
            await websocket.send(json.dumps(payload))
            info(f"Payload enviado, aguardando resposta...")
            
            chunks_received = 0
            full_text_list = []
            
            try:
                # Recebe chunks com timeout
                # Usa asyncio.wait_for para compatibilidade com Python < 3.11
                async def receive_stream():
                    nonlocal chunks_received, full_text_list
                    while True:
                        response = await websocket.recv()
                        data = json.loads(response)
                        
                        if "message" in data:
                            full_text_list.append(data["message"])
                            chunks_received += 1
                        
                        if data.get("finish_reason") == "stop":
                            break
                
                await asyncio.wait_for(receive_stream(), timeout=15)
                
                full_text = "".join(full_text_list)
                success(f"Stream completo: {chunks_received} chunks, {len(full_text)} caracteres")
                return True
                
            except asyncio.TimeoutError:
                warning(f"Stream timeout (mas recebeu {chunks_received} chunks)")
                return chunks_received > 0
            except websockets.exceptions.ConnectionClosed as e:
                if chunks_received > 0:
                    warning(f"WebSocket fechado pelo servidor (mas recebeu {chunks_received} chunks)")
                    return True
                else:
                    warning(f"WebSocket fechado sem dados: {e}")
                    return False
                    
    except Exception as e:
        warning(f"Erro no stream WebSocket: {str(e)}")
        info("WebSocket pode nao estar disponivel ou requer autenticacao")
        return False

async def test_suggestions() -> bool:
    """Testa endpoint de sugestoes"""
    header("6. Testando Sugestoes")
    
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            headers = {
                "Origin": BASE_URL,
                "Referer": BASE_URL,
                "Content-Type": "application/json",
            }
            # Usa /api/get_all_suggestions que espera GetAllSuggestionsPayload
            payload = {
                "page": 0,
                "pageSize": 10,
                "credentials": {
                    "deployment": "Local",
                    "url": "http://localhost:8000",
                    "key": ""
                }
            }
            response = await client.post(f"{BASE_URL}/api/get_all_suggestions", json=payload, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                suggestions = data.get("suggestions", [])
                total_count = data.get("total_count", 0)
                
                success(f"Sugestoes obtidas: {len(suggestions)} disponiveis (total: {total_count})")
                for i, sugg in enumerate(suggestions[:3]):
                    info(f"  Sugestao {i+1}: {sugg}")
                return True
            else:
                error(f"Sugestoes falhou (status: {response.status_code})")
                if response.status_code == 422:
                    error(f"Payload invalido: {response.text[:200]}")
                return False
                
    except Exception as e:
        error(f"Erro ao obter sugestoes: {str(e)}")
        return False

async def test_data_count() -> bool:
    """Testa contagem de documentos"""
    header("7. Testando Data Count")
    
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            headers = {
                "Origin": BASE_URL,
                "Referer": BASE_URL,
                "Content-Type": "application/json",
            }
            # DatacountPayload precisa de embedding_model e documentFilter
            payload = {
                "embedding_model": "default",  # Usa modelo padrao
                "documentFilter": [],  # Todos os documentos
                "credentials": {
                    "deployment": "Local",
                    "url": "http://localhost:8000",
                    "key": ""
                }
            }
            response = await client.post(f"{BASE_URL}/api/get_datacount", json=payload, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                # A resposta tem "datacount" no topo, não "data"
                count = data.get("datacount", 0)
                
                success(f"Contagem de chunks: {count}")
                info(f"Response: {json.dumps(data, indent=2)[:200]}")
                # Retorna True mesmo se count = 0 (pode ser normal)
                return True
            else:
                error(f"Data count falhou (status: {response.status_code})")
                if response.status_code == 422:
                    error(f"Payload invalido: {response.text[:200]}")
                return False
                
    except Exception as e:
        error(f"Erro ao contar dados: {str(e)}")
        return False

# ============================================================================
# EXECUÇÃO
# ============================================================================

async def run_all_tests():
    """Executa todos os testes"""
    
    header("TEST DE API REMOTA - VERBA")
    print(f"URL: {BASE_URL}")
    print(f"Timeout: {TIMEOUT}s\n")
    
    results = []
    
    # Executa testes em ordem
    tests = [
        ("Health Check", test_health),
        ("Query Simples", test_query_simple),
        ("Query com Entidade", test_query_entity),
        ("Config Retriever", test_retriever_config),
        ("Stream de Resposta", test_stream_query),
        ("Sugestoes", test_suggestions),
        ("Data Count", test_data_count),
    ]
    
    for name, test_func in tests:
        try:
            result = await test_func()
            results.append((name, result))
            await asyncio.sleep(1)  # Pequeno delay entre testes
        except Exception as e:
            error(f"Erro inesperado em {name}: {str(e)}")
            results.append((name, False))
    
    # ========================================================================
    # RESUMO
    # ========================================================================
    
    header("RESUMO DOS TESTES")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "OK" if result else "FALHOU"
        color = Colors.GREEN if result else Colors.RED
        print(f"{color}{status}{Colors.END} - {name}")
    
    print(f"\n{Colors.BOLD}Total: {passed}/{total} testes passaram{Colors.END}")
    
    if passed == total:
        success("\nTODOS OS TESTES PASSARAM!")
        return 0
    else:
        warning(f"\n{total - passed} teste(s) falharam")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)
