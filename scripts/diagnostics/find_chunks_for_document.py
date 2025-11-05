#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para encontrar chunks de um documento específico
"""

import sys
import requests

if sys.platform == 'win32':
    import io as io_encoding
    sys.stdout = io_encoding.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

weaviate_url = "https://weaviate-production-0d0e.up.railway.app"
doc_title = "Dossiê_ Flow Executive Finders.pdf"

print("🔍 Buscando documento e chunks...\n")

# 1. Busca documento
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

response = requests.post(f"{weaviate_url}/v1/graphql", json=doc_query, timeout=30)
data = response.json()
docs = data.get('data', {}).get('Get', {}).get('VERBA_DOCUMENTS', [])
if not docs:
    print("❌ Documento não encontrado")
    sys.exit(1)

doc_uuid = docs[0].get('_additional', {}).get('id')
print(f"✅ Documento: {docs[0].get('title')}")
print(f"   UUID: {doc_uuid}\n")

# 2. Busca chunks na collection principal
collection_name = "VERBA_Embedding_all_MiniLM_L6_v2"

print(f"🔍 Buscando chunks em {collection_name}...")

# Tenta buscar por título primeiro (pode ser que doc_uuid esteja diferente)
chunk_query_by_title = {
    "query": f"""
    {{
        Get {{
            {collection_name}(
                where: {{
                    path: ["title"]
                    operator: Equal
                    valueString: "{doc_title}"
                }}
                limit: 10
            ) {{
                text
                chunk_id
                doc_uuid
                title
                entities_local_ids
                entities
                section_title
                _additional {{
                    id
                }}
            }}
        }}
    }}
    """
}

response = requests.post(f"{weaviate_url}/v1/graphql", json=chunk_query_by_title, timeout=30)
data = response.json()

if 'errors' in data:
    print(f"❌ Erro: {data['errors']}")
else:
    chunks = data.get('data', {}).get('Get', {}).get(collection_name, [])
    
    if chunks:
        print(f"✅ {len(chunks)} chunks encontrados por título\n")
        
        # Mostra estatísticas
        chunks_with_entities = sum(1 for c in chunks if c.get('entities_local_ids'))
        chunks_with_section = sum(1 for c in chunks if c.get('section_title'))
        
        print(f"📊 Estatísticas:")
        print(f"   - Chunks com entities_local_ids: {chunks_with_entities}/{len(chunks)}")
        print(f"   - Chunks com section_title: {chunks_with_section}/{len(chunks)}")
        
        # Mostra exemplos
        print(f"\n📋 Exemplos de chunks com metadados:")
        for chunk in chunks[:5]:
            print(f"\n   Chunk {chunk.get('chunk_id')}:")
            print(f"      doc_uuid: {chunk.get('doc_uuid', 'N/A')[:30]}...")
            print(f"      entities_local_ids: {chunk.get('entities_local_ids', [])}")
            print(f"      section_title: {chunk.get('section_title', 'N/A')}")
            print(f"      Texto: {chunk.get('text', '')[:80]}...")
    else:
        print(f"⚠️  Nenhum chunk encontrado por título")
        
        # Tenta buscar alguns chunks aleatórios para ver a estrutura
        print(f"\n🔍 Buscando chunks aleatórios para ver estrutura...")
        random_query = {
            "query": f"""
            {{
                Get {{
                    {collection_name}(
                        limit: 5
                    ) {{
                        text
                        chunk_id
                        doc_uuid
                        title
                        entities_local_ids
                        entities
                        section_title
                        _additional {{
                            id
                        }}
                    }}
                }}
            }}
            """
        }
        
        response = requests.post(f"{weaviate_url}/v1/graphql", json=random_query, timeout=30)
        data = response.json()
        
        if 'errors' not in data:
            random_chunks = data.get('data', {}).get('Get', {}).get(collection_name, [])
            if random_chunks:
                print(f"✅ {len(random_chunks)} chunks aleatórios encontrados\n")
                print(f"📋 Estrutura de um chunk de exemplo:")
                sample = random_chunks[0]
                print(f"   - chunk_id: {sample.get('chunk_id')}")
                print(f"   - title: {sample.get('title', 'N/A')}")
                print(f"   - doc_uuid: {sample.get('doc_uuid', 'N/A')[:30]}...")
                print(f"   - entities_local_ids: {sample.get('entities_local_ids', 'N/A')}")
                print(f"   - entities: {sample.get('entities', 'N/A')}")
                print(f"   - section_title: {sample.get('section_title', 'N/A')}")
                print(f"   - text: {sample.get('text', '')[:100]}...")


