"""
Plugin: Entity-Aware Retriever
Retriever que usa filtros entity-aware para evitar contaminação

=== ARQUITETURA ===

ENTIDADE (spaCy NER) vs SEMÂNTICA (Vector Search):

1. ENTIDADE
   - O QUÊ: Coisas com identidade única (Apple, Steve Jobs, São Paulo)
   - COMO: spaCy extrai menções, Gazetteer mapeia para entity_id
   - BENEFÍCIO: WHERE filter (rápido, preciso)
   - LIMITAÇÃO: Só funciona com nomes conhecidos
   - EXEMPLO: "apple" → entity_id="Q123"

2. SEMÂNTICA
   - O QUÊ: Significado e contexto (inovação, visão, disruptivo)
   - COMO: Embedding model converte em vetor
   - BENEFÍCIO: Captura conceitos abstratos
   - LIMITAÇÃO: Pode trazer resultados sem entidade esperada
   - EXEMPLO: "inovação" → vetor [0.234, 0.891, ...]

3. HÍBRIDO (IDEAL - O QUE IMPLEMENTAMOS)
   - Combina: entity_filter AND semantic_search
   - QUERY: "apple e inovação"
   - FLUXO:
     1. Extrai entidade: Apple → entity_id="Q123"
     2. Extrai semanticamente: "inovação" → busca vetorial
     3. Aplica WHERE: chunks.entity_id = "Q123" (FILTRA)
     4. Dentro desses chunks, busca: "inovação" (SEMANTICAMENTE)
     5. Retorna: chunks sobre Apple que mencionam inovação
"""

from goldenverba.components.interfaces import Retriever
from goldenverba.components.types import InputConfig
from verba_extensions.compatibility.weaviate_imports import Filter, WEAVIATE_V4
from typing import Optional, Dict, Any, List
from wasabi import msg


class EntityAwareRetriever(Retriever):
    """
    Retriever que combina filtros entity-aware com busca semântica.
    
    Fluxo:
    1. Extrai entidades da query (spaCy + Gazetteer)
    2. Aplica WHERE filter no Weaviate (rápido!)
    3. Dentro dos resultados, faz busca semântica (relevância)
    4. Retorna chunks filtrados + relevantes
    
    Exemplo:
    Query: "descreva o que se fala sobre a Apple e Inovação"
    ├─ Entidade: Apple → entity_id="Q123"
    ├─ Semântica: "inovação" → vetor
    ├─ WHERE: entities = "Q123" (FILTRA)
    ├─ Vector search: "inovação" (DENTRO dos resultados)
    └─ Resultado: chunks sobre Apple que falam de inovação
    """
    
    def __init__(self):
        super().__init__()
        self.description = "Entity-Aware Retriever com busca semântica"
        self.name = "EntityAware"
        
        self.config["Search Mode"] = InputConfig(
            type="dropdown",
            value="Hybrid Search",
            description="Search mode to use.",
            values=["Hybrid Search"],
        )
        self.config["Limit Mode"] = InputConfig(
            type="dropdown",
            value="Autocut",
            description="Method for limiting results",
            values=["Autocut", "Fixed"],
        )
        self.config["Limit/Sensitivity"] = InputConfig(
            type="number",
            value=1,
            description="Limit value or sensitivity",
            values=[],
        )
        self.config["Chunk Window"] = InputConfig(
            type="number",
            value=1,
            description="Number of surrounding chunks",
            values=[],
        )
        self.config["Alpha"] = InputConfig(
            type="text",
            value="0.6",
            description="Hybrid search alpha (0.0=keyword, 1.0=vector). Use decimal format (e.g., 0.6)",
            values=[],
        )
        self.config["Enable Entity Filter"] = InputConfig(
            type="bool",
            value=True,
            description="Enable entity-aware pre-filtering",
            values=[],
        )
        self.config["Enable Semantic Search"] = InputConfig(
            type="bool",
            value=True,
            description="Enable semantic search within filtered results",
            values=[],
        )
    
    async def retrieve(
        self,
        client,
        query: str,
        vector: List[float],
        config: Dict,
        weaviate_manager,
        embedder: str,
        labels: List[str],
        document_uuids: List[str],
    ):
        """
        Retrieval com filtros entity-aware + busca semântica
        
        Fluxo:
        1. Parse query para separar entidades de conceitos
        2. Se tem entidades: aplica WHERE filter
        3. Dentro dos filtrados: faz busca semântica
        4. Retorna chunks ordenados por relevância
        """
        from goldenverba.components.retriever.WindowRetriever import WindowRetriever
        from verba_extensions.plugins.query_parser import parse_query
        
        msg.info(f"EntityAwareRetriever processando: '{query}'")
        
        # CONFIG
        search_mode = config["Search Mode"].value
        limit_mode = config["Limit Mode"].value
        limit = int(config["Limit/Sensitivity"].value)
        alpha_value = config["Alpha"].value
        alpha = float(alpha_value) if isinstance(alpha_value, str) else float(alpha_value)
        enable_entity_filter = config.get("Enable Entity Filter", {}).value if isinstance(config.get("Enable Entity Filter"), InputConfig) else True
        enable_semantic = config.get("Enable Semantic Search", {}).value if isinstance(config.get("Enable Semantic Search"), InputConfig) else True
        
        # 1. PARSE QUERY
        parsed = parse_query(query)
        entity_ids = [e["entity_id"] for e in parsed["entities"] if e["entity_id"]]
        semantic_terms = parsed["semantic_concepts"]
        
        msg.info(f"  Entidades: {entity_ids}")
        msg.info(f"  Conceitos: {semantic_terms}")
        
        # 2. CONSTRÓI FILTRO DE ENTIDADE (WHERE clause)
        entity_filter = None
        if enable_entity_filter and entity_ids:
            entity_filter = Filter.by_property("entities_local_ids").contains_any(entity_ids)
            msg.good(f"  Aplicando filtro: entities = {entity_ids}")
        
        # 3. DETERMINA QUERY PARA BUSCA SEMÂNTICA
        search_query = query  # Padrão: query completa
        
        if enable_semantic and semantic_terms:
            # Se tem conceitos semânticos, usa-os para melhorar a busca
            search_query = " ".join(semantic_terms)
            msg.info(f"  Query semântica: '{search_query}'")
        
        # 4. BUSCA HÍBRIDA COM FILTRO (O MAGIC AQUI!)
        if search_mode == "Hybrid Search":
            try:
                if entity_filter and enable_entity_filter:
                    # FILTRA por entidade, DEPOIS faz busca semântica
                    msg.info(f"  Executando: Hybrid search com entity filter")
                    
                    chunks = await weaviate_manager.hybrid_chunks_with_filter(
                        client=client,
                        embedder=embedder,
                        query=search_query,        # ← Query semântica ou completa
                        vector=vector,              # ← Vetor da query
                        limit_mode=limit_mode,
                        limit=limit,
                        labels=labels,
                        document_uuids=document_uuids,
                        filters=entity_filter,      # ← FILTRA por entidade PRIMEIRO
                        alpha=alpha,
                    )
                else:
                    # Sem filtro de entidade: busca normal
                    msg.info(f"  Executando: Hybrid search sem entity filter")
                    
                    chunks = await weaviate_manager.hybrid_chunks(
                        client=client,
                        embedder=embedder,
                        query=search_query,
                        vector=vector,
                        limit_mode=limit_mode,
                        limit=limit,
                        labels=labels,
                        document_uuids=document_uuids,
                    )
            except Exception as e:
                msg.fail(f"Erro na busca híbrida: {str(e)}")
                # Fallback
                chunks = []
        
        if len(chunks) == 0:
            msg.warn("Nenhum chunk encontrado")
            return ([], "We couldn't find any chunks to the query")
        
        msg.good(f"Encontrados {len(chunks)} chunks")
        
        # 5. PROCESSA CHUNKS (aplicar window)
        chunks, message = await self._process_chunks(
            client, chunks, weaviate_manager, embedder, config
        )
        
        return (chunks, message)
    
    async def _process_chunks(self, client, chunks, weaviate_manager, embedder, config):
        """Processa chunks aplicando window technique"""
        
        chunk_window = int(config.get("Chunk Window", {}).value if hasattr(config.get("Chunk Window"), 'value') else config.get("Chunk Window", 1))
        
        if chunk_window > 0 and chunks:
            # Agrupa chunks adjacentes com window
            windowed_chunks = []
            for i, chunk in enumerate(chunks):
                context_chunks = chunks[max(0, i - chunk_window):min(len(chunks), i + chunk_window + 1)]
                # Acessa content do Weaviate object corretamente
                combined_content = " ".join([
                    c.properties["content"] if hasattr(c, "properties") else c.get("content", "")
                    for c in context_chunks
                ])
                # Atualiza o content do chunk atual
                if hasattr(chunk, "properties"):
                    chunk.properties["content"] = combined_content
                else:
                    chunk["content"] = combined_content
                windowed_chunks.append(chunk)
            chunks = windowed_chunks
        
        return (chunks, "Chunks retrieved with entity-aware filtering")
    
    def combine_context(self, documents: list[dict]) -> str:
        """Combina contexto dos documentos"""
        from goldenverba.components.retriever.WindowRetriever import WindowRetriever
        window_retriever = WindowRetriever()
        return window_retriever.combine_context(documents)


def register():
    """
    Registra este plugin no sistema de extensões
    """
    return {
        'name': 'entity_aware_retriever',
        'version': '1.0.0',
        'description': 'Entity-aware retriever with anti-contamination filtering',
        'retrievers': [EntityAwareRetriever()],
        'compatible_verba_version': '>=2.1.0',
    }

