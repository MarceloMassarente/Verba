#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para atualizar schema do Verba adicionando campos de ETL
Execute este script para adicionar propriedades de ETL às collections existentes
"""

import sys
import os
import asyncio

# Adiciona caminho do projeto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if sys.platform == 'win32':
    import io as io_encoding
    sys.stdout = io_encoding.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from verba_extensions.integration.schema_updater import update_all_embedding_collections
from goldenverba.components import managers
from wasabi import msg

async def main():
    """Atualiza schema de todas as collections de embedding"""
    
    print("=" * 80)
    print("🔧 Atualização de Schema: Adicionar Campos de ETL")
    print("=" * 80 + "\n")
    
    # Conecta ao Weaviate
    weaviate_manager = managers.WeaviateManager()
    
    # Tenta conectar (precisa das variáveis de ambiente)
    try:
        from verba_extensions.compatibility.weaviate_imports import get_weaviate_client
        
        client = await get_weaviate_client()
        
        if not client:
            msg.warn("❌ Não foi possível conectar ao Weaviate")
            msg.info("💡 Verifique variáveis de ambiente: WEAVIATE_URL, WEAVIATE_API_KEY")
            return
        
        msg.good("✅ Conectado ao Weaviate\n")
        
        # Atualiza todas as collections
        results = await update_all_embedding_collections(client, weaviate_manager)
        
        print("\n" + "=" * 80)
        print("📊 RESUMO")
        print("=" * 80 + "\n")
        
        success_count = sum(1 for r in results.values() if r)
        total_count = len(results)
        
        for collection_name, success in results.items():
            status = "✅" if success else "❌"
            print(f"{status} {collection_name}")
        
        print(f"\n✅ {success_count}/{total_count} collections atualizadas com sucesso")
        
        if success_count > 0:
            print("\n💡 Próximos passos:")
            print("   1. Reimporte documentos para que ETL salve metadados")
            print("   2. Verifique se metadados estão sendo salvos corretamente")
            print("   3. Teste queries por entidades")
        
        await client.close()
        
    except Exception as e:
        msg.warn(f"❌ Erro: {str(e)}")
        import traceback
        traceback.print_exc()
        return

if __name__ == "__main__":
    asyncio.run(main())


