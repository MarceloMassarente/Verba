from typing import Literal, Optional, List, Any
from pydantic import BaseModel, Field, field_validator
from enum import Enum

# Valid named vectors for search (Weaviate targetVector) -- must match retriever/QueryBuilder
TargetVectorName = Literal["default", "concept_vec", "company_vec", "sector_vec"]
EntityFilterMode = Literal["strict", "boost", "adaptive", "hybrid"]
TwoPhaseMode = Literal["auto", "enabled", "disabled"]
TwoPhaseFilterLevel = Literal["chunk", "document"]


class AdvancedSearchOptions(BaseModel):
    """
    Optional API controls for EntityAware search. Passed only to Verba HTTP API;
    does not expose Weaviate connection details.
    """

    target_vectors: Optional[List[TargetVectorName]] = None
    enable_multi_vector: Optional[bool] = None
    two_phase_mode: Optional[TwoPhaseMode] = None
    two_phase_filter_level: Optional[TwoPhaseFilterLevel] = None
    entity_filter_mode: Optional[EntityFilterMode] = None
    alpha: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    enable_query_expansion: Optional[bool] = None
    enable_dynamic_alpha: Optional[bool] = None
    enable_relative_score_fusion: Optional[bool] = None
    reranker_top_k: Optional[int] = Field(default=None, ge=0)
    debug: Optional[bool] = None

    @field_validator("target_vectors")
    @classmethod
    def _dedupe_target_vectors(
        cls, v: Optional[List[str]]
    ) -> Optional[List[str]]:
        if v is None or not v:
            return v
        seen: set[str] = set()
        out: list[str] = []
        for x in v:
            if x not in seen:
                seen.add(x)
                out.append(x)
        return out


class Credentials(BaseModel):
    deployment: Literal["Weaviate", "Docker", "Local", "Custom"]
    url: str
    key: str


class ConversationItem(BaseModel):
    type: str
    content: str


class ChunksPayload(BaseModel):
    uuid: str
    page: int
    pageSize: int
    credentials: Credentials


class GetChunkPayload(BaseModel):
    uuid: str
    embedder: str
    credentials: Credentials


class GetVectorPayload(BaseModel):
    uuid: str
    showAll: bool
    credentials: Credentials


class ConnectPayload(BaseModel):
    credentials: Credentials
    port: str


class DataBatchPayload(BaseModel):
    chunk: str
    isLastChunk: bool
    total: int
    fileID: str
    order: int
    credentials: Credentials


class LoadPayload(BaseModel):
    reader: str
    chunker: str
    embedder: str
    fileBytes: list[str]
    fileNames: list[str]
    filePath: str
    document_type: str
    chunkUnits: int
    chunkOverlap: int


class ImportPayload(BaseModel):
    data: list
    textValues: list[str]
    config: dict


class GetComponentPayload(BaseModel):
    component: str


class SetComponentPayload(BaseModel):
    component: str
    selected_component: str


# Import


class FileStatus(str, Enum):
    READY = "READY"
    CREATE_NEW = "CREATE_NEW"
    STARTING = "STARTING"
    LOADING = "LOADING"
    CHUNKING = "CHUNKING"
    EMBEDDING = "EMBEDDING"
    INGESTING = "INGESTING"
    NER = "NER"
    EXTRACTION = "EXTRACTION"
    SUMMARIZING = "SUMMARIZING"
    DONE = "DONE"
    ERROR = "ERROR"


class ConfigSetting(BaseModel):
    type: str
    value: str | int | bool | float
    description: str
    values: list[str]


class RAGComponentConfig(BaseModel):
    name: str
    variables: list[str]
    library: list[str]
    description: str
    config: dict[str, ConfigSetting]
    type: str
    available: bool


class RAGComponentClass(BaseModel):
    selected: str
    components: dict[str, RAGComponentConfig]


class RAGConfig(BaseModel):
    Reader: RAGComponentClass
    Chunker: RAGComponentClass
    Embedder: RAGComponentClass
    Retriever: RAGComponentClass
    Generator: RAGComponentClass
    Advanced: Optional[dict[str, Any]] = None


class StatusReport(BaseModel):
    fileID: str
    status: str
    message: str
    took: float


class CreateNewDocument(BaseModel):
    new_file_id: str
    filename: str
    original_file_id: str


class FileConfig(BaseModel):
    fileID: str
    filename: str
    isURL: bool
    overwrite: bool
    extension: str
    source: str
    content: str
    labels: list[str]
    rag_config: dict[str, Any]
    file_size: int
    status: FileStatus
    metadata: str
    status_report: dict


class ImportStreamPayload(BaseModel):
    fileMap: dict[str, FileConfig]


class VerbaConfig(BaseModel):
    RAG: dict[str, Any]
    SETTING: dict


class DocumentFilter(BaseModel):
    title: str
    uuid: str


class GetSuggestionsPayload(BaseModel):
    query: str
    limit: int
    credentials: Credentials


class DeleteSuggestionPayload(BaseModel):
    uuid: str
    credentials: Credentials


class GetAllSuggestionsPayload(BaseModel):
    page: int
    pageSize: int
    credentials: Credentials


class QueryPayload(BaseModel):
    """
    Payload para endpoint /api/query.
    
    Attributes:
        query: A query string to search for
        RAG: RAG configuration to use for the query
        labels: Labels to filter documents
        documentFilter: Document filters to apply
        credentials: Weaviate connection credentials
        preset: (Optional) Nome do preset a aplicar. Se especificado, sobrescreve
                as configurações do EntityAware Retriever com os valores do preset.
                Valores válidos: consulting_frameworks, company_research, 
                sector_analysis, speed, max_quality, balanced, offline
    """
    query: str
    RAG: dict[str, Any]
    labels: list[str]
    documentFilter: list[DocumentFilter]
    credentials: Credentials
    preset: Optional[str] = None  # Preset to apply (optional)
    advanced_search: Optional[AdvancedSearchOptions] = None


class DatacountPayload(BaseModel):
    embedding_model: str
    documentFilter: list[DocumentFilter]
    credentials: Credentials


class SetRAGConfigPayload(BaseModel):
    rag_config: RAGConfig
    credentials: Credentials


class GetRerankerPresetsPayload(BaseModel):
    credentials: Credentials


class ApplyRerankerPresetPayload(BaseModel):
    preset_name: str
    query: str | None = None  # Opcional, para auto-seleção baseada em query
    credentials: Credentials


class ExternalQueryPayload(BaseModel):
    """
    Payload simplificado para endpoint /api/external/query.
    
    Este endpoint carrega automaticamente o RAG config do servidor,
    mantendo todas as capacidades avançadas de retrieval e reranking.
    
    Attributes:
        query: Texto da busca
        preset: (Optional) Preset a aplicar: speed, balanced, max_quality,
                consulting_frameworks, company_research, sector_analysis
        labels: (Optional) Labels para filtrar documentos
        documentFilter: (Optional) Filtros de documentos específicos
        credentials: Credenciais de conexão Weaviate
    """
    query: str
    preset: Optional[str] = None
    labels: Optional[list[str]] = None
    documentFilter: Optional[list[DocumentFilter]] = None
    credentials: Credentials
    advanced_search: Optional[AdvancedSearchOptions] = None


class SetUserConfigPayload(BaseModel):
    user_config: dict
    credentials: Credentials


class SetThemeConfigPayload(BaseModel):
    theme: dict
    themes: dict
    credentials: Credentials


class ChunkScore(BaseModel):
    uuid: str
    score: float
    chunk_id: int
    embedder: str


class GetContentPayload(BaseModel):
    uuid: str
    page: int
    chunkScores: list[ChunkScore]
    credentials: Credentials


class GeneratePayload(BaseModel):
    query: str
    context: str
    conversation: list[ConversationItem]
    rag_config: dict[str, Any]
    # Optional fields for iterative retrieval support in websocket generation.
    # Backward compatible: existing clients can omit these fields.
    credentials: Optional[Credentials] = None
    labels: Optional[list[str]] = None
    documentFilter: Optional[list[DocumentFilter]] = None


class ConfigPayload(BaseModel):
    config: VerbaConfig


class RAGConfigPayload(BaseModel):
    config: VerbaConfig


class SearchQueryPayload(BaseModel):
    query: str
    labels: list[str]
    page: int
    pageSize: int
    credentials: Credentials


class GetDocumentPayload(BaseModel):
    uuid: str
    credentials: Credentials


class DocumentByFrameworkPayload(BaseModel):
    framework: str
    credentials: Credentials


class DocumentByCompanyPayload(BaseModel):
    company: str
    credentials: Credentials


class DocumentBySectorPayload(BaseModel):
    sector: str
    credentials: Credentials


class DocumentSearchFilters(BaseModel):
    frameworks: Optional[List[str]] = None
    companies: Optional[List[str]] = None
    sectors: Optional[List[str]] = None
    limit: int = 50
    offset: int = 0
    credentials: Credentials


class ResetPayload(BaseModel):
    resetMode: str
    credentials: Credentials


class GetPresetConfigPayload(BaseModel):
    """Payload for getting RAGConfig with preset applied."""
    preset_name: str
    credentials: Credentials


class SearchDocumentsForAgentsPayload(BaseModel):
    """
    Grouped search for analytical agents: same inputs as /api/query, plus
    document-level grouping limits.
    """
    query: str
    RAG: dict[str, Any]
    labels: list[str] = []
    documentFilter: list[DocumentFilter] = []
    credentials: Credentials
    preset: Optional[str] = None
    advanced_search: Optional[AdvancedSearchOptions] = None
    limit_docs: int = 20
    top_hits_per_doc: int = 5


class ReadDocumentForAgentsPayload(BaseModel):
    """Controlled read: page, window, section, outline, full_if_small."""
    doc_uuid: str
    credentials: Credentials
    mode: Literal["page", "window", "section", "outline", "full_if_small"] = "page"
    page: int = 1
    page_size: int = 10
    section: Optional[str] = None
    chunk_id: Optional[int] = None
    radius: int = 5
    max_chars: int = 50_000


class ReadContextAroundPayload(BaseModel):
    """Shorthand window read around a chunk_id."""
    doc_uuid: str
    chunk_id: int
    credentials: Credentials
    radius: int = 5
