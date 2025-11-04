"""
Plugin: Temporal Filter
Extrai faixas de datas de queries e cria filtros temporais

Baseado em RAG2: api/server.py filtros temporais
"""

import re
from typing import Optional, Tuple
from datetime import datetime
from verba_extensions.compatibility.weaviate_imports import Filter


class TemporalFilterPlugin:
    """
    Plugin que extrai faixas de datas de queries e cria filtros Weaviate.
    
    Features:
    - Detecção de anos (2024, 2023-2024)
    - Detecção de palavras-chave: "desde", "até", "from", "to", "until"
    - Detecção de meses e datas completas
    - Criação de filtros Weaviate com greater_or_equal e less_or_equal
    """
    
    def __init__(self):
        # Palavras-chave PT
        self.pt_keywords_start = ["desde", "a partir de", "após", "depois de"]
        self.pt_keywords_end = ["até", "até", "antes de", "até o"]
        
        # Palavras-chave EN
        self.en_keywords_start = ["from", "since", "after", "starting"]
        self.en_keywords_end = ["to", "until", "before", "up to"]
    
    def extract_date_range(self, query: str) -> Optional[Tuple[Optional[str], Optional[str]]]:
        """
        Extrai faixa de datas da query.
        
        Args:
            query: Query do usuário
            
        Returns:
            Tuple (start_date, end_date) ou None se não detectar datas
            - start_date: Data início em formato ISO (YYYY-MM-DD) ou None
            - end_date: Data fim em formato ISO (YYYY-MM-DD) ou None
        """
        if not query or not query.strip():
            return None
        
        query_lower = query.lower()
        
        # 1. Detectar anos (2024, 2023-2024, etc.)
        year_pattern = r'\b(20\d{2})\b'
        years = re.findall(year_pattern, query)
        
        if years:
            years_int = [int(y) for y in years]
            min_year = min(years_int)
            max_year = max(years_int)
            
            # Se tem range de anos (ex: "2023-2024")
            if len(years_int) > 1:
                return (f"{min_year}-01-01", f"{max_year}-12-31")
            else:
                # Ano único
                # Verificar se tem palavras-chave de range
                has_start = any(kw in query_lower for kw in self.pt_keywords_start + self.en_keywords_start)
                has_end = any(kw in query_lower for kw in self.pt_keywords_end + self.en_keywords_end)
                
                if has_start:
                    # "desde 2024" -> (2024-01-01, None)
                    return (f"{min_year}-01-01", None)
                elif has_end:
                    # "até 2024" -> (None, 2024-12-31)
                    return (None, f"{min_year}-12-31")
                else:
                    # Ano único sem keywords: assumir range do ano
                    return (f"{min_year}-01-01", f"{min_year}-12-31")
        
        # 2. Detectar palavras-chave com anos
        # "desde 2024" ou "from 2024"
        for kw in self.pt_keywords_start + self.en_keywords_start:
            pattern = rf'{kw}\s+(\d{{4}})'
            match = re.search(pattern, query_lower)
            if match:
                year = int(match.group(1))
                return (f"{year}-01-01", None)
        
        # "até 2024" ou "until 2024"
        for kw in self.pt_keywords_end + self.en_keywords_end:
            pattern = rf'{kw}\s+(\d{{4}})'
            match = re.search(pattern, query_lower)
            if match:
                year = int(match.group(1))
                return (None, f"{year}-12-31")
        
        # 3. Detectar datas completas (DD/MM/YYYY, YYYY-MM-DD, etc.)
        date_patterns = [
            r'\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b',  # DD/MM/YYYY ou DD-MM-YYYY
            r'\b(\d{4})[/-](\d{1,2})[/-](\d{1,2})\b',  # YYYY/MM/DD ou YYYY-MM-DD
        ]
        
        dates = []
        for pattern in date_patterns:
            matches = re.findall(pattern, query)
            for match in matches:
                try:
                    if len(match[0]) == 4:  # YYYY-MM-DD
                        year, month, day = int(match[0]), int(match[1]), int(match[2])
                    else:  # DD/MM/YYYY
                        day, month, year = int(match[0]), int(match[1]), int(match[2])
                    dates.append(f"{year}-{month:02d}-{day:02d}")
                except:
                    continue
        
        if dates:
            if len(dates) == 1:
                # Data única: assumir como start_date
                return (dates[0], None)
            else:
                # Múltiplas datas: range
                dates_sorted = sorted(dates)
                return (dates_sorted[0], dates_sorted[-1])
        
        # Não detectou datas
        return None
    
    def build_temporal_filter(
        self,
        start_date: Optional[str],
        end_date: Optional[str],
        date_field: str = "chunk_date"
    ) -> Optional[Filter]:
        """
        Constrói filtro temporal para Weaviate.
        
        Args:
            start_date: Data início em formato ISO (YYYY-MM-DD) ou None
            end_date: Data fim em formato ISO (YYYY-MM-DD) ou None
            date_field: Nome do campo de data no Weaviate (default: "chunk_date")
            
        Returns:
            Filter Weaviate ou None se não houver datas
        """
        if not start_date and not end_date:
            return None
        
        filters = []
        
        try:
            if start_date:
                # Parse date
                start_dt = datetime.fromisoformat(start_date)
                filters.append(
                    Filter.by_property(date_field).greater_or_equal(start_dt)
                )
            
            if end_date:
                # Parse date
                end_dt = datetime.fromisoformat(end_date)
                filters.append(
                    Filter.by_property(date_field).less_or_equal(end_dt)
                )
            
            # Combinar filtros
            if len(filters) == 1:
                return filters[0]
            elif len(filters) == 2:
                return Filter.all_of(filters)
            else:
                return None
                
        except Exception as e:
            # Fallback: retornar None se filtro falhar
            return None
    
    def get_temporal_filter_for_query(
        self,
        query: str,
        date_field: str = "chunk_date"
    ) -> Optional[Filter]:
        """
        Método de conveniência: extrai datas e cria filtro.
        
        Args:
            query: Query do usuário
            date_field: Nome do campo de data no Weaviate
            
        Returns:
            Filter Weaviate ou None se não detectar datas
        """
        date_range = self.extract_date_range(query)
        if date_range:
            start_date, end_date = date_range
            return self.build_temporal_filter(start_date, end_date, date_field)
        return None

