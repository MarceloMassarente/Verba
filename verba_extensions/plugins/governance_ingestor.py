"""
Governance Ingestor

Reader dedicado para documentos de governança corporativa.
Baseado no UnifiedConsultingIngestor, mas com presets/metadados para:
- Órgão: conselho vs comitê
- Tipo documental: ata, pauta, preparatory_documents, bylaws, internal_rules
"""

import re
from typing import Dict, Any, List

from verba_extensions.readers.unified_consulting_ingestor import UnifiedConsultingIngestor
from goldenverba.components.document import Document
from goldenverba.server.types import FileConfig


COMMITTEE_RE = re.compile(r'\b(comit[eê]|comitê)\b', re.IGNORECASE)
BOARD_RE = re.compile(r'\bconselho(?:\s+de\s+administra(?:ç|c)ão)?\b', re.IGNORECASE)
DOC_TYPE_PATTERNS = {
    "ata": re.compile(r'\bata\b', re.IGNORECASE),
    "pauta": re.compile(r'\bpauta\b', re.IGNORECASE),
    "preparatory_documents": re.compile(
        r'\b(material(?:\s+de)?\s+apoio|apresenta(?:ç|c)(?:ão|ões)|anexo(?:s)?|'
        r'documento(?:s)?\s+de\s+prepara(?:ç|c)(?:ão|ões)|briefing)\b',
        re.IGNORECASE,
    ),
    "bylaws": re.compile(r'\b(estatuto(?:s)?|estatuto\s+social)\b', re.IGNORECASE),
    "internal_rules": re.compile(r'\b(regimento(?:s)?(?:\s+interno)?)\b', re.IGNORECASE),
}


class GovernanceIngestor(UnifiedConsultingIngestor):
    """Reader especializado em documentos de governança corporativa."""

    def __init__(self):
        super().__init__()
        self.name = "Governance Ingestor"
        self.description = (
            "Ingestor dedicado a governança (conselho/comitê). "
            "Classifica tipo documental (ata, pauta, preparatórios, estatutos e regimentos) "
            "e preserva metadados para chunking/auditoria."
        )

    async def load(self, config: dict, fileConfig: FileConfig) -> List[Document]:
        documents = await super().load(config, fileConfig)
        for document in documents:
            if not hasattr(document, "meta") or document.meta is None:
                document.meta = {}

            classification = self._classify_document(fileConfig.filename, document.content or "")
            document.meta["governance_mode"] = True
            document.meta.update(classification)
        return documents

    def _classify_document(self, filename: str, text: str) -> Dict[str, Any]:
        joined = f"{filename}\n{text[:4000]}"

        governance_body = "unknown"
        committee_match = COMMITTEE_RE.search(joined)
        board_match = BOARD_RE.search(joined)
        if committee_match and not board_match:
            governance_body = "comite"
        elif board_match and not committee_match:
            governance_body = "conselho"
        elif board_match and committee_match:
            governance_body = "comite" if committee_match.start() < board_match.start() else "conselho"

        governance_document_type = "other"
        for doc_type, pattern in DOC_TYPE_PATTERNS.items():
            if pattern.search(joined):
                governance_document_type = doc_type
                break

        return {
            "governance_body": governance_body,
            "governance_document_type": governance_document_type,
        }


def register():
    """Register Governance Ingestor plugin."""
    return {
        "name": "GovernanceIngestor",
        "version": "1.0.0",
        "description": "Reader dedicado a governança corporativa com classificação por órgão e tipo documental.",
        "readers": [GovernanceIngestor()],
        "compatible_verba_version": ">=2.0.0",
    }
