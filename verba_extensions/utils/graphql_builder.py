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
        top_occurrences_limit: int = 10,
        entity_source: str = "local"
    ) -> str:
        """
        Constrói query GraphQL para agregação de entidades.
        
        OTIMIZAÇÃO FASE 2: Parametrizado entity_source para remover redundância
        - entity_source="local": apenas entities_local_ids (pré-chunking ETL)
        - entity_source="section": apenas section_entity_ids (pós-chunking ETL)
        - entity_source="both": ambas (útil para análise completa)
        
        Args:
            collection_name: Nome da collection
            filters: Filtros opcionais (ex: {"entities_local_ids": ["Q312"]})
            group_by: Campos para agrupar (ex: ["doc_uuid", "chunk_date"])
            top_occurrences_limit: Limite para top occurrences
            entity_source: Qual fonte de entidades usar ("local", "section", "both")
            
        Returns:
            Query GraphQL como string
            
        Exemplo:
            query = builder.build_entity_aggregation(
                collection_name="VERBA_Embedding_all_MiniLM_L6_v2",
                filters={"entities_local_ids": ["Q312", "Q2283"]},
                group_by=["doc_uuid"],
                entity_source="local"  # Usar apenas pré-chunking
            )
        """
        where_clause = self._build_where_clause(filters) if filters else ""
        
        # Validar entity_source
        if entity_source not in ("local", "section", "both"):
            entity_source = "local"
        
        # Construir campos de entidades baseado em entity_source
        entity_fields = ""
        if entity_source == "local":
            entity_fields = f"""entities_local_ids {{
        count
        topOccurrences(limit: {top_occurrences_limit}) {{
          occurs
          value
        }}
      }}"""
        elif entity_source == "section":
            entity_fields = f"""section_entity_ids {{
        count
        topOccurrences(limit: {top_occurrences_limit}) {{
          occurs
          value
        }}
      }}"""
        else:  # "both"
            entity_fields = f"""entities_local_ids {{
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
      }}"""
        
        # Agregação básica
        if not group_by:
            query = f"""
{{
  Aggregate {{
    {collection_name}(
      {where_clause}
    ) {{
      {entity_fields}
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
          {entity_fields}
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
        
        OTIMIZAÇÃO FASE 1: Auto-detecta tipo de query e aplica parsing específico
        - Entity frequency → chamada parse_entity_frequency()
        - Document stats → chamada parse_document_stats()
        - Genérico → retorna estrutura simples
        
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
            
            # OTIMIZAÇÃO FASE 1: Auto-detectar tipo de query e aplicar parsing específico
            if "groupedBy" in collection_data:
                groups = collection_data["groupedBy"]["groups"]
                
                # Detectar se é entity frequency (tem entities_local_ids nos groups)
                if groups and "entities_local_ids" in groups[0]:
                    return self.parse_entity_frequency(results)
                
                # Detectar se é document stats (agrupado por doc_uuid)
                group_by = collection_data.get("groupedBy", {}).get("path", [])
                if group_by and group_by[0] == "doc_uuid":
                    return self.parse_document_stats(results)
                
                # Genérico: agregação com groupBy
                return {
                    "type": "grouped",
                    "groups": groups,
                    "total_groups": len(groups),
                    "statistics": {"type": "grouped"}
                }
            else:
                # Agregação simples
                return {
                    "type": "simple",
                    "data": collection_data,
                    "statistics": {"type": "simple"}
                }
                
        except Exception as e:
            msg.warn(f"Erro ao parsear resultados: {str(e)}")
            return {"error": str(e), "raw_results": results}
    
    def parse_entity_frequency(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        OTIMIZAÇÃO FASE 1: Parser otimizado para entity frequency queries.
        
        Transforma estrutura aninhada do GraphQL em formato plano e acessível.
        
        Args:
            results: Resultado GraphQL com entities_local_ids
            
        Returns:
            {
                "type": "entity_frequency",
                "entities": [
                    {"id": "Q312", "count": 60, "percentage": 0.58},
                    {"id": "Q2283", "count": 40, "percentage": 0.39}
                ],
                "total": 103,
                "unique_entities": 2
            }
        """
        try:
            aggregate = results.get("data", {}).get("Aggregate", {})
            collection_name = list(aggregate.keys())[0]
            collection_data = aggregate[collection_name]
            
            # Extrair dados planos
            entities = []
            total_count = 0
            
            # Se é groupedBy, pegar primeiro group (ou agregar todos)
            if "groupedBy" in collection_data:
                groups = collection_data["groupedBy"]["groups"]
                if groups and "entities_local_ids" in groups[0]:
                    entity_data = groups[0]["entities_local_ids"]
                else:
                    return {"error": "Formato inesperado para entity frequency"}
            else:
                # Agregação simples
                entity_data = collection_data.get("entities_local_ids", {})
            
            # Processar topOccurrences
            if "topOccurrences" in entity_data:
                for occ in entity_data["topOccurrences"]:
                    count = occ.get("occurs", 0)
                    entity_id = occ.get("value", "unknown")
                    total_count += count
                    entities.append({
                        "id": entity_id,
                        "count": count
                    })
            
            # Calcular percentages
            for entity in entities:
                entity["percentage"] = round(entity["count"] / total_count, 4) if total_count > 0 else 0.0
            
            # Ordenar por frequência (descendente)
            entities.sort(key=lambda x: x["count"], reverse=True)
            
            return {
                "type": "entity_frequency",
                "entities": entities,
                "total": total_count,
                "unique_entities": len(entities),
                "statistics": {
                    "top_entity": entities[0] if entities else None,
                    "concentration": round(entities[0]["count"] / total_count, 4) if entities and total_count > 0 else 0.0
                }
            }
            
        except Exception as e:
            msg.warn(f"Erro ao parsear entity frequency: {str(e)}")
            return {"error": str(e), "type": "entity_frequency"}
    
    def parse_document_stats(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        OTIMIZAÇÃO FASE 1: Parser otimizado para document statistics queries.
        
        Transforma resultados groupedBy em estatísticas por documento.
        
        Args:
            results: Resultado GraphQL agrupado por doc_uuid
            
        Returns:
            {
                "type": "document_stats",
                "documents": [
                    {
                        "doc_uuid": "...",
                        "chunk_count": 45,
                        "entity_count": 120,
                        "top_entities": [...],
                        "date_range": {"min": "...", "max": "..."}
                    }
                ],
                "total_documents": 3,
                "statistics": {...}
            }
        """
        try:
            aggregate = results.get("data", {}).get("Aggregate", {})
            collection_name = list(aggregate.keys())[0]
            collection_data = aggregate[collection_name]
            
            documents = []
            total_chunks = 0
            
            if "groupedBy" in collection_data:
                groups = collection_data["groupedBy"]["groups"]
                
                for group in groups:
                    # Extrair contagem de chunks deste documento
                    chunk_count = group.get("count", 0)
                    total_chunks += chunk_count
                    
                    # Extrair entidades
                    entity_data = group.get("entities_local_ids", {})
                    entity_count = entity_data.get("count", 0)
                    top_entities = []
                    
                    if "topOccurrences" in entity_data:
                        top_entities = [
                            {"id": occ.get("value"), "count": occ.get("occurs")}
                            for occ in entity_data["topOccurrences"][:5]  # Top 5
                        ]
                    
                    # Extrair date range
                    date_range = {"min": None, "max": None}
                    if "chunk_date" in group:
                        date_data = group["chunk_date"].get("date", {})
                        date_range = {
                            "min": date_data.get("minimum"),
                            "max": date_data.get("maximum")
                        }
                    
                    documents.append({
                        "chunk_count": chunk_count,
                        "entity_count": entity_count,
                        "top_entities": top_entities,
                        "date_range": date_range
                    })
            
            return {
                "type": "document_stats",
                "documents": documents,
                "total_documents": len(documents),
                "total_chunks": total_chunks,
                "statistics": {
                    "avg_chunks_per_doc": round(total_chunks / len(documents), 2) if documents else 0,
                    "avg_entities_per_doc": round(sum(d.get("entity_count", 0) for d in documents) / len(documents), 2) if documents else 0
                }
            }
            
        except Exception as e:
            msg.warn(f"Erro ao parsear document stats: {str(e)}")
            return {"error": str(e), "type": "document_stats"}
    
    def aggregate_entity_frequencies(
        self,
        entities_local: Optional[Dict[str, int]] = None,
        entities_section: Optional[Dict[str, int]] = None,
        weight_local: float = 1.0,
        weight_section: float = 0.5
    ) -> Dict[str, Dict[str, Any]]:
        """
        OTIMIZAÇÃO FASE 2: Agregar frequências de entidades de múltiplas fontes.
        
        Combina entities_local_ids e section_entity_ids com pesos para dar
        uma visão única e unificada das entidades.
        
        Args:
            entities_local: Dict {entity_id: count} de entities_local_ids
            entities_section: Dict {entity_id: count} de section_entity_ids
            weight_local: Peso para local entities (default: 1.0)
            weight_section: Peso para section entities (default: 0.5)
            
        Returns:
            {
                "Q312": {
                    "local": 60,
                    "section": 5,
                    "total": 62.5,
                    "percentage": 0.61,
                    "source_primary": "local"
                },
                ...
            }
            
        Exemplo:
            entities_local = {"Q312": 60, "Q2283": 40}
            entities_section = {"Q312": 5}
            
            aggregated = builder.aggregate_entity_frequencies(
                entities_local=entities_local,
                entities_section=entities_section
            )
            # Retorna: {"Q312": {local: 60, section: 5, total: 62.5, ...}}
        """
        aggregated = {}
        
        # Processar entidades locais
        if entities_local:
            for entity_id, count in entities_local.items():
                if entity_id not in aggregated:
                    aggregated[entity_id] = {"local": 0, "section": 0}
                aggregated[entity_id]["local"] = count * weight_local
        
        # Processar entidades de seção
        if entities_section:
            for entity_id, count in entities_section.items():
                if entity_id not in aggregated:
                    aggregated[entity_id] = {"local": 0, "section": 0}
                aggregated[entity_id]["section"] = count * weight_section
        
        # Calcular totais e percentages
        total_sum = sum(
            e["local"] + e["section"] 
            for e in aggregated.values()
        )
        
        for entity_id, data in aggregated.items():
            data["total"] = data["local"] + data["section"]
            data["percentage"] = round(data["total"] / total_sum, 4) if total_sum > 0 else 0.0
            
            # Definir fonte primária
            if data["local"] > 0 and data["local"] >= data["section"]:
                data["source_primary"] = "local"
            elif data["section"] > 0:
                data["source_primary"] = "section"
            else:
                data["source_primary"] = "unknown"
        
        # Ordenar por total (descendente)
        sorted_entities = dict(sorted(
            aggregated.items(),
            key=lambda x: x[1]["total"],
            reverse=True
        ))
        
        return sorted_entities

