"""
GraphQL Builder
Constrói queries GraphQL dinâmicas para Weaviate

Aprende do RAG2: queries GraphQL complexas com suporte a named vectors, filtros e hybrid search
"""

from typing import Dict, Any, List, Optional
import json


class GraphQLBuilder:
    """
    Constrói queries GraphQL para Weaviate.
    
    Suporta:
    - Hybrid search (BM25 + vector)
    - Named vectors (targetVector)
    - Filtros complexos (where clause)
    - Multi-vector search (via targetVectors)
    """
    
    def build_query(
        self,
        class_name: str,
        query: str,
        vector: Optional[List[float]] = None,
        target_vector: Optional[str] = None,
        filters: Optional[Any] = None,  # Weaviate Filter object
        alpha: float = 0.5,
        limit: int = 50,
        return_properties: Optional[List[str]] = None
    ) -> str:
        """
        Constrói query GraphQL.
        
        Args:
            class_name: Nome da classe Weaviate
            query: Query do usuário (string, para BM25)
            vector: Vetor pré-calculado (para nearVector)
            target_vector: Nome do vetor nomeado (ex: "concept_vec")
            filters: Filtros Weaviate (Filter object)
            alpha: Alpha para busca híbrida (0.0 = só BM25, 1.0 = só vector)
            limit: Limite de resultados
            return_properties: Propriedades a retornar
        
        Returns:
            Query GraphQL como string
        """
        # Construir where clause
        where_clause = self._build_where_clause(filters)
        
        # Construir hybrid search
        hybrid_clause = self._build_hybrid_clause(query, vector, target_vector, alpha)
        
        # Campos a retornar
        fields = return_properties or self._get_default_fields(class_name)
        
        # Montar query GraphQL
        graphql = self._format_graphql(
            class_name=class_name,
            hybrid_clause=hybrid_clause,
            where_clause=where_clause,
            fields=fields,
            limit=limit,
            target_vector=target_vector if vector else None  # Só usar target_vector se há vector
        )
        
        return graphql
    
    def _build_where_clause(self, filters: Optional[Any]) -> Optional[str]:
        """
        Constrói where clause GraphQL a partir de filtros Weaviate.
        
        Args:
            filters: Filter object do Weaviate (ou None)
        
        Returns:
            String com where clause GraphQL ou None
        """
        if filters is None:
            return None
        
        # Converter Filter object para GraphQL where clause
        # Isso requer serializar o Filter para formato GraphQL
        try:
            # Tentar obter representação GraphQL do Filter
            if hasattr(filters, 'to_dict'):
                filter_dict = filters.to_dict()
            elif hasattr(filters, '__dict__'):
                filter_dict = filters.__dict__
            else:
                # Fallback: tentar usar diretamente
                filter_dict = filters
            
            # Converter para formato GraphQL
            where_str = self._filter_dict_to_graphql(filter_dict)
            return where_str
        except Exception as e:
            # Se falhar, retornar None (sem filtro)
            return None
    
    def _filter_dict_to_graphql(self, filter_dict: Dict[str, Any]) -> str:
        """
        Converte dict de filtro para string GraphQL.
        
        Args:
            filter_dict: Dict com estrutura de filtro
        
        Returns:
            String GraphQL where clause
        """
        # Implementação simplificada - pode ser expandida conforme necessário
        # Por enquanto, retorna formato básico
        if not filter_dict:
            return None
        
        # Construir where clause recursivamente
        if "path" in filter_dict:
            # Filtro simples
            path = filter_dict["path"]
            operator = filter_dict.get("operator", "Equal")
            value = filter_dict.get("value")
            
            # Determinar tipo de valor
            if isinstance(value, bool):
                value_str = f'valueBoolean: {str(value).lower()}'
            elif isinstance(value, list):
                if all(isinstance(v, str) for v in value):
                    value_str = f'valueStringArray: {json.dumps(value)}'
                else:
                    value_str = f'valueTextArray: {json.dumps(value)}'
            elif isinstance(value, (int, float)):
                value_str = f'valueNumber: {value}'
            else:
                value_str = f'valueString: "{value}"'
            
            return f'where: {{path: ["{path}"], operator: {operator}, {value_str}}}'
        
        elif "operands" in filter_dict:
            # Filtro composto (AND/OR)
            operator = filter_dict.get("operator", "And")
            operands = filter_dict["operands"]
            
            operand_strs = []
            for operand in operands:
                if isinstance(operand, dict):
                    operand_str = self._filter_dict_to_graphql(operand)
                    if operand_str:
                        operand_strs.append(operand_str)
            
            if not operand_strs:
                return None
            
            if len(operand_strs) == 1:
                return operand_strs[0]
            
            return f'where: {{operator: {operator}, operands: [{", ".join(operand_strs)}]}}'
        
        return None
    
    def _build_hybrid_clause(
        self,
        query: str,
        vector: Optional[List[float]],
        target_vector: Optional[str],
        alpha: float
    ) -> str:
        """
        Constrói clause de busca híbrida.
        
        Args:
            query: Query do usuário (string)
            vector: Vetor pré-calculado
            target_vector: Nome do vetor nomeado
            alpha: Alpha para busca híbrida
        
        Returns:
            String com hybrid clause GraphQL
        """
        if vector is not None:
            # Hybrid search com vetor
            vector_str = json.dumps(vector)
            hybrid_parts = [
                f'hybrid: {{query: "{query}", alpha: {alpha}, vector: {vector_str}'
            ]
            
            if target_vector:
                hybrid_parts[0] += f', targetVector: "{target_vector}"'
            
            hybrid_parts[0] += '}'
            return hybrid_parts[0]
        else:
            # Apenas BM25 (sem vetor)
            return f'bm25: {{query: "{query}"}}'
    
    def _get_default_fields(self, class_name: str) -> List[str]:
        """
        Retorna campos padrão para cada classe.
        
        Args:
            class_name: Nome da classe Weaviate
        
        Returns:
            Lista de nomes de campos
        """
        # Campos padrão para collections de embedding do Verba
        if "VERBA_Embedding" in class_name or "Embedding" in class_name:
            return [
                "text",
                "doc_uuid",
                "chunk_id",
                "chunk_date",
                "chunk_lang",
                "frameworks",
                "companies",
                "sectors",
                "concept_text",
                "sector_text",
                "company_text"
            ]
        elif class_name == "VERBA_DOCUMENTS":
            return [
                "title",
                "doc_uuid",
                "labels",
                "chunk_date"
            ]
        else:
            # Fallback genérico
            return ["text", "doc_uuid"]
    
    def _format_graphql(
        self,
        class_name: str,
        hybrid_clause: str,
        where_clause: Optional[str],
        fields: List[str],
        limit: int,
        target_vector: Optional[str] = None
    ) -> str:
        """
        Formata query GraphQL completa.
        
        Args:
            class_name: Nome da classe
            hybrid_clause: Clause de busca híbrida
            where_clause: Clause where (opcional)
            fields: Campos a retornar
            limit: Limite de resultados
            target_vector: Nome do vetor nomeado (opcional)
        
        Returns:
            Query GraphQL formatada
        """
        # Construir campos
        fields_str = "\n        ".join(fields)
        
        # Construir query
        query_parts = [f'Get {{', f'  {class_name}(']
        
        # Adicionar hybrid/bm25
        query_parts.append(f'    {hybrid_clause}')
        
        # Adicionar where se houver
        if where_clause:
            query_parts.append(f'    {where_clause}')
        
        # Adicionar limit
        query_parts.append(f'    limit: {limit}')
        
        # Fechar parâmetros
        query_parts.append('  ) {')
        
        # Adicionar campos
        query_parts.append(f'    {fields_str}')
        
        # Adicionar metadata
        query_parts.append('    _additional {')
        query_parts.append('      id')
        query_parts.append('      distance')
        query_parts.append('    }')
        
        # Fechar query
        query_parts.append('  }')
        query_parts.append('}')
        
        return '\n'.join(query_parts)


def get_graphql_builder() -> GraphQLBuilder:
    """
    Factory function para obter instância singleton do GraphQLBuilder.
    
    Returns:
        Instância de GraphQLBuilder
    """
    if not hasattr(get_graphql_builder, '_instance'):
        get_graphql_builder._instance = GraphQLBuilder()
    return get_graphql_builder._instance
