"""
RAG 2.0 Enhancement: Adaptive Query Analysis via Entropy

Este módulo fornece análise de entropia para decisão adaptativa de rewriting.
Compartilhado entre QueryRewriterPlugin e QueryBuilderPlugin.

Conceito:
- Entropia alta = query genérica (ex: "o que é isso?") → precisa rewrite forte
- Entropia baixa = query específica (ex: "Steve Jobs cofundador Apple 2007") → skip ou rewrite leve
"""

import re
from typing import Dict, Any, Tuple
from wasabi import msg


class AdaptiveEntropyAnalyzer:
    """
    Analisador de entropia para decisão adaptativa de query rewriting.
    
    Calcula métricas léxicas para determinar se uma query é:
    - Específica (baixa entropia): contém entidades, termos técnicos, nomes próprios
    - Genérica (alta entropia): muitas stopwords, poucas entidades, termos vagos
    """
    
    def __init__(
        self,
        threshold_skip: float = 0.3,
        threshold_light: float = 0.5,
        threshold_strong: float = 0.7
    ):
        """
        Inicializa o analisador.
        
        Args:
            threshold_skip: Abaixo disso, não reescrever (muito específico)
            threshold_light: Entre skip e light, rewrite leve
            threshold_strong: Acima disso, rewrite forte (muito genérico)
        """
        self.threshold_skip = threshold_skip
        self.threshold_light = threshold_light
        self.threshold_strong = threshold_strong
        
        # Stopwords PT/EN - importadas do módulo utilitário comum
        from verba_extensions.utils.language_utils import STOPWORDS_PT, STOPWORDS_EN, get_all_stopwords
        self._stopwords_pt = STOPWORDS_PT
        self._stopwords_en = STOPWORDS_EN
        self._stopwords = get_all_stopwords()
    
    def calculate_entropy(self, query: str) -> Tuple[float, Dict[str, Any]]:
        """
        Calcula entropia léxica da query.
        
        Args:
            query: Query do usuário
            
        Returns:
            Tuple[float, Dict]: (entropy_score 0-1, debug_info)
        """
        if not query or not query.strip():
            return 0.5, {"error": "empty query"}
        
        # Tokenizar
        words = re.findall(r'\b\w+\b', query.lower())
        
        if len(words) == 0:
            return 0.5, {"error": "no words"}
        
        # Remover stopwords
        content_words = [w for w in words if w not in self._stopwords and len(w) > 1]
        
        if len(content_words) == 0:
            return 1.0, {"reason": "only_stopwords", "words": words}
        
        # Métricas
        total_words = len(words)
        unique_words = len(set(words))
        content_word_count = len(content_words)
        
        # Detectar entidades (maiúscula ou números)
        entities = [w for w in query.split() if len(w) > 0 and (w[0].isupper() or any(c.isdigit() for c in w))]
        entity_count = len(entities)
        
        # Calcular ratios
        uniqueness_ratio = unique_words / total_words if total_words > 0 else 0
        stopword_ratio = (total_words - content_word_count) / total_words if total_words > 0 else 0
        entity_ratio = min(entity_count / max(total_words, 1), 1.0)
        length_factor = min(total_words / 10, 1.0)
        
        # Entropia combinada
        entropy = (
            0.3 * uniqueness_ratio +
            0.4 * stopword_ratio +
            0.2 * (1 - entity_ratio) +
            0.1 * (1 - length_factor)
        )
        
        debug_info = {
            "total_words": total_words,
            "unique_words": unique_words,
            "content_words": content_word_count,
            "entities_detected": entities,
            "uniqueness_ratio": round(uniqueness_ratio, 3),
            "stopword_ratio": round(stopword_ratio, 3),
            "entity_ratio": round(entity_ratio, 3),
            "length_factor": round(length_factor, 3),
            "entropy": round(entropy, 3)
        }
        
        return entropy, debug_info
    
    def analyze(self, query: str, log_output: bool = True) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Analisa query e decide modo de rewriting.
        
        Args:
            query: Query do usuário
            log_output: Se True, loga decisão
            
        Returns:
            Tuple[bool, str, Dict]: (should_rewrite, mode, debug_info)
            - mode: "skip" | "light" | "moderate" | "strong"
        """
        entropy, debug_info = self.calculate_entropy(query)
        
        if entropy < self.threshold_skip:
            mode = "skip"
            should = False
            if log_output:
                msg.info(f"  Adaptive: SKIP (entropy={entropy:.3f}, query específica)")
        elif entropy < self.threshold_light:
            mode = "light"
            should = True
            if log_output:
                msg.info(f"  Adaptive: LIGHT (entropy={entropy:.3f})")
        elif entropy < self.threshold_strong:
            mode = "moderate"
            should = True
            if log_output:
                msg.info(f"  Adaptive: MODERATE (entropy={entropy:.3f})")
        else:
            mode = "strong"
            should = True
            if log_output:
                msg.info(f"  Adaptive: STRONG (entropy={entropy:.3f}, query genérica)")
        
        debug_info["rewrite_mode"] = mode
        debug_info["should_rewrite"] = should
        
        return should, mode, debug_info


# Singleton para reutilização
_default_analyzer = None

def get_analyzer() -> AdaptiveEntropyAnalyzer:
    """Retorna instância singleton do analisador."""
    global _default_analyzer
    if _default_analyzer is None:
        _default_analyzer = AdaptiveEntropyAnalyzer()
    return _default_analyzer


def should_rewrite_query(query: str) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Função de conveniência para análise rápida.
    
    Args:
        query: Query do usuário
        
    Returns:
        Tuple[bool, str, Dict]: (should_rewrite, mode, debug_info)
    """
    return get_analyzer().analyze(query)



