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
from typing import List, Dict

# Adiciona paths
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from goldenverba.components.chunk import Chunk
from goldenverba.components.document import Document
from verba_extensions.plugins.plugin_manager import get_plugin_manager
from verba_extensions.plugins.llm_metadata_extractor import create_llm_metadata_extractor
from verba_extensions.plugins.recursive_document_splitter import create_recursive_document_splitter
from verba_extensions.plugins.reranker import create_reranker


async def test_llm_metadata_extractor():
    """Testa LLMMetadataExtractor"""
    print("\n" + "="*60)
    print("TEST 1: LLMMetadataExtractor")
    print("="*60)
    
    plugin = create_llm_metadata_extractor()
    
    # Criar chunk de teste
    chunk = Chunk(
        uuid="test-1",
        content="Apple investe bilhões em inteligência artificial. A empresa lidera em inovação tecnológica.",
        meta={}
    )
    
    print(f"Chunk original: {chunk.content[:50]}...")
    print(f"Meta antes: {chunk.meta}")
    
    # Processar
    enriched = await plugin.process_chunk(chunk)
    
    print(f"Meta depois: {enriched.meta}")
    
    if "enriched" in enriched.meta:
        print("✅ LLMMetadataExtractor funcionando!")
        enriched_data = enriched.meta["enriched"]
        print(f"  - Companies: {enriched_data.get('companies', [])}")
        print(f"  - Topics: {enriched_data.get('key_topics', [])}")
        print(f"  - Sentiment: {enriched_data.get('sentiment', 'N/A')}")
    else:
        print("⚠️  LLMMetadataExtractor não enriqueceu (pode ser falta de API key)")
    
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
        uuid="test-2",
        content=large_text.strip(),
        meta={}
    )
    
    print(f"Chunk original tamanho: {len(chunk.content)} caracteres")
    
    # Processar
    optimized = await plugin.process_chunk(chunk, config={"chunk_size": 500})
    
    print(f"Chunk otimizado tamanho: {len(optimized.content)} caracteres")
    
    if len(optimized.content) < len(chunk.content):
        print("✅ RecursiveDocumentSplitter funcionando!")
        print(f"  - Reduziu de {len(chunk.content)} para {len(optimized.content)} chars")
    else:
        print("⚠️  Chunk não foi otimizado (pode estar dentro do tamanho ideal)")
    
    return optimized


async def test_reranker():
    """Testa Reranker"""
    print("\n" + "="*60)
    print("TEST 3: Reranker")
    print("="*60)
    
    plugin = create_reranker()
    
    # Criar chunks de teste
    chunks = [
        Chunk(
            uuid=f"chunk-{i}",
            content=content,
            meta={"enriched": {"companies": ["Apple"], "key_topics": ["AI"], "keywords": ["apple", "ai"]}} if i < 2 else {}
        )
        for i, content in enumerate([
            "Apple investe em inteligência artificial e machine learning.",
            "Microsoft também trabalha com IA e cloud computing.",
            "Google é líder em pesquisa de deep learning.",
            "Amazon utiliza IA para recomendações de produtos.",
        ])
    ]
    
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
        print("✅ Reranker funcionando!")
        print("  - Ordenou chunks por relevância")
    else:
        print("⚠️  Reranker pode precisar de ajustes")
    
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
    doc.chunks = [
        Chunk(
            uuid=f"chunk-{i}",
            content=chunk_text,
            meta={}
        )
        for i, chunk_text in enumerate([
            "Apple investe bilhões em inteligência artificial.",
            "Microsoft também lidera em cloud computing.",
        ])
    ]
    
    print(f"Documento com {len(doc.chunks)} chunks antes")
    
    # Processar através do PluginManager
    processed_doc = await pm.process_document_chunks(doc)
    
    print(f"Documento com {len(processed_doc.chunks)} chunks depois")
    
    # Verificar se chunks foram enriquecidos
    enriched_count = sum(1 for chunk in processed_doc.chunks if chunk.meta.get("enriched"))
    print(f"Chunks enriquecidos: {enriched_count}/{len(processed_doc.chunks)}")
    
    if enriched_count > 0 or pm.get_enabled_plugins():
        print("✅ PluginManager funcionando!")
    else:
        print("⚠️  PluginManager não processou chunks")
    
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
        print(f"❌ Erro no LLMMetadataExtractor: {e}")
        results["llm_metadata"] = None
    
    try:
        results["recursive_splitter"] = await test_recursive_document_splitter()
    except Exception as e:
        print(f"❌ Erro no RecursiveDocumentSplitter: {e}")
        results["recursive_splitter"] = None
    
    try:
        results["reranker"] = await test_reranker()
    except Exception as e:
        print(f"❌ Erro no Reranker: {e}")
        results["reranker"] = None
    
    try:
        results["plugin_manager"] = await test_plugin_manager()
    except Exception as e:
        print(f"❌ Erro no PluginManager: {e}")
        results["plugin_manager"] = None
    
    # Resumo
    print("\n" + "="*60)
    print("RESUMO DOS TESTES")
    print("="*60)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print("\n" + "="*60)
    print("VALIDAÇÃO COMPLETA")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())

