"""
Script para corrigir ou deletar documentos corrompidos no Weaviate.

Problema: Documentos com campo 'meta' = None que impedem deleção.
Erro: "the JSON object must be str, bytes or bytearray, not NoneType"
"""

import os
import json
import asyncio
import sys

# Tenta importar wasabi, mas não é crítico
try:
    from wasabi import msg
except ImportError:
    # Fallback simples se wasabi não estiver disponível
    class SimpleMsg:
        def info(self, text): print(f"ℹ️  {text}")
        def good(self, text): print(f"✅ {text}")
        def warn(self, text): print(f"⚠️  {text}")
        def fail(self, text): print(f"❌ {text}")
    msg = SimpleMsg()

# Imports do Weaviate (direto, sem depender do Verba completo)
try:
    import weaviate
    from weaviate.classes.query import Filter
except ImportError:
    print("❌ Erro: weaviate-client não instalado")
    print("   Execute: pip install weaviate-client")
    exit(1)


def find_corrupted_documents(client, collection_name: str):
    """
    Encontra documentos com campo 'meta' = None ou inválido.
    """
    msg.info(f"🔍 Buscando documentos corrompidos em {collection_name}...")
    
    collection = client.collections.get(collection_name)
    corrupted = []
    
    try:
        # Busca todos os documentos
        for doc in collection.iterator():
            meta = doc.properties.get("meta")
            
            # Verifica se meta é None ou não é uma string JSON válida
            if meta is None:
                corrupted.append({
                    "uuid": str(doc.uuid),
                    "title": doc.properties.get("title", "Sem título"),
                    "problem": "meta is None"
                })
            elif isinstance(meta, str):
                try:
                    json.loads(meta)
                except (json.JSONDecodeError, TypeError):
                    corrupted.append({
                        "uuid": str(doc.uuid),
                        "title": doc.properties.get("title", "Sem título"),
                        "problem": f"meta is not valid JSON: {meta[:50]}"
                    })
            else:
                corrupted.append({
                    "uuid": str(doc.uuid),
                    "title": doc.properties.get("title", "Sem título"),
                    "problem": f"meta is not string: {type(meta)}"
                })
    
    except Exception as e:
        msg.fail(f"Erro ao buscar documentos: {str(e)}")
        return []
    
    return corrupted


def fix_document_meta(client, collection_name: str, uuid: str, fix_mode: str = "default"):
    """
    Corrige o campo 'meta' de um documento.
    
    Args:
        fix_mode: "default" (cria meta padrão) ou "delete" (deleta documento)
    """
    collection = client.collections.get(collection_name)
    
    try:
        doc = collection.query.fetch_object_by_id(uuid)
        
        if fix_mode == "delete":
            # Deleta diretamente sem depender do campo meta
            msg.info(f"🗑️  Deletando documento {uuid}...")
            
            # Primeiro deleta chunks relacionados
            try:
                # Tenta encontrar o embedder de outras fontes
                # Se não conseguir, deleta todos os chunks de todos os embedders
                from goldenverba.components.managers import WeaviateManager
                manager = WeaviateManager()
                
                # Lista de embedders comuns
                common_embedders = [
                    "OpenAI", "Cohere", "VoyageAI", "Upstage", 
                    "SentenceTransformers", "all-MiniLM-L6-v2"
                ]
                
                # Lista todas as collections e deleta chunks relacionados
                all_collections = client.collections.list_all()
                for coll_name in all_collections:
                    if "Embedding" in coll_name:
                        try:
                            embedder_collection = client.collections.get(coll_name)
                            embedder_collection.data.delete_many(
                                where=Filter.by_property("doc_uuid").equal(uuid)
                            )
                            msg.info(f"   Chunks deletados de {coll_name}")
                        except Exception as e:
                            # Ignora erros
                            pass
                
                # Deleta o documento
                collection.data.delete_by_id(uuid)
                msg.good(f"✅ Documento {uuid} deletado com sucesso!")
                return True
                
            except Exception as e:
                msg.warn(f"⚠️  Erro ao deletar: {str(e)}")
                return False
        
        else:  # fix_mode == "default"
            # Cria meta padrão
            msg.info(f"🔧 Corrigindo meta do documento {uuid}...")
            
            default_meta = {
                "Embedder": {
                    "config": {
                        "Model": {
                            "value": "all-MiniLM-L6-v2"  # Default
                        }
                    }
                }
            }
            
            # Atualiza o documento
            collection.data.update(
                uuid=uuid,
                properties={"meta": json.dumps(default_meta)}
            )
            
            msg.good(f"✅ Meta corrigido para documento {uuid}")
            return True
            
    except Exception as e:
        msg.fail(f"❌ Erro ao processar documento {uuid}: {str(e)}")
        return False


def main():
    """
    Função principal.
    """
    import sys
    
    # Verifica argumentos
    if len(sys.argv) < 2:
        print("""
Uso: python scripts/fix_corrupted_documents.py <comando> [opções]

Comandos:
  list          - Lista documentos corrompidos
  fix           - Corrige documentos (cria meta padrão)
  delete        - Deleta documentos corrompidos
  delete-all    - Deleta TODOS os documentos corrompidos (sem confirmação)

Exemplos:
  python scripts/fix_corrupted_documents.py list
  python scripts/fix_corrupted_documents.py fix
  python scripts/fix_corrupted_documents.py delete <uuid>
  python scripts/fix_corrupted_documents.py delete-all
        """)
        return
    
    command = sys.argv[1]
    
    # Configuração
    WEAVIATE_URL = os.getenv("WEAVIATE_URL_VERBA") or os.getenv("WEAVIATE_URL", "http://localhost:8080")
    WEAVIATE_API_KEY = os.getenv("WEAVIATE_API_KEY_VERBA") or os.getenv("WEAVIATE_API_KEY", "")
    
    # Conecta ao Weaviate diretamente
    msg.info(f"Conectando ao Weaviate: {WEAVIATE_URL}")
    
    try:
        # Conecta diretamente ao Weaviate sem passar pelo Verba
        if WEAVIATE_API_KEY:
            client = weaviate.connect_to_custom(
                http_host=WEAVIATE_URL.replace("http://", "").replace("https://", "").split(":")[0],
                http_port=int(WEAVIATE_URL.split(":")[-1]) if ":" in WEAVIATE_URL else 8080,
                http_secure=WEAVIATE_URL.startswith("https://"),
                auth_credentials=weaviate.classes.init.Auth.api_key(WEAVIATE_API_KEY) if WEAVIATE_API_KEY else None
            )
        else:
            # Local/embedded
            if "localhost" in WEAVIATE_URL or "127.0.0.1" in WEAVIATE_URL:
                client = weaviate.connect_to_local(
                    host=WEAVIATE_URL.replace("http://", "").split(":")[0],
                    port=int(WEAVIATE_URL.split(":")[-1]) if ":" in WEAVIATE_URL else 8080
                )
            else:
                # Tenta custom mesmo sem auth
                parsed = WEAVIATE_URL.replace("http://", "").replace("https://", "")
                host = parsed.split(":")[0] if ":" in parsed else parsed
                port = int(parsed.split(":")[1]) if ":" in parsed else 8080
                client = weaviate.connect_to_custom(
                    http_host=host,
                    http_port=port,
                    http_secure=WEAVIATE_URL.startswith("https://")
                )
        
        if not client.is_ready():
            msg.fail("Weaviate nao esta pronto")
            return
        
        msg.good("Conectado ao Weaviate")
        
        # Collection padrão do Verba
        collection_name = "VERBA_Document"
        
        corrupted = find_corrupted_documents(client, collection_name)
        
        if not corrupted:
            msg.good("✅ Nenhum documento corrompido encontrado!")
            return
        
        msg.warn(f"⚠️  Encontrados {len(corrupted)} documentos corrompidos:")
        for doc in corrupted:
            print(f"  - {doc['title']} ({doc['uuid']}) - {doc['problem']}")
        
        # Executa comando
        if command == "list":
            msg.info("📋 Lista de documentos corrompidos:")
            for doc in corrupted:
                print(f"  UUID: {doc['uuid']}")
                print(f"  Título: {doc['title']}")
                print(f"  Problema: {doc['problem']}")
                print()
        
        elif command == "fix":
            msg.info("Corrigindo documentos...")
            fixed = 0
            for doc in corrupted:
                if fix_document_meta(client, collection_name, doc['uuid'], "default"):
                    fixed += 1
            msg.good(f"{fixed}/{len(corrupted)} documentos corrigidos")
        
        elif command == "delete":
            if len(sys.argv) < 3:
                msg.fail("UUID necessario. Use: python scripts/fix_corrupted_documents.py delete <uuid>")
                return
            
            uuid = sys.argv[2]
            if fix_document_meta(client, collection_name, uuid, "delete"):
                msg.good("Documento deletado")
            else:
                msg.fail("Falha ao deletar documento")
        
        elif command == "delete-all":
            msg.warn("ATENCAO: Isso vai deletar TODOS os documentos corrompidos!")
            confirm = input("Digite 'SIM' para confirmar: ")
            if confirm != "SIM":
                msg.info("Operacao cancelada")
                return
            
            msg.info("Deletando documentos corrompidos...")
            deleted = 0
            for doc in corrupted:
                if fix_document_meta(client, collection_name, doc['uuid'], "delete"):
                    deleted += 1
            msg.good(f"{deleted}/{len(corrupted)} documentos deletados")
        
        else:
            msg.fail(f"❌ Comando desconhecido: {command}")
        
        client.close()
        
    except Exception as e:
        msg.fail(f"❌ Erro: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

