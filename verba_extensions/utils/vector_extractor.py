"""
Vector Extractor
Extrai textos especializados do chunk para alimentar named vectors

Cada named vector recebe texto focado em um aspecto específico:
- concept_vec: Conceitos abstratos (frameworks, estratégias, metodologias)
- sector_vec: Setores/indústrias (varejo, bancos, tecnologia)
- company_vec: Empresas específicas (Apple, Microsoft, etc.)
"""

from typing import List, Optional
from wasabi import msg


class VectorExtractor:
    """
    Extrai textos especializados para named vectors.
    
    A estratégia é enriquecer o texto base com metadados relevantes:
    - concept_text: frameworks + termos semânticos + texto base
    - sector_text: setores + texto base
    - company_text: empresas + texto base
    """
    
    def extract_concept_text(self, chunk) -> str:
        """
        Extrai texto focado em conceitos abstratos.
        
        Combina:
        - Frameworks detectados (SWOT, Porter, BCG, etc.)
        - Termos semânticos/conceitos abstratos
        - Texto base do chunk
        
        Args:
            chunk: Chunk object (deve ter .content e .meta)
        
        Returns:
            Texto especializado para concept_vec
        """
        # Extrai frameworks do meta
        frameworks = []
        if hasattr(chunk, 'meta') and chunk.meta:
            frameworks = chunk.meta.get("frameworks", [])
            if not isinstance(frameworks, list):
                frameworks = []
        
        # Extrai termos semânticos (se disponível)
        semantic_terms = []
        if hasattr(chunk, 'meta') and chunk.meta:
            semantic_terms = chunk.meta.get("semantic_concepts", [])
            if not isinstance(semantic_terms, list):
                semantic_terms = []
        
        # Texto base
        base_text = chunk.content if hasattr(chunk, 'content') else ""
        
        # Combina tudo
        concept_parts = []
        if frameworks:
            concept_parts.extend(frameworks)
        if semantic_terms:
            concept_parts.extend(semantic_terms)
        if base_text:
            concept_parts.append(base_text)
        
        return " ".join(concept_parts)
    
    def extract_sector_text(self, chunk) -> str:
        """
        Extrai texto focado em setores/indústrias.
        
        Combina:
        - Setores detectados (varejo, bancos, tecnologia, etc.)
        - Texto base do chunk
        
        Args:
            chunk: Chunk object (deve ter .content e .meta)
        
        Returns:
            Texto especializado para sector_vec
        """
        # Extrai setores do meta
        sectors = []
        if hasattr(chunk, 'meta') and chunk.meta:
            sectors = chunk.meta.get("sectors", [])
            if not isinstance(sectors, list):
                sectors = []
        
        # Texto base
        base_text = chunk.content if hasattr(chunk, 'content') else ""
        
        # Combina
        sector_parts = []
        if sectors:
            sector_parts.extend(sectors)
        if base_text:
            sector_parts.append(base_text)
        
        return " ".join(sector_parts)
    
    def extract_company_text(self, chunk) -> str:
        """
        Extrai texto focado em empresas específicas.
        
        Combina:
        - Empresas detectadas (Apple, Microsoft, etc.)
        - Texto base do chunk
        
        Args:
            chunk: Chunk object (deve ter .content e .meta)
        
        Returns:
            Texto especializado para company_vec
        """
        # Extrai empresas do meta
        companies = []
        if hasattr(chunk, 'meta') and chunk.meta:
            companies = chunk.meta.get("companies", [])
            if not isinstance(companies, list):
                companies = []
        
        # Texto base
        base_text = chunk.content if hasattr(chunk, 'content') else ""
        
        # Combina
        company_parts = []
        if companies:
            company_parts.extend(companies)
        if base_text:
            company_parts.append(base_text)
        
        return " ".join(company_parts)
    
    def extract_all_texts(self, chunk) -> dict:
        """
        Extrai todos os textos especializados de uma vez.
        
        Args:
            chunk: Chunk object
        
        Returns:
            Dict com concept_text, sector_text, company_text
        """
        return {
            "concept_text": self.extract_concept_text(chunk),
            "sector_text": self.extract_sector_text(chunk),
            "company_text": self.extract_company_text(chunk),
        }


def get_vector_extractor() -> VectorExtractor:
    """
    Factory function para obter instância singleton do VectorExtractor.
    
    Returns:
        Instância de VectorExtractor
    """
    if not hasattr(get_vector_extractor, '_instance'):
        get_vector_extractor._instance = VectorExtractor()
    return get_vector_extractor._instance

