#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para acessar Weaviate diretamente e verificar conteúdo armazenado
Compara o conteúdo no Weaviate com o texto extraído do PDF
"""

import sys
import os
import asyncio

if sys.platform == 'win32':
    import io as io_encoding
    sys.stdout = io_encoding.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

try:
    from weaviate import WeaviateClient
    from weaviate.classes.query import Filter
    from weaviate.connect import ConnectionParams, AuthApiKey
except ImportError:
    print("❌ weaviate-client não instalado. Execute: pip install weaviate-client")
    sys.exit(1)

async def check_weaviate_content():
    """Acessa Weaviate e verifica conteúdo do documento"""
    
    # URL do Weaviate
    weaviate_url = "https://weaviate-production-0d0e.up.railway.app"
    
    print(f"🔗 Conectando ao Weaviate: {weaviate_url}\n")
    print("=" * 80)
    
    try:
        # Conecta ao Weaviate (sem autenticação para Railway público)
        # Se precisar de auth, adicione: auth_credentials=AuthApiKey(api_key)
        client = WeaviateClient(
            ConnectionParams.from_params(
                http_host=weaviate_url.replace("https://", "").replace("http://", ""),
                http_port=443,
                http_secure=True,
                grpc_host=weaviate_url.replace("https://", "").replace("http://", ""),
                grpc_port=50051,
                grpc_secure=True,
            )
        )
        
        await client.connect()
        print("✅ Conectado ao Weaviate\n")
        
        # Busca o documento
        doc_title = "Dossiê_ Flow Executive Finders.pdf"
        print(f"🔍 Buscando documento: {doc_title}\n")
        
        document_collection = client.collections.get("VERBA_DOCUMENTS")
        
        # Busca pelo título
        results = await document_collection.query.fetch_objects(
            filters=Filter.by_property("title").equal(doc_title),
            limit=1
        )
        
        if not results.objects:
            print(f"❌ Documento não encontrado no Weaviate")
            print(f"\n📋 Documentos disponíveis:")
            all_docs = await document_collection.query.fetch_objects(limit=10)
            for doc in all_docs.objects:
                print(f"   - {doc.properties.get('title', 'N/A')}")
            return
        
        doc = results.objects[0]
        print(f"✅ Documento encontrado: {doc.properties.get('title')}\n")
        print(f"📄 UUID: {doc.uuid}\n")
        
        # Verifica o conteúdo armazenado
        content = doc.properties.get('content', '')
        
        print("=" * 80)
        print("📊 ANÁLISE DO CONTEÚDO ARMAZENADO NO WEAVIATE")
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
        print(f"\n📋 Amostra do conteúdo (primeiras 20 linhas não vazias):")
        print("-" * 80)
        for i, line in enumerate(non_empty_lines[:20]):
            print(f"{i+1:3d}: {line[:70]}")
        print("-" * 80)
        
        # Busca chunks relacionados
        print(f"\n🔍 Buscando chunks relacionados...")
        embedder_collection = client.collections.get("VERBA_Embedding_SentenceTransformers")
        
        chunk_results = await embedder_collection.query.fetch_objects(
            filters=Filter.by_property("doc_uuid").equal(str(doc.uuid)),
            limit=5
        )
        
        print(f"   - Chunks encontrados: {len(chunk_results.objects)}")
        
        if chunk_results.objects:
            print(f"\n   📋 Amostra de chunks (primeiros 3):")
            for i, chunk in enumerate(chunk_results.objects[:3]):
                chunk_text = chunk.properties.get('text', '')[:100]
                print(f"      Chunk {i+1}: {chunk_text}...")
        
        # CONCLUSÃO
        print("\n" + "=" * 80)
        print("📊 CONCLUSÃO")
        print("=" * 80)
        
        if progressive_patterns:
            print("\n⚠️  PADRÃO DE REPETIÇÃO ENCONTRADO NO WEAVIATE")
            print("   O problema está no conteúdo ARMAZENADO, não apenas na visualização")
            print("   Isso indica que a fragmentação ocorre durante o PROCESSAMENTO")
        else:
            print("\n✅ Nenhum padrão de repetição encontrado no Weaviate")
            print("   O conteúdo está armazenado corretamente")
            print("   O problema está na VISUALIZAÇÃO no frontend")
        
        await client.close()
        
    except Exception as e:
        print(f"❌ Erro ao acessar Weaviate: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Tenta método alternativo (REST API direta)
        print(f"\n🔄 Tentando método alternativo (REST API)...")
        try:
            import requests
            response = requests.get(f"{weaviate_url}/v1/schema")
            if response.status_code == 200:
                print(f"✅ Weaviate está acessível via REST")
                print(f"   Schema disponível em: {weaviate_url}/v1/schema")
            else:
                print(f"❌ Erro ao acessar REST API: {response.status_code}")
        except Exception as e2:
            print(f"❌ Erro no método alternativo: {str(e2)}")

if __name__ == "__main__":
    asyncio.run(check_weaviate_content())


