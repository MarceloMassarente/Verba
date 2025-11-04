from spacy.tokens import Doc, Span


class Chunk:
    def __init__(
        self,
        content: str = "",
        content_without_overlap: str = "",
        chunk_id: str = "",
        start_i: int = 0,
        end_i: int = 0,
    ):
        self.content = content
        self.title = ""
        self.chunk_id = chunk_id
        self.vector = None
        self.doc_uuid = None
        self.pca = [0, 0, 0]
        self.start_i = start_i
        self.end_i = end_i
        self.content_without_overlap = content_without_overlap
        self.labels = []
        self.meta = {}  # Metadata dict for plugins (e.g., enriched metadata from LLMMetadataExtractor)
        self.uuid = None  # UUID for chunk identification

    def to_json(self) -> dict:
        """Convert the Chunk object to a dictionary."""
        import json
        return {
            "content": self.content,
            "chunk_id": self.chunk_id,
            "doc_uuid": self.doc_uuid,
            "title": self.title,
            "pca": self.pca,
            "start_i": self.start_i,
            "end_i": self.end_i,
            "content_without_overlap": self.content_without_overlap,
            "labels": self.labels,
            "meta": json.dumps(self.meta) if self.meta else "{}",  # Serialize meta dict
            "uuid": self.uuid,
        }

    @classmethod
    def from_json(cls, data: dict):
        """Construct a Chunk object from a dictionary."""
        import json
        chunk = cls(
            content=data.get("content", ""),
            title=data.get("title", ""),
            chunk_id=data.get("chunk_id", 0),
            start_i=data.get("start_i", 0),
            end_i=data.get("end_i", 0),
            content_without_overlap=data.get("content_without_overlap", ""),
            labels=data.get("labels", []),
        )
        chunk.doc_uuid = (data.get("doc_uuid", ""),)
        chunk.uuid = data.get("uuid")
        # Deserialize meta if present
        meta_str = data.get("meta", "{}")
        try:
            chunk.meta = json.loads(meta_str) if isinstance(meta_str, str) else (meta_str or {})
        except:
            chunk.meta = {}
        return chunk
