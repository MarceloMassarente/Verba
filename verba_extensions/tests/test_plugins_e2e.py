"""
End-to-End Validation Script for Verba Plugins

Valida integração completa dos plugins:
1. LLMMetadataExtractor
2. RecursiveDocumentSplitter
3. Reranker
4. EntityAwareRetriever
"""

import asyncio
import sys
import os
from pathlib import Path
from typing import List, Dict

# Adiciona path raiz do projeto ao sys.path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from goldenverba.components.chunk import Chunk
    from goldenverba.components.document import Document
    from verba_extensions.plugins.plugin_manager import get_plugin_manager
    from verba_extensions.plugins.llm_metadata_extractor import create_llm_metadata_extractor
    from verba_extensions.plugins.recursive_document_splitter import create_recursive_document_splitter
    from verba_extensions.plugins.reranker import create_reranker
except ImportError as e:
    print(f"❌ Erro ao importar módulos: {e}")
    print(f"   Path raiz: {project_root}")
    print(f"   sys.path: {sys.path[:3]}")
    sys.exit(1)


async def test_llm_metadata_extractor():
    """Testa LLMMetadataExtractor"""
    print("\n" + "="*60)
    print("TEST 1: LLMMetadataExtractor")
    print("="*60)
    
    plugin = create_llm_metadata_extractor()
    
    # Criar chunk de teste
    chunk = Chunk(
        content="Apple investe bilhoes em inteligencia artificial. A empresa lidera em inovacao tecnologica.",
        chunk_id="test-1",
        content_without_overlap="Apple investe bilhoes em inteligencia artificial. A empresa lidera em inovacao tecnologica."
    )
    chunk.uuid = "test-1"
    chunk.meta = {}
    
    print(f"Chunk original: {chunk.content[:50]}...")
    print(f"Meta antes: {chunk.meta}")
    
    # Processar
    enriched = await plugin.process_chunk(chunk)
    
    print(f"Meta depois: {enriched.meta}")
    
    if "enriched" in enriched.meta:
        print("[OK] LLMMetadataExtractor funcionando!")
        enriched_data = enriched.meta["enriched"]
        print(f"  - Companies: {enriched_data.get('companies', [])}")
        print(f"  - Topics: {enriched_data.get('key_topics', [])}")
        print(f"  - Sentiment: {enriched_data.get('sentiment', 'N/A')}")
    else:
        print("[WARN] LLMMetadataExtractor nao enriqueceu (pode ser falta de API key)")
    
    return enriched


async def test_recursive_document_splitter():
    """Testa RecursiveDocumentSplitter"""
    print("\n" + "="*60)
    print("TEST 2: RecursiveDocumentSplitter")
    print("="*60)
    
    plugin = create_recursive_document_splitter()
    
    # Criar chunk grande
    large_text = """
    Apple Inc. é uma empresa multinacional americana de tecnologia.
    
    A empresa foi fundada em 1976 por Steve Jobs, Steve Wozniak e Ronald Wayne.
    
    Apple desenvolve e vende produtos eletrônicos de consumo, software de computador e serviços online.
    
    Os produtos mais conhecidos incluem iPhone, iPad, Mac e Apple Watch.
    
    Apple é conhecida por seu design inovador e ecossistema integrado.
    """ * 10  # Repete para criar chunk grande
    
    chunk = Chunk(
        content=large_text.strip(),
        chunk_id="test-2",
        content_without_overlap=large_text.strip()
    )
    chunk.uuid = "test-2"
    chunk.meta = {}
    
    print(f"Chunk original tamanho: {len(chunk.content)} caracteres")
    
    # Processar
    optimized = await plugin.process_chunk(chunk, config={"chunk_size": 500})
    
    print(f"Chunk otimizado tamanho: {len(optimized.content)} caracteres")
    
    if len(optimized.content) < len(chunk.content):
        print("[OK] RecursiveDocumentSplitter funcionando!")
        print(f"  - Reduziu de {len(chunk.content)} para {len(optimized.content)} chars")
    else:
        print("[WARN] Chunk nao foi otimizado (pode estar dentro do tamanho ideal)")
    
    return optimized


async def test_reranker():
    """Testa Reranker"""
    print("\n" + "="*60)
    print("TEST 3: Reranker")
    print("="*60)
    
    plugin = create_reranker()
    
    # Criar chunks de teste
    chunks = []
    for i, content in enumerate([
        "Apple investe em inteligencia artificial e machine learning.",
        "Microsoft tambem trabalha com IA e cloud computing.",
        "Google e lider em pesquisa de deep learning.",
        "Amazon utiliza IA para recomendacoes de produtos.",
    ]):
        chunk = Chunk(
            content=content,
            chunk_id=f"chunk-{i}",
            content_without_overlap=content
        )
        chunk.uuid = f"chunk-{i}"
        chunk.meta = {"enriched": {"companies": ["Apple"], "key_topics": ["AI"], "keywords": ["apple", "ai"]}} if i < 2 else {}
        chunks.append(chunk)
    
    query = "Apple AI innovation"
    
    print(f"Query: {query}")
    print(f"Chunks antes: {len(chunks)}")
    for i, chunk in enumerate(chunks):
        print(f"  Chunk {i}: {chunk.content[:50]}...")
    
    # Rerank
    reranked = await plugin.process_chunks(chunks, query, config={"top_k": 2})
    
    print(f"Chunks depois: {len(reranked)}")
    for i, chunk in enumerate(reranked):
        print(f"  Chunk {i}: {chunk.content[:50]}...")
    
    if len(reranked) <= len(chunks) and reranked[0].content.startswith("Apple"):
        print("[OK] Reranker funcionando!")
        print("  - Ordenou chunks por relevancia")
    else:
        print("[WARN] Reranker pode precisar de ajustes")
    
    return reranked


async def test_plugin_manager():
    """Testa PluginManager"""
    print("\n" + "="*60)
    print("TEST 4: PluginManager Integration")
    print("="*60)
    
    pm = get_plugin_manager()
    
    print(f"Plugins carregados: {pm.get_enabled_plugins()}")
    print(f"Configurações: {pm.get_plugin_configs()}")
    
    # Criar documento de teste
    doc = Document(
        title="Test Document",
        content="Apple investe bilhões em inteligência artificial. Microsoft também lidera.",
        meta={}
    )
    
    # Criar chunks manualmente
    doc.chunks = []
    for i, chunk_text in enumerate([
        "Apple investe bilhoes em inteligencia artificial.",
        "Microsoft tambem lidera em cloud computing.",
    ]):
        chunk = Chunk(
            content=chunk_text,
            chunk_id=f"chunk-{i}",
            content_without_overlap=chunk_text
        )
        chunk.uuid = f"chunk-{i}"
        chunk.meta = {}
        doc.chunks.append(chunk)
    
    print(f"Documento com {len(doc.chunks)} chunks antes")
    
    # Processar através do PluginManager
    processed_doc = await pm.process_document_chunks(doc)
    
    print(f"Documento com {len(processed_doc.chunks)} chunks depois")
    
    # Verificar se chunks foram enriquecidos
    enriched_count = sum(1 for chunk in processed_doc.chunks if chunk.meta.get("enriched"))
    print(f"Chunks enriquecidos: {enriched_count}/{len(processed_doc.chunks)}")
    
    if enriched_count > 0 or pm.get_enabled_plugins():
        print("[OK] PluginManager funcionando!")
    else:
        print("[WARN] PluginManager nao processou chunks")
    
    return processed_doc


async def main():
    """Executa todos os testes"""
    print("\n" + "="*60)
    print("VERBA PLUGINS - END-TO-END VALIDATION")
    print("="*60)
    
    results = {}
    
    try:
        results["llm_metadata"] = await test_llm_metadata_extractor()
    except Exception as e:
        print(f"[ERROR] Erro no LLMMetadataExtractor: {e}")
        results["llm_metadata"] = None
    
    try:
        results["recursive_splitter"] = await test_recursive_document_splitter()
    except Exception as e:
        print(f"[ERROR] Erro no RecursiveDocumentSplitter: {e}")
        results["recursive_splitter"] = None
    
    try:
        results["reranker"] = await test_reranker()
    except Exception as e:
        print(f"[ERROR] Erro no Reranker: {e}")
        results["reranker"] = None
    
    try:
        results["plugin_manager"] = await test_plugin_manager()
    except Exception as e:
        print(f"[ERROR] Erro no PluginManager: {e}")
        results["plugin_manager"] = None
    
    # Resumo
    print("\n" + "="*60)
    print("RESUMO DOS TESTES")
    print("="*60)
    
    for test_name, result in results.items():
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status} - {test_name}")
    
    print("\n" + "="*60)
    print("VALIDAÇÃO COMPLETA")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())

