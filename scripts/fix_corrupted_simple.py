"""
Script simples para corrigir documentos corrompidos via HTTP REST apenas.
Não depende de gRPC, funciona com Railway público.
"""

import os
import json
import sys
import requests

WEAVIATE_URL = os.getenv("WEAVIATE_URL", "https://weaviate-production-0d0e.up.railway.app")
API_KEY = os.getenv("WEAVIATE_API_KEY_VERBA") or os.getenv("WEAVIATE_API_KEY", "")

def get_headers():
    """Retorna headers para requisições"""
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"
    return headers

def get_schema():
    """Obtém schema do Weaviate"""
    url = f"{WEAVIATE_URL.rstrip('/')}/v1/schema"
    response = requests.get(url, headers=get_headers(), timeout=30)
    response.raise_for_status()
    return response.json()

def list_all_documents(collection_name="VERBA_DOCUMENTS"):
    """Lista todos os documentos via GraphQL (v4)"""
    # Usa GraphQL para buscar objetos (sem especificar campos específicos)
    query = """
    {
      Get {
        %s(limit: 1000) {
          _additional {
            id
          }
        }
      }
    }
    """ % collection_name
    
    url = f"{WEAVIATE_URL.rstrip('/')}/v1/graphql"
    payload = {"query": query}
    
    response = requests.post(url, json=payload, headers=get_headers(), timeout=30)
    response.raise_for_status()
    data = response.json()
    
    if "errors" in data:
        raise Exception(f"GraphQL error: {data['errors']}")
    
    results = data.get("data", {}).get("Get", {}).get(collection_name, [])
    
    # Busca propriedades completas via REST API
    docs = []
    for item in results:
        doc_id = item.get("_additional", {}).get("id")
        if doc_id:
            # Busca objeto completo via REST
            try:
                obj_url = f"{WEAVIATE_URL.rstrip('/')}/v1/objects/{doc_id}"
                obj_response = requests.get(obj_url, headers=get_headers(), timeout=30)
                if obj_response.status_code == 200:
                    obj_data = obj_response.json()
                    docs.append({
                        "id": doc_id,
                        "properties": obj_data.get("properties", {})
                    })
            except Exception:
                # Se falhar, usa dados do GraphQL
                docs.append({
                    "id": doc_id,
                    "properties": {}
                })
    
    return docs

def find_corrupted():
    """Encontra documentos corrompidos"""
    print("Buscando collections disponiveis...")
    schema = get_schema()
    collections = [c.get("class", "") for c in schema.get("classes", [])]
    print(f"Collections encontradas: {collections}")
    
    # Tenta encontrar collection de documentos
    doc_collection = None
    for coll in collections:
        if "DOCUMENTS" in coll.upper() and "EMBEDDING" not in coll.upper():
            doc_collection = coll
            break
    
    if not doc_collection:
        print("Nenhuma collection de documentos encontrada!")
        return []
    
    print(f"Usando collection: {doc_collection}")
    print("Buscando documentos...")
    docs = list_all_documents(doc_collection)
    print(f"Total de documentos: {len(docs)}")
    
    corrupted = []
    for doc in docs:
        props = doc.get("properties", {})
        meta = props.get("meta")
        
        if meta is None:
            corrupted.append({
                "uuid": doc["id"],
                "title": props.get("title", "Sem titulo"),
                "problem": "meta is None"
            })
        elif isinstance(meta, str):
            try:
                json.loads(meta)
            except (json.JSONDecodeError, TypeError):
                corrupted.append({
                    "uuid": doc["id"],
                    "title": props.get("title", "Sem titulo"),
                    "problem": "meta is not valid JSON"
                })
        else:
            corrupted.append({
                "uuid": doc["id"],
                "title": props.get("title", "Sem titulo"),
                "problem": f"meta is not string: {type(meta)}"
            })
    
    return corrupted

def fix_document(uuid, collection_name="VERBA_Document", fix_mode="default"):
    """Corrige ou deleta documento via GraphQL"""
    if fix_mode == "delete":
        # Deleta via GraphQL mutation
        mutation = """
        mutation {
          Delete {
            %s(where: {path: ["id"], operator: Equal, valueString: "%s"}) {
              successful
            }
          }
        }
        """ % (collection_name, uuid)
        
        url = f"{WEAVIATE_URL.rstrip('/')}/v1/graphql"
        payload = {"query": mutation}
        response = requests.post(url, json=payload, headers=get_headers(), timeout=30)
        response.raise_for_status()
        data = response.json()
        
        if data.get("data", {}).get("Delete", {}).get(collection_name, []):
            print(f"Documento {uuid} deletado!")
            return True
        else:
            print(f"Falha ao deletar documento {uuid}")
            return False
    else:
        # Corrige meta - usa GraphQL Update (mais compatível com v4)
        default_meta = {
            "Embedder": {
                "config": {
                    "Model": {
                        "value": "all-MiniLM-L6-v2"
                    }
                }
            }
        }
        
        meta_json = json.dumps(default_meta)
        # Escapa para GraphQL
        meta_escaped = meta_json.replace('\\', '\\\\').replace('"', '\\"')
        
        # GraphQL Update mutation
        mutation = """
        mutation {
          Update {
            %s(where: {path: ["id"], operator: Equal, valueString: "%s"}, set: {meta: "%s"}) {
              successful
            }
          }
        }
        """ % (collection_name, uuid, meta_escaped)
        
        url = f"{WEAVIATE_URL.rstrip('/')}/v1/graphql"
        payload = {"query": mutation}
        
        try:
            response = requests.post(url, json=payload, headers=get_headers(), timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if "errors" in data:
                # Se GraphQL falhar, tenta batch update
                return fix_via_batch(uuid, collection_name, default_meta)
            
            update_result = data.get("data", {}).get("Update", {}).get(collection_name, [])
            # update_result pode ser lista ou dict
            if isinstance(update_result, list) and len(update_result) > 0:
                print(f"Meta corrigido para documento {uuid}")
                return True
            elif isinstance(update_result, dict) and update_result.get("successful"):
                print(f"Meta corrigido para documento {uuid}")
                return True
            else:
                # Tenta batch update como fallback
                return fix_via_batch(uuid, collection_name, default_meta)
        except Exception as e:
            print(f"Erro GraphQL, tentando batch: {e}")
            return fix_via_batch(uuid, collection_name, default_meta)

def fix_via_batch(uuid, collection_name, default_meta):
    """Tenta corrigir via REST API v1 (PUT para atualizar)"""
    try:
        # Weaviate v1 REST API - PUT para atualizar objeto completo
        # Primeiro busca o objeto atual
        get_url = f"{WEAVIATE_URL.rstrip('/')}/v1/objects/{uuid}"
        get_response = requests.get(get_url, headers=get_headers(), timeout=30)
        
        if get_response.status_code != 200:
            print(f"Nao foi possivel buscar documento {uuid}: {get_response.status_code}")
            print(f"Response: {get_response.text[:200]}")
            return False
        
        obj_data = get_response.json()
        current_props = obj_data.get("properties", {}).copy()  # Cria cópia
        obj_class = obj_data.get("class")  # Pega class do objeto
        
        # Remove campos imutáveis que podem estar no objeto
        for key in ["id", "uuid", "_id"]:
            if key in current_props:
                del current_props[key]
        
        # Atualiza apenas o campo meta
        current_props["meta"] = json.dumps(default_meta)
        
        # Tenta PATCH primeiro (mais comum em v4)
        patch_url = f"{WEAVIATE_URL.rstrip('/')}/v1/objects/{uuid}"
        patch_payload = {
            "properties": {
                "meta": json.dumps(default_meta)
            }
        }
        
        patch_response = requests.patch(patch_url, json=patch_payload, headers=get_headers(), timeout=30)
        
        if patch_response.status_code == 200:
            print(f"Meta corrigido via PATCH para documento {uuid}")
            return True
        
        # Se PATCH falhar, tenta PUT
        put_url = f"{WEAVIATE_URL.rstrip('/')}/v1/objects/{uuid}"
        put_payload = {
            "class": obj_class or collection_name,
            "properties": current_props
        }
        
        put_response = requests.put(put_url, json=put_payload, headers=get_headers(), timeout=30)
        put_response.raise_for_status()
        
        print(f"Meta corrigido via PUT para documento {uuid}")
        return True
    except requests.exceptions.HTTPError as e:
        print(f"Falha ao corrigir documento {uuid}: {e}")
        if hasattr(e.response, 'text'):
            print(f"Detalhes: {e.response.text[:300]}")
        return False
    except Exception as e:
        print(f"Falha ao corrigir documento {uuid}: {e}")
        return False

def main():
    if len(sys.argv) < 2:
        print("""
Uso: python scripts/fix_corrupted_simple.py <comando>

Comandos:
  list          - Lista documentos corrompidos
  fix           - Corrige documentos (cria meta padrao)
  delete-all    - Deleta TODOS os documentos corrompidos

Exemplos:
  WEAVIATE_URL=https://weaviate-production-0d0e.up.railway.app python scripts/fix_corrupted_simple.py list
  WEAVIATE_URL=https://weaviate-production-0d0e.up.railway.app python scripts/fix_corrupted_simple.py fix
        """)
        return
    
    command = sys.argv[1]
    
    print(f"Conectando ao Weaviate: {WEAVIATE_URL}")
    
    try:
        # Testa conexão
        response = requests.get(f"{WEAVIATE_URL.rstrip('/')}/v1/.well-known/ready", timeout=10)
        response.raise_for_status()
        print("Conectado ao Weaviate!")
        
        corrupted = find_corrupted()
        
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
            # Pega collection name do schema
            schema = get_schema()
            collection_name = None
            for coll in schema.get("classes", []):
                if "Document" in coll.get("class", "") or "VERBA" in coll.get("class", "").upper():
                    collection_name = coll.get("class")
                    break
            if not collection_name and schema.get("classes"):
                collection_name = schema["classes"][0].get("class")
            
            for doc in corrupted:
                try:
                    if fix_document(doc['uuid'], collection_name or "VERBA_Document", "default"):
                        fixed += 1
                except Exception as e:
                    print(f"Erro ao corrigir {doc['uuid']}: {e}")
            print(f"\n{fixed}/{len(corrupted)} documentos corrigidos!")
        
        elif command == "delete-all":
            print("\nATENCAO: Isso vai deletar TODOS os documentos corrompidos!")
            confirm = input("Digite 'SIM' para confirmar: ")
            if confirm != "SIM":
                print("Operacao cancelada")
                return
            
            print("\nDeletando documentos corrompidos...")
            # Pega collection name
            schema = get_schema()
            collection_name = None
            for coll in schema.get("classes", []):
                if "Document" in coll.get("class", "") or "VERBA" in coll.get("class", "").upper():
                    collection_name = coll.get("class")
                    break
            if not collection_name and schema.get("classes"):
                collection_name = schema["classes"][0].get("class")
            
            deleted = 0
            for doc in corrupted:
                try:
                    if fix_document(doc['uuid'], collection_name or "VERBA_Document", "delete"):
                        deleted += 1
                except Exception as e:
                    print(f"Erro ao deletar {doc['uuid']}: {e}")
            print(f"\n{deleted}/{len(corrupted)} documentos deletados!")
        
        else:
            print(f"Comando desconhecido: {command}")
        
    except Exception as e:
        print(f"Erro: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

