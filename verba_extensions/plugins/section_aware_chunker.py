"""
Section-Aware Chunker - Chunking que respeita limites de seções
Melhora qualidade ao evitar cortar entidades/seções no meio
"""

import re
from typing import List
from goldenverba.components.chunk import Chunk
from goldenverba.components.interfaces import Chunker
from goldenverba.components.document import Document
from goldenverba.components.types import InputConfig
from goldenverba.components.interfaces import Embedding
from wasabi import msg


def detect_sections(text: str) -> List[dict]:
    """
    Detecta seções no texto usando heurísticas simples
    
    Procura por:
    - Linhas que parecem títulos (curtas, maiúsculas, numeradas)
    - Quebras duplas/triplas de linha
    - Padrões de título markdown (# ## ###)
    """
    sections = []
    
    # Divide por múltiplas quebras de linha (2+ linhas vazias)
    parts = re.split(r'\n\n\n+', text.strip())
    
    if len(parts) <= 1:
        # Sem seções claras, retorna documento inteiro
        return [{"title": "", "content": text, "start": 0, "end": len(text)}]
    
    current_pos = 0
    
    for i, part in enumerate(parts):
        part = part.strip()
        if not part:
            continue
        
        # Tenta detectar título na primeira linha
        lines = part.split('\n')
        title = ""
        content_start = 0
        
        if len(lines) > 0:
            first_line = lines[0].strip()
            
            # Heurísticas para identificar título:
            # 1. Linha curta (< 100 chars)
            # 2. Não termina com ponto
            # 3. Pode ter números/padrões de título
            # 4. Pode ser todo maiúsculo (parcial)
            if (len(first_line) < 100 and 
                not first_line.endswith('.') and
                (len(first_line.split()) <= 15 or
                 first_line.isupper() or
                 re.match(r'^\d+[\.)]', first_line) or  # "1. Título" ou "1) Título"
                 re.match(r'^[A-Z][^\.]*:', first_line))):  # "TÍTULO:"
                title = first_line
                content_start = 1
        
        # Conteúdo é o resto
        content = '\n'.join(lines[content_start:]).strip()
        
        if content:
            start = current_pos
            end = start + len(part)
            sections.append({
                "title": title,
                "content": content,
                "start": start,
                "end": end
            })
            current_pos = end + 2  # +2 para quebras de linha
    
    return sections


class SectionAwareChunker(Chunker):
    """
    Chunker que respeita limites de seções
    
    Divide documentos respeitando estrutura natural (seções, artigos),
    evitando cortar entidades ou tópicos no meio.
    """
    
    def __init__(self):
        super().__init__()
        self.name = "Section-Aware"
        self.description = "Chunking que respeita limites de seções para melhor coerência semântica"
        self.config = {
            "Chunk Size": InputConfig(
                type="number",
                value=300,
                description="Tamanho alvo de palavras por chunk",
                values=[],
            ),
            "Overlap": InputConfig(
                type="number",
                value=50,
                description="Overlap em palavras entre chunks",
                values=[],
            ),
            "Min Section Size": InputConfig(
                type="number",
                value=100,
                description="Tamanho mínimo (palavras) para considerar seção separada",
                values=[],
            ),
        }
    
    async def chunk(
        self,
        config: dict,
        documents: list[Document],
        embedder: Embedding | None = None,
        embedder_config: dict | None = None,
    ) -> list[Document]:
        """
        Chunking que respeita seções
        """
        chunk_size = int(config.get("Chunk Size", {}).value if hasattr(config.get("Chunk Size", {}), 'value') else 300)
        overlap = int(config.get("Overlap", {}).value if hasattr(config.get("Overlap", {}), 'value') else 50)
        min_section_size = int(config.get("Min Section Size", {}).value if hasattr(config.get("Min Section Size", {}), 'value') else 100)
        
        for document in documents:
            # Skip se já tem chunks
            if len(document.chunks) > 0:
                continue
            
            text = document.content
            
            # Detecta seções
            sections = detect_sections(text)
            
            if len(sections) <= 1:
                # Sem seções claras, usa chunking padrão por sentenças
                msg.info(f"Documento sem seções claras, usando chunking por sentenças")
                await self._chunk_by_sentences(document, chunk_size, overlap)
                continue
            
            msg.info(f"Detectadas {len(sections)} seções no documento")
            
            # Chunking por seção
            all_chunks = []
            chunk_id_counter = 0
            
            for section in sections:
                section_text = section["content"]
                section_title = section["title"]
                
                # Conta palavras aproximadas
                word_count = len(section_text.split())
                
                if word_count <= chunk_size:
                    # Seção cabe em um chunk
                    chunk = Chunk(
                        content=section_text,
                        chunk_id=chunk_id_counter,
                        start_i=section["start"],
                        end_i=section["end"],
                        content_without_overlap=section_text,
                    )
                    
                    # Adiciona metadados de seção se disponível
                    if hasattr(chunk, 'meta') or True:  # Verifica estrutura
                        # Metadados serão adicionados via document.meta depois
                        pass
                    
                    all_chunks.append(chunk)
                    chunk_id_counter += 1
                    
                else:
                    # Seção grande: divide respeitando parágrafos
                    paragraphs = section_text.split('\n\n')
                    
                    current_chunk_parts = []
                    current_chunk_words = 0
                    char_offset = section["start"]
                    
                    for para in paragraphs:
                        para_words = len(para.split())
                        
                        if current_chunk_words + para_words > chunk_size and current_chunk_parts:
                            # Finaliza chunk atual
                            chunk_text = '\n\n'.join(current_chunk_parts)
                            chunk_start = char_offset - len(chunk_text)
                            chunk_end = char_offset
                            
                            chunk = Chunk(
                                content=chunk_text,
                                chunk_id=chunk_id_counter,
                                start_i=chunk_start,
                                end_i=chunk_end,
                                content_without_overlap=chunk_text,
                            )
                            all_chunks.append(chunk)
                            chunk_id_counter += 1
                            
                            # Inicia novo chunk com overlap
                            if overlap > 0:
                                # Pega últimas palavras do chunk anterior para overlap
                                last_sentences = chunk_text.split('.')[-overlap//20:]  # Aproximação
                                current_chunk_parts = [' '.join(last_sentences)] if last_sentences else []
                                current_chunk_words = len(' '.join(current_chunk_parts).split())
                            else:
                                current_chunk_parts = []
                                current_chunk_words = 0
                        
                        current_chunk_parts.append(para)
                        current_chunk_words += para_words
                        char_offset += len(para) + 2  # +2 para \n\n
                    
                    # Adiciona último chunk da seção
                    if current_chunk_parts:
                        chunk_text = '\n\n'.join(current_chunk_parts)
                        chunk_start = section["end"] - len(chunk_text)
                        chunk_end = section["end"]
                        
                        chunk = Chunk(
                            content=chunk_text,
                            chunk_id=chunk_id_counter,
                            start_i=chunk_start,
                            end_i=chunk_end,
                            content_without_overlap=chunk_text,
                        )
                        all_chunks.append(chunk)
                        chunk_id_counter += 1
            
            # Adiciona chunks ao documento
            document.chunks = all_chunks
            
            # Adiciona metadados de seções no documento
            if not hasattr(document, 'meta') or document.meta is None:
                document.meta = {}
            
            # Armazena informações de seções para uso posterior (ETL pode usar)
            document.meta["sections"] = [
                {"title": s["title"], "start": s["start"], "end": s["end"]} 
                for s in sections
            ]
            
            msg.good(f"Documento dividido em {len(all_chunks)} chunks respeitando {len(sections)} seções")
        
        return documents
    
    async def _chunk_by_sentences(
        self,
        document: Document,
        chunk_size: int,
        overlap: int
    ):
        """
        Fallback: chunking por sentenças (quando não há seções claras)
        """
        try:
            # Usa SpaCy se disponível no documento
            if hasattr(document, 'spacy_doc') and document.spacy_doc:
                doc = document.spacy_doc
                sentences = [sent.text for sent in doc.sents]
            else:
                # Fallback simples: divide por pontos
                sentences = re.split(r'[.!?]+\s+', document.content)
                sentences = [s.strip() for s in sentences if s.strip()]
            
            if not sentences:
                document.chunks.append(
                    Chunk(
                        content=document.content,
                        chunk_id=0,
                        start_i=0,
                        end_i=len(document.content),
                        content_without_overlap=document.content,
                    )
                )
                return
            
            i = 0
            chunk_id_counter = 0
            char_end_i = -1
            
            while i < len(sentences):
                start_i = i
                end_i = min(i + chunk_size // 20, len(sentences))  # ~20 palavras por sentença
                
                chunk_text = ' '.join(sentences[start_i:end_i])
                chunk_start = char_end_i + 1 if i > 0 else 0
                char_end_i = chunk_start + len(chunk_text)
                
                chunk = Chunk(
                    content=chunk_text,
                    chunk_id=chunk_id_counter,
                    start_i=chunk_start,
                    end_i=char_end_i,
                    content_without_overlap=chunk_text,
                )
                
                document.chunks.append(chunk)
                chunk_id_counter += 1
                
                if end_i == len(sentences):
                    break
                
                i += max(1, end_i - start_i - overlap // 20)
        
        except Exception as e:
            msg.warn(f"Erro no chunking por sentenças: {str(e)}, usando chunk único")
            document.chunks.append(
                Chunk(
                    content=document.content,
                    chunk_id=0,
                    start_i=0,
                    end_i=len(document.content),
                    content_without_overlap=document.content,
                )
            )


def register():
    """
    Registra plugin
    """
    return {
        'name': 'section_aware_chunker',
        'version': '1.0.0',
        'description': 'Chunker que respeita limites de seções para melhor coerência semântica',
        'chunkers': [SectionAwareChunker()],
        'compatible_verba_version': '>=2.1.0',
    }

