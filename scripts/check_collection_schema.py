#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para verificar o schema da collection de embedding
"""

import sys
import requests
import json

if sys.platform == 'win32':
    import io as io_encoding
    sys.stdout = io_encoding.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

weaviate_url = "https://weaviate-production-0d0e.up.railway.app"

print("🔍 Verificando schema da collection...\n")

# Busca schema completo
response = requests.get(f"{weaviate_url}/v1/schema", timeout=30)
if response.status_code == 200:
    schema = response.json()
    
    # Procura collection de embedding
    collection_name = "VERBA_Embedding_all_MiniLM_L6_v2"
    
    for cls in schema.get('classes', []):
        if cls.get('class') == collection_name:
            print(f"✅ Collection encontrada: {collection_name}\n")
            print("=" * 80)
            print("📋 PROPRIEDADES DISPONÍVEIS:")
            print("=" * 80 + "\n")
            
            properties = cls.get('properties', [])
            for prop in properties:
                prop_name = prop.get('name', 'N/A')
                prop_type = prop.get('dataType', [])
                index_filterable = prop.get('indexFilterable', False)
                index_searchable = prop.get('indexSearchable', False)
                
                # Marca campos relacionados a ETL
                etl_marker = ""
                if 'entity' in prop_name.lower():
                    etl_marker = " [ETL]"
                elif 'section' in prop_name.lower():
                    etl_marker = " [ETL]"
                
                print(f"   {prop_name:30s} {str(prop_type):20s} filterable={index_filterable} searchable={index_searchable}{etl_marker}")
            
            break
    else:
        print(f"❌ Collection {collection_name} não encontrada")
        print(f"\nCollections disponíveis:")
        for cls in schema.get('classes', []):
            if 'Embedding' in cls.get('class', ''):
                print(f"   - {cls.get('class')}")
else:
    print(f"❌ Erro ao buscar schema: {response.status_code}")


