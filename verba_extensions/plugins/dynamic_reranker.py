"""
RAG 2.0 Enhancement: Dynamic Multi-Dimensional Score Enricher

Este plugin ENRIQUECE scores de chunks com dimensões adicionais:
1. Similaridade semântica (score original do retriever)
2. Recência (chunks mais recentes = mais relevantes)
3. Frequência de entidades (chunks com mais entidades = mais relevantes)
4. Autoridade do documento (opcional)

IMPORTANTE: Este plugin NÃO substitui o RerankerPlugin existente!
- RerankerPlugin: Usa APIs (Cohere, Jina, etc.) para reranking semântico
- DynamicReranker: Enriquece scores com metadados locais (zero custo)

Uso recomendado:
1. DynamicReranker ANTES do RerankerPlugin (enriquece scores)
2. Ou como alternativa leve quando não há APIs disponíveis

Benefícios:
- Zero custo de API
- Muito rápido (local)
- Configurável via pesos
- Complementa o RerankerPlugin existente
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from wasabi import msg


class DynamicReranker:
    """
    Reranker multi-dimensional que combina múltiplos sinais.
    
    Score final = w1*similarity + w2*recency + w3*entity_freq + w4*authority
    
    Onde:
    - similarity: Score original do retriever (0-1)
    - recency: Quão recente é o chunk (0-1, 1=hoje)
    - entity_freq: Quantas entidades o chunk menciona (0-1, normalizado)
    - authority: Confiabilidade do documento fonte (0-1)
    """
    
    def __init__(
        self,
        similarity_weight: float = 0.7,
        recency_weight: float = 0.15,
        entity_weight: float = 0.15,
        authority_weight: float = 0.0,
        recency_decay_days: int = 365
    ):
        """
        Inicializa o reranker.
        
        Args:
            similarity_weight: Peso do score de similaridade (default: 0.7)
            recency_weight: Peso do score de recência (default: 0.15)
            entity_weight: Peso do score de entidades (default: 0.15)
            authority_weight: Peso do score de autoridade (default: 0.0)
            recency_decay_days: Dias para decay de recência (default: 365)
        """
        # Normalizar pesos para somar 1.0
        total = similarity_weight + recency_weight + entity_weight + authority_weight
        if total > 0:
            self.similarity_weight = similarity_weight / total
            self.recency_weight = recency_weight / total
            self.entity_weight = entity_weight / total
            self.authority_weight = authority_weight / total
        else:
            self.similarity_weight = 1.0
            self.recency_weight = 0.0
            self.entity_weight = 0.0
            self.authority_weight = 0.0
        
        self.recency_decay_days = recency_decay_days
    
    def _calculate_recency_score(self, chunk: Dict[str, Any]) -> float:
        """
        Calcula score de recência (0-1, 1=hoje).
        
        Usa chunk_date se disponível, senão retorna 0.5 (neutro).
        """
        chunk_date = chunk.get("chunk_date") or chunk.get("date")
        
        if not chunk_date:
            return 0.5  # Neutro se não temos data
        
        try:
            # Tentar parsear data
            if isinstance(chunk_date, str):
                # Tentar vários formatos
                for fmt in ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%d/%m/%Y"]:
                    try:
                        date = datetime.strptime(chunk_date.split("T")[0], fmt.split("T")[0])
                        break
                    except ValueError:
                        continue
                else:
                    return 0.5
            elif isinstance(chunk_date, datetime):
                date = chunk_date
            else:
                return 0.5
            
            # Calcular dias desde hoje
            days_old = (datetime.now() - date).days
            
            # Score decai linearmente até recency_decay_days
            # 0 dias = 1.0, recency_decay_days = 0.0
            score = max(0.0, 1.0 - (days_old / self.recency_decay_days))
            
            return score
            
        except Exception:
            return 0.5
    
    def _calculate_entity_score(self, chunk: Dict[str, Any]) -> float:
        """
        Calcula score baseado em frequência de entidades (0-1).
        
        Mais entidades = chunk mais informativo.
        """
        # Tentar diferentes campos de entidades
        entities = (
            chunk.get("entities") or
            chunk.get("entities_local_ids") or
            chunk.get("section_entity_ids") or
            []
        )
        
        if isinstance(entities, str):
            # Se for string, tentar split
            entities = [e.strip() for e in entities.split(",") if e.strip()]
        
        entity_count = len(entities) if isinstance(entities, list) else 0
        
        # Normalizar: até 5 entidades = score 1.0
        return min(entity_count / 5.0, 1.0)
    
    def _calculate_authority_score(self, chunk: Dict[str, Any]) -> float:
        """
        Calcula score de autoridade do documento (0-1).
        
        Pode ser baseado em:
        - Tipo de documento (whitepaper > blog)
        - Fonte (oficial > terceiros)
        - Metadados de qualidade
        """
        # Por enquanto, retornar 1.0 (todos documentos são iguais)
        # Pode ser expandido para usar metadados específicos
        
        doc_type = chunk.get("doc_type", "").lower()
        
        # Hierarquia de autoridade
        authority_map = {
            "whitepaper": 1.0,
            "report": 0.9,
            "official": 0.9,
            "documentation": 0.85,
            "article": 0.7,
            "blog": 0.6,
            "news": 0.5,
            "forum": 0.4,
            "social": 0.3,
        }
        
        for key, score in authority_map.items():
            if key in doc_type:
                return score
        
        return 0.7  # Default médio
    
    def calculate_combined_score(self, chunk: Dict[str, Any]) -> float:
        """
        Calcula score combinado para um chunk.
        
        Args:
            chunk: Dict com dados do chunk
            
        Returns:
            float: Score combinado (0-1)
        """
        # Score de similaridade (original do retriever)
        similarity_score = chunk.get("score", 0.5)
        
        # Normalizar se necessário (alguns retrievers retornam 0-100)
        if similarity_score > 1.0:
            similarity_score = similarity_score / 100.0
        
        # Outros scores
        recency_score = self._calculate_recency_score(chunk)
        entity_score = self._calculate_entity_score(chunk)
        authority_score = self._calculate_authority_score(chunk)
        
        # Combinar com pesos
        combined = (
            self.similarity_weight * similarity_score +
            self.recency_weight * recency_score +
            self.entity_weight * entity_score +
            self.authority_weight * authority_score
        )
        
        return combined
    
    def rerank_chunks(
        self,
        chunks: List[Dict[str, Any]],
        return_scores: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Reordena chunks por score combinado.
        
        Args:
            chunks: Lista de chunks para reranking
            return_scores: Se True, adiciona campo 'combined_score' aos chunks
            
        Returns:
            Lista de chunks reordenados (maior score primeiro)
        """
        if not chunks:
            return chunks
        
        # Calcular scores
        scored_chunks = []
        for chunk in chunks:
            combined_score = self.calculate_combined_score(chunk)
            
            if return_scores:
                chunk_copy = chunk.copy()
                chunk_copy["combined_score"] = round(combined_score, 4)
                chunk_copy["original_score"] = chunk.get("score", 0)
                scored_chunks.append((combined_score, chunk_copy))
            else:
                scored_chunks.append((combined_score, chunk))
        
        # Ordenar por score (maior primeiro)
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        
        # Retornar apenas chunks
        return [chunk for _, chunk in scored_chunks]
    
    def rerank_documents(
        self,
        documents: List[Dict[str, Any]],
        rerank_chunks_within: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Reordena documentos e opcionalmente chunks dentro deles.
        
        Args:
            documents: Lista de documentos
            rerank_chunks_within: Se True, também reordena chunks dentro de cada doc
            
        Returns:
            Lista de documentos reordenados
        """
        if not documents:
            return documents
        
        reranked_docs = []
        
        for doc in documents:
            doc_copy = doc.copy()
            
            # Rerank chunks dentro do documento
            if rerank_chunks_within and "chunks" in doc_copy:
                doc_copy["chunks"] = self.rerank_chunks(doc_copy["chunks"])
            
            # Calcular score médio do documento baseado nos chunks
            if "chunks" in doc_copy and doc_copy["chunks"]:
                avg_score = sum(
                    self.calculate_combined_score(c) for c in doc_copy["chunks"]
                ) / len(doc_copy["chunks"])
                doc_copy["doc_combined_score"] = round(avg_score, 4)
            else:
                doc_copy["doc_combined_score"] = 0.5
            
            reranked_docs.append(doc_copy)
        
        # Ordenar documentos por score médio
        reranked_docs.sort(key=lambda d: d.get("doc_combined_score", 0), reverse=True)
        
        return reranked_docs


# Função de conveniência
def rerank_results(
    chunks: List[Dict[str, Any]],
    similarity_weight: float = 0.7,
    recency_weight: float = 0.15,
    entity_weight: float = 0.15
) -> List[Dict[str, Any]]:
    """
    Função de conveniência para reranking rápido.
    
    Args:
        chunks: Lista de chunks
        similarity_weight: Peso da similaridade
        recency_weight: Peso da recência
        entity_weight: Peso das entidades
        
    Returns:
        Lista de chunks reordenados
    """
    reranker = DynamicReranker(
        similarity_weight=similarity_weight,
        recency_weight=recency_weight,
        entity_weight=entity_weight
    )
    return reranker.rerank_chunks(chunks)

