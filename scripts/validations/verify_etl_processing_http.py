"""
Script para verificar ETL usando HTTP direto (quando gRPC falha)

Uso:
    python scripts/verify_etl_processing_http.py https://weaviate-production-0d0e.up.railway.app "Estudo Mercado Headhunting Brasil.pdf"
"""

import os
import sys
import json
import requests
from typing import Optional, List, Dict, Any
from wasabi import msg


def get_weaviate_url() -> str:
    """Obtém URL do Weaviate"""
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = os.getenv("WEAVIATE_URL", "http://localhost:8080")
    return url.rstrip("/")


def get_doc_title() -> Optional[str]:
    """Obtém título do documento"""
    if len(sys.argv) > 2:
        return sys.argv[2]
    return None


def weaviate_get(url: str, path: str, headers: Dict = None) -> Dict:
    """Faz GET request ao Weaviate"""
    full_url = f"{url}{path}"
    if headers is None:
        headers = {}
    
    try:
        response = requests.get(full_url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        msg.fail(f"Erro ao fazer GET {path}: {str(e)}")
        raise


def weaviate_post(url: str, path: str, data: Dict, headers: Dict = None) -> Dict:
    """Faz POST request ao Weaviate"""
    full_url = f"{url}{path}"
    if headers is None:
        headers = {"Content-Type": "application/json"}
    
    try:
        response = requests.post(full_url, json=data, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        msg.fail(f"Erro ao fazer POST {path}: {str(e)}")
        raise


def get_document_by_title(weaviate_url: str, doc_title: str) -> Optional[Dict]:
    """Busca documento por título usando GraphQL v4"""
    # GraphQL query format for Weaviate v4
    query_str = f"""
    {{
        Get {{
            VERBA_DOCUMENTS(
                where: {{
                    path: ["title"]
                    operator: Equal
                    valueString: "{doc_title}"
                }}
                limit: 1
            ) {{
                _additional {{
                    id
                }}
                title
            }}
        }}
    }}
    """
    
    query = {"query": query_str}
    
    try:
        result = weaviate_post(weaviate_url, "/v1/graphql", query)
        if result.get("data", {}).get("Get", {}).get("VERBA_DOCUMENTS"):
            docs = result["data"]["Get"]["VERBA_DOCUMENTS"]
            if docs:
                return docs[0]
        return None
    except Exception as e:
        msg.warn(f"Erro ao buscar documento: {str(e)}")
        # Tenta método alternativo via REST
        try:
            msg.info("Tentando metodo alternativo via REST...")
            # Busca via REST API
            response = requests.get(
                f"{weaviate_url}/v1/objects?class=VERBA_DOCUMENTS&limit=100",
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                objects = data.get("objects", [])
                for obj in objects:
                    props = obj.get("properties", {})
                    if props.get("title") == doc_title:
                        return {
                            "_additional": {"id": obj.get("id")},
                            "properties": props
                        }
        except Exception as e2:
            msg.warn(f"Metodo alternativo tambem falhou: {str(e2)}")
        return None


def get_collections(weaviate_url: str) -> List[str]:
    """Lista todas as collections"""
    try:
        result = weaviate_get(weaviate_url, "/v1/schema")
        return [cls["class"] for cls in result.get("classes", [])]
    except Exception as e:
        msg.warn(f"Erro ao listar collections: {str(e)}")
        return []


def get_collection_schema(weaviate_url: str, collection_name: str) -> Dict:
    """Obtém schema de uma collection"""
    try:
        result = weaviate_get(weaviate_url, f"/v1/schema/{collection_name}")
        return result
    except Exception as e:
        msg.warn(f"Erro ao obter schema: {str(e)}")
        return {}


def get_chunks_for_document(weaviate_url: str, collection_name: str, doc_uuid: str, limit: int = 100) -> List[Dict]:
    """Busca chunks de um documento"""
    # Tenta via REST primeiro
    try:
        # Escapa o UUID se necessário
        import urllib.parse
        encoded_uuid = urllib.parse.quote(doc_uuid, safe='')
        response = requests.get(
            f"{weaviate_url}/v1/objects?class={collection_name}&where={{\"path\":[\"doc_uuid\"],\"operator\":\"Equal\",\"valueString\":\"{doc_uuid}\"}}&limit={limit}",
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        if response.status_code == 200:
            data = response.json()
            objects = data.get("objects", [])
            return [{"_additional": {"id": obj.get("id")}, "properties": obj.get("properties", {})} for obj in objects]
    except Exception as e:
        msg.warn(f"REST method failed: {str(e)}, trying GraphQL...")
    
    # Fallback para GraphQL
    query_str = f"""
    {{
        Get {{
            {collection_name}(
                where: {{
                    path: ["doc_uuid"]
                    operator: Equal
                    valueString: "{doc_uuid}"
                }}
                limit: {limit}
            ) {{
                _additional {{ id }}
                entities_local_ids
                section_title
                section_entity_ids
                primary_entity_id
                etl_version
            }}
        }}
    }}
    """
    
    query = {"query": query_str}
    
    try:
        result = weaviate_post(weaviate_url, "/v1/graphql", query)
        if result.get("data", {}).get("Get", {}).get(collection_name):
            return result["data"]["Get"][collection_name]
        return []
    except Exception as e:
        msg.warn(f"Erro ao buscar chunks: {str(e)}")
        return []


def check_etl_properties(chunk: Dict) -> Dict[str, bool]:
    """Verifica se chunk tem propriedades ETL"""
    props = chunk.get("properties", {})
    return {
        "has_entities_local": bool(props.get("entities_local_ids")),
        "has_section_title": bool(props.get("section_title")),
        "has_section_entities": bool(props.get("section_entity_ids")),
        "has_primary_entity": bool(props.get("primary_entity_id")),
        "has_etl_version": bool(props.get("etl_version")),
        "has_etl": bool(props.get("entities_local_ids") or props.get("section_title") or props.get("primary_entity_id"))
    }


def verify_etl_processing(weaviate_url: str, doc_title: str = None):
    """Verifica se ETL foi processado corretamente"""
    msg.info("=" * 70)
    msg.info("Verificacao de Processamento ETL (via HTTP)")
    msg.info("=" * 70)
    
    # Lista documentos se não especificado
    if not doc_title:
        msg.info("\n📋 Buscando documentos...")
        # Tenta via REST primeiro (mais simples)
        docs = []
        try:
            response = requests.get(
                f"{weaviate_url}/v1/objects?class=VERBA_DOCUMENTS&limit=10",
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                objects = data.get("objects", [])
                docs = [{"_additional": {"id": obj.get("id")}, "properties": obj.get("properties", {})} for obj in objects]
        except Exception as e:
            # Fallback para GraphQL
            msg.warn(f"REST falhou, tentando GraphQL: {str(e)}")
            query_str = """
            {
                Get {
                    VERBA_DOCUMENTS(limit: 10) {
                        _additional { id }
                        title
                    }
                }
            }
            """
            query = {"query": query_str}
            try:
                result = weaviate_post(weaviate_url, "/v1/graphql", query)
                docs = result.get("data", {}).get("Get", {}).get("VERBA_DOCUMENTS", [])
            except Exception as e2:
                msg.warn(f"GraphQL tambem falhou: {str(e2)}")
        
        if docs:
            msg.info(f"\nDocumentos encontrados: {len(docs)}")
            for i, doc in enumerate(docs, 1):
                title = doc.get("properties", {}).get("title", "N/A")
                msg.info(f"   {i}. {title}")
            if docs:
                doc_title = docs[0].get("properties", {}).get("title")
                msg.info(f"\nVerificando primeiro documento: {doc_title}")
        else:
            msg.fail("Nenhum documento encontrado")
            return
    
    # Busca documento
    msg.info(f"\nBuscando documento: {doc_title}")
    document = get_document_by_title(weaviate_url, doc_title)
    
    if not document:
        msg.fail(f"Documento '{doc_title}' nao encontrado")
        return
    
    doc_uuid = document.get("_additional", {}).get("id", "")
    doc_props = document.get("properties", {})
    msg.good(f"Documento encontrado: {doc_uuid[:50]}...")
    msg.info(f"   Titulo: {doc_props.get('title', 'N/A')}")
    
    # Lista collections de embedding
    all_collections = get_collections(weaviate_url)
    embedding_collections = [c for c in all_collections if "VERBA_Embedding" in c]
    
    if not embedding_collections:
        msg.fail("Nenhuma collection de embedding encontrada")
        return
    
    msg.info(f"\nCollections de embedding encontradas: {len(embedding_collections)}")
    
    # Verifica cada collection - primeiro verifica quais têm chunks
    collections_with_chunks = []
    for collection_name in embedding_collections:
        chunks_check = get_chunks_for_document(weaviate_url, collection_name, doc_uuid, limit=1)
        if chunks_check:
            collections_with_chunks.append((collection_name, len(chunks_check)))
    
    if collections_with_chunks:
        msg.info(f"\nCollections com chunks encontradas: {len(collections_with_chunks)}")
        for col_name, count in collections_with_chunks:
            msg.info(f"   - {col_name}: {count} chunk(s) (amostra)")
    
    # Verifica cada collection
    for collection_name in embedding_collections:
        msg.info(f"\n{'=' * 70}")
        msg.info(f"Verificando: {collection_name}")
        msg.info(f"{'=' * 70}")
        
        # Verifica schema
        schema = get_collection_schema(weaviate_url, collection_name)
        props = schema.get("properties", [])
        prop_names = [p.get("name") for p in props]
        
        etl_props = [
            "entities_local_ids", "section_title", "section_entity_ids",
            "section_scope_confidence", "primary_entity_id", 
            "entity_focus_score", "etl_version"
        ]
        
        has_etl_props = any(p in prop_names for p in etl_props)
        if has_etl_props:
            msg.good(f"Schema ETL-aware presente")
            found_etl = [p for p in etl_props if p in prop_names]
            msg.info(f"   Propriedades ETL: {', '.join(found_etl)}")
        else:
            msg.warn(f"Schema ETL-aware NAO encontrado")
        
        # Busca chunks
        chunks = get_chunks_for_document(weaviate_url, collection_name, doc_uuid, limit=100)
        
        if not chunks:
            msg.info(f"   Nenhum chunk encontrado nesta collection")
            continue
        
        msg.good(f"{len(chunks)} chunks encontrados (amostra)")
        
        # Analisa chunks
        chunks_with_etl = 0
        chunks_with_entities = 0
        chunks_with_section = 0
        total_entities = 0
        
        for chunk in chunks:
            etl_check = check_etl_properties(chunk)
            
            if etl_check["has_etl"]:
                chunks_with_etl += 1
            if etl_check["has_entities_local"]:
                chunks_with_entities += 1
                props = chunk.get("properties", {})
                entities = props.get("entities_local_ids", [])
                if isinstance(entities, list):
                    total_entities += len(entities)
            if etl_check["has_section_title"] or etl_check["has_section_entities"]:
                chunks_with_section += 1
        
        # Estatísticas
        msg.info(f"\nEstatisticas dos Chunks (amostra de {len(chunks)}):")
        msg.info(f"   Chunks com ETL: {chunks_with_etl}/{len(chunks)}")
        msg.info(f"   Chunks com entidades: {chunks_with_entities}/{len(chunks)}")
        msg.info(f"   Chunks com section scope: {chunks_with_section}/{len(chunks)}")
        
        if chunks_with_etl > 0:
            msg.good(f"ETL foi processado! {chunks_with_etl} chunks tem propriedades ETL")
            
            # Mostra exemplo de chunk com ETL
            for chunk in chunks[:5]:
                props = chunk.get("properties", {})
                if props.get("entities_local_ids"):
                    msg.info(f"\nExemplo de chunk com ETL:")
                    chunk_id = chunk.get("_additional", {}).get("id", "N/A")
                    msg.info(f"   UUID: {str(chunk_id)[:50]}...")
                    entities_local = props.get("entities_local_ids", [])
                    msg.info(f"   Entidades (local): {entities_local[:5] if isinstance(entities_local, list) else 'N/A'}")
                    entities_section = props.get("section_entity_ids", [])
                    msg.info(f"   Entidades (section): {entities_section[:5] if isinstance(entities_section, list) else 'N/A'}")
                    msg.info(f"   Primary Entity: {props.get('primary_entity_id', 'N/A')}")
                    msg.info(f"   Section Title: {props.get('section_title', 'N/A')}")
                    msg.info(f"   ETL Version: {props.get('etl_version', 'N/A')}")
                    break
        else:
            msg.warn(f"Nenhum chunk tem propriedades ETL preenchidas")
            msg.info(f"   Isso pode indicar que ETL pos-chunking nao foi executado")
    
    msg.info(f"\n{'=' * 70}")
    msg.info("Verificacao concluida")
    msg.info(f"{'=' * 70}")


def main():
    """Função principal"""
    weaviate_url = get_weaviate_url()
    doc_title = get_doc_title()
    
    msg.info(f"Conectando ao Weaviate: {weaviate_url}")
    
    # Testa conexão
    try:
        # Tenta obter schema para verificar conexão
        result = weaviate_get(weaviate_url, "/v1/schema")
        msg.good("Weaviate esta acessivel")
    except Exception as e:
        msg.warn(f"Erro ao verificar conexao (continuando mesmo assim): {str(e)}")
        # Continua mesmo se falhar, pode ser que GraphQL funcione
    
    # Verifica ETL
    try:
        verify_etl_processing(weaviate_url, doc_title)
    except Exception as e:
        msg.fail(f"❌ Erro durante verificação: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

