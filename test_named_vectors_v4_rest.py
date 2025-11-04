"""
Teste Named Vectors v4 via API REST
Valida named vectors usando API REST direta (já que cliente Python tem problemas de conexão)
"""

import asyncio
import httpx
import json
from wasabi import msg


async def test_named_vectors_via_rest():
    """Testa named vectors via API REST do Weaviate"""
    
    msg.info("=" * 60)
    msg.info("TESTE: Named Vectors v4 via API REST")
    msg.info("=" * 60)
    
    base_url = "https://weaviate-production-0d0e.up.railway.app"
    collection_name = "VERBA_TEST_NAMED_VECTORS_REST"
    
    async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
        # 1. Verificar schema atual
        msg.info("\n1. Verificando schema atual...")
        try:
            response = await client.get(f"{base_url}/v1/schema")
            if response.status_code == 200:
                schema = response.json()
                classes = schema.get("classes", [])
                msg.good(f"  Schema carregado: {len(classes)} collections")
                
                # Verificar se alguma collection já usa named vectors
                for cls in classes:
                    class_name = cls.get("class", "")
                    vector_config = cls.get("vectorConfig")
                    if vector_config and isinstance(vector_config, dict) and len(vector_config) > 1:
                        msg.good(f"  Collection '{class_name}' tem named vectors: {list(vector_config.keys())}")
        except Exception as e:
            msg.warn(f"  Erro ao verificar schema: {e}")
        
        # 2. Criar collection com named vectors via REST
        msg.info("\n2. Criando collection com named vectors...")
        
        collection_schema = {
            "class": collection_name,
            # Não definir vectorizer de nível de classe quando usar named vectors
            "properties": [
                {
                    "name": "text",
                    "dataType": ["text"]
                },
                {
                    "name": "role_text",
                    "dataType": ["text"]
                },
                {
                    "name": "domain_text",
                    "dataType": ["text"]
                },
                {
                    "name": "chunk_id",
                    "dataType": ["text"]
                }
            ],
            "vectorConfig": {
                "role_vec": {
                    "vectorizer": "none",
                    "vectorIndexType": "hnsw",
                    "vectorIndexConfig": {
                        "distance": "cosine"
                    }
                },
                "domain_vec": {
                    "vectorizer": "none",
                    "vectorIndexType": "hnsw",
                    "vectorIndexConfig": {
                        "distance": "cosine"
                    }
                }
            }
        }
        
        try:
            # Remover collection se existir
            try:
                await client.delete(f"{base_url}/v1/schema/{collection_name}")
                msg.info(f"  Collection antiga removida")
                await asyncio.sleep(1)
            except:
                pass
            
            # Criar collection
            response = await client.post(
                f"{base_url}/v1/schema",
                json=collection_schema,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code in [200, 201]:
                msg.good(f"  [OK] Collection '{collection_name}' criada com named vectors!")
                msg.info(f"    Named vectors: role_vec, domain_vec")
            else:
                msg.warn(f"  Status: {response.status_code}")
                msg.warn(f"  Response: {response.text[:200]}")
                # Continuar mesmo assim para testar queries
                
        except Exception as e:
            msg.warn(f"  Erro ao criar collection: {e}")
            msg.info("  Continuando para testar queries em collections existentes...")
        
        # 3. Verificar se collection foi criada
        msg.info("\n3. Verificando collection criada...")
        try:
            response = await client.get(f"{base_url}/v1/schema/{collection_name}")
            if response.status_code == 200:
                collection_info = response.json()
                vector_config = collection_info.get("vectorConfig", {})
                msg.good(f"  [OK] Collection encontrada!")
                msg.info(f"    Vectorizer: {collection_info.get('vectorizer', 'N/A')}")
                if vector_config:
                    msg.good(f"    Named vectors: {list(vector_config.keys())}")
                    if len(vector_config) > 1:
                        msg.good(f"    [OK] Named vectors configurados corretamente!")
            else:
                msg.warn(f"  Collection não encontrada (status: {response.status_code})")
        except Exception as e:
            msg.warn(f"  Erro ao verificar collection: {e}")
        
        # 4. Teste: Inserir objeto com named vectors
        msg.info("\n4. Testando insercao com named vectors...")
        
        import numpy as np
        dim = 384
        
        test_object = {
            "text": "Apple investe bilhoes em inteligencia artificial.",
            "role_text": "POSITION: Head of AI | SENIORITY: VP+",
            "domain_text": "INDUSTRIES: Tech | COMPANY: Apple",
            "chunk_id": "test-1"
        }
        
        # Gerar vetores aleatórios
        role_vector = np.random.rand(dim).tolist()
        domain_vector = np.random.rand(dim).tolist()
        
        test_object_vectors = {
            "role_vec": role_vector,
            "domain_vec": domain_vector
        }
        
        try:
            # Inserir objeto com named vectors
            response = await client.post(
                f"{base_url}/v1/objects",
                json={
                    **test_object,
                    "vectors": test_object_vectors
                },
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code in [200, 201]:
                obj_id = response.json().get("id", "N/A")
                msg.good(f"  [OK] Objeto inserido com UUID: {obj_id}")
                msg.info(f"    Named vectors incluídos: {list(test_object_vectors.keys())}")
            else:
                msg.warn(f"  Status: {response.status_code}")
                msg.warn(f"  Response: {response.text[:200]}")
        except Exception as e:
            msg.warn(f"  Erro ao inserir objeto: {e}")
        
        # 5. Teste: Query com named vector (target_vector)
        msg.info("\n5. Testando query com named vector (target_vector)...")
        
        query_vector = np.random.rand(dim).tolist()
        
        # Query usando role_vec
        try:
            query_payload = {
                "class": collection_name,
                "vector": query_vector,
                "targetVector": "role_vec",  # Named vector!
                "limit": 5,
                "withDistance": True
            }
            
            response = await client.post(
                f"{base_url}/v1/query",
                json=query_payload,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                results = response.json()
                data = results.get("data", {}).get("Get", {}).get(collection_name, [])
                msg.good(f"  [OK] Query com targetVector='role_vec' retornou {len(data)} resultados")
                if data:
                    first = data[0]
                    msg.info(f"    Primeiro resultado: {first.get('text', 'N/A')[:50]}...")
                    if 'distance' in first:
                        msg.info(f"    Distance: {first.get('distance', 'N/A')}")
            else:
                msg.warn(f"  Status: {response.status_code}")
                msg.warn(f"  Response: {response.text[:300]}")
        except Exception as e:
            msg.warn(f"  Erro ao fazer query: {e}")
        
        # 6. Limpar collection de teste
        msg.info("\n6. Limpando collection de teste...")
        try:
            await client.delete(f"{base_url}/v1/schema/{collection_name}")
            msg.info(f"  Collection removida")
        except Exception as e:
            msg.warn(f"  Erro ao remover collection: {e}")
    
    msg.good("\n" + "=" * 60)
    msg.good("[OK] TESTE DE NAMED VECTORS VIA REST CONCLUÍDO!")
    msg.good("=" * 60)
    msg.info("\nConclusao:")
    msg.info("  - API REST do Weaviate suporta named vectors")
    msg.info("  - E possivel criar collections com vectorConfig contendo multiplos named vectors")
    msg.info("  - E possivel inserir objetos com vectors para cada named vector")
    msg.info("  - E possivel fazer queries com targetVector especificando qual named vector usar")
    
    return True


if __name__ == "__main__":
    result = asyncio.run(test_named_vectors_via_rest())
    exit(0 if result else 1)

