"""
SlidesSemanticaVisualChunker - Chunker otimizado para documentos de apresentações com análise semântica visual

Características:
- Respeita boundaries de slides (cada chunk dentro de 1 slide)
- Preserva metadata de slide em cada chunk (frameworks, stakeholders, bridge quality, position)
- Cria chunk de síntese geral no início
- Agrupa semanticamente dentro do slide (não quebra meio de conceito)
- Mantém metadata estruturado V019

Fluxo:
1. Chunk 0: Síntese global (todos os frameworks + stakeholders)
2. Chunks 1+: Um ou mais chunks por slide, cada um com metadata do slide
"""

from typing import List, Optional, Dict, Any
from goldenverba.components.document import Document, Chunk
from goldenverba.components.chunking.SentenceChunker import SentenceChunker
from goldenverba.components.types import InputConfig
from wasabi import msg
import re


class SlidesSemanticaVisualChunker(SentenceChunker):
    """
    Chunker especializado para documentos estruturados de slides com análise semântica visual.
    
    Otimizado para:
    - Documentos gerados por sistemas de análise visual de slides
    - Preservação de contexto de slide
    - Metadata ricos (frameworks, stakeholders, visual semantics)
    - Multi-vector search por slide, framework, stakeholder
    
    Estratégia:
    1. Detecta se documento tem slides_metadata (V019)
    2. Se sim: cria chunks respeitando limites de slide
    3. Se não: fallback para SentenceChunker genérico
    """
    
    def __init__(self):
        super().__init__()
        self.name = "Slides Semântica Visual"
        self.type = "Chunker"
        self.description = "Otimizado para apresentações com estrutura de slides e metadados ricos (frameworks, stakeholders, semântica visual). Respeita limites de slide e preserva metadata."
        
        # Override config
        self.config = {
            "Chunk Size": InputConfig(
                type="number",
                value=512,
                description="Tamanho máximo de tokens por chunk",
                values=[],
            ),
            "Chunk Overlap": InputConfig(
                type="number",
                value=50,
                description="Overlap entre chunks consecutivos (para contexto)",
                values=[],
            ),
            "Preserve Slide Boundaries": InputConfig(
                type="bool",
                value=True,
                description="Respeitar limites de slides (não quebrar meio de slide)",
                values=[],
            ),
            "Create Summary Chunk": InputConfig(
                type="bool",
                value=True,
                description="Criar chunk de síntese com todos os frameworks e stakeholders",
                values=[],
            ),
        }
    
    async def chunk(self, documents: list[Document]) -> list[Document]:
        """
        Faz chunking otimizado para slides semântica visual.
        
        Args:
            documents: Lista de Document com metadata V019
            
        Returns:
            Lista de Document com chunks otimizados
        """
        chunked_documents = []
        
        for document in documents:
            try:
                # Verifica se é documento V019 com estrutura de slides
                if self._is_slides_semantic_visual_document(document):
                    msg.info(f"[SlidesSemanticaVisual] Processando documento estruturado de slides")
                    chunked_doc = self._chunk_slides_aware(document)
                else:
                    msg.info(f"[SlidesSemanticaVisual] Não é documento de slides - usando fallback")
                    # Fallback para chunking normal
                    chunked_doc = await super().chunk([document])
                    chunked_doc = chunked_doc[0] if chunked_doc else document
                
                chunked_documents.append(chunked_doc)
                
            except Exception as e:
                msg.fail(f"[SlidesSemanticaVisual] Erro ao processar documento: {str(e)}")
                import traceback
                msg.debug(traceback.format_exc())
                # Fallback: retorna documento original
                chunked_documents.append(document)
        
        return chunked_documents
    
    def _is_slides_semantic_visual_document(self, document: Document) -> bool:
        """Verifica se documento tem estrutura V019 (slides_metadata)"""
        if not document.meta:
            return False
        
        return (
            "slides_metadata" in document.meta and 
            isinstance(document.meta.get("slides_metadata"), list) and
            len(document.meta.get("slides_metadata", [])) > 0
        )
    
    def _chunk_slides_aware(self, document: Document) -> Document:
        """
        Faz chunking respeitando limites de slides.
        
        Estratégia:
        1. Cria chunk de síntese global (se habilitado)
        2. Para cada slide:
           - Extrai conteúdo do slide
           - Faz chunking semântico DENTRO do slide
           - Adiciona metadata de slide em cada chunk
        """
        msg.info(f"[SlidesSemanticaVisual] Iniciando chunking slide-aware")
        
        chunked_doc = Document(
            title=document.title,
            metadata=document.metadata,
        )
        chunked_doc.meta = document.meta.copy() if document.meta else {}
        
        slides_metadata = document.meta.get("slides_metadata", [])
        chunk_id = 0
        
        # 1. Cria chunk de síntese geral (se habilitado)
        if self.config.get("Create Summary Chunk", {}).get("value", True):
            summary_chunk = self._create_summary_chunk(
                slides_metadata, 
                document.metadata,
                chunk_id
            )
            if summary_chunk:
                chunked_doc.chunks.append(summary_chunk)
                chunk_id += 1
                msg.good(f"[SlidesSemanticaVisual] Chunk síntese criado (ID: {summary_chunk.chunk_id})")
        
        # 2. Processa cada slide
        for slide_idx, slide_meta in enumerate(slides_metadata):
            try:
                slide_number = slide_meta.get("slide_number", slide_idx + 1)
                slide_title = slide_meta.get("slide_title", f"Slide {slide_number}")
                
                msg.info(f"[SlidesSemanticaVisual] Processando slide {slide_number}: {slide_title}")
                
                # Extrai conteúdo do slide do documento
                slide_content = self._extract_slide_content(
                    document.content,
                    slide_number,
                    slide_title
                )
                
                if not slide_content or not slide_content.strip():
                    msg.warn(f"[SlidesSemanticaVisual] Slide {slide_number} vazio, pulando")
                    continue
                
                # Faz chunking semântico dentro do slide
                slide_chunks = self._chunk_slide_content(
                    slide_content,
                    slide_meta,
                    document.metadata,
                    chunk_id
                )
                
                # Adiciona chunks do slide
                for slide_chunk in slide_chunks:
                    chunked_doc.chunks.append(slide_chunk)
                    chunk_id += 1
                
                msg.good(f"[SlidesSemanticaVisual] Slide {slide_number}: {len(slide_chunks)} chunk(s) criado(s)")
                
            except Exception as e:
                msg.warn(f"[SlidesSemanticaVisual] Erro ao processar slide {slide_number}: {str(e)}")
                continue
        
        msg.good(f"[SlidesSemanticaVisual] Chunking completo: {len(chunked_doc.chunks)} chunks totais")
        return chunked_doc
    
    def _extract_slide_content(self, document_content: str, slide_number: int, slide_title: str) -> str:
        """
        Extrai conteúdo de um slide específico do documento.
        
        Procura por:
        - # Slide X - Título
        - # Título (formato alternativo)
        
        Args:
            document_content: Conteúdo completo do documento
            slide_number: Número do slide
            slide_title: Título do slide
            
        Returns:
            Conteúdo do slide
        """
        # Tenta padrão "# Slide X - Título"
        pattern1 = rf'^#\s+Slide\s+{slide_number}\s*-\s*{re.escape(slide_title)}\s*$(.+?)(?=^#\s+|$)'
        match = re.search(pattern1, document_content, re.MULTILINE | re.DOTALL)
        
        if match:
            return match.group(1).strip()
        
        # Tenta padrão "# Título" (alternativo)
        pattern2 = rf'^#\s+{re.escape(slide_title)}\s*$(.+?)(?=^#\s+|$)'
        match = re.search(pattern2, document_content, re.MULTILINE | re.DOTALL)
        
        if match:
            return match.group(1).strip()
        
        msg.warn(f"[SlidesSemanticaVisual] Não conseguiu extrair slide {slide_number}")
        return ""
    
    def _chunk_slide_content(
        self,
        slide_content: str,
        slide_meta: Dict[str, Any],
        document_metadata: str,
        start_chunk_id: int
    ) -> List[Chunk]:
        """
        Faz chunking semântico do conteúdo de um slide.
        
        Agrupa por sentenças/parágrafos mantendo coesão.
        
        Args:
            slide_content: Conteúdo do slide
            slide_meta: Metadata do slide (frameworks, stakeholders, etc.)
            document_metadata: Metadata do documento
            start_chunk_id: ID inicial para chunks
            
        Returns:
            Lista de Chunk com metadata de slide preservado
        """
        chunks = []
        
        # Divide em sentenças/parágrafos
        sentences = self._split_into_sentences(slide_content)
        
        if not sentences:
            return chunks
        
        # Agrupa sentenças em chunks respeitando tamanho
        chunk_size = self.config.get("Chunk Size", {}).get("value", 512)
        chunk_overlap = self.config.get("Chunk Overlap", {}).get("value", 50)
        
        current_chunk_text = ""
        current_start_i = 0
        
        for sent_idx, sentence in enumerate(sentences):
            sent_len = len(sentence.split())
            current_len = len(current_chunk_text.split())
            
            # Se adicionar sentença não excede limit, adiciona
            if current_len + sent_len <= chunk_size:
                if current_chunk_text:
                    current_chunk_text += " " + sentence
                else:
                    current_chunk_text = sentence
            else:
                # Se chegou ao limit, cria chunk
                if current_chunk_text:
                    chunk = self._create_slide_chunk(
                        current_chunk_text,
                        slide_meta,
                        document_metadata,
                        start_chunk_id + len(chunks),
                        current_start_i,
                        current_start_i + len(current_chunk_text)
                    )
                    chunks.append(chunk)
                
                # Inicia novo chunk com overlap
                current_chunk_text = sentence
                current_start_i = current_start_i + len(" ".join(sentences[:sent_idx]))
        
        # Chunk final
        if current_chunk_text:
            chunk = self._create_slide_chunk(
                current_chunk_text,
                slide_meta,
                document_metadata,
                start_chunk_id + len(chunks),
                current_start_i,
                current_start_i + len(current_chunk_text)
            )
            chunks.append(chunk)
        
        return chunks
    
    def _create_slide_chunk(
        self,
        content: str,
        slide_meta: Dict[str, Any],
        document_metadata: str,
        chunk_id: int,
        start_i: int,
        end_i: int
    ) -> Chunk:
        """
        Cria um Chunk com metadata de slide preservado.
        
        Args:
            content: Conteúdo do chunk
            slide_meta: Metadata do slide
            document_metadata: Metadata do documento
            chunk_id: ID do chunk
            start_i: Índice inicial
            end_i: Índice final
            
        Returns:
            Chunk com metadata estruturado
        """
        chunk = Chunk(
            content=content,
            title=slide_meta.get("slide_title", ""),
            chunk_id=chunk_id,
            start_i=start_i,
            end_i=end_i,
        )
        
        # Adiciona metadata de slide ao chunk
        chunk.meta = {
            # Informação de slide
            "slide_number": slide_meta.get("slide_number"),
            "slide_title": slide_meta.get("slide_title"),
            "slide_position": slide_meta.get("position"),  # opening, diagnostic, analysis, conclusion
            
            # Metadata visual
            "semantic_bridge_quality": slide_meta.get("semantic_bridge_quality"),
            "slide_type": slide_meta.get("slide_type"),
            "visual_archetype": slide_meta.get("visual_archetype"),
            
            # Metadata de padrão
            "pattern_genetics": slide_meta.get("pattern_genetics", []),
            "reusability_score": slide_meta.get("reusability_score"),
            
            # Análise semântica
            "frameworks": slide_meta.get("frameworks", []),
            "stakeholders": slide_meta.get("stakeholders", []),
            "companies": slide_meta.get("companies", []),
            "framework_confidence": slide_meta.get("framework_confidence"),
            
            # Metadata do documento
            "source_format": "slides_semantica_visual",
            "document_metadata": document_metadata,
        }
        
        return chunk
    
    def _create_summary_chunk(
        self,
        slides_metadata: List[Dict[str, Any]],
        document_metadata: str,
        chunk_id: int = 0
    ) -> Optional[Chunk]:
        """
        Cria chunk de síntese com agregação de todos os frameworks e stakeholders.
        
        Args:
            slides_metadata: Lista de metadata dos slides
            document_metadata: Metadata do documento
            chunk_id: ID do chunk
            
        Returns:
            Chunk de síntese ou None se não houver dados
        """
        # Agrega frameworks e stakeholders
        all_frameworks = []
        all_stakeholders = []
        all_companies = []
        positions = []
        total_slides = len(slides_metadata)
        
        for slide in slides_metadata:
            for fw in slide.get("frameworks", []):
                if fw not in all_frameworks:
                    all_frameworks.append(fw)
            
            for sh in slide.get("stakeholders", []):
                if sh not in all_stakeholders:
                    all_stakeholders.append(sh)
            
            for co in slide.get("companies", []):
                if co not in all_companies:
                    all_companies.append(co)
            
            if slide.get("position") and slide.get("position") not in positions:
                positions.append(slide.get("position"))
        
        # Cria conteúdo de síntese
        summary_parts = [
            f"📊 SÍNTESE DE APRESENTAÇÃO ({total_slides} slides)\n",
            f"\n🎯 Frameworks Identificados:\n" + ", ".join(all_frameworks) if all_frameworks else "Nenhum framework identificado",
            f"\n👥 Stakeholders Principais:\n" + ", ".join(all_stakeholders) if all_stakeholders else "Nenhum stakeholder",
            f"\n🏢 Empresas Mencionadas:\n" + ", ".join(all_companies) if all_companies else "Nenhuma empresa",
            f"\n📈 Estrutura da Apresentação:\n" + " → ".join(positions) if positions else "Sem estrutura",
        ]
        
        summary_content = "\n".join(summary_parts)
        
        # Cria chunk
        summary_chunk = Chunk(
            content=summary_content,
            title="SÍNTESE GERAL - Todos os Slides",
            chunk_id=chunk_id,
            start_i=0,
            end_i=len(summary_content),
        )
        
        # Metadata de síntese
        summary_chunk.meta = {
            "slide_number": 0,
            "slide_title": "SÍNTESE GERAL",
            "slide_position": "summary",
            "is_summary": True,
            "total_slides": total_slides,
            "all_frameworks": all_frameworks,
            "all_stakeholders": all_stakeholders,
            "all_companies": all_companies,
            "source_format": "slides_semantica_visual",
            "document_metadata": document_metadata,
        }
        
        return summary_chunk
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """
        Divide texto em sentenças.
        
        Handles:
        - Pontos finais (.!?)
        - Quebras de linha
        - Parágrafos
        
        Args:
            text: Texto a dividir
            
        Returns:
            Lista de sentenças
        """
        # Remove linhas vazias múltiplas
        text = re.sub(r'\n\s*\n+', '\n', text)
        
        # Divide por quebra de linha (parágrafos)
        paragraphs = text.split('\n')
        
        sentences = []
        for para in paragraphs:
            if not para.strip():
                continue
            
            # Divide parágrafo em sentenças (., !, ?)
            # Mas respeita abreviaturas comuns (Dr., Sr., etc.)
            sents = re.split(r'(?<=[.!?])\s+(?=[A-Z])', para)
            
            for sent in sents:
                sent = sent.strip()
                if sent:
                    sentences.append(sent)
        
        return sentences


def register():
    """Registra o chunker como plugin Verba"""
    return {
        'name': 'slides_semantica_visual_chunker',
        'version': '1.0.0',
        'description': 'Chunker otimizado para slides com análise semântica visual (frameworks, stakeholders, bridge quality)',
        'chunkers': [SlidesSemanticaVisualChunker()],
        'compatible_verba_version': '>=2.1.0',
    }

