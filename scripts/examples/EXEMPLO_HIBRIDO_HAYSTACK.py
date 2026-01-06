"""
Exemplo de implementação híbrida: Haystack + Customização

Este exemplo mostra como usar Haystack para componentes genéricos
mantendo a lógica customizada de entity-aware filtering.
"""

from haystack import Pipeline
from haystack.components.rankers import CrossEncoderRanker
from haystack.document_stores import WeaviateDocumentStore
from haystack.components.classifiers import QueryClassifier
from typing import List, Dict, Any
from wasabi import msg

# ============================================================================
# PARTE 1: CUSTOMIZAÇÃO MANTIDA (Entity-Aware Filtering)
# ============================================================================

class EntityAwareWeaviateRetriever:
    """
    Retriever customizado que mantém sua lógica de entity-aware filtering.
    Usa Weaviate diretamente para filtros complexos.
    """
    
    def __init__(self, weaviate_manager, client, embedder):
        self.weaviate_manager = weaviate_manager
        self.client = client
        self.embedder = embedder
    
    async def retrieve(
        self,
        query: str,
        vector: List[float],
        config: Dict,
        labels: List[str] = None,
        document_uuids: List[str] = None,
    ):
        """
        Mantém sua lógica original de entity-aware filtering.
        """
        from verba_extensions.plugins.query_parser import parse_query
        from verba_extensions.compatibility.weaviate_imports import Filter
        
        # 1. Parse query (sua lógica original)
        parsed = parse_query(query)
        entity_ids = [e["entity_id"] for e in parsed["entities"] if e["entity_id"]]
        semantic_terms = parsed["semantic_concepts"]
        
        msg.info(f"Entidades detectadas: {entity_ids}")
        msg.info(f"Conceitos semânticos: {semantic_terms}")
        
        # 2. Constrói filtro entity-aware (sua lógica original)
        entity_filter = None
        if entity_ids:
            entity_property = "section_entity_ids"  # Evita contaminação
            entity_filter = Filter.by_property(entity_property).contains_any(entity_ids)
            msg.good(f"Aplicando filtro: {entity_property} = {entity_ids}")
        
        # 3. Query semântica
        search_query = " ".join(semantic_terms) if semantic_terms else query
        
        # 4. Busca híbrida com filtro (sua lógica original)
        alpha = float(config.get("Alpha", {}).value) if isinstance(config.get("Alpha"), object) else 0.6
        limit = int(config.get("Limit/Sensitivity", {}).value) if isinstance(config.get("Limit/Sensitivity"), object) else 10
        limit_mode = config.get("Limit Mode", {}).value if isinstance(config.get("Limit Mode"), object) else "Autocut"
        
        if entity_filter:
            chunks = await self.weaviate_manager.hybrid_chunks_with_filter(
                client=self.client,
                embedder=self.embedder,
                query=search_query,
                vector=vector,
                limit_mode=limit_mode,
                limit=limit,
                labels=labels or [],
                document_uuids=document_uuids or [],
                filters=entity_filter,
                alpha=alpha,
            )
        else:
            chunks = await self.weaviate_manager.hybrid_chunks(
                client=self.client,
                embedder=self.embedder,
                query=search_query,
                vector=vector,
                limit_mode=limit_mode,
                limit=limit,
                labels=labels or [],
                document_uuids=document_uuids or [],
                alpha=alpha,
            )
        
        # 5. Converte para formato Haystack Document
        from haystack import Document
        
        documents = []
        for chunk in chunks:
            if hasattr(chunk, "properties"):
                doc = Document(
                    content=chunk.properties.get("content", ""),
                    meta={
                        "chunk_id": chunk.properties.get("chunk_id", ""),
                        "doc_uuid": chunk.properties.get("doc_uuid", ""),
                        "score": chunk.metadata.score if hasattr(chunk, "metadata") else 0,
                    }
                )
                documents.append(doc)
        
        return {"documents": documents}


# ============================================================================
# PARTE 2: HAYSTACK PARA COMPONENTES GENÉRICOS
# ============================================================================

class HaystackRAGPipeline:
    """
    Pipeline RAG usando Haystack para componentes genéricos
    e customização para features específicas.
    """
    
    def __init__(self, weaviate_manager, client, embedder):
        self.weaviate_manager = weaviate_manager
        self.client = client
        self.embedder = embedder
        
        # Componente customizado (entity-aware)
        self.entity_retriever = EntityAwareWeaviateRetriever(
            weaviate_manager, client, embedder
        )
        
        # Componente Haystack (reranking genérico)
        self.reranker = CrossEncoderRanker(
            model="cross-encoder/ms-marco-MiniLM-L-6-v2"
        )
        
        # Componente Haystack (query classification)
        self.query_classifier = QueryClassifier()
        
        # Pipeline
        self.pipeline = Pipeline()
        self.pipeline.add_component("reranker", self.reranker)
    
    async def retrieve_and_rerank(
        self,
        query: str,
        vector: List[float],
        config: Dict,
        labels: List[str] = None,
        document_uuids: List[str] = None,
    ):
        """
        Pipeline completo:
        1. Entity-aware retrieval (customizado)
        2. Reranking (Haystack)
        """
        # 1. Entity-aware retrieval (customizado)
        result = await self.entity_retriever.retrieve(
            query=query,
            vector=vector,
            config=config,
            labels=labels,
            document_uuids=document_uuids,
        )
        
        documents = result["documents"]
        
        if not documents:
            return {"documents": [], "context": "Nenhum documento encontrado"}
        
        msg.good(f"Retrieved {len(documents)} documents")
        
        # 2. Reranking (Haystack - componente genérico)
        reranked_result = self.reranker.run(
            query=query,
            documents=documents,
            top_k=config.get("Limit/Sensitivity", {}).value if isinstance(config.get("Limit/Sensitivity"), object) else 10
        )
        
        reranked_docs = reranked_result["documents"]
        msg.good(f"Reranked to {len(reranked_docs)} documents")
        
        # 3. Gera contexto (similar ao seu código original)
        context = self._generate_context(reranked_docs)
        
        return {
            "documents": reranked_docs,
            "context": context
        }
    
    def _generate_context(self, documents):
        """Gera contexto dos documentos (similar ao combine_context)"""
        context_parts = []
        for doc in documents:
            title = doc.meta.get("title", "Unknown")
            content = doc.content
            context_parts.append(f"## {title}\n\n{content}\n")
        return "\n".join(context_parts)


# ============================================================================
# PARTE 3: USO COMPARATIVO
# ============================================================================

async def exemplo_uso_comparativo():
    """
    Comparação entre abordagem atual e híbrida.
    """
    
    # Dados de exemplo
    query = "descreva o que se fala sobre a Apple e Inovação"
    vector = [0.1] * 384  # Exemplo
    config = {
        "Alpha": type('obj', (object,), {'value': '0.6'}),
        "Limit/Sensitivity": type('obj', (object,), {'value': '10'}),
        "Limit Mode": type('obj', (object,), {'value': 'Autocut'}),
    }
    
    # ========================================================================
    # ABORDAGEM ATUAL (Tudo customizado - 821 linhas)
    # ========================================================================
    print("=" * 60)
    print("ABORDAGEM ATUAL: Tudo customizado")
    print("=" * 60)
    print("✅ Entity-aware filtering")
    print("✅ Query building schema-aware")
    print("✅ Filtros hierárquicos")
    print("✅ Reranking customizado")
    print("⚠️  Muito código (821 linhas)")
    print("⚠️  Difícil de testar componentes isoladamente")
    print()
    
    # from verba_extensions.plugins.entity_aware_retriever import EntityAwareRetriever
    # retriever = EntityAwareRetriever()
    # documents, context = await retriever.retrieve(
    #     client=client,
    #     query=query,
    #     vector=vector,
    #     config=config,
    #     weaviate_manager=weaviate_manager,
    #     embedder="embedder_name",
    #     labels=[],
    #     document_uuids=[],
    # )
    
    # ========================================================================
    # ABORDAGEM HAYSTACK PURO (Tudo Haystack - perderia features)
    # ========================================================================
    print("=" * 60)
    print("ABORDAGEM HAYSTACK PURO: Tudo Haystack")
    print("=" * 60)
    print("✅ Código limpo e modular")
    print("✅ Reranking pronto")
    print("✅ Query classification pronto")
    print("❌ PERDE: Entity-aware filtering avançado")
    print("❌ PERDE: Filtros hierárquicos")
    print("❌ PERDE: Query building schema-aware")
    print("❌ PERDE: Filtros de frequência")
    print()
    
    # from haystack import Pipeline
    # from haystack.components.retrievers import InMemoryBM25Retriever
    # from haystack.components.rankers import CrossEncoderRanker
    # 
    # pipeline = Pipeline()
    # pipeline.add_component("retriever", InMemoryBM25Retriever(document_store=doc_store))
    # pipeline.add_component("reranker", CrossEncoderRanker())
    # pipeline.connect("retriever", "reranker")
    # 
    # result = pipeline.run({"retriever": {"query": query}})
    
    # ========================================================================
    # ABORDAGEM HÍBRIDA (Recomendada)
    # ========================================================================
    print("=" * 60)
    print("ABORDAGEM HÍBRIDA: Haystack + Customização")
    print("=" * 60)
    print("✅ Mantém: Entity-aware filtering")
    print("✅ Mantém: Filtros hierárquicos")
    print("✅ Usa Haystack: Reranking (componente genérico)")
    print("✅ Usa Haystack: Query classification")
    print("✅ Código mais limpo (~400 linhas vs 821)")
    print("✅ Componentes testáveis isoladamente")
    print("✅ Flexibilidade para trocar componentes")
    print()
    
    # pipeline_híbrido = HaystackRAGPipeline(
    #     weaviate_manager=weaviate_manager,
    #     client=client,
    #     embedder="embedder_name"
    # )
    # 
    # result = await pipeline_híbrido.retrieve_and_rerank(
    #     query=query,
    #     vector=vector,
    #     config=config,
    #     labels=[],
    #     document_uuids=[],
    # )
    
    print("=" * 60)
    print("RECOMENDAÇÃO: Usar abordagem híbrida")
    print("=" * 60)
    print("""
    Vantagens:
    1. Reduz código de 821 para ~400 linhas
    2. Mantém todas as features importantes
    3. Componentes genéricos (reranking) vêm prontos e testados
    4. Facilita manutenção e testes
    5. Permite migração gradual
    """)


# ============================================================================
# PARTE 4: MIGRAÇÃO GRADUAL
# ============================================================================

def plano_migracao_gradual():
    """
    Plano de migração gradual para Haystack.
    """
    steps = [
        {
            "step": 1,
            "acao": "Substituir reranking customizado",
            "beneficio": "Usar CrossEncoderRanker do Haystack",
            "risco": "Baixo",
            "codigo": """
# ANTES (linhas 632-674)
reranker = plugin_manager.get_plugin("Reranker")
reranked = await reranker.process_chunks(chunks, query, config)

# DEPOIS
from haystack.components.rankers import CrossEncoderRanker
reranker = CrossEncoderRanker()
result = reranker.run(query=query, documents=chunks, top_k=10)
            """
        },
        {
            "step": 2,
            "acao": "Substituir query rewriting básico",
            "beneficio": "Usar QueryClassifier do Haystack",
            "risco": "Médio (manter QueryBuilder customizado)",
            "codigo": """
# ANTES (linhas 253-288)
rewriter = QueryRewriterPlugin()
strategy = await rewriter.rewrite_query(query)

# DEPOIS (para queries simples)
from haystack.components.classifiers import QueryClassifier
classifier = QueryClassifier()
result = classifier.run(query=query)

# MANTER QueryBuilderPlugin para queries complexas com schema
            """
        },
        {
            "step": 3,
            "acao": "Manter entity-aware filtering",
            "beneficio": "Preserva features críticas",
            "risco": "Nenhum (não muda)",
            "codigo": """
# MANTÉM código original (linhas 290-625)
# Entity filtering, filtros hierárquicos, etc.
            """
        },
        {
            "step": 4,
            "acao": "Integrar com pipeline Haystack",
            "beneficio": "Arquitetura modular",
            "risco": "Médio (requer refatoração)",
            "codigo": """
# Criar wrapper para entity retriever
class EntityAwareRetriever(HaystackComponent):
    def run(self, query, vector, ...):
        # Sua lógica atual
        return {"documents": documents}

# Pipeline
pipeline = Pipeline()
pipeline.add_component("retriever", EntityAwareRetriever())
pipeline.add_component("reranker", CrossEncoderRanker())
pipeline.connect("retriever", "reranker")
            """
        }
    ]
    
    print("=" * 60)
    print("PLANO DE MIGRAÇÃO GRADUAL")
    print("=" * 60)
    for step in steps:
        print(f"\n{step['step']}. {step['acao']}")
        print(f"   Benefício: {step['beneficio']}")
        print(f"   Risco: {step['risco']}")
        print(f"   Código:")
        print(step['codigo'])


if __name__ == "__main__":
    import asyncio
    asyncio.run(exemplo_uso_comparativo())
    plano_migracao_gradual()


