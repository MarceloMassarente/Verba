"""
GraphQL Builder para queries complexas no Weaviate
Focado em agregações complexas e queries multi-collection

Uso:
    from verba_extensions.utils.graphql_builder import GraphQLBuilder
    
    builder = GraphQLBuilder()
    
    # Agregação de entidades
    query = builder.build_entity_aggregation(
        collection_name="VERBA_Embedding_all_MiniLM_L6_v2",
        filters={"entities_local_ids": ["Q312", "Q2283"]}
    )
    
    results = await builder.execute(client, query)
"""

import json
from typing import Dict, Any, Optional, List
from wasabi import msg


class GraphQLBuilder:
    """
    Construtor de queries GraphQL para Weaviate v4.
    
    Focado em:
    - Agregações complexas (estatísticas, contagens, top occurrences)
    - Queries multi-collection
    - Queries com filtros aninhados extremos
    """
    
    def __init__(self):
        pass
    
    def build_entity_aggregation(
        self,
        collection_name: str,
        filters: Optional[Dict[str, Any]] = None,
        group_by: Optional[List[str]] = None,
        top_occurrences_limit: int = 10
    ) -> str:
        """
        Constrói query GraphQL para agregação de entidades.
        
        Args:
            collection_name: Nome da collection
            filters: Filtros opcionais (ex: {"entities_local_ids": ["Q312"]})
            group_by: Campos para agrupar (ex: ["doc_uuid", "chunk_date"])
            top_occurrences_limit: Limite para top occurrences
            
        Returns:
            Query GraphQL como string
            
        Exemplo:
            query = builder.build_entity_aggregation(
                collection_name="VERBA_Embedding_all_MiniLM_L6_v2",
                filters={"entities_local_ids": ["Q312", "Q2283"]},
                group_by=["doc_uuid"]
            )
        """
        where_clause = self._build_where_clause(filters) if filters else ""
        
        # Agregação básica
        if not group_by:
            query = f"""
{{
  Aggregate {{
    {collection_name}(
      {where_clause}
    ) {{
      entities_local_ids {{
        count
        topOccurrences(limit: {top_occurrences_limit}) {{
          occurs
          value
        }}
      }}
      section_entity_ids {{
        count
        topOccurrences(limit: {top_occurrences_limit}) {{
          occurs
          value
        }}
      }}
      chunk_date {{
        count
        date {{
          count
          minimum
          maximum
        }}
      }}
      doc_uuid {{
        count
        topOccurrences(limit: {top_occurrences_limit}) {{
          occurs
          value
        }}
      }}
    }}
  }}
}}
"""
        else:
            # Agregação com groupBy
            group_by_fields = self._build_group_by_fields(group_by)
            query = f"""
{{
  Aggregate {{
    {collection_name}(
      {where_clause}
    ) {{
      groupedBy {{
        path: ["{group_by[0]}"]
        groups {{
          count
          {group_by_fields}
          entities_local_ids {{
            count
            topOccurrences(limit: {top_occurrences_limit}) {{
              occurs
              value
            }}
          }}
        }}
      }}
    }}
  }}
}}
"""
        
        return query.strip()
    
    def build_document_stats_query(
        self,
        collection_name: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Constrói query GraphQL para estatísticas por documento.
        
        Args:
            collection_name: Nome da collection
            filters: Filtros opcionais
            
        Returns:
            Query GraphQL como string
            
        Exemplo:
            query = builder.build_document_stats_query(
                collection_name="VERBA_Embedding_all_MiniLM_L6_v2"
            )
            # Retorna: estatísticas agrupadas por doc_uuid
        """
        where_clause = self._build_where_clause(filters) if filters else ""
        
        query = f"""
{{
  Aggregate {{
    {collection_name}(
      {where_clause}
    ) {{
      groupedBy {{
        path: ["doc_uuid"]
        groups {{
          count
          entities_local_ids {{
            count
            topOccurrences(limit: 5) {{
              occurs
              value
            }}
          }}
          chunk_date {{
            date {{
              minimum
              maximum
            }}
          }}
        }}
      }}
    }}
  }}
}}
"""
        return query.strip()
    
    def build_multi_collection_query(
        self,
        queries: List[Dict[str, Any]]
    ) -> str:
        """
        Constrói query GraphQL com múltiplas collections em paralelo.
        
        Args:
            queries: Lista de queries, cada uma com:
                {
                    "alias": "documents",  # Nome para resultado
                    "collection": "VERBA_DOCUMENTS",
                    "limit": 10,
                    "filters": {...},
                    "fields": ["title", "uuid"]
                }
                
        Returns:
            Query GraphQL como string
            
        Exemplo:
            query = builder.build_multi_collection_query([
                {
                    "alias": "documents",
                    "collection": "VERBA_DOCUMENTS",
                    "limit": 10,
                    "fields": ["title", "uuid"]
                },
                {
                    "alias": "chunks",
                    "collection": "VERBA_Embedding_all_MiniLM_L6_v2",
                    "limit": 50,
                    "filters": {"doc_uuid": ["doc-1"]},
                    "fields": ["content", "entities_local_ids"]
                }
            ])
        """
        query_parts = []
        
        for q in queries:
            alias = q.get("alias", q["collection"])
            collection = q["collection"]
            limit = q.get("limit", 10)
            fields = q.get("fields", ["*"])
            filters = q.get("filters")
            
            where_clause = self._build_where_clause(filters) if filters else ""
            fields_str = self._build_fields(fields)
            
            query_parts.append(f"""
  {alias}: Get {{
    {collection}(
      limit: {limit}
      {where_clause}
    ) {{
      {fields_str}
      _additional {{
        id
      }}
    }}
  }}
""")
        
        query = f"""
{{
{''.join(query_parts)}
}}
"""
        return query.strip()
    
    def build_complex_filter_query(
        self,
        collection_name: str,
        filter_logic: Dict[str, Any],
        limit: int = 50,
        fields: Optional[List[str]] = None
    ) -> str:
        """
        Constrói query GraphQL com filtros extremamente complexos.
        
        Args:
            collection_name: Nome da collection
            filter_logic: Lógica de filtros aninhada:
                {
                    "operator": "And",
                    "operands": [
                        {
                            "operator": "Or",
                            "operands": [
                                {"path": ["entities_local_ids"], "operator": "ContainsAny", "valueText": ["Q312"]},
                                {"path": ["entities_local_ids"], "operator": "ContainsAny", "valueText": ["Q2283"]}
                            ]
                        },
                        {"path": ["chunk_date"], "operator": "GreaterThanEqual", "valueDate": "2024-01-01T00:00:00Z"}
                    ]
                }
            limit: Limite de resultados
            fields: Campos a retornar
            
        Returns:
            Query GraphQL como string
        """
        where_clause = self._build_complex_where_clause(filter_logic)
        fields_str = self._build_fields(fields or ["content", "entities_local_ids", "chunk_date"])
        
        query = f"""
{{
  Get {{
    {collection_name}(
      limit: {limit}
      where: {where_clause}
    ) {{
      {fields_str}
      _additional {{
        id
        distance
        explainScore
      }}
    }}
  }}
}}
"""
        return query.strip()
    
    def _build_where_clause(self, filters: Dict[str, Any]) -> str:
        """Constrói cláusula where simples"""
        if not filters:
            return ""
        
        conditions = []
        
        for prop, value in filters.items():
            if isinstance(value, list):
                # ContainsAny
                values_str = ", ".join([f'"{v}"' for v in value])
                conditions.append(f"""
      path: ["{prop}"]
      operator: ContainsAny
      valueText: [{values_str}]
""")
            elif isinstance(value, str):
                # Equal
                conditions.append(f"""
      path: ["{prop}"]
      operator: Equal
      valueText: "{value}"
""")
            elif isinstance(value, (int, float)):
                # Equal (number)
                conditions.append(f"""
      path: ["{prop}"]
      operator: Equal
      valueNumber: {value}
""")
        
        if len(conditions) == 1:
            return f"where: {{\n{conditions[0]}    }}"
        else:
            # Multiple conditions - combine with And
            conditions_str = "".join([f"        {c}" for c in conditions])
            return f"""where: {{
      operator: And
      operands: [
{conditions_str}      ]
    }}"""
    
    def _build_complex_where_clause(self, filter_logic: Dict[str, Any]) -> str:
        """Constrói cláusula where complexa (aninhada)"""
        operator = filter_logic.get("operator", "And")
        operands = filter_logic.get("operands", [])
        
        if not operands:
            return "{}"
        
        operand_strs = []
        for operand in operands:
            if "operands" in operand:
                # Nested operator
                nested_clause = self._build_complex_where_clause(operand)
                operand_strs.append(f"      {nested_clause}")
            else:
                # Simple condition
                path = operand.get("path", [])
                op = operand.get("operator", "Equal")
                value_type = operand.get("valueType", "valueText")
                value = operand.get(value_type, operand.get("value", ""))
                
                if isinstance(path, list):
                    path_str = ", ".join([f'"{p}"' for p in path])
                else:
                    path_str = f'"{path}"'
                
                if value_type == "valueDate":
                    value_str = f'"{value}"'
                elif value_type == "valueNumber":
                    value_str = str(value)
                elif isinstance(value, list):
                    values_str = ", ".join([f'"{v}"' for v in value])
                    value_str = f"[{values_str}]"
                else:
                    value_str = f'"{value}"'
                
                operand_strs.append(f"""      {{
        path: [{path_str}]
        operator: {op}
        {value_type}: {value_str}
      }}""")
        
        operands_str = ",\n".join(operand_strs)
        
        return f"""{{
      operator: {operator}
      operands: [
{operands_str}
      ]
    }}"""
    
    def _build_fields(self, fields: List[str]) -> str:
        """Constrói lista de campos"""
        if "*" in fields:
            return "content\n      entities_local_ids\n      chunk_date\n      doc_uuid"
        
        return "\n      ".join(fields)
    
    def _build_group_by_fields(self, group_by: List[str]) -> str:
        """Constrói campos para groupBy aninhado"""
        if len(group_by) <= 1:
            return ""
        
        nested_groups = []
        for i, field in enumerate(group_by[1:], 1):
            nested_groups.append(f"""
          groupedBy {{
            path: ["{field}"]
            groups {{
              count
            }}
          }}""")
        
        return "".join(nested_groups)
    
    async def execute(
        self,
        client,
        query: str,
        collection_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executa query GraphQL no Weaviate.
        
        Args:
            client: Cliente Weaviate
            query: Query GraphQL como string
            collection_name: Nome da collection (opcional, para validação)
            
        Returns:
            Resultado da query como dict
            
        Raises:
            Exception: Se query falhar
        """
        try:
            # Weaviate v4 usa client.query.raw() para GraphQL
            if hasattr(client, "query"):
                result = await client.query.raw(query)
                return result
            else:
                # Fallback: tentar método direto
                result = await client.graphql.query(query)
                return result
                
        except Exception as e:
            msg.warn(f"Erro ao executar query GraphQL: {str(e)}")
            msg.warn(f"Query: {query[:200]}...")
            raise
    
    def parse_aggregation_results(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parseia resultados de agregação GraphQL para formato mais útil.
        
        Args:
            results: Resultado da query GraphQL
            
        Returns:
            Dict formatado com estatísticas
        """
        try:
            # Extrair dados do resultado GraphQL
            aggregate = results.get("data", {}).get("Aggregate", {})
            
            if not aggregate:
                return {"error": "Nenhum resultado de agregação encontrado"}
            
            # Primeira collection (assumimos que há apenas uma)
            collection_name = list(aggregate.keys())[0]
            collection_data = aggregate[collection_name]
            
            # Verificar se é groupedBy ou agregação simples
            if "groupedBy" in collection_data:
                # Agregação com groupBy
                groups = collection_data["groupedBy"]["groups"]
                return {
                    "type": "grouped",
                    "groups": groups,
                    "total_groups": len(groups)
                }
            else:
                # Agregação simples
                return {
                    "type": "simple",
                    "data": collection_data
                }
                
        except Exception as e:
            msg.warn(f"Erro ao parsear resultados: {str(e)}")
            return {"error": str(e), "raw_results": results}

