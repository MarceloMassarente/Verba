#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para validar se ETL pré-chunking foi usado e está disponível nos chunks
Verifica:
1. Se entity_spans foram usados no chunking
2. Se entidades estão registradas nos chunks
3. Se estão disponíveis para queries
"""

import sys
import requests
import json

if sys.platform == 'win32':
    import io as io_encoding
    sys.stdout = io_encoding.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

weaviate_url = "https://weaviate-production-0d0e.up.railway.app"
doc_title = "Dossiê_ Flow Executive Finders.pdf"

print("=" * 80)
print("🔍 VALIDAÇÃO: ETL Pré-Chunking")
print("=" * 80 + "\n")

# 1. Busca o documento
print("📄 ETAPA 1: Buscando documento...")
try:
    doc_query = {
        "query": """
        {
            Get {
                VERBA_DOCUMENTS(
                    where: {
                        path: ["title"]
                        operator: Equal
                        valueString: "Dossiê_ Flow Executive Finders.pdf"
                    }
                    limit: 1
                ) {
                    title
                    _additional {
                        id
                    }
                }
            }
        }
        """
    }
    
    response = requests.post(
        f"{weaviate_url}/v1/graphql",
        json=doc_query,
        headers={"Content-Type": "application/json"},
        timeout=30
    )
    
    if response.status_code != 200:
        print(f"❌ Erro ao buscar documento: {response.status_code}")
        sys.exit(1)
    
    data = response.json()
    if 'errors' in data:
        print(f"❌ Erro GraphQL: {data['errors']}")
        sys.exit(1)
    
    docs = data.get('data', {}).get('Get', {}).get('VERBA_DOCUMENTS', [])
    if not docs:
        print(f"❌ Documento não encontrado")
        sys.exit(1)
    
    doc = docs[0]
    doc_uuid = doc.get('_additional', {}).get('id')
    print(f"✅ Documento encontrado: {doc.get('title')}")
    print(f"   UUID: {doc_uuid}\n")
    
except Exception as e:
    print(f"❌ Erro: {str(e)}")
    sys.exit(1)

# 2. Busca chunks e verifica metadados de ETL
print("=" * 80)
print("📊 ETAPA 2: Verificando chunks e metadados de ETL...")
print("=" * 80 + "\n")

embedding_collections = [
    "VERBA_Embedding_all_MiniLM_L6_v2",
    "VERBA_Embedding_SentenceTransformers"
]

chunks_found = False
for collection_name in embedding_collections:
    print(f"🔍 Testando collection: {collection_name}...")
    
    chunk_query = {
        "query": f"""
        {{
            Get {{
                {collection_name}(
                    where: {{
                        path: ["doc_uuid"]
                        operator: Equal
                        valueString: "{doc_uuid}"
                    }}
                    limit: 20
                ) {{
                    text
                    chunk_id
                    doc_uuid
                    title
                    # Metadados de ETL pré-chunking
                    entities_local_ids
                    entities
                    section_entity_ids
                    section_title
                    # Metadados gerais
                    _additional {{
                        id
                    }}
                }}
            }}
        }}
        """
    }
    
    try:
        response = requests.post(
            f"{weaviate_url}/v1/graphql",
            json=chunk_query,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            if 'errors' not in data:
                chunks = data.get('data', {}).get('Get', {}).get(collection_name, [])
                if chunks:
                    print(f"✅ {len(chunks)} chunks encontrados em {collection_name}\n")
                    chunks_found = True
                    
                    # Analisa metadados de ETL
                    print("=" * 80)
                    print("📊 ANÁLISE DE METADADOS DE ETL")
                    print("=" * 80 + "\n")
                    
                    # Estatísticas
                    chunks_with_entities = 0
                    chunks_with_entity_ids = 0
                    chunks_with_section = 0
                    total_entities = 0
                    total_entity_ids = 0
                    
                    for chunk in chunks:
                        # Verifica entities_local_ids (ETL pré-chunking)
                        entity_ids = chunk.get('entities_local_ids', [])
                        if entity_ids:
                            chunks_with_entity_ids += 1
                            total_entity_ids += len(entity_ids)
                        
                        # Verifica entities (pode ser do ETL pós-chunking)
                        entities = chunk.get('entities', [])
                        if entities:
                            chunks_with_entities += 1
                            total_entities += len(entities)
                        
                        # Verifica section (ETL pós-chunking)
                        section_title = chunk.get('section_title', '')
                        if section_title:
                            chunks_with_section += 1
                    
                    print(f"📈 Estatísticas Gerais:")
                    print(f"   - Total de chunks analisados: {len(chunks)}")
                    print(f"   - Chunks com entities_local_ids: {chunks_with_entity_ids} ({chunks_with_entity_ids/len(chunks)*100:.1f}%)")
                    print(f"   - Chunks com entities: {chunks_with_entities} ({chunks_with_entities/len(chunks)*100:.1f}%)")
                    print(f"   - Chunks com section_title: {chunks_with_section} ({chunks_with_section/len(chunks)*100:.1f}%)")
                    print(f"   - Total de entity_ids: {total_entity_ids}")
                    print(f"   - Total de entities: {total_entities}")
                    
                    # Mostra exemplos de chunks com metadados
                    print(f"\n📋 Exemplos de Chunks com Metadados de ETL:")
                    print("-" * 80)
                    
                    examples_shown = 0
                    for chunk in chunks:
                        entity_ids = chunk.get('entities_local_ids', [])
                        entities = chunk.get('entities', [])
                        section_title = chunk.get('section_title', '')
                        
                        if entity_ids or entities or section_title:
                            examples_shown += 1
                            if examples_shown > 5:
                                break
                            
                            print(f"\n   Chunk {chunk.get('chunk_id')}:")
                            chunk_text = chunk.get('text', '')[:100]
                            print(f"      Texto: {chunk_text}...")
                            
                            if entity_ids:
                                print(f"      ✅ entities_local_ids: {entity_ids[:5]}{'...' if len(entity_ids) > 5 else ''}")
                            else:
                                print(f"      ❌ entities_local_ids: NÃO DISPONÍVEL")
                            
                            if entities:
                                print(f"      ✅ entities: {len(entities)} entidades")
                            else:
                                print(f"      ❌ entities: NÃO DISPONÍVEL")
                            
                            if section_title:
                                print(f"      ✅ section_title: {section_title}")
                            else:
                                print(f"      ❌ section_title: NÃO DISPONÍVEL")
                    
                    # Verifica se há chunks SEM metadados
                    chunks_without_etl = len(chunks) - chunks_with_entity_ids - chunks_with_entities
                    if chunks_without_etl > 0:
                        print(f"\n⚠️  {chunks_without_etl} chunks SEM metadados de ETL")
                    
                    # Validação
                    print("\n" + "=" * 80)
                    print("✅ VALIDAÇÃO")
                    print("=" * 80 + "\n")
                    
                    if chunks_with_entity_ids > 0:
                        print(f"✅ ETL Pré-Chunking: FUNCIONOU")
                        print(f"   - {chunks_with_entity_ids} chunks têm entities_local_ids")
                        print(f"   - Isso indica que entity_spans foram usados no chunking")
                    else:
                        print(f"❌ ETL Pré-Chunking: NÃO ENCONTRADO")
                        print(f"   - Nenhum chunk tem entities_local_ids")
                        print(f"   - Isso indica que ETL pré-chunking não foi aplicado ou não foi salvo")
                    
                    if chunks_with_entities > 0 or chunks_with_section > 0:
                        print(f"\n✅ ETL Pós-Chunking: FUNCIONOU")
                        print(f"   - {chunks_with_entities} chunks têm entities")
                        print(f"   - {chunks_with_section} chunks têm section_title")
                    else:
                        print(f"\n⚠️  ETL Pós-Chunking: NÃO ENCONTRADO")
                        print(f"   - Nenhum chunk tem entities ou section_title")
                        print(f"   - Isso pode indicar que ETL pós-chunking não foi executado")
                    
                    # Testa se está disponível para queries
                    print("\n" + "=" * 80)
                    print("🔍 ETAPA 3: Testando Disponibilidade para Queries")
                    print("=" * 80 + "\n")
                    
                    # Tenta buscar chunks por entity_id
                    if total_entity_ids > 0:
                        # Pega um entity_id de exemplo
                        sample_entity_id = None
                        for chunk in chunks:
                            entity_ids = chunk.get('entities_local_ids', [])
                            if entity_ids:
                                sample_entity_id = entity_ids[0]
                                break
                        
                        if sample_entity_id:
                            print(f"🔍 Testando query por entity_id: {sample_entity_id}")
                            
                            query_test = {
                                "query": f"""
                                {{
                                    Get {{
                                        {collection_name}(
                                            where: {{
                                                path: ["entities_local_ids"]
                                                operator: ContainsAny
                                                valueString: ["{sample_entity_id}"]
                                            }}
                                            limit: 5
                                        ) {{
                                            text
                                            chunk_id
                                            entities_local_ids
                                            _additional {{
                                                id
                                            }}
                                        }}
                                    }}
                                }}
                                """
                            }
                            
                            query_response = requests.post(
                                f"{weaviate_url}/v1/graphql",
                                json=query_test,
                                headers={"Content-Type": "application/json"},
                                timeout=30
                            )
                            
                            if query_response.status_code == 200:
                                query_data = query_response.json()
                                if 'errors' not in query_data:
                                    query_chunks = query_data.get('data', {}).get('Get', {}).get(collection_name, [])
                                    print(f"   ✅ Query funcionou: {len(query_chunks)} chunks encontrados")
                                    print(f"   ✅ Metadados de ETL estão DISPONÍVEIS para queries")
                                else:
                                    print(f"   ⚠️  Erro na query: {query_data.get('errors')}")
                            else:
                                print(f"   ⚠️  Erro HTTP: {query_response.status_code}")
                    else:
                        print(f"⚠️  Não há entity_ids para testar queries")
                    
                    break
                    
    except Exception as e:
        print(f"   ⚠️  Erro: {str(e)}")
        continue

if not chunks_found:
    print("❌ Nenhum chunk encontrado nas collections testadas")
    print("   Verifique se o documento foi importado corretamente")

print("\n" + "=" * 80)
print("📋 RESUMO FINAL")
print("=" * 80 + "\n")

if chunks_found:
    print("✅ Chunks encontrados e analisados")
    print("📊 Verifique as estatísticas acima para confirmar se ETL foi aplicado")
else:
    print("❌ Não foi possível encontrar chunks para análise")


