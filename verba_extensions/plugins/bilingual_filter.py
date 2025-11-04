"""
Plugin: Bilingual Filter
Detecta idioma da query e cria filtro para chunks no mesmo idioma

Baseado em RAG2: api/server.py _detect_query_lang()
"""

from typing import Optional
from verba_extensions.compatibility.weaviate_imports import Filter


class BilingualFilterPlugin:
    """
    Plugin que detecta idioma da query e cria filtro Weaviate.
    
    Estratégia:
    - Usa heurística de palavras-chave PT/EN
    - Cria filtro Filter.by_property("chunk_lang").equal(query_lang)
    - Compatível com EntityAwareRetriever
    """
    
    def __init__(self):
        # Palavras-chave PT (stopwords e palavras comuns)
        self.pt_words = [
            "de", "da", "do", "em", "para", "com", "sem", "sobre", "entre",
            "como", "onde", "quando", "quem", "porque", "por", "que", "este",
            "está", "são", "faz", "trabalha", "experiência", "empresa",
            "empresas", "sobre", "sobre", "sobre", "sobre", "sobre",
            "fazer", "fazendo", "feito", "fez", "fizeram",
            "trabalhar", "trabalhando", "trabalhou", "trabalharam",
            "inovação", "inovação", "inovação", "inovação", "inovação"
        ]
        
        # Palavras-chave EN (stopwords e palavras comuns)
        self.en_words = [
            "the", "a", "an", "of", "in", "on", "at", "to", "for", "with",
            "from", "by", "about", "as", "is", "are", "was", "were", "been",
            "experience", "company", "companies", "work", "worked", "working",
            "innovation", "innovative", "innovate", "innovating",
            "make", "making", "made", "makes"
        ]
    
    def detect_query_language(self, query: str) -> Optional[str]:
        """
        Detecta idioma da query usando heurística de palavras-chave.
        
        Args:
            query: Query do usuário
            
        Returns:
            "pt" para português, "en" para inglês, None se não detectar
        """
        if not query or not query.strip():
            return None
        
        query_lower = query.lower()
        
        # Contar ocorrências de palavras-chave
        pt_count = sum(1 for word in self.pt_words if f" {word} " in f" {query_lower} ")
        en_count = sum(1 for word in self.en_words if f" {word} " in f" {query_lower} ")
        
        # Se ambos zero, tentar detectar por padrões específicos
        if pt_count == 0 and en_count == 0:
            # Padrões PT
            pt_patterns = ["não", "não", "não", "não", "não", "não"]
            en_patterns = ["not", "don't", "doesn't", "didn't", "won't", "can't"]
            
            pt_pattern_count = sum(1 for pattern in pt_patterns if pattern in query_lower)
            en_pattern_count = sum(1 for pattern in en_patterns if pattern in query_lower)
            
            if pt_pattern_count > en_pattern_count:
                return "pt"
            elif en_pattern_count > pt_pattern_count:
                return "en"
            else:
                # Não detectou, retornar None
                return None
        
        # Retornar idioma com mais ocorrências
        if pt_count > en_count:
            return "pt"
        elif en_count > pt_count:
            return "en"
        else:
            # Empate, retornar None
            return None
    
    def build_language_filter(self, query_lang: str) -> Optional[Filter]:
        """
        Constrói filtro Weaviate para idioma.
        
        Args:
            query_lang: Idioma detectado ("pt" ou "en")
            
        Returns:
            Filter Weaviate ou None se query_lang inválido
        """
        if query_lang not in ["pt", "en"]:
            return None
        
        try:
            return Filter.by_property("chunk_lang").equal(query_lang)
        except Exception as e:
            # Fallback: retornar None se filtro falhar
            return None
    
    def get_language_filter_for_query(self, query: str) -> Optional[Filter]:
        """
        Método de conveniência: detecta idioma e cria filtro.
        
        Args:
            query: Query do usuário
            
        Returns:
            Filter Weaviate ou None se não detectar idioma
        """
        query_lang = self.detect_query_language(query)
        if query_lang:
            return self.build_language_filter(query_lang)
        return None

