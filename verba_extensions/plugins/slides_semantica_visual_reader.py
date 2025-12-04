"""
Slides Semântica Visual Reader - Reader customizado para arquivos .md de apresentações com análise semântica visual

Processa arquivos Markdown estruturados com:
- Metadados ricos (frameworks, stakeholders, semantic bridge quality, etc.)
- Estrutura de slides (1 slide = 1 seção H1)
- Pattern Genetics (componentes atômicos identificados)
- Visual Semantics (análise visual de gráficos)
- Posição narrativa no deck (opening, diagnostic, analysis, conclusion)

Integrado com SlidesSemanticaVisualChunker para preservar contexto de slides.
"""

import re
import base64
from typing import List, Dict, Any, Optional
from goldenverba.components.document import Document, create_document
from goldenverba.components.interfaces import Reader
from goldenverba.server.types import FileConfig
from goldenverba.components.types import InputConfig
from wasabi import msg


class SlidesSemanticaVisualReader(Reader):
    """
    Reader customizado para .md com estrutura de slides e análise semântica visual.
    
    Características:
    - ✅ Extrai metadados ricos (frameworks, stakeholders, qualidade semântica)
    - ✅ Suporta estrutura de múltiplos slides (1 slide = 1 seção H1)
    - ✅ Marca enable_etl=True automaticamente
    - ✅ Preserva metadata estruturado em document.meta["slides_metadata"]
    - ✅ Integrado com SlidesSemanticaVisualChunker
    
    Uso Recomendado:
    1. Selecionar este reader
    2. Selecionar "Slides Semântica Visual" como chunker
    3. Selecionar embedder de preferência
    4. Import automático respeitará estrutura de slides
    """
    
    def __init__(self):
        super().__init__()
        self.name = "Slides Semântica Visual"
        self.type = "FILE"
        self.extension = [".md"]
        self.description = "Otimizado para apresentações estruturadas com análise semântica visual. Processa Markdown com estrutura de slides (H1) e metadados ricos (frameworks, stakeholders, qualidade de ponte semântica, etc.). Use com chunker 'Slides Semântica Visual' para resultados otimizados."
        
        self.config["Enable ETL"] = InputConfig(
            type="bool",
            value=True,
            description="Aplicar ETL A2 automaticamente (NER + Section Scope) para enriquecimento adicional",
            values=[],
        )
        
        self.config["Extract Visual Semantics"] = InputConfig(
            type="bool",
            value=True,
            description="Extrair semântica visual e metadata estruturado dos slides",
            values=[],
        )
    
    async def load(self, config: dict, fileConfig: FileConfig) -> List[Document]:
        """
        Carrega arquivo .md com estrutura de slides e extrai metadata rico.
        
        Args:
            config: Configuração do reader
            fileConfig: Configuração do arquivo
            
        Returns:
            Lista com 1 Document contendo todos os slides + metadata estruturado
        """
        msg.info(f"[SlidesSemanticaVisual] Carregando {fileConfig.filename}")
        
        # Decodifica conteúdo
        try:
            if fileConfig.extension.lower() == "md":
                if isinstance(fileConfig.content, str):
                    content = fileConfig.content
                else:
                    decoded_bytes = base64.b64decode(fileConfig.content)
                    content = decoded_bytes.decode('utf-8')
            else:
                msg.warn(f"[SlidesSemanticaVisual] Extensão {fileConfig.extension} não suportada, tentando como texto")
                if isinstance(fileConfig.content, str):
                    content = fileConfig.content
                else:
                    decoded_bytes = base64.b64decode(fileConfig.content)
                    content = decoded_bytes.decode('utf-8')
        except Exception as e:
            msg.fail(f"[SlidesSemanticaVisual] Erro ao decodificar conteúdo: {str(e)}")
            raise
        
        # Extrai metadados de slides se habilitado
        metadata = {}
        if config.get("Extract Visual Semantics", {}).get("value", True):
            metadata = self._extract_slides_metadata(content)
        
        # Cria documento
        document = create_document(content, fileConfig)
        
        # Adiciona metadata de slides
        if not document.meta:
            document.meta = {}
        
        # Marca para ETL
        document.meta["enable_etl"] = config.get("Enable ETL", {}).get("value", True)
        document.meta["doc_type"] = "slides_semantica_visual"
        document.meta["source_format"] = "slides_semantica_visual_markdown"
        
        # Adiciona todos os metadados estruturados
        document.meta.update(metadata)
        
        total_slides = len(metadata.get("slides_metadata", []))
        msg.good(f"[SlidesSemanticaVisual] ✅ Documento carregado: {total_slides} slides processados")
        msg.info(f"[SlidesSemanticaVisual] 💡 Recomendação: use chunker 'Slides Semântica Visual' para resultados otimizados")
        
        return [document]
    
    def _extract_slides_metadata(self, content: str) -> Dict[str, Any]:
        """
        Extrai metadata específico de slides (estrutura semântica visual).
        
        Formato esperado:
        - Slides separados por H1 (# Slide X - Título ou # Título)
        - Metadados por slide em formato **Chave:** valor
        - Frameworks, Stakeholders, Qualidade de Ponte, etc.
        
        Returns:
            Dict com metadata estruturado e agregações
        """
        metadata = {
            "slides_metadata": [],
            "frameworks": [],
            "stakeholders": [],
            "companies": [],
            "positions": [],
            "total_slides": 0,
        }
        
        # Divide conteúdo em slides (por H1)
        slide_pattern = r'^#\s+Slide\s+(\d+)\s*-\s*(.+)$'
        slides = re.split(slide_pattern, content, flags=re.MULTILINE)
        
        # Se não encontrou slides no formato "Slide X", tenta formato alternativo
        if len(slides) <= 1:
            slides = re.split(r'^#\s+(.+)$', content, flags=re.MULTILINE)
            if len(slides) <= 1:
                # Documento sem estrutura de slides - extrai como documento único
                slide_meta = self._extract_single_slide_metadata(content, 1, "Documento Completo")
                metadata["slides_metadata"].append(slide_meta)
                metadata["total_slides"] = 1
                self._aggregate_metadata(slide_meta, metadata)
                return metadata
        
        # Processa slides encontrados
        # slides[0] é texto antes do primeiro slide
        # Depois vem pares: (número, título, conteúdo) ou (título, conteúdo)
        
        for i in range(1, len(slides), 3):
            if i + 1 < len(slides):
                slide_number = slides[i]
                slide_title = slides[i + 1]
                slide_content = slides[i + 2] if i + 2 < len(slides) else ""
                
                # Extrai metadata do slide
                slide_meta = self._extract_single_slide_metadata(
                    slide_content,
                    slide_number=slide_number,
                    slide_title=slide_title
                )
                
                metadata["slides_metadata"].append(slide_meta)
                self._aggregate_metadata(slide_meta, metadata)
        
        metadata["total_slides"] = len(metadata["slides_metadata"])
        msg.info(f"[SlidesSemanticaVisual] Metadados extraídos: {len(metadata['slides_metadata'])} slides, {len(metadata['frameworks'])} frameworks")
        
        return metadata
    
    def _extract_single_slide_metadata(self, slide_content: str, slide_number: int, slide_title: str) -> Dict[str, Any]:
        """
        Extrai metadata de um slide individual.
        
        Args:
            slide_content: Conteúdo do slide em markdown
            slide_number: Número do slide
            slide_title: Título do slide
            
        Returns:
            Dict com metadata estruturado do slide
        """
        slide_meta = {
            "slide_number": int(slide_number) if isinstance(slide_number, (int, str)) and str(slide_number).isdigit() else 1,
            "slide_title": str(slide_title).strip(),
            "frameworks": [],
            "stakeholders": [],
            "companies": [],
            "position": None,
            "semantic_bridge_quality": None,
            "slide_type": None,
            "visual_archetype": None,
            "pattern_genetics": [],
            "reusability_score": None,
        }
        
        # ════════════════════════════════════════════════════════════
        # EXTRAÇÃO DE FRAMEWORKS
        # ════════════════════════════════════════════════════════════
        fw_match = re.search(r'\*\*Frameworks.*?:\*\*\s*(.+?)(?=\*\*|$)', slide_content, re.IGNORECASE | re.DOTALL)
        if fw_match:
            frameworks_str = fw_match.group(1).strip()
            frameworks_clean = re.sub(r'\s*\([^)]*\)', '', frameworks_str)
            frameworks = [fw.strip() for fw in re.split(r'[,\n]', frameworks_clean) if fw.strip()]
            slide_meta["frameworks"] = frameworks
            
            confidence_match = re.search(r'\(confiança:\s*([\d.]+)\)', frameworks_str, re.IGNORECASE)
            if confidence_match:
                try:
                    slide_meta["framework_confidence"] = float(confidence_match.group(1))
                except:
                    pass
        
        # ════════════════════════════════════════════════════════════
        # EXTRAÇÃO DE STAKEHOLDERS
        # ════════════════════════════════════════════════════════════
        sh_match = re.search(r'\*\*Stakeholders.*?:\*\*\s*(.+?)(?=\*\*|$)', slide_content, re.IGNORECASE | re.DOTALL)
        if sh_match:
            stakeholders_str = sh_match.group(1).strip()
            stakeholders = [sh.strip() for sh in re.split(r'[,\n]', stakeholders_str) if sh.strip()]
            slide_meta["stakeholders"] = stakeholders
            
            # Identifica empresas nos stakeholders
            for sh in stakeholders:
                if any(term in sh.lower() for term in ['inc', 'ltd', 'corp', 's.a', 'sa', 'ltda', 'banco', 'bank']):
                    if sh not in slide_meta["companies"]:
                        slide_meta["companies"].append(sh)
        
        # ════════════════════════════════════════════════════════════
        # EXTRAÇÃO DE QUALIDADE SEMÂNTICA
        # ════════════════════════════════════════════════════════════
        bridge_match = re.search(r'\*\*(?:Qualidade da Ponte|Semantic Bridge).*?:\*\*\s*([\d.]+)', slide_content, re.IGNORECASE)
        if bridge_match:
            try:
                slide_meta["semantic_bridge_quality"] = float(bridge_match.group(1))
            except:
                pass
        
        # ════════════════════════════════════════════════════════════
        # EXTRAÇÃO DE POSIÇÃO NO DECK
        # ════════════════════════════════════════════════════════════
        pos_match = re.search(r'\*\*Posição.*?:\*\*\s*(\w+)', slide_content, re.IGNORECASE)
        if pos_match:
            position = pos_match.group(1).lower().strip()
            if position in ["opening", "diagnostic", "analysis", "conclusion", "recomendation", "summary"]:
                slide_meta["position"] = position
        
        # ════════════════════════════════════════════════════════════
        # EXTRAÇÃO DE TIPO DE SLIDE
        # ════════════════════════════════════════════════════════════
        type_match = re.search(r'\*\*Tipo de Slide.*?:\*\*\s*(\w+)', slide_content, re.IGNORECASE)
        if type_match:
            slide_meta["slide_type"] = type_match.group(1).lower().strip()
        
        # ════════════════════════════════════════════════════════════
        # EXTRAÇÃO DE ARQUÉTIPO VISUAL
        # ════════════════════════════════════════════════════════════
        arch_match = re.search(r'\*\*Arquétipo Visual.*?:\*\*\s*(\w+)', slide_content, re.IGNORECASE)
        if arch_match:
            slide_meta["visual_archetype"] = arch_match.group(1).lower().strip()
        
        # ════════════════════════════════════════════════════════════
        # EXTRAÇÃO DE PATTERN GENETICS
        # ════════════════════════════════════════════════════════════
        pattern_match = re.search(r'\*\*Pattern Genetics.*?:\*\*\s*(.+?)(?=\*\*|$)', slide_content, re.IGNORECASE | re.DOTALL)
        if pattern_match:
            patterns_str = pattern_match.group(1).strip()
            patterns = [p.strip() for p in re.split(r'[,\n]', patterns_str) if p.strip()]
            slide_meta["pattern_genetics"] = patterns
        
        # ════════════════════════════════════════════════════════════
        # EXTRAÇÃO DE REUSABILITY SCORE
        # ════════════════════════════════════════════════════════════
        reuse_match = re.search(r'\*\*Reusability Score.*?:\*\*\s*([\d.]+)', slide_content, re.IGNORECASE)
        if reuse_match:
            try:
                slide_meta["reusability_score"] = float(reuse_match.group(1))
            except:
                pass
        
        return slide_meta
    
    def _aggregate_metadata(self, slide_meta: Dict[str, Any], metadata: Dict[str, Any]) -> None:
        """
        Agrega metadata de um slide para metadata global.
        
        Args:
            slide_meta: Metadata de um slide
            metadata: Dict global de metadata para atualizar
        """
        for fw in slide_meta.get("frameworks", []):
            if fw not in metadata["frameworks"]:
                metadata["frameworks"].append(fw)
        
        for sh in slide_meta.get("stakeholders", []):
            if sh not in metadata["stakeholders"]:
                metadata["stakeholders"].append(sh)
        
        for co in slide_meta.get("companies", []):
            if co not in metadata["companies"]:
                metadata["companies"].append(co)
        
        if slide_meta.get("position") and slide_meta.get("position") not in metadata["positions"]:
            metadata["positions"].append(slide_meta.get("position"))


def register():
    """Registra o reader como plugin Verba"""
    return {
        'name': 'slides_semantica_visual_reader',
        'version': '1.0.0',
        'description': 'Reader para arquivos .md com estrutura de slides e análise semântica visual (frameworks, stakeholders, bridge quality)',
        'readers': [SlidesSemanticaVisualReader()],
        'compatible_verba_version': '>=2.1.0',
    }


# ════════════════════════════════════════════════════════════════════════════════
# COMPATIBILIDADE: Alias para V019MarkdownReader (para código legado)
# ════════════════════════════════════════════════════════════════════════════════
class V019MarkdownReader(SlidesSemanticaVisualReader):
    """Alias legado para compatibilidade com código V019"""
    pass

