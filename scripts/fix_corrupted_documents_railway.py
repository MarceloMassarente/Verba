"""
Script simplificado para corrigir documentos corrompidos no Railway.

Uso no Railway:
  railway run python scripts/fix_corrupted_documents_railway.py list
  railway run python scripts/fix_corrupted_documents_railway.py fix
  railway run python scripts/fix_corrupted_documents_railway.py delete-all
"""

import os
import json
import sys

try:
    import weaviate
    from weaviate.classes.query import Filter
    from weaviate.classes.init import Auth, AdditionalConfig
except ImportError:
    print("Erro: weaviate-client nao instalado")
    sys.exit(1)


def get_weaviate_client():
    """Conecta ao Weaviate usando variáveis de ambiente do Railway ou URL direta"""
    # Railway: WEAVIATE_HTTP_HOST e WEAVIATE_HTTP_PORT
    http_host = os.getenv("WEAVIATE_HTTP_HOST")
    http_port = os.getenv("WEAVIATE_HTTP_PORT", "8080")
    grpc_host = os.getenv("WEAVIATE_GRPC_HOST")
    grpc_port = os.getenv("WEAVIATE_GRPC_PORT", "50051")
    
    api_key = os.getenv("WEAVIATE_API_KEY_VERBA") or os.getenv("WEAVIATE_API_KEY", "")
    
    # URL direta do Railway (se fornecida via argumento ou env)
    railway_url = os.getenv("RAILWAY_WEAVIATE_URL", "https://weaviate-production-0d0e.up.railway.app")
    
    if http_host and grpc_host:
        # Modo Railway (rede privada)
        auth_creds = Auth.api_key(api_key) if api_key else None
        return weaviate.connect_to_custom(
            http_host=http_host,
            http_port=int(http_port),
            http_secure=False,
            grpc_host=grpc_host,
            grpc_port=int(grpc_port),
            grpc_secure=False,
            auth_credentials=auth_creds
        )
    else:
        # Fallback: URL completa (prioriza Railway URL se disponível)
        url = os.getenv("WEAVIATE_URL_VERBA") or os.getenv("WEAVIATE_URL") or railway_url
        if api_key:
            # WCS ou custom com auth
            if ".weaviate.network" in url or ".weaviate.cloud" in url:
                cluster = url.replace("http://", "").replace("https://", "").rstrip("/")
                return weaviate.connect_to_weaviate_cloud(
                    cluster_url=cluster,
                    auth_credentials=Auth.api_key(api_key)
                )
            else:
                # Custom URL
                parsed = url.replace("http://", "").replace("https://", "")
                host = parsed.split(":")[0] if ":" in parsed else parsed
                port = int(parsed.split(":")[1]) if ":" in parsed else 8080
                return weaviate.connect_to_custom(
                    http_host=host,
                    http_port=port,
                    http_secure=url.startswith("https://"),
                    auth_credentials=Auth.api_key(api_key)
                )
        else:
            # Custom sem auth (Railway ou local)
            parsed = url.replace("http://", "").replace("https://", "").rstrip("/")
            secure = url.startswith("https://")
            
            # Remove porta se presente
            if ":" in parsed:
                parts = parsed.split(":")
                host = parts[0]
                port = int(parts[1])
            else:
                host = parsed
                # Porta padrão: 443 para HTTPS, 8080 para HTTP
                port = 443 if secure else 8080
            
            # Railway HTTPS geralmente não expõe gRPC publicamente
            # Usa apenas HTTP/HTTPS (sem gRPC)
            # Para Railway público, usamos apenas HTTP REST
            from weaviate.classes.init import AdditionalConfig, Timeout
            
            return weaviate.connect_to_custom(
                http_host=host,
                http_port=port,
                http_secure=secure,
                grpc_host="localhost",  # Dummy - não será usado
                grpc_port=50051,
                grpc_secure=False,
                additional_config=AdditionalConfig(
                    timeout=Timeout(query=60, insert=120)
                ),
                skip_init_checks=True  # Não valida gRPC
            )


def find_corrupted_documents(client):
    """Encontra documentos com meta = None"""
    print("Buscando documentos corrompidos...")
    
    collection_name = "VERBA_Document"
    
    try:
        collection = client.collections.get(collection_name)
    except Exception as e:
        print(f"Erro ao acessar collection {collection_name}: {e}")
        print(f"Collections disponiveis: {client.collections.list_all()}")
        return []
    
    corrupted = []
    
    try:
        # Usa query.fetch_objects em vez de iterator (mais compatível com HTTP-only)
        result = collection.query.fetch_objects(limit=1000)
        docs = result.objects
        
        for doc in docs:
            meta = doc.properties.get("meta")
            
            if meta is None:
                corrupted.append({
                    "uuid": str(doc.uuid),
                    "title": doc.properties.get("title", "Sem titulo"),
                    "problem": "meta is None"
                })
            elif isinstance(meta, str):
                try:
                    json.loads(meta)
                except (json.JSONDecodeError, TypeError):
                    corrupted.append({
                        "uuid": str(doc.uuid),
                        "title": doc.properties.get("title", "Sem titulo"),
                        "problem": f"meta is not valid JSON"
                    })
            else:
                corrupted.append({
                    "uuid": str(doc.uuid),
                    "title": doc.properties.get("title", "Sem titulo"),
                    "problem": f"meta is not string: {type(meta)}"
                })
        
        # Se houver mais documentos, busca em lotes
        offset = 1000
        while True:
            try:
                result = collection.query.fetch_objects(limit=1000, offset=offset)
                if not result.objects:
                    break
                for doc in result.objects:
                    meta = doc.properties.get("meta")
                    if meta is None:
                        corrupted.append({
                            "uuid": str(doc.uuid),
                            "title": doc.properties.get("title", "Sem titulo"),
                            "problem": "meta is None"
                        })
                    elif isinstance(meta, str):
                        try:
                            json.loads(meta)
                        except (json.JSONDecodeError, TypeError):
                            corrupted.append({
                                "uuid": str(doc.uuid),
                                "title": doc.properties.get("title", "Sem titulo"),
                                "problem": f"meta is not valid JSON"
                            })
                    else:
                        corrupted.append({
                            "uuid": str(doc.uuid),
                            "title": doc.properties.get("title", "Sem titulo"),
                            "problem": f"meta is not string: {type(meta)}"
                        })
                offset += 1000
            except Exception:
                break
    except Exception as e:
        print(f"Erro ao buscar documentos: {e}")
        return []
    
    return corrupted


def fix_document(client, uuid, fix_mode="default"):
    """Corrige ou deleta documento"""
    collection_name = "VERBA_Document"
    collection = client.collections.get(collection_name)
    
    try:
        doc = collection.query.fetch_object_by_id(uuid)
        
        if fix_mode == "delete":
            print(f"Deletando documento {uuid}...")
            
            # Deleta chunks de todas as collections de embedding
            all_collections = client.collections.list_all()
            for coll_name in all_collections:
                if "Embedding" in coll_name:
                    try:
                        embedder_collection = client.collections.get(coll_name)
                        embedder_collection.data.delete_many(
                            where=Filter.by_property("doc_uuid").equal(uuid)
                        )
                        print(f"  Chunks deletados de {coll_name}")
                    except Exception:
                        pass
            
            # Deleta documento
            collection.data.delete_by_id(uuid)
            print(f"Documento {uuid} deletado!")
            return True
        
        else:  # fix
            print(f"Corrigindo meta do documento {uuid}...")
            
            default_meta = {
                "Embedder": {
                    "config": {
                        "Model": {
                            "value": "all-MiniLM-L6-v2"
                        }
                    }
                }
            }
            
            collection.data.update(
                uuid=uuid,
                properties={"meta": json.dumps(default_meta)}
            )
            
            print(f"Meta corrigido para documento {uuid}")
            return True
            
    except Exception as e:
        print(f"Erro ao processar documento {uuid}: {e}")
        return False


def main():
    if len(sys.argv) < 2:
        print("""
Uso: python scripts/fix_corrupted_documents_railway.py <comando>

Comandos:
  list          - Lista documentos corrompidos
  fix           - Corrige documentos (cria meta padrao)
  delete-all    - Deleta TODOS os documentos corrompidos

Exemplos:
  railway run python scripts/fix_corrupted_documents_railway.py list
  railway run python scripts/fix_corrupted_documents_railway.py fix
  railway run python scripts/fix_corrupted_documents_railway.py delete-all
        """)
        return
    
    command = sys.argv[1]
    
    print("Conectando ao Weaviate...")
    try:
        client = get_weaviate_client()
        
        if not client.is_ready():
            print("Weaviate nao esta pronto")
            return
        
        print("Conectado ao Weaviate!")
        
        corrupted = find_corrupted_documents(client)
        
        if not corrupted:
            print("Nenhum documento corrompido encontrado!")
            return
        
        print(f"\nEncontrados {len(corrupted)} documentos corrompidos:")
        for doc in corrupted:
            print(f"  - {doc['title']} ({doc['uuid']}) - {doc['problem']}")
        
        if command == "list":
            print("\nLista de documentos corrompidos:")
            for doc in corrupted:
                print(f"  UUID: {doc['uuid']}")
                print(f"  Titulo: {doc['title']}")
                print(f"  Problema: {doc['problem']}")
                print()
        
        elif command == "fix":
            print("\nCorrigindo documentos...")
            fixed = 0
            for doc in corrupted:
                if fix_document(client, doc['uuid'], "default"):
                    fixed += 1
            print(f"\n{fixed}/{len(corrupted)} documentos corrigidos!")
        
        elif command == "delete-all":
            print("\nATENCAO: Isso vai deletar TODOS os documentos corrompidos!")
            confirm = input("Digite 'SIM' para confirmar: ")
            if confirm != "SIM":
                print("Operacao cancelada")
                return
            
            print("\nDeletando documentos corrompidos...")
            deleted = 0
            for doc in corrupted:
                if fix_document(client, doc['uuid'], "delete"):
                    deleted += 1
            print(f"\n{deleted}/{len(corrupted)} documentos deletados!")
        
        else:
            print(f"Comando desconhecido: {command}")
        
        client.close()
        
    except Exception as e:
        print(f"Erro: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

