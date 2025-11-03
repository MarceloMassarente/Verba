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

3. HÍBRIDO (IDEAL)
   - Combina: entity_filter AND semantic_search
   - QUERY: "apple e inovação"
   - FLUXO:
     1. Extrai entidade: Apple → entity_id="Q123"
     2. Extrai semanticamente: "inovação" → busca vetorial
     3. Aplica WHERE: chunks.entity_id = "Q123"
     4. Combina com score de similaridade
     5. Retorna: chunks sobre Apple que mencionam inovação
"""

from goldenverba.components.interfaces import Retriever
from goldenverba.components.types import InputConfig
from verba_extensions.compatibility.weaviate_imports import Filter, WEAVIATE_V4
from typing import Optional, Dict, Any, List
from wasabi import msg

class EntityAwareRetriever(Retriever):
    """
    Retriever que suporta pre-filter entity-aware usando where filters do Weaviate
    Mantém compatibilidade com interface padrão do Verba
    """
    
    def __init__(self):
        super().__init__()
        self.description = "Retrieve relevant chunks with entity-aware filtering to prevent contamination"
        self.name = "EntityAware"
        
        self.config["Search Mode"] = InputConfig(
            type="dropdown",
            value="Hybrid Search",
            description="Switch between search types.",
            values=["Hybrid Search"],
        )
        self.config["Limit Mode"] = InputConfig(
            type="dropdown",
            value="Autocut",
            description="Method for limiting the results.",
            values=["Autocut", "Fixed"],
        )
        self.config["Limit/Sensitivity"] = InputConfig(
            type="number",
            value=32,
            description="Value for limiting the results.",
            values=[],
        )
        self.config["Chunk Window"] = InputConfig(
            type="number",
            value=1,
            description="Number of surrounding chunks to add to context",
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
        Retrieval com suporte a filtros entity-aware
        Compatível com interface padrão do Verba
        """
        from goldenverba.components.retriever.WindowRetriever import WindowRetriever
        
        # Usa WindowRetriever como base e adiciona filtros entity-aware
        search_mode = config["Search Mode"].value
        limit_mode = config["Limit Mode"].value
        limit = int(config["Limit/Sensitivity"].value)
        # Alpha pode ser string ou número, converter para float
        alpha_value = config["Alpha"].value
        alpha = float(alpha_value) if isinstance(alpha_value, str) else float(alpha_value)
        enable_entity_filter = config.get("Enable Entity Filter", {}).value if isinstance(config.get("Enable Entity Filter"), InputConfig) else True
        
        # Constrói filtros adicionais baseados em entity_ids se disponível
        # Isso seria injetado via orquestrador ou query analysis
        entity_filter = None
        
        # Se entity_filter estiver disponível no contexto (via hooks), usa ele
        from verba_extensions.hooks import global_hooks
        # Usa execute_hook_async se disponível (para hooks async)
        try:
            entity_context = await global_hooks.execute_hook_async('entity_aware.get_filters', query)
        except:
            # Fallback para sync
            entity_context = global_hooks.execute_hook('entity_aware.get_filters', query)
        
        if entity_context and enable_entity_filter:
            entity_filter = self._build_entity_filter(entity_context)
        
        # Combina filtros
        all_filters = []
        
        # Constrói filtros compatíveis com v3/v4
        filter_dict = {}
        
        if labels:
            if WEAVIATE_V4:
                all_filters.append(Filter.by_property("labels").contains_all(labels))
            else:
                filter_dict['labels'] = {'path': ['labels'], 'operator': 'ContainsAll', 'valueString': labels}
        
        if document_uuids:
            if WEAVIATE_V4:
                all_filters.append(Filter.by_property("doc_uuid").contains_any(document_uuids))
            else:
                filter_dict['doc_uuid'] = {'path': ['doc_uuid'], 'operator': 'ContainsAny', 'valueString': document_uuids}
        
        if entity_filter:
            if WEAVIATE_V4:
                all_filters.append(entity_filter)
            else:
                # Para v3, entity_filter já deve ser dict
                if isinstance(entity_filter, dict):
                    filter_dict['entity'] = entity_filter
        
        # Aplica filtros combinados
        final_filter = None
        if WEAVIATE_V4:
            if len(all_filters) > 1:
                final_filter = all_filters[0]
                for f in all_filters[1:]:
                    final_filter = final_filter & f
            elif len(all_filters) == 1:
                final_filter = all_filters[0]
        else:
            # Para v3, usa dict com operador "And"
            if filter_dict:
                if len(filter_dict) > 1:
                    final_filter = {
                        'operator': 'And',
                        'operands': list(filter_dict.values())
                    }
                else:
                    final_filter = list(filter_dict.values())[0]
        
        # Busca híbrida com filtros
        if search_mode == "Hybrid Search":
            chunks = await weaviate_manager.hybrid_chunks(
                client,
                embedder,
                query,
                vector,
                limit_mode,
                limit,
                labels,  # Mantém compatibilidade
                document_uuids,  # Mantém compatibilidade
            )
            
            # Se temos filtros entity-aware, aplica pós-busca ou modifica a busca
            # Para compatibilidade total, precisamos modificar hybrid_chunks
            # Por enquanto, filtra resultados manualmente se necessário
            if entity_filter and chunks:
                chunks = await self._filter_chunks_by_entity(chunks, entity_context)
        
        if len(chunks) == 0:
            return ([], "We couldn't find any chunks matching the query")
        
        # Resto da lógica similar ao WindowRetriever
        return await self._process_chunks(
            client, chunks, weaviate_manager, embedder, config
        )
    
    def _build_entity_filter(self, entity_context: Dict) -> Optional[Any]:
        """Constrói filtro Weaviate baseado em entity IDs (compatível v3/v4)"""
        if not entity_context or 'entity_ids' not in entity_context:
            return None
        
        entity_ids = entity_context['entity_ids']
        if not entity_ids:
            return None
        
        # Para v4, usa Filter objects; para v3, usa dict
        if WEAVIATE_V4:
            # Filtro: entities_local_ids OU (section_entity_ids + confidence)
            filters = []
            
            # Entidades no chunk
            filters.append(
                Filter.by_property("entities_local_ids").contains_any(entity_ids)
            )
            
            # Entidades na seção com confiança alta
            if entity_context.get('require_section_confidence', 0.7):
                section_filters = [
                    Filter.by_property("section_entity_ids").contains_any(entity_ids),
                    Filter.by_property("section_scope_confidence").greater_or_equal(
                        entity_context.get('require_section_confidence', 0.7)
                    )
                ]
                section_combo = section_filters[0]
                for sf in section_filters[1:]:
                    section_combo = section_combo & sf
                filters.append(section_combo)
            
            # Combina com OR
            if len(filters) > 1:
                combined = filters[0]
                for f in filters[1:]:
                    combined = combined | f
                return combined
            
            return filters[0] if filters else None
        else:
            # Para v3, retorna dict
            local_filter = {
                'path': ['entities_local_ids'],
                'operator': 'ContainsAny',
                'valueString': entity_ids
            }
            
            section_filter = {
                'path': ['section_entity_ids'],
                'operator': 'ContainsAny',
                'valueString': entity_ids
            }
            
            # Combina com OR
            return {
                'operator': 'Or',
                'operands': [local_filter, section_filter]
            }
    
    async def _filter_chunks_by_entity(self, chunks: List, entity_context: Dict) -> List:
        """Filtra chunks por entidades (fallback se filtro não funcionar na busca)"""
        entity_ids = set(entity_context.get('entity_ids', []))
        if not entity_ids:
            return chunks
        
        filtered = []
        for chunk in chunks:
            props = chunk.properties
            local_ids = set(props.get('entities_local_ids', []))
            section_ids = set(props.get('section_entity_ids', []))
            
            # Inclui se tem entidade local OU na seção com confiança alta
            if local_ids & entity_ids:
                filtered.append(chunk)
            elif section_ids & entity_ids:
                confidence = props.get('section_scope_confidence', 0.0)
                if confidence >= entity_context.get('require_section_confidence', 0.7):
                    filtered.append(chunk)
        
        return filtered if filtered else chunks  # Fallback se nenhum match
    
    async def _process_chunks(self, client, chunks, weaviate_manager, embedder, config):
        """Processa chunks similar ao WindowRetriever - retorna chunks processados"""
        # Em vez de chamar WindowRetriever (que espera Threshold e outros params),
        # processamos os chunks diretamente aqui
        
        # Aplica window technique se configurado
        chunk_window = int(config.get("Chunk Window", {}).value if hasattr(config.get("Chunk Window"), 'value') else config.get("Chunk Window", 1))
        
        if chunk_window > 0 and chunks:
            # Agrupa chunks adjacentes
            windowed_chunks = []
            for i, chunk in enumerate(chunks):
                context_chunks = chunks[max(0, i - chunk_window):min(len(chunks), i + chunk_window + 1)]
                combined_content = " ".join([c.content for c in context_chunks])
                chunk.content = combined_content
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

