#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para acessar Weaviate via REST API e verificar conteúdo
"""

import sys
import requests
import json

if sys.platform == 'win32':
    import io as io_encoding
    sys.stdout = io_encoding.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

weaviate_url = "https://weaviate-production-0d0e.up.railway.app"

print(f"🔗 Acessando Weaviate via REST: {weaviate_url}\n")
print("=" * 80)

# Testa conexão
try:
    response = requests.get(f"{weaviate_url}/v1/.well-known/ready", timeout=10)
    if response.status_code == 200:
        print("✅ Weaviate está acessível\n")
    else:
        print(f"⚠️  Weaviate respondeu com status {response.status_code}\n")
except Exception as e:
    print(f"❌ Erro ao conectar: {str(e)}\n")
    sys.exit(1)

# Busca schema
print("🔍 Verificando schema...\n")
try:
    response = requests.get(f"{weaviate_url}/v1/schema", timeout=10)
    if response.status_code == 200:
        schema = response.json()
        classes = schema.get('classes', [])
        print(f"✅ Schema encontrado: {len(classes)} classes\n")
        
        # Procura VERBA_DOCUMENTS
        doc_class = None
        for cls in classes:
            if cls.get('class') == 'VERBA_DOCUMENTS':
                doc_class = cls
                break
        
        if doc_class:
            print(f"✅ Collection VERBA_DOCUMENTS encontrada\n")
        else:
            print(f"⚠️  Collection VERBA_DOCUMENTS não encontrada")
            print(f"   Classes disponíveis:")
            for cls in classes:
                print(f"   - {cls.get('class')}")
    else:
        print(f"❌ Erro ao buscar schema: {response.status_code}")
except Exception as e:
    print(f"❌ Erro: {str(e)}")

# Busca documento específico
print("\n" + "=" * 80)
print("🔍 Buscando documento 'Dossiê_ Flow Executive Finders.pdf'...\n")

try:
    # Query GraphQL para buscar documento
    query = {
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
                    content
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
        json=query,
        headers={"Content-Type": "application/json"},
        timeout=30
    )
    
    if response.status_code == 200:
        data = response.json()
        if 'errors' in data:
            print(f"❌ Erro GraphQL: {data['errors']}\n")
        else:
            results = data.get('data', {}).get('Get', {}).get('VERBA_DOCUMENTS', [])
            
            if results:
                doc = results[0]
                print(f"✅ Documento encontrado!\n")
                print(f"📄 Título: {doc.get('title')}\n")
                print(f"📄 UUID: {doc.get('_additional', {}).get('id')}\n")
                
                content = doc.get('content', '')
                print("=" * 80)
                print("📊 ANÁLISE DO CONTEÚDO NO WEAVIATE")
                print("=" * 80 + "\n")
                
                lines = content.split('\n')
                non_empty_lines = [l.strip() for l in lines if l.strip()]
                
                print(f"📈 Estatísticas:")
                print(f"   - Total de linhas: {len(lines)}")
                print(f"   - Linhas não vazias: {len(non_empty_lines)}")
                print(f"   - Total de caracteres: {len(content)}")
                
                # Procura padrão de repetição
                print(f"\n🔍 Buscando padrão 'posicionamento':")
                pos_lines = [l for l in non_empty_lines if 'posicionamento' in l.lower() and 'flow' in l.lower()]
                print(f"   - Linhas encontradas: {len(pos_lines)}")
                
                if pos_lines:
                    print(f"\n   📋 Linhas com 'posicionamento' e 'Flow':")
                    for i, line in enumerate(pos_lines[:10]):
                        print(f"      {i+1}: {line[:80]}")
                
                # Verifica padrão de repetição progressiva
                print(f"\n🔍 Verificando padrão de repetição progressiva:")
                progressive_patterns = []
                for i in range(len(non_empty_lines) - 1):
                    curr = non_empty_lines[i]
                    next_l = non_empty_lines[i + 1] if i + 1 < len(non_empty_lines) else ""
                    
                    if 'posicionamento' in curr.lower() or 'posicionamento' in next_l.lower():
                        if len(curr) > 10 and len(next_l) > 10:
                            # Verifica corte progressivo
                            if (next_l in curr and curr.startswith(next_l)) or \
                               (curr in next_l and next_l.startswith(curr)):
                                progressive_patterns.append((i+1, curr, next_l))
                
                if progressive_patterns:
                    print(f"   ⚠️  PADRÃO DE REPETIÇÃO PROGRESSIVA ENCONTRADO ({len(progressive_patterns)} casos):")
                    for line_num, curr, next_l in progressive_patterns[:5]:
                        print(f"      Linha {line_num}: '{curr[:50]}' → '{next_l[:50]}'")
                else:
                    print(f"   ✅ Nenhum padrão de repetição progressiva encontrado")
                
                # Mostra amostra do conteúdo
                print(f"\n📋 Amostra do conteúdo (linhas 20-35):")
                print("-" * 80)
                for i in range(19, min(35, len(non_empty_lines))):
                    if i < len(non_empty_lines):
                        print(f"{i+1:3d}: {non_empty_lines[i][:70]}")
                print("-" * 80)
                
                # Busca chunks relacionados - tenta diferentes collections de embedding
                doc_uuid = doc.get('_additional', {}).get('id')
                print(f"\n🔍 Buscando chunks relacionados (doc_uuid: {doc_uuid})...")
                
                # Tenta diferentes collections de embedding
                embedding_collections = [
                    "VERBA_Embedding_all_MiniLM_L6_v2",  # Parece ser a collection principal (6188 objetos)
                    "VERBA_Embedding_SentenceTransformers",
                    "VERBA_Embedding_text_embedding_ada_002"
                ]
                
                chunks_found = False
                for collection_name in embedding_collections:
                    # Tenta primeiro com doc_uuid como string
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
                                    _additional {{
                                        id
                                    }}
                                }}
                            }}
                        }}
                        """
                    }
                    
                    try:
                        chunk_response = requests.post(
                            f"{weaviate_url}/v1/graphql",
                            json=chunk_query,
                            headers={"Content-Type": "application/json"},
                            timeout=30
                        )
                        
                        if chunk_response.status_code == 200:
                            chunk_data = chunk_response.json()
                            if 'errors' not in chunk_data:
                                chunks = chunk_data.get('data', {}).get('Get', {}).get(collection_name, [])
                                if chunks:
                                    print(f"   ✅ Chunks encontrados em {collection_name}: {len(chunks)}")
                                    chunks_found = True
                                    
                                    # Verifica se algum chunk pertence ao documento
                                    doc_chunks = [c for c in chunks if c.get('doc_uuid') == doc_uuid or c.get('title') == doc_title]
                                    if doc_chunks:
                                        print(f"   ✅ {len(doc_chunks)} chunks pertencem ao documento '{doc_title}'")
                                    
                                    # Procura chunks com "posicionamento"
                                    pos_chunks = [c for c in chunks if 'posicionamento' in c.get('text', '').lower()]
                                    if pos_chunks:
                                        print(f"\n   📋 Chunks contendo 'posicionamento' ({len(pos_chunks)}):")
                                        for chunk in pos_chunks[:5]:
                                            chunk_text = chunk.get('text', '')
                                            print(f"\n      Chunk {chunk.get('chunk_id')} (doc_uuid: {chunk.get('doc_uuid', 'N/A')[:20]}...):")
                                            # Mostra linhas do chunk
                                            chunk_lines = chunk_text.split('\n')
                                            non_empty = [l for l in chunk_lines if l.strip()]
                                            
                                            print(f"         Total de linhas: {len(chunk_lines)}, Não vazias: {len(non_empty)}")
                                            
                                            # Mostra linhas com "posicionamento"
                                            for i, line in enumerate(chunk_lines):
                                                if 'posicionamento' in line.lower():
                                                    print(f"         Linha {i+1}: {line[:70]} >>>")
                                                    # Mostra contexto (linhas antes e depois)
                                                    start = max(0, i-2)
                                                    end = min(len(chunk_lines), i+3)
                                                    for j in range(start, end):
                                                        if chunk_lines[j].strip():
                                                            marker = " >>>" if j == i else ""
                                                            print(f"         {j+1:2d}: {chunk_lines[j][:70]}{marker}")
                                                    break
                                        
                                        # Verifica padrão de repetição dentro dos chunks
                                        print(f"\n   🔍 Verificando padrão de repetição progressiva nos chunks:")
                                        progressive_found = False
                                        for chunk in pos_chunks[:5]:
                                            chunk_text = chunk.get('text', '')
                                            chunk_lines = [l.strip() for l in chunk_text.split('\n') if l.strip()]
                                            
                                            for i in range(len(chunk_lines) - 1):
                                                curr = chunk_lines[i]
                                                next_l = chunk_lines[i + 1] if i + 1 < len(chunk_lines) else ""
                                                
                                                if 'posicionamento' in curr.lower() or 'posicionamento' in next_l.lower():
                                                    if len(curr) > 10 and len(next_l) > 10:
                                                        # Verifica corte progressivo
                                                        if (next_l in curr and curr.startswith(next_l)) or \
                                                           (curr in next_l and next_l.startswith(curr)):
                                                            if not progressive_found:
                                                                print(f"      ⚠️  PADRÃO DE REPETIÇÃO PROGRESSIVA ENCONTRADO:")
                                                                progressive_found = True
                                                            print(f"         Chunk {chunk.get('chunk_id')}:")
                                                            print(f"         '{curr[:50]}'")
                                                            print(f"         '{next_l[:50]}'")
                                        
                                        if not progressive_found:
                                            print(f"      ✅ Nenhum padrão de repetição progressiva encontrado nos chunks")
                                    else:
                                        print(f"   ⚠️  Nenhum chunk contém 'posicionamento'")
                                    
                                    break
                    except Exception as e:
                        continue
                
                if not chunks_found:
                    print(f"   ⚠️  Nenhum chunk encontrado nas collections testadas")
                
                chunk_response = requests.post(
                    f"{weaviate_url}/v1/graphql",
                    json=chunk_query,
                    headers={"Content-Type": "application/json"},
                    timeout=30
                )
                
                if chunk_response.status_code == 200:
                    chunk_data = chunk_response.json()
                    if 'errors' not in chunk_data:
                        chunks = chunk_data.get('data', {}).get('Get', {}).get('VERBA_Embedding_SentenceTransformers', [])
                        print(f"   - Chunks encontrados: {len(chunks)}")
                        
                        if chunks:
                            print(f"\n   📋 Amostra de chunks (primeiros 3):")
                            for i, chunk in enumerate(chunks[:3]):
                                chunk_text = chunk.get('text', '')[:100]
                                print(f"      Chunk {chunk.get('chunk_id')}: {chunk_text}...")
                
                # CONCLUSÃO
                print("\n" + "=" * 80)
                print("📊 CONCLUSÃO")
                print("=" * 80)
                
                if progressive_patterns:
                    print("\n⚠️  PADRÃO DE REPETIÇÃO ENCONTRADO NO WEAVIATE")
                    print("   O problema está no conteúdo ARMAZENADO")
                    print("   Isso indica que a fragmentação ocorre durante o PROCESSAMENTO")
                else:
                    print("\n✅ Nenhum padrão de repetição encontrado no Weaviate")
                    print("   O conteúdo está armazenado corretamente")
                    print("   O problema está na VISUALIZAÇÃO no frontend")
            else:
                print(f"❌ Documento não encontrado")
                print(f"\n📋 Listando documentos disponíveis...")
                
                # Lista todos os documentos
                list_query = {
                    "query": """
                    {
                        Get {
                            VERBA_DOCUMENTS(limit: 10) {
                                title
                                _additional {
                                    id
                                }
                            }
                        }
                    }
                    """
                }
                
                list_response = requests.post(
                    f"{weaviate_url}/v1/graphql",
                    json=list_query,
                    headers={"Content-Type": "application/json"},
                    timeout=30
                )
                
                if list_response.status_code == 200:
                    list_data = list_response.json()
                    if 'errors' not in list_data:
                        docs = list_data.get('data', {}).get('Get', {}).get('VERBA_DOCUMENTS', [])
                        print(f"   Documentos encontrados ({len(docs)}):")
                        for doc in docs:
                            print(f"   - {doc.get('title')}")
    else:
        print(f"❌ Erro ao buscar documento: {response.status_code}")
        print(f"   Response: {response.text[:200]}")
        
except Exception as e:
    print(f"❌ Erro: {str(e)}")
    import traceback
    traceback.print_exc()

