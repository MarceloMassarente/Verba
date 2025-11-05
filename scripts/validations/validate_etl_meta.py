#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para validar ETL verificando o campo meta dos chunks
"""

import sys
import requests
import json

if sys.platform == 'win32':
    import io as io_encoding
    sys.stdout = io_encoding.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

weaviate_url = "https://weaviate-production-0d0e.up.railway.app"
doc_title = "Dossiê_ Flow Executive Finders.pdf"
collection_name = "VERBA_Embedding_all_MiniLM_L6_v2"

print("=" * 80)
print("🔍 VALIDAÇÃO: ETL Pré-Chunking (via campo meta)")
print("=" * 80 + "\n")

# 1. Busca documento
print("📄 ETAPA 1: Buscando documento...")
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

# 2. Busca chunks por título
print("=" * 80)
print("📊 ETAPA 2: Buscando chunks...")
print("=" * 80 + "\n")

chunk_query = {
    "query": f"""
    {{
        Get {{
            {collection_name}(
                where: {{
                    path: ["title"]
                    operator: Equal
                    valueString: "{doc_title}"
                }}
                limit: 20
            ) {{
                chunk_id
                title
                content
                meta
                doc_uuid
                _additional {{
                    id
                }}
            }}
        }}
    }}
    """
}

response = requests.post(f"{weaviate_url}/v1/graphql", json=chunk_query, timeout=30)
data = response.json()

if 'errors' in data:
    print(f"❌ Erro: {data['errors']}")
    sys.exit(1)

chunks = data.get('data', {}).get('Get', {}).get(collection_name, [])

if not chunks:
    print("❌ Nenhum chunk encontrado")
    sys.exit(1)

print(f"✅ {len(chunks)} chunks encontrados\n")

# 3. Analisa metadados
print("=" * 80)
print("📊 ETAPA 3: Analisando metadados de ETL...")
print("=" * 80 + "\n")

chunks_with_etl_meta = 0
chunks_with_entities = 0
chunks_with_section = 0
total_entity_ids = 0

for chunk in chunks:
    meta_str = chunk.get('meta', '')
    if not meta_str:
        continue
    
    try:
        # Tenta parsear como JSON
        if isinstance(meta_str, str):
            meta = json.loads(meta_str)
        else:
            meta = meta_str
        
        # Verifica metadados de ETL
        has_etl = False
        
        # entities_local_ids (ETL pré-chunking)
        entity_ids = meta.get('entities_local_ids', [])
        if entity_ids:
            has_etl = True
            chunks_with_entities += 1
            total_entity_ids += len(entity_ids)
        
        # entities (ETL pós-chunking)
        entities = meta.get('entities', [])
        if entities:
            has_etl = True
        
        # section_title (ETL pós-chunking)
        section_title = meta.get('section_title', '')
        if section_title:
            has_etl = True
            chunks_with_section += 1
        
        # entity_spans (ETL pré-chunking - usado no chunking)
        entity_spans = meta.get('entity_spans', [])
        if entity_spans:
            has_etl = True
        
        if has_etl:
            chunks_with_etl_meta += 1
            
    except json.JSONDecodeError:
        # Meta pode não ser JSON válido
        continue
    except Exception as e:
        continue

# 4. Mostra exemplos
print(f"📈 Estatísticas:")
print(f"   - Total de chunks analisados: {len(chunks)}")
print(f"   - Chunks com meta: {sum(1 for c in chunks if c.get('meta'))}")
print(f"   - Chunks com metadados de ETL: {chunks_with_etl_meta}")
print(f"   - Chunks com entities_local_ids: {chunks_with_entities}")
print(f"   - Chunks com section_title: {chunks_with_section}")
print(f"   - Total de entity_ids encontrados: {total_entity_ids}")

# Mostra exemplos detalhados
print(f"\n📋 Exemplos de chunks com metadados:")
print("-" * 80)

examples_shown = 0
for chunk in chunks:
    meta_str = chunk.get('meta', '')
    if not meta_str:
        continue
    
    try:
        if isinstance(meta_str, str):
            meta = json.loads(meta_str)
        else:
            meta = meta_str
        
        # Verifica se tem metadados de ETL
        entity_ids = meta.get('entities_local_ids', [])
        entity_spans = meta.get('entity_spans', [])
        section_title = meta.get('section_title', '')
        
        if entity_ids or entity_spans or section_title:
            examples_shown += 1
            if examples_shown > 5:
                break
            
            print(f"\n   Chunk {chunk.get('chunk_id')}:")
            print(f"      Content: {chunk.get('content', '')[:80]}...")
            
            if entity_spans:
                print(f"      ✅ entity_spans: {len(entity_spans)} spans (usado no chunking)")
                print(f"         Exemplos: {entity_spans[:2]}")
            
            if entity_ids:
                print(f"      ✅ entities_local_ids: {entity_ids[:5]}{'...' if len(entity_ids) > 5 else ''}")
            else:
                print(f"      ❌ entities_local_ids: NÃO DISPONÍVEL")
            
            if section_title:
                print(f"      ✅ section_title: {section_title}")
            else:
                print(f"      ❌ section_title: NÃO DISPONÍVEL")
            
            # Mostra meta completo para debug
            print(f"      Meta completo: {json.dumps(meta, indent=8, ensure_ascii=False)[:200]}...")
            
    except Exception as e:
        continue

# 5. Validação final
print("\n" + "=" * 80)
print("✅ VALIDAÇÃO FINAL")
print("=" * 80 + "\n")

if chunks_with_entities > 0:
    print(f"✅ ETL Pré-Chunking: FUNCIONOU")
    print(f"   - {chunks_with_entities} chunks têm entities_local_ids")
    print(f"   - {total_entity_ids} entity_ids encontrados")
    print(f"   - Metadados estão DISPONÍVEIS para queries")
else:
    print(f"❌ ETL Pré-Chunking: NÃO ENCONTRADO")
    print(f"   - Nenhum chunk tem entities_local_ids")
    print(f"   - Isso indica que ETL pré-chunking não foi aplicado ou não foi salvo")

if chunks_with_section > 0:
    print(f"\n✅ ETL Pós-Chunking: FUNCIONOU")
    print(f"   - {chunks_with_section} chunks têm section_title")
else:
    print(f"\n⚠️  ETL Pós-Chunking: NÃO ENCONTRADO")
    print(f"   - Nenhum chunk tem section_title")

# Testa query por entity_id
if total_entity_ids > 0:
    print(f"\n🔍 Testando query por entity_id...")
    # Pega um entity_id de exemplo do primeiro chunk com entities
    sample_entity_id = None
    for chunk in chunks:
        meta_str = chunk.get('meta', '')
        if meta_str:
            try:
                if isinstance(meta_str, str):
                    meta = json.loads(meta_str)
                else:
                    meta = meta_str
                entity_ids = meta.get('entities_local_ids', [])
                if entity_ids:
                    sample_entity_id = entity_ids[0]
                    break
            except:
                continue
    
    if sample_entity_id:
        print(f"   Testando com entity_id: {sample_entity_id}")
        # Nota: Como entities_local_ids está em meta (JSON), a query pode precisar ser diferente
        print(f"   ⚠️  Query por entity_id requer que o campo seja indexado separadamente")
        print(f"   💡 Considere adicionar entities_local_ids como campo próprio no schema")


