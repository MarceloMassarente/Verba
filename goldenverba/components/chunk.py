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
        self.chunk_lang = None  # Language code (pt, en, etc.) for bilingual filtering
        self.chunk_date = None  # Date in ISO format (YYYY-MM-DD) for temporal filtering

    def to_json(self) -> dict:
        """Convert the Chunk object to a dictionary."""
        import json
        
        # Convert chunk_id to float if it's a string (e.g., '6_154' -> 6.154 or hash)
        # Weaviate requires chunk_id to be a number, not a string
        chunk_id_value = self.chunk_id
        if isinstance(chunk_id_value, str):
            # If it's a string like '6_154', convert to unique float
            if '_' in chunk_id_value:
                try:
                    # Try to parse as 'original_subindex' format
                    parts = chunk_id_value.split('_')
                    if len(parts) == 2:
                        original = float(parts[0])
                        subindex = float(parts[1])
                        # Convert to float: original.subindex (e.g., 6_154 -> 6.154)
                        # But if subindex is > 1000, use hash to avoid precision issues
                        if subindex < 1000:
                            chunk_id_value = original + (subindex / 1000.0)
                        else:
                            # Use hash for large subindexes to ensure uniqueness
                            chunk_id_value = float(hash(chunk_id_value) % (10**10))
                    else:
                        # Fallback: use hash for any string format
                        chunk_id_value = float(hash(chunk_id_value) % (10**10))
                except (ValueError, IndexError):
                    # If parsing fails, use hash
                    chunk_id_value = float(hash(chunk_id_value) % (10**10))
            else:
                # Try to convert string to float directly
                try:
                    chunk_id_value = float(chunk_id_value)
                except (ValueError, TypeError):
                    # Fallback: use hash
                    chunk_id_value = float(hash(str(chunk_id_value)) % (10**10))
        elif chunk_id_value is None or chunk_id_value == "":
            chunk_id_value = 0.0
        else:
            # Ensure it's a number
            try:
                chunk_id_value = float(chunk_id_value)
            except (ValueError, TypeError):
                chunk_id_value = 0.0
        
        return {
            "content": self.content,
            "chunk_id": chunk_id_value,  # Now guaranteed to be float
            "doc_uuid": self.doc_uuid,
            "title": self.title,
            "pca": self.pca,
            "start_i": self.start_i,
            "end_i": self.end_i,
            "content_without_overlap": self.content_without_overlap,
            "labels": self.labels,
            "meta": json.dumps(self.meta) if self.meta else "{}",  # Serialize meta dict
            "uuid": self.uuid,
            "chunk_lang": self.chunk_lang or "",  # Language code for bilingual filtering
            "chunk_date": self.chunk_date or "",  # Date in ISO format for temporal filtering
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
        chunk.chunk_lang = data.get("chunk_lang")  # Language code
        chunk.chunk_date = data.get("chunk_date")  # Date
        # Deserialize meta if present
        meta_str = data.get("meta", "{}")
        try:
            chunk.meta = json.loads(meta_str) if isinstance(meta_str, str) else (meta_str or {})
        except:
            chunk.meta = {}
        return chunk
