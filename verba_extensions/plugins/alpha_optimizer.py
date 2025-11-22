"""
Alpha Optimizer Plugin
Calcula alpha otimizado para busca híbrida baseado no tipo de query

Detecta automaticamente se query é:
- entity-rich: Queries com entidades específicas → alpha baixo (foco BM25)
- exploratory: Queries exploratórias/conceituais → alpha alto (foco vector)
"""

import re
from typing import List, Optional
from wasabi import msg


class AlphaOptimizerPlugin:
    """
    Plugin para otimização dinâmica de alpha em busca híbrida.
    
    Alpha controla o balance entre BM25 (keyword) e Vector (semantic):
    - alpha = 0.0: Apenas BM25 (keyword matching)
    - alpha = 1.0: Apenas Vector (semantic search)
    - alpha = 0.5: Balanceado
    """
    
    def __init__(self):
        """Inicializa Alpha Optimizer"""
        pass
    
    def detect_query_type(
        self, 
        query: str, 
        entities: List[str]
    ) -> str:
        """
        Detecta o tipo de query para ajustar alpha.
        
        Args:
            query: Query do usuário
            entities: Lista de entidades detectadas
        
        Returns:
            "entity-rich" ou "exploratory"
        """
        query_lower = query.lower()
        query_words = query_lower.split()
        
        # Indicadores de query entity-rich
        entity_indicators = [
            len(entities) > 0,  # Tem entidades detectadas
            any(len(word) > 3 and word[0].isupper() for word in query_words),  # Palavras capitalizadas
            bool(re.search(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', query)),  # Nomes próprios
            any(keyword in query_lower for keyword in [
                "capacidade", "capacity", "revenue", "receita",
                "market share", "participação", "stock", "ação"
            ]),  # Termos específicos de entidade
            len(query_words) <= 5,  # Query curta (geralmente específica)
        ]
        
        # Indicadores de query exploratory
        exploratory_indicators = [
            any(keyword in query_lower for keyword in [
                "como", "how", "o que", "what", "quais", "which",
                "oportunidades", "opportunities", "tendências", "trends",
                "estratégia", "strategy", "abordagem", "approach"
            ]),  # Palavras exploratórias
            len(query_words) > 8,  # Query longa (geralmente exploratória)
            "?" in query,  # Pergunta
            any(keyword in query_lower for keyword in [
                "melhor", "best", "recomendação", "recommendation",
                "análise", "analysis", "visão", "vision"
            ]),  # Termos exploratórios
        ]
        
        # Contar indicadores
        entity_score = sum(1 for indicator in entity_indicators if indicator)
        exploratory_score = sum(1 for indicator in exploratory_indicators if indicator)
        
        # Decisão
        if entity_score > exploratory_score:
            return "entity-rich"
        else:
            return "exploratory"
    
    async def calculate_optimal_alpha(
        self,
        query: str,
        entities: List[str],
        intent: Optional[str] = None
    ) -> float:
        """
        Calcula alpha otimizado baseado no tipo de query.
        
        Args:
            query: Query do usuário
            entities: Lista de entidades detectadas
            intent: Intent da query (comparison, description, search) - opcional
        
        Returns:
            Alpha otimizado (0.0-1.0)
        """
        query_type = self.detect_query_type(query, entities)
        
        # Alpha baseado no tipo de query
        if query_type == "entity-rich":
            # Queries com entidades específicas → alpha baixo (foco BM25)
            base_alpha = 0.3
            msg.info(f"AlphaOptimizer: Query entity-rich detectada → alpha={base_alpha} (foco BM25)")
        else:
            # Queries exploratórias → alpha alto (foco vector)
            base_alpha = 0.7
            msg.info(f"AlphaOptimizer: Query exploratory detectada → alpha={base_alpha} (foco vector)")
        
        # Ajustes baseados em intent
        if intent:
            if intent == "comparison":
                # Comparações beneficiam de BM25 (nomes específicos)
                base_alpha = max(0.2, base_alpha - 0.1)
            elif intent == "description":
                # Descrições beneficiam de vector (conceitos)
                base_alpha = min(0.8, base_alpha + 0.1)
        
        # Ajustes baseados em comprimento da query
        query_words = query.split()
        if len(query_words) <= 3:
            # Query muito curta → mais BM25
            base_alpha = max(0.2, base_alpha - 0.1)
        elif len(query_words) > 15:
            # Query muito longa → mais vector
            base_alpha = min(0.8, base_alpha + 0.1)
        
        # Garantir limites
        alpha = max(0.0, min(1.0, base_alpha))
        
        return alpha

