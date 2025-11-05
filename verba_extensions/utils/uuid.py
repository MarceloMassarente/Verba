"""
Utilitários para geração de UUIDs determinísticos.

Garante idempotência e evita duplicidade ao reexecutar ETL ou fazer re-uploads.
Adaptado do RAG2 para Verba.

Features:
- UUID v5 baseado em namespace + identificador
- Determinístico: mesmo input = mesmo UUID
- Idempotência garantida

Uso:
    from verba_extensions.utils.uuid import (
        generate_doc_uuid,
        generate_chunk_uuid,
        generate_chunk_uuid_by_type
    )
    
    # UUID para documento
    doc_uuid = generate_doc_uuid(
        source_url=doc.meta.get("source_url"),
        public_identifier=doc.meta.get("public_id"),
        title=doc.title
    )
    
    # UUID para chunk
    chunk_uuid = generate_chunk_uuid(
        doc_uuid=doc_uuid,
        chunk_id=f"{doc_uuid}:{chunk.chunk_id}"
    )
    
    # UUID para chunk com tipo (múltiplos vetores)
    role_uuid = generate_chunk_uuid_by_type(
        doc_uuid=doc_uuid,
        vec_type="role",
        chunk_id=f"{doc_uuid}:{chunk.chunk_id}"
    )

Benefícios:
- Re-uploads não criam duplicatas
- Upsert seguro (mesmo documento sempre tem mesmo UUID)
- Idempotência garantida

Documentação completa: verba_extensions/utils/README.md
"""
import uuid
from typing import Optional


def generate_doc_uuid(source_url: Optional[str] = None, public_identifier: Optional[str] = None, title: Optional[str] = None) -> str:
    """
    Gera UUID determinístico para um documento.
    
    Args:
        source_url: URL completa do documento (prioridade 1)
        public_identifier: Identificador público (slug) (prioridade 2)
        title: Título do documento (fallback)
    
    Returns:
        UUID v5 determinístico (baseado em namespace URL + identificador)
    """
    # Namespace URL para UUID v5
    NS_URL = uuid.UUID('6ba7b811-9dad-11d1-80b4-00c04fd430c8')
    
    # Prioriza source_url, depois public_identifier, depois title
    identifier = source_url or public_identifier or title or ""
    
    if not identifier:
        raise ValueError("source_url, public_identifier ou title deve ser fornecido")
    
    # Normaliza para garantir determinismo
    identifier = identifier.strip().lower()
    
    return str(uuid.uuid5(NS_URL, identifier))


def generate_chunk_uuid(doc_uuid: str, chunk_id: str) -> str:
    """
    Gera UUID determinístico para um chunk baseado no doc_uuid e chunk_id.
    
    Args:
        doc_uuid: UUID do documento pai
        chunk_id: Identificador composto do chunk (ex: "doc_id:parent_type:parent_id:idx")
    
    Returns:
        UUID v5 determinístico
    """
    # Namespace UUID para chunks (poderia ser outro namespace, mas reutilizamos NS_URL)
    NS_URL = uuid.UUID('6ba7b811-9dad-11d1-80b4-00c04fd430c8')
    
    # Combina doc_uuid + chunk_id para garantir unicidade
    combined = f"{doc_uuid}:{chunk_id}"
    
    # Normaliza
    combined = combined.strip().lower()
    
    return str(uuid.uuid5(NS_URL, combined))


def generate_chunk_uuid_by_type(doc_uuid: str, vec_type: str, chunk_id: str) -> str:
    """
    Gera UUID determinístico para um chunk com tipo específico (role/domain).
    Usado quando um chunk precisa de múltiplos vetores.
    
    Args:
        doc_uuid: UUID do documento pai
        vec_type: Tipo do vetor ("role", "domain", "bio", etc.)
        chunk_id: Identificador composto do chunk
    
    Returns:
        UUID v5 determinístico
    """
    # Namespace UUID para chunks com tipo
    NS_URL = uuid.UUID('6ba7b811-9dad-11d1-80b4-00c04fd430c8')
    
    # Combina doc_uuid + vec_type + chunk_id para garantir unicidade
    combined = f"{doc_uuid}:{vec_type}:{chunk_id}"
    
    # Normaliza
    combined = combined.strip().lower()
    
    return str(uuid.uuid5(NS_URL, combined))

