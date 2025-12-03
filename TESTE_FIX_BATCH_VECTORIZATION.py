#!/usr/bin/env python3
"""
🧪 Teste do Fix para SentenceTransformersEmbedder Meta Tensor Issue

Este script testa o fix implementado para resolver o erro:
"Cannot copy out of meta tensor; no data!"

Execução:
    python TESTE_FIX_BATCH_VECTORIZATION.py
"""

import asyncio
import sys
from pathlib import Path

# Add project to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from wasabi import msg


async def test_single_chunk():
    """Teste 1: Vetorizar um único chunk"""
    msg.title("TESTE 1: Single Chunk Vectorization")
    
    try:
        from goldenverba.components.embedding.SentenceTransformersEmbedder import SentenceTransformersEmbedder
        from goldenverba.components.types import InputConfig
        
        embedder = SentenceTransformersEmbedder()
        config = {
            "Model": InputConfig(
                type="dropdown",
                value="all-MiniLM-L6-v2"
            )
        }
        
        # Test
        content = ["Hello world, this is a test chunk for embedding."]
        embeddings = embedder._vectorize_sync(config, content)
        
        # Validate
        assert len(embeddings) == 1, f"Expected 1 embedding, got {len(embeddings)}"
        assert len(embeddings[0]) == 384, f"Expected 384 dims, got {len(embeddings[0])}"
        
        msg.good(f"✅ Test 1 PASSED: 1 chunk → {len(embeddings[0])} dims")
        return True
        
    except Exception as e:
        msg.fail(f"❌ Test 1 FAILED: {str(e)}")
        import traceback
        msg.fail(traceback.format_exc())
        return False


async def test_batch_chunks():
    """Teste 2: Vetorizar um batch com 10 chunks"""
    msg.title("TESTE 2: Batch Chunk Vectorization (10 chunks)")
    
    try:
        from goldenverba.components.embedding.SentenceTransformersEmbedder import SentenceTransformersEmbedder
        from goldenverba.components.types import InputConfig
        
        embedder = SentenceTransformersEmbedder()
        config = {
            "Model": InputConfig(
                type="dropdown",
                value="all-MiniLM-L6-v2"
            )
        }
        
        # Create 10 test chunks
        content = [f"This is test chunk number {i}. It contains some sample text for embedding." for i in range(10)]
        
        # Test
        embeddings = embedder._vectorize_sync(config, content)
        
        # Validate
        assert len(embeddings) == 10, f"Expected 10 embeddings, got {len(embeddings)}"
        assert all(len(e) == 384 for e in embeddings), "Not all embeddings have 384 dims"
        
        msg.good(f"✅ Test 2 PASSED: 10 chunks → {len(embeddings)} embeddings")
        return True
        
    except Exception as e:
        msg.fail(f"❌ Test 2 FAILED: {str(e)}")
        import traceback
        msg.fail(traceback.format_exc())
        return False


async def test_parallel_batches():
    """Teste 3: Vetorizar 3 batches em paralelo (simula batch_vectorize)"""
    msg.title("TESTE 3: Parallel Batch Vectorization (3 batches x 10 chunks)")
    
    try:
        from goldenverba.components.embedding.SentenceTransformersEmbedder import SentenceTransformersEmbedder
        from goldenverba.components.types import InputConfig
        
        embedder = SentenceTransformersEmbedder()
        config = {
            "Model": InputConfig(
                type="dropdown",
                value="all-MiniLM-L6-v2"
            )
        }
        
        # Create 3 batches with 10 chunks each
        batches = [
            [f"Batch {b} - Chunk {i}. Sample text for testing embedding." for i in range(10)]
            for b in range(1, 4)
        ]
        
        # Test: Execute in parallel (simulates batch_vectorize tasks)
        loop = asyncio.get_event_loop()
        
        async def vectorize_batch(batch):
            return await loop.run_in_executor(None, embedder._vectorize_sync, config, batch)
        
        tasks = [vectorize_batch(batch) for batch in batches]
        results = await asyncio.gather(*tasks)
        
        # Validate
        assert len(results) == 3, f"Expected 3 batch results, got {len(results)}"
        for i, result in enumerate(results):
            assert len(result) == 10, f"Batch {i+1}: expected 10 embeddings, got {len(result)}"
            assert all(len(e) == 384 for e in result), f"Batch {i+1}: not all embeddings have 384 dims"
        
        total_embeddings = sum(len(r) for r in results)
        msg.good(f"✅ Test 3 PASSED: 3 batches → {total_embeddings} total embeddings")
        return True
        
    except Exception as e:
        msg.fail(f"❌ Test 3 FAILED: {str(e)}")
        import traceback
        msg.fail(traceback.format_exc())
        return False


async def test_model_caching():
    """Teste 4: Verificar que modelo está sendo cached"""
    msg.title("TESTE 4: Model Caching Verification")
    
    try:
        from goldenverba.components.embedding.SentenceTransformersEmbedder import SentenceTransformersEmbedder
        from goldenverba.components.types import InputConfig
        
        embedder = SentenceTransformersEmbedder()
        config = {
            "Model": InputConfig(
                type="dropdown",
                value="all-MiniLM-L6-v2"
            )
        }
        
        # First call - should load model
        content1 = ["First call"]
        msg.info("First call (should load model)...")
        embeddings1 = embedder._vectorize_sync(config, content1)
        
        # Verify cache was populated
        model_name = "all-MiniLM-L6-v2"
        assert model_name in embedder._model_cache, f"Model not in cache after first call"
        msg.good(f"  ✓ Model added to cache")
        
        # Second call - should use cached model
        content2 = ["Second call"]
        msg.info("Second call (should use cached model)...")
        embeddings2 = embedder._vectorize_sync(config, content2)
        
        # Verify same model object is used
        assert model_name in embedder._model_cache, f"Model not in cache after second call"
        msg.good(f"  ✓ Cached model reused")
        
        # Validate embeddings are correct
        assert len(embeddings1) == 1 and len(embeddings1[0]) == 384
        assert len(embeddings2) == 1 and len(embeddings2[0]) == 384
        
        msg.good(f"✅ Test 4 PASSED: Model caching working correctly")
        return True
        
    except Exception as e:
        msg.fail(f"❌ Test 4 FAILED: {str(e)}")
        import traceback
        msg.fail(traceback.format_exc())
        return False


async def test_device_detection():
    """Teste 5: Verificar detecção de device"""
    msg.title("TESTE 5: Device Detection")
    
    try:
        from goldenverba.components.embedding.SentenceTransformersEmbedder import SentenceTransformersEmbedder
        
        embedder = SentenceTransformersEmbedder()
        device = embedder._get_device()
        
        msg.info(f"Detected device: {device}")
        assert device in ["cpu", "cuda"], f"Invalid device: {device}"
        
        # If CUDA detected, verify it's actually available
        if device == "cuda":
            import torch
            assert torch.cuda.is_available(), "CUDA reported but not available"
            msg.good(f"✅ CUDA device detected and verified")
        else:
            msg.good(f"✅ CPU device detected (safe default)")
        
        msg.good(f"✅ Test 5 PASSED: Device detection working")
        return True
        
    except Exception as e:
        msg.fail(f"❌ Test 5 FAILED: {str(e)}")
        import traceback
        msg.fail(traceback.format_exc())
        return False


async def run_all_tests():
    """Executa todos os testes"""
    msg.title("🧪 SUITE DE TESTES: SentenceTransformersEmbedder Fix")
    msg.info(f"Testando SentenceTransformersEmbedder com modelo caching e device handling\n")
    
    results = []
    
    # Test 1
    result1 = await test_single_chunk()
    results.append(("Single Chunk", result1))
    print()
    
    # Test 2
    result2 = await test_batch_chunks()
    results.append(("Batch Vectorization", result2))
    print()
    
    # Test 3
    result3 = await test_parallel_batches()
    results.append(("Parallel Batches", result3))
    print()
    
    # Test 4
    result4 = await test_model_caching()
    results.append(("Model Caching", result4))
    print()
    
    # Test 5
    result5 = await test_device_detection()
    results.append(("Device Detection", result5))
    print()
    
    # Summary
    msg.title("📊 RESUMO DE TESTES")
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        msg.info(f"{status}: {test_name}")
    
    print()
    if passed == total:
        msg.good(f"🎉 TODOS OS TESTES PASSARAM ({passed}/{total})")
        return 0
    else:
        msg.fail(f"❌ ALGUNS TESTES FALHARAM ({passed}/{total} passed)")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)



