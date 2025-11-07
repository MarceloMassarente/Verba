"""
Plugin: Bilingual Filter
Detecta idioma da query e cria filtro para chunks no mesmo idioma

⭐ NOVO: Suporta code-switching (PT+EN) em documentos corporativos
Baseado em RAG2: api/server.py _detect_query_lang()
"""

from typing import Optional, List
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
    
    def detect_query_language_simple(self, query: str) -> Optional[str]:
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
    
    def detect_query_language(self, query: str) -> Optional[str]:
        """
        Detecta idioma da query com suporte a code-switching
        
        Args:
            query: Query do usuário
            
        Returns:
            "pt", "en", "pt-en", "en-pt", ou None
        """
        try:
            from verba_extensions.utils.code_switching_detector import get_detector
            detector = get_detector()
            language_code, stats = detector.detect_language_mix(query)
            return language_code
        except Exception:
            # Fallback para detecção simples
            return self.detect_query_language_simple(query)
    
    def build_language_filter(self, query_lang: str, allow_bilingual: bool = True) -> Optional[Filter]:
        """
        Constrói filtro Weaviate para idioma com suporte a code-switching
        
        Args:
            query_lang: Idioma detectado ("pt", "en", "pt-en", "en-pt")
            allow_bilingual: Se True, aceita chunks bilíngues quando query é bilíngue
            
        Returns:
            Filter Weaviate ou None se query_lang inválido
            
        Exemplos:
            query_lang="pt" → chunk_lang IN ["pt", "pt-en"]  (aceita PT puro ou PT com jargão EN)
            query_lang="en" → chunk_lang IN ["en", "en-pt"]  (aceita EN puro ou EN com termos PT)
            query_lang="pt-en" → chunk_lang IN ["pt", "en", "pt-en", "en-pt"]  (aceita tudo bilíngue)
        """
        if not query_lang:
            return None
        
        try:
            from verba_extensions.utils.code_switching_detector import get_detector
            detector = get_detector()
            
            # Se query é bilíngue, aceitar chunks em ambos idiomas + bilíngues
            if detector.is_bilingual(query_lang) and allow_bilingual:
                # Query bilíngue: aceitar PT, EN, PT-EN, EN-PT
                accepted_languages = ["pt", "en", "pt-en", "en-pt"]
                return Filter.by_property("chunk_lang").contains_any(accepted_languages)
            
            # Se query é monolíngue mas allow_bilingual=True, aceitar chunks bilíngues também
            if allow_bilingual:
                primary = detector.get_primary_language(query_lang)
                if primary == "pt":
                    # Query PT: aceitar chunks PT ou PT-EN
                    return Filter.by_property("chunk_lang").contains_any(["pt", "pt-en"])
                elif primary == "en":
                    # Query EN: aceitar chunks EN ou EN-PT
                    return Filter.by_property("chunk_lang").contains_any(["en", "en-pt"])
            
            # Fallback: filtro estrito (apenas idioma exato)
            if query_lang in ["pt", "en"]:
                return Filter.by_property("chunk_lang").equal(query_lang)
            
            return None
            
        except Exception as e:
            # Fallback: detecção simples
            if query_lang not in ["pt", "en"]:
                return None
            try:
                if allow_bilingual:
                    # Aceitar chunk_lang exato ou bilíngue
                    if query_lang == "pt":
                        return Filter.by_property("chunk_lang").contains_any(["pt", "pt-en"])
                    elif query_lang == "en":
                        return Filter.by_property("chunk_lang").contains_any(["en", "en-pt"])
                return Filter.by_property("chunk_lang").equal(query_lang)
            except:
                return None
    
    def get_language_filter_for_query(self, query: str, allow_bilingual: bool = True) -> Optional[Filter]:
        """
        Método de conveniência: detecta idioma e cria filtro com suporte a code-switching
        
        Args:
            query: Query do usuário
            allow_bilingual: Se True, aceita chunks bilíngues (padrão: True para contexto corporativo)
            
        Returns:
            Filter Weaviate ou None se não detectar idioma
        """
        query_lang = self.detect_query_language(query)
        if query_lang:
            return self.build_language_filter(query_lang, allow_bilingual=allow_bilingual)
        return None

