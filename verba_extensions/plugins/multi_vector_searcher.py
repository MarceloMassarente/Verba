"""
Multi-Vector Searcher
Busca inteligente em múltiplos named vectors com combinação RRF (Reciprocal Rank Fusion)

Aprende do RAG2: busca paralela em múltiplos vetores especializados e combinação inteligente
"""

import asyncio
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from wasabi import msg


@dataclass
class VectorSearchResult:
    """Resultado de uma busca em um vetor específico"""
    vector_name: str
    results: List[Dict[str, Any]]
    score: float = 1.0  # Score de relevância deste vetor (0-1)


class MultiVectorSearcher:
    """
    Executor de buscas em múltiplos named vectors com combinação RRF.
    
    Permite:
    1. Buscar em 2-3 vetores em paralelo (concept_vec, sector_vec, company_vec)
    2. Combinar resultados com RRF (Reciprocal Rank Fusion)
    3. Deduplicação automática
    4. Reranking opcional
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Inicializa MultiVectorSearcher.
        
        Args:
            config: Configuração opcional
        """
        self.config = config or {}
        self.default_limit = self.config.get("default_limit", 50)
        self.default_alpha = self.config.get("default_alpha", 0.5)
        self.rrf_k = self.config.get("rrf_k", 60)  # Parâmetro RRF
    
    async def search_multi_vector(
        self,
        client,
        collection_name: str,
        query: str,
        query_vector: List[float],  # Embedding pré-calculado da query
        vectors: List[str],  # ["concept_vec", "sector_vec"]
        filters: Optional[Any] = None,  # Weaviate Filter
        limit: int = 50,
        vector_weights: Optional[Dict[str, float]] = None,
        alpha: float = 0.5,
        fusion_type: str = "RRF",  # "RRF" (manual) ou "RELATIVE_SCORE" (nativo Weaviate)
        query_properties: Optional[List[str]] = None  # Propriedades para BM25 (ex: ["content", "title^2"])
    ) -> Dict[str, Any]:
        """
        Executa busca em múltiplos named vectors em paralelo e combina resultados.
        
        ⚠️ IMPORTANTE: Modo BYOV - query_vector deve ser pré-calculado.
        
        Args:
            client: Cliente Weaviate v4
            collection_name: Nome da collection
            query: Query do usuário (string, usado para BM25)
            query_vector: Embedding pré-calculado da query
            vectors: Lista de vetores a usar (ex: ["concept_vec", "sector_vec"])
            filters: Filtros Weaviate (Filter object)
            limit: Limite de resultados finais
            vector_weights: Pesos para cada vetor (ex: {"concept_vec": 0.6, "sector_vec": 0.4})
            alpha: Alpha para busca híbrida (0.0 = só BM25, 1.0 = só vector)
            fusion_type: Tipo de fusão ("RRF" para manual, "RELATIVE_SCORE" para nativo Weaviate)
            query_properties: Propriedades para BM25 (ex: ["content", "title^2"] para boost de título)
        
        Returns:
            Dict com:
            - results: Resultados combinados e deduplicados
            - vector_results: Resultados por vetor
            - combined_scores: Scores combinados (RRF ou Relative Score)
            - metadata: Metadados da busca
        """
        # Validar entrada
        if not vectors or len(vectors) < 2:
            msg.warn("MultiVectorSearch requer >=2 vetores, usando busca simples")
            return await self._single_vector_search(
                client, collection_name, query, query_vector, vectors[0] if vectors else None,
                filters, limit, alpha
            )
        
        # Pesos padrão se não especificados
        if not vector_weights:
            weight = 1.0 / len(vectors)
            vector_weights = {v: weight for v in vectors}
        
        msg.info(f"Busca multi-vetor: {vectors} com pesos {vector_weights}")
        
        # Executar buscas em paralelo
        try:
            search_tasks = [
                self._search_single_vector(
                    client, collection_name, query, query_vector, vector_name,
                    filters, limit, alpha, query_properties
                )
                for vector_name in vectors
            ]
            
            vector_results = await asyncio.gather(*search_tasks, return_exceptions=True)
            
            # Processar resultados
            results_by_vector = {}
            for i, vector_name in enumerate(vectors):
                if isinstance(vector_results[i], Exception):
                    msg.warn(f"Erro na busca de {vector_name}: {vector_results[i]}")
                    results_by_vector[vector_name] = []
                else:
                    results_by_vector[vector_name] = vector_results[i]
            
            # Combinar resultados
            if fusion_type == "RELATIVE_SCORE":
                # Tentar usar Relative Score Fusion nativo do Weaviate
                combined = await self._combine_with_relative_score_fusion(
                    client,
                    collection_name,
                    query,
                    query_vector,
                    vectors,
                    vector_weights,
                    filters,
                    limit,
                    alpha,
                    query_properties
                )
                if combined is None:
                    # Fallback para RRF se Relative Score não disponível
                    msg.warn("Relative Score Fusion não disponível, usando RRF como fallback")
                    combined = self._combine_with_rrf(
                        results_by_vector,
                        vector_weights,
                        limit
                    )
            else:
                # Usar RRF manual (comportamento padrão)
                combined = self._combine_with_rrf(
                    results_by_vector,
                    vector_weights,
                    limit
                )
            
            return {
                "results": combined["results"],
                "vector_results": results_by_vector,
                "combined_scores": combined["scores"],
                "metadata": {
                    "vectors_used": vectors,
                    "vector_weights": vector_weights,
                    "total_results": len(combined["results"]),
                    "results_per_vector": {v: len(r) for v, r in results_by_vector.items()}
                }
            }
            
        except Exception as e:
            msg.fail(f"Erro em multi-vector search: {e}")
            raise
    
    async def _search_single_vector(
        self,
        client,
        collection_name: str,
        query: str,
        query_vector: List[float],
        vector_name: str,
        filters: Optional[Any],
        limit: int,
        alpha: float,
        query_properties: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Executa busca em um vetor específico usando nearVector + BM25.
        
        Args:
            client: Cliente Weaviate
            collection_name: Nome da collection
            query: Query do usuário (string, para BM25)
            query_vector: Vetor da query (pré-calculado, para nearVector)
            vector_name: Nome do vetor (ex: "concept_vec")
            filters: Filtros Weaviate
            limit: Limite de resultados
            alpha: Alpha para busca híbrida (0.0 = só BM25, 1.0 = só vector)
        
        Returns:
            Lista de resultados
        """
        from weaviate.classes.query import MetadataQuery
        
        try:
            collection = client.collections.get(collection_name)
            
            # Busca vetorial (nearVector)
            vector_results = []
            if alpha > 0:
                try:
                    response = await collection.query.near_vector(
                        vector=query_vector,
                        target_vector=vector_name,
                        limit=int(limit * alpha * 1.5),  # Buscar mais para combinar com BM25
                        filters=filters,
                        return_metadata=MetadataQuery(distance=True),
                        return_properties=["text", "doc_uuid", "chunk_id", "frameworks", "companies", "sectors"]
                    )
                    
                    if response and hasattr(response, 'objects'):
                        for obj in response.objects:
                            obj_dict = dict(obj.properties)
                            if obj.metadata and hasattr(obj.metadata, 'distance'):
                                obj_dict["_distance"] = obj.metadata.distance
                            obj_dict["_search_type"] = "vector"
                            obj_dict["_source_vector"] = vector_name
                            obj_dict["_uuid"] = str(obj.uuid)
                            vector_results.append(obj_dict)
                except Exception as vec_error:
                    msg.debug(f"Vector search falhou para {vector_name}: {vec_error}")
                    vector_results = []
            
            # Busca BM25 (text-only) - opcional
            bm25_results = []
            if alpha < 1.0 and query:
                try:
                    # BM25 busca no texto geral (não usa target_vector)
                    # Usa query_properties se especificado (permite boost, ex: ["content", "title^2"])
                    bm25_kwargs = {
                        "query": query,
                        "limit": int(limit * (1 - alpha) * 1.5),
                        "filters": filters,
                        "return_metadata": MetadataQuery(score=True),
                        "return_properties": ["text", "doc_uuid", "chunk_id", "frameworks", "companies", "sectors"]
                    }
                    
                    # Adiciona query_properties se disponível (Weaviate v4+)
                    if query_properties:
                        try:
                            bm25_kwargs["query_properties"] = query_properties
                        except TypeError:
                            # Se query_properties não suportado, ignora
                            pass
                    
                    response = await collection.query.bm25(**bm25_kwargs)
                    
                    if response and hasattr(response, 'objects'):
                        for obj in response.objects:
                            obj_dict = dict(obj.properties)
                            if obj.metadata and hasattr(obj.metadata, 'score'):
                                obj_dict["_score"] = obj.metadata.score
                            obj_dict["_search_type"] = "bm25"
                            obj_dict["_source_vector"] = vector_name
                            obj_dict["_uuid"] = str(obj.uuid)
                            bm25_results.append(obj_dict)
                except Exception as bm25_error:
                    msg.debug(f"BM25 search falhou para {vector_name}: {bm25_error}")
                    bm25_results = []
            
            # Combinar resultados (priorizar vector, depois BM25)
            seen_uuids = set()
            combined_results = []
            
            # Primeiro adicionar vector results
            for result in vector_results:
                uuid = result.get("_uuid")
                if uuid and uuid not in seen_uuids:
                    seen_uuids.add(uuid)
                    combined_results.append(result)
            
            # Depois adicionar BM25 results (se não duplicados)
            for result in bm25_results:
                uuid = result.get("_uuid")
                if uuid and uuid not in seen_uuids:
                    seen_uuids.add(uuid)
                    combined_results.append(result)
            
            # Limitar ao número solicitado
            results = combined_results[:limit]
            msg.debug(f"✓ Combined search ({vector_name}): {len(results)} resultados únicos")
            
            return results
            
        except Exception as e:
            msg.warn(f"Erro ao buscar em {vector_name}: {e}")
            return []
    
    async def _single_vector_search(
        self,
        client,
        collection_name: str,
        query: str,
        query_vector: List[float],
        vector_name: Optional[str],
        filters: Optional[Any],
        limit: int,
        alpha: float
    ) -> Dict[str, Any]:
        """Fallback para busca em um único vetor"""
        msg.info(f"Usando fallback: busca em vetor {vector_name}")
        
        results = await self._search_single_vector(
            client, collection_name, query, query_vector, vector_name,
            filters, limit, alpha
        )
        
        return {
            "results": results,
            "vector_results": {vector_name: results} if vector_name else {},
            "combined_scores": {},
            "metadata": {
                "fallback": True,
                "vector_used": vector_name
            }
        }
    
    def _combine_with_rrf(
        self,
        results_by_vector: Dict[str, List[Dict[str, Any]]],
        vector_weights: Dict[str, float],
        limit: int
    ) -> Dict[str, Any]:
        """
        Combina resultados de múltiplos vetores usando RRF (Reciprocal Rank Fusion).
        
        RRF Score = sum(1 / (k + rank)) para cada vetor onde o documento aparece
        
        Args:
            results_by_vector: Dict {vector_name: [results]}
            vector_weights: Pesos para cada vetor
            limit: Limite de resultados finais
        
        Returns:
            Dict com results e scores
        """
        # Mapear UUIDs para objetos e ranks
        uuid_to_result = {}
        uuid_to_ranks = {}  # {uuid: {vector: rank}}
        
        for vector_name, results in results_by_vector.items():
            weight = vector_weights.get(vector_name, 1.0 / len(results_by_vector))
            
            for rank, result in enumerate(results, start=1):
                uuid = result.get("_uuid") or result.get("id")
                if not uuid:
                    continue
                
                if uuid not in uuid_to_result:
                    uuid_to_result[uuid] = result
                    uuid_to_ranks[uuid] = {}
                
                uuid_to_ranks[uuid][vector_name] = rank
        
        # Calcular scores RRF
        combined_scores = {}
        for uuid, ranks in uuid_to_ranks.items():
            rrf_score = 0.0
            for vector_name, rank in ranks.items():
                weight = vector_weights.get(vector_name, 1.0 / len(results_by_vector))
                # RRF: 1 / (k + rank)
                rrf_contribution = weight / (self.rrf_k + rank)
                rrf_score += rrf_contribution
            
            combined_scores[uuid] = rrf_score
        
        # Reordenar por score RRF
        sorted_uuids = sorted(
            combined_scores.keys(),
            key=lambda u: combined_scores[u],
            reverse=True
        )[:limit]
        
        # Retornar resultados reordenados
        combined_results = [
            {
                **uuid_to_result[uuid],
                "_rrf_score": combined_scores[uuid],
                "_vector_ranks": uuid_to_ranks[uuid]
            }
            for uuid in sorted_uuids
        ]
        
        return {
            "results": combined_results,
            "scores": combined_scores
        }
    
    def _deduplicate(
        self,
        results: List[Dict[str, Any]],
        key: str = "_uuid"
    ) -> List[Dict[str, Any]]:
        """
        Remove duplicatas dos resultados.
        
        Args:
            results: Lista de resultados
            key: Chave para identificar duplicatas (default: "_uuid")
        
        Returns:
            Lista deduplicada
        """
        seen = set()
        deduplicated = []
        
        for result in results:
            uuid = result.get(key)
            if uuid and uuid not in seen:
                seen.add(uuid)
                deduplicated.append(result)
        
        return deduplicated
    
    async def _combine_with_relative_score_fusion(
        self,
        client,
        collection_name: str,
        query: str,
        query_vector: List[float],
        vectors: List[str],
        vector_weights: Dict[str, float],
        filters: Optional[Any],
        limit: int,
        alpha: float,
        query_properties: Optional[List[str]]
    ) -> Optional[Dict[str, Any]]:
        """
        Combina resultados usando Relative Score Fusion nativo do Weaviate.
        
        Usa collection.query.hybrid() com fusion_type=RELATIVE_SCORE e target_vector.
        Preserva magnitude da similaridade (não apenas rank).
        
        Args:
            client: Cliente Weaviate
            collection_name: Nome da collection
            query: Query do usuário
            query_vector: Embedding da query
            vectors: Lista de vetores
            vector_weights: Pesos para cada vetor
            filters: Filtros Weaviate
            limit: Limite de resultados
            alpha: Alpha para busca híbrida
            query_properties: Propriedades para BM25
        
        Returns:
            Dict com results e scores, ou None se não disponível
        """
        try:
            from weaviate.classes.query import MetadataQuery, HybridVector, TargetVectors
            import weaviate.classes.query as wvc_query
            
            collection = client.collections.get(collection_name)
            
            # Construir target_vector com pesos manuais
            # Se temos 2+ vetores, usar TargetVectors.manual_weights
            if len(vectors) >= 2:
                weights_dict = {v: vector_weights.get(v, 1.0 / len(vectors)) for v in vectors}
                target_vector = TargetVectors.manual_weights(weights=weights_dict)
            else:
                # Apenas um vetor
                target_vector = vectors[0] if vectors else None
            
            # Preparar kwargs para hybrid query
            hybrid_kwargs = {
                "query": query,
                "vector": HybridVector.near_vector(
                    vector={vectors[0]: query_vector} if vectors else query_vector
                ) if vectors else query_vector,
                "target_vector": target_vector,
                "alpha": alpha,
                "limit": limit,
                "return_metadata": MetadataQuery(score=True, distance=True, explain_score=True),
                "filters": filters
            }
            
            # Adicionar fusion_type se disponível
            try:
                hybrid_kwargs["fusion_type"] = wvc_query.HybridFusion.RELATIVE_SCORE
            except (AttributeError, TypeError):
                # Se fusion_type não disponível, retorna None para usar RRF
                return None
            
            # Adicionar query_properties se disponível
            if query_properties:
                try:
                    hybrid_kwargs["query_properties"] = query_properties
                except TypeError:
                    pass  # Ignora se não suportado
            
            # Executar busca híbrida com Relative Score Fusion
            response = await collection.query.hybrid(**hybrid_kwargs)
            
            if not response or not hasattr(response, 'objects'):
                return None
            
            # Converter resultados para formato esperado
            results = []
            scores = {}
            
            for obj in response.objects:
                obj_dict = dict(obj.properties)
                obj_dict["_uuid"] = str(obj.uuid)
                
                # Extrair score do metadata
                if obj.metadata:
                    if hasattr(obj.metadata, 'score'):
                        score = obj.metadata.score
                    elif hasattr(obj.metadata, 'distance'):
                        # Converter distance para score (1 - distance para cosine)
                        score = 1.0 - obj.metadata.distance
                    else:
                        score = 0.0
                else:
                    score = 0.0
                
                obj_dict["_score"] = score
                obj_dict["_source_vector"] = ",".join(vectors)  # Múltiplos vetores
                results.append(obj_dict)
                scores[str(obj.uuid)] = score
            
            # Ordenar por score
            results.sort(key=lambda x: x.get("_score", 0), reverse=True)
            results = results[:limit]
            
            msg.info(f"Relative Score Fusion: {len(results)} resultados combinados")
            
            return {
                "results": results,
                "scores": scores
            }
            
        except Exception as e:
            msg.debug(f"Relative Score Fusion não disponível: {str(e)}")
            return None

