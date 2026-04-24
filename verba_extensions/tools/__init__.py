"""
Agent-oriented document search and read tools (HTTP-backed).

Reuses VerbaManager.retrieve_chunks and WeaviateManager chunk/document access.
"""

from verba_extensions.tools.document_reader import (
    search_documents_grouped,
    read_document_controlled,
    read_context_around_chunk,
)

__all__ = [
    "search_documents_grouped",
    "read_document_controlled",
    "read_context_around_chunk",
]
