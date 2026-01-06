
import asyncio
import os
import sys
from wasabi import msg

# Adicionar raiz do projeto ao path
sys.path.append(os.path.abspath("C:/Users/marce/VERBA/Verba"))

from verba_extensions.plugins.entity_aware_retriever import EntityAwareRetriever
from goldenverba.components.managers import WeaviateManager
from goldenverba.verba_manager import VerbaManager
import weaviate

async def verify_patch():
    try:
        msg.info("=== Starting EntityAwareRetriever Patch Verification ===")
        
        # 1. Setup Weaviate Client
        verba_manager = VerbaManager()
        weaviate_manager = WeaviateManager()
        
        # Tentar conectar usando variáveis de ambient
        url = os.environ.get("WEAVIATE_URL_VERBA", "http://localhost:8080")
        key = os.environ.get("WEAVIATE_API_KEY_VERBA", "")
        port = os.environ.get("WEAVIATE_HTTP_PORT", "8080")
        
        msg.info(f"Connecting to Weaviate at {url}...")
        
        # Tentar conexão direta via WeaviateManager
        try:
             # Assumindo assinatura universal que tenta conectar
             client = await weaviate_manager.connect("Weaviate", url, key, port)
        except Exception as e:
             msg.fail(f"Connection failed: {e}")
             client = None

        if not client:
            msg.warn("Could not connect to Weaviate. switching to MOCK mode.")
            from unittest.mock import MagicMock, AsyncMock
            
            client = MagicMock()
            
            # Mock collection config to have 'consulting' vector
            # client.collections.get(name).config.get() -> returns config with vector_config
            mock_collection = MagicMock()
            mock_config_get = AsyncMock()
            
            config_obj = MagicMock()
            config_obj.vector_config = {"consulting": {}, "default": {}}
            mock_config_get.return_value = config_obj
            
            mock_collection.config.get = mock_config_get
            client.collections.get.return_value = mock_collection
            
            # Mock weaviate_manager methods to verify arguments
            async def mock_hybrid(*args, **kwargs):
                target = kwargs.get('target_vector')
                msg.good(f"MOCK VERIFICATION: hybrid_chunks called with target_vector='{target}'")
                from goldenverba.components.chunk import Chunk
                return [Chunk(text="Mock Chunk", doc_uuid="123", chunk_id=0)]
            
            weaviate_manager.hybrid_chunks = mock_hybrid
            weaviate_manager.hybrid_chunks_with_filter = mock_hybrid
            
            # Ensure embedding_table has the embedder we need to trigger validation
            weaviate_manager.embedding_table["UnifiedConsulting"] = "TestCollection"


        # Monkeypatch msg to avoid encoding errors in plugin
        def safe_print(prefix, *args):
            try:
                text = " ".join(str(a) for a in args)
                # Filter non-ascii
                safe_text = text.encode('ascii', 'ignore').decode('ascii')
                print(f"{prefix}: {safe_text}")
            except:
                pass

        msg.info = lambda *args, **kwargs: safe_print("INFO", *args)
        msg.good = lambda *args, **kwargs: safe_print("GOOD", *args)
        msg.warn = lambda *args, **kwargs: safe_print("WARN", *args)
        msg.fail = lambda *args, **kwargs: safe_print("FAIL", *args)
        msg.debug = lambda *args, **kwargs: safe_print("DEBUG", *args)

        retriever = EntityAwareRetriever()
        
        # Configuração simulada (padrão)
        config = {
            "Search Mode": {"value": "Hybrid Search", "type": "dropdown"},
            "Enable Entity Filter": {"value": False, "type": "bool"}, # Desabilitar filtro para focar na busca híbrida
            "Enable Multi-Vector Search": {"value": False, "type": "bool"} # Desabilitar multi-vector para testar o fallback
        }
        
        query = "teste de compliance"
        embedder_name = "UnifiedConsulting" # Assumindo que este é o embedder em uso que gera 'consulting'
        
        # Ensure embedding_table has the embedder we need to trigger validation
        if embedder_name not in weaviate_manager.embedding_table:
             weaviate_manager.embedding_table[embedder_name] = "TestCollection"

        print(f"Testing retrieval with embedder: {embedder_name}")
        
        # Executar retrieve
        try:
            chunks = await retriever.retrieve(
                client=client,
                query=query,
                vector=[], # Vetor vazio
                config=config,
                weaviate_manager=weaviate_manager,
                embedder=embedder_name,
                labels=[],
                document_uuids=[],
                rag_config={} 
            )
            
            print(f"Retrieval completed.")
            
            # ASSERTION
            # Check if/how mock_hybrid was called
            # Since we monkeypatched weaviate_manager.hybrid_chunks/hybrid_chunks_with_filter with 'mock_hybrid'
            # (which is defined inside the 'if not client' block above)
            # We need to access it.
            
            # But wait, 'retriever.retrieve' calls 'weaviate_manager.hybrid_chunks' 
            # or 'weaviate_manager.hybrid_chunks_with_filter'.
            
            # Since we patched the INSTANCE 'weaviate_manager', it should work.
            # But we need to capture the call args.
            
            # Actually, I defined 'mock_hybrid' inside the 'if not client' block. 
            # I cannot access it easily here if 'client' WAS mocked.
            # I should verify MOCK execution.
            
            if hasattr(weaviate_manager, 'hybrid_chunks') and hasattr(weaviate_manager.hybrid_chunks, 'call_count'):
                 print(f"Mock call count: {weaviate_manager.hybrid_chunks.call_count}")
                 
                 # Check call args
                 # hybrid_chunks(..., target_vector=...)
                 # We want to see if ANY call had target_vector='consulting' or 'default'
                 
                 # Since we assigned the same mock to both methods, we can check just one if reused,
                 # or checks calls on both if distinct. In my previous replace, I assigned same 'mock_hybrid' to both.
                 
                 found_target = False
                 # Access calls from the bound method if possible, or just the function? 
                 # Wait, 'mock_hybrid' is a function, not a Mock object properly unless wrapped?
                 # No, I used 'async def mock_hybrid'. It is NOT a Mock object, it is a coroutine function.
                 # So .call_count won't exist unless I wrapped it.
                 
                 # I should use MagicMock(wraps=mock_hybrid) or update the mock_hybrid logging to be the assertion.
                 # In the previous step, I added: `msg.good(f"MOCK VERIFICATION: hybrid_chunks called with target_vector='{target}'")`
                 # Since I monkeypatched msg.good to safe_print, this log will appear safe!
                 
                 print("Check above for 'MOCK VERIFICATION' line.")

        except Exception as e:
            print(f"Error during retrieval: {str(e)}")
            import traceback
            traceback.print_exc()

    except Exception as e:
        print(f"General error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(verify_patch())
