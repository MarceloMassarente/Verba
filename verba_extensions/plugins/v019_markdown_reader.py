"""
V019 Markdown Reader - Reader customizado para arquivos .md gerados pelo Sistema V019

Processa arquivos Markdown com estrutura V019 que incluem:
- Metadados ricos (frameworks, stakeholders, semantic bridge quality, etc.)
- Estrutura de slides (1 slide = 1 seção H1)
- Pattern Genetics (componentes atômicos identificados)
- Visual Semantics (análise visual de gráficos)
"""

import re
import base64
from typing import List, Dict, Any, Optional
from goldenverba.components.document import Document, create_document
from goldenverba.components.interfaces import Reader
from goldenverba.server.types import FileConfig
from goldenverba.components.types import InputConfig
from wasabi import msg


class V019MarkdownReader(Reader):
    """
    Reader customizado para .md gerados pelo Sistema V019 de semântica visual.
    
    Características:
    - Extrai metadados ricos do formato V019
    - Suporta estrutura de múltiplos slides (1 slide = 1 seção H1)
    - Marca enable_etl=True automaticamente
    - Preserva metadata estruturado em document.meta
    """
    
    def __init__(self):
        super().__init__()
        self.name = "V019 Markdown Reader"
        self.type = "FILE"
        self.extension = [".md"]
        self.description = "Processa arquivos Markdown gerados pelo Sistema V019 com estrutura de slides e metadados ricos (frameworks, stakeholders, pattern genetics, visual semantics, etc.). Aplica ETL A2 automaticamente."
        
        self.config["Enable ETL"] = InputConfig(
            type="bool",
            value=True,
            description="Aplicar ETL A2 automaticamente (NER + Section Scope)",
            values=[],
        )
    
    async def load(self, config: dict, fileConfig: FileConfig) -> List[Document]:
        """
        Carrega arquivo .md V019 e extrai metadata rico.
        
        Args:
            config: Configuração do reader
            fileConfig: Configuração do arquivo
            
        Returns:
            Lista de Document com metadata V019 em document.meta
        """
        msg.info(f"[V019-Reader] Carregando {fileConfig.filename}")
        
        # Decodifica conteúdo
        try:
            if fileConfig.extension.lower() == "md":
                if isinstance(fileConfig.content, str):
                    # Se já é string (pode acontecer em alguns casos)
                    content = fileConfig.content
                else:
                    # Decodifica base64
                    decoded_bytes = base64.b64decode(fileConfig.content)
                    content = decoded_bytes.decode('utf-8')
            else:
                msg.warn(f"[V019-Reader] Extensão {fileConfig.extension} não suportada, tentando como texto")
                if isinstance(fileConfig.content, str):
                    content = fileConfig.content
                else:
                    decoded_bytes = base64.b64decode(fileConfig.content)
                    content = decoded_bytes.decode('utf-8')
        except Exception as e:
            msg.fail(f"[V019-Reader] Erro ao decodificar conteúdo: {str(e)}")
            raise
        
        # Extrai metadados V019
        metadata = self._extract_v019_metadata(content)
        
        # Cria documento
        document = create_document(content, fileConfig)
        
        # Adiciona metadata V019
        if not document.meta:
            document.meta = {}
        
        # Marca para ETL
        document.meta["enable_etl"] = True
        document.meta["doc_type"] = "v019_consulting_deck"
        document.meta["source_format"] = "v019_markdown"
        
        # Adiciona todos os metadados V019 extraídos
        document.meta.update(metadata)
        
        msg.good(f"[V019-Reader] Documento carregado com {len(metadata.get('slides_metadata', []))} slides processados")
        
        return [document]
    
    def _extract_v019_metadata(self, content: str) -> Dict[str, Any]:
        """
        Extrai metadata específico do formato V019.
        
        Formato esperado:
        - Slides separados por H1 (# Slide X - Título)
        - Metadados por slide em formato **Chave:** valor
        - Pattern Genetics com estrutura específica
        
        Returns:
            Dict com metadata extraído
        """
        metadata = {
            "slides_metadata": [],
            "frameworks": [],  # Agregado de todos os frameworks
            "stakeholders": [],  # Agregado de todos os stakeholders
            "companies": [],  # Extraído de stakeholders se for empresa
            "total_slides": 0,
        }
        
        # Divide conteúdo em slides (por H1)
        slide_pattern = r'^#\s+Slide\s+(\d+)\s*-\s*(.+)$'
        slides = re.split(slide_pattern, content, flags=re.MULTILINE)
        
        # Se não encontrou slides no formato esperado, trata como documento único
        if len(slides) <= 1:
            # Tenta formato alternativo: apenas H1
            slides = re.split(r'^#\s+(.+)$', content, flags=re.MULTILINE)
            if len(slides) <= 1:
                # Documento sem estrutura de slides - extrai metadata global
                slide_meta = self._extract_slide_metadata(content, slide_number=1, slide_title="Documento Completo")
                metadata["slides_metadata"].append(slide_meta)
                metadata["total_slides"] = 1
                # Agrega frameworks e stakeholders
                if slide_meta.get("frameworks"):
                    metadata["frameworks"].extend(slide_meta["frameworks"])
                if slide_meta.get("stakeholders"):
                    metadata["stakeholders"].extend(slide_meta["stakeholders"])
                if slide_meta.get("companies"):
                    metadata["companies"].extend(slide_meta["companies"])
                return metadata
        
        # Processa slides encontrados
        # slides[0] é texto antes do primeiro slide
        # Depois vem pares: (número, título, conteúdo)
        
        slide_index = 0
        for i in range(1, len(slides), 3):
            if i + 1 < len(slides):
                slide_number = slides[i]
                slide_title = slides[i + 1]
                slide_content = slides[i + 2] if i + 2 < len(slides) else ""
                
                # Extrai metadata do slide
                slide_meta = self._extract_slide_metadata(
                    slide_content,
                    slide_number=slide_number,
                    slide_title=slide_title
                )
                
                metadata["slides_metadata"].append(slide_meta)
                slide_index += 1
                
                # Agrega frameworks e stakeholders
                if slide_meta.get("frameworks"):
                    for fw in slide_meta["frameworks"]:
                        if fw not in metadata["frameworks"]:
                            metadata["frameworks"].append(fw)
                
                if slide_meta.get("stakeholders"):
                    for sh in slide_meta["stakeholders"]:
                        if sh not in metadata["stakeholders"]:
                            metadata["stakeholders"].append(sh)
                
                if slide_meta.get("companies"):
                    for comp in slide_meta["companies"]:
                        if comp not in metadata["companies"]:
                            metadata["companies"].append(comp)
        
        metadata["total_slides"] = len(metadata["slides_metadata"])
        
        return metadata
    
    def _extract_slide_metadata(self, slide_content: str, slide_number: str, slide_title: str) -> Dict[str, Any]:
        """
        Extrai metadata de um slide individual.
        
        Args:
            slide_content: Conteúdo do slide
            slide_number: Número do slide
            slide_title: Título do slide
            
        Returns:
            Dict com metadata do slide
        """
        slide_meta = {
            "slide_number": slide_number,
            "slide_title": slide_title,
            "frameworks": [],
            "stakeholders": [],
            "companies": [],
        }
        
        # Extrai frameworks
        fw_match = re.search(r'\*\*Frameworks Deste Slide:\*\*\s*(.+)', slide_content, re.IGNORECASE)
        if fw_match:
            frameworks_str = fw_match.group(1).strip()
            # Remove parênteses com confiança se existir (ex: "BCG Matrix (confiança: 0.95)")
            frameworks_clean = re.sub(r'\s*\([^)]*\)', '', frameworks_str)
            frameworks = [fw.strip() for fw in re.split(r'[,\n]', frameworks_clean) if fw.strip()]
            slide_meta["frameworks"] = frameworks
            
            # Extrai confiança se estiver no formato original
            confidence_match = re.search(r'\(confiança:\s*([\d.]+)\)', frameworks_str, re.IGNORECASE)
            if confidence_match:
                try:
                    slide_meta["framework_confidence"] = float(confidence_match.group(1))
                except:
                    pass
        
        # Extrai stakeholders
        sh_match = re.search(r'\*\*Stakeholders Deste Slide:\*\*\s*(.+)', slide_content, re.IGNORECASE)
        if sh_match:
            stakeholders_str = sh_match.group(1).strip()
            stakeholders = [sh.strip() for sh in re.split(r'[,\n]', stakeholders_str) if sh.strip()]
            slide_meta["stakeholders"] = stakeholders
            
            # Tenta identificar empresas nos stakeholders (heurística simples)
            for sh in stakeholders:
                # Se contém termos comuns de empresas ou está em maiúsculas, pode ser empresa
                if any(term in sh.lower() for term in ['inc', 'ltd', 'corp', 's.a', 'sa', 'ltda', 'banco', 'bank']):
                    if sh not in slide_meta["companies"]:
                        slide_meta["companies"].append(sh)
        
        # Extrai qualidade da ponte semântica
        bridge_match = re.search(r'\*\*Qualidade da Ponte:\*\*\s*([\d.]+)', slide_content, re.IGNORECASE)
        if not bridge_match:
            # Tenta formato alternativo
            bridge_match = re.search(r'Semantic Bridge Quality[:\s]+([\d.]+)', slide_content, re.IGNORECASE)
        if bridge_match:
            try:
                slide_meta["semantic_bridge_quality"] = float(bridge_match.group(1))
            except:
                pass
        
        # Extrai posição do slide
        pos_match = re.search(r'\*\*Posição:\*\*\s*(\w+)', slide_content, re.IGNORECASE)
        if pos_match:
            slide_meta["slide_position"] = pos_match.group(1).strip().lower()
        
        # Extrai tipo do slide
        type_match = re.search(r'\*\*Tipo:\*\*\s*(\w+)', slide_content, re.IGNORECASE)
        if type_match:
            slide_meta["slide_type"] = type_match.group(1).strip().lower()
        
        # Extrai Pattern Genetics
        pattern_genetics = []
        reusability_score = None
        
        # Procura por seção de Pattern Genetics
        pg_section_match = re.search(r'\*\*Pattern Genetics:?\*\*[:\s]*\n(.*?)(?=\n\n|\*\*|\Z)', slide_content, re.DOTALL | re.IGNORECASE)
        if pg_section_match:
            pg_content = pg_section_match.group(1)
            
            # Extrai elementos atômicos
            atomic_match = re.search(r'ELEMENTOS ATÔMICOS[:\s]*\n(.*?)(?=\n-|\n\*\*|\Z)', pg_content, re.DOTALL | re.IGNORECASE)
            if atomic_match:
                atomic_content = atomic_match.group(1)
                # Lista de elementos (formato - item ou * item)
                elements = re.findall(r'[-*]\s*\*\*(.+?)\*\*', atomic_content)
                if not elements:
                    # Tenta formato sem negrito
                    elements = re.findall(r'[-*]\s*(.+?)(?:\n|$)', atomic_content)
                pattern_genetics = [elem.strip() for elem in elements if elem.strip()]
            
            # Extrai reusabilidade
            reuse_match = re.search(r'REUSABILIDADE[:\s]*([\d.]+)%?', pg_content, re.IGNORECASE)
            if reuse_match:
                try:
                    reusability_score = float(reuse_match.group(1))
                except:
                    pass
        
        if pattern_genetics:
            slide_meta["pattern_genetics"] = pattern_genetics
        if reusability_score is not None:
            slide_meta["reusability_score"] = reusability_score
        
        # Extrai Visual Archetype
        archetype_match = re.search(r'\*\*Visual Archetype:\*\*\s*(\w+)', slide_content, re.IGNORECASE)
        if not archetype_match:
            # Tenta formato alternativo
            archetype_match = re.search(r'Archetype[:\s]+(\w+)', slide_content, re.IGNORECASE)
        if archetype_match:
            slide_meta["visual_archetype"] = archetype_match.group(1).strip().lower()
        
        # Extrai dados financeiros se houver
        financial_match = re.search(r'\*\*Dados Financeiros Deste Slide:\*\*\s*(.+)', slide_content, re.IGNORECASE)
        if financial_match:
            slide_meta["financial_data"] = financial_match.group(1).strip()
        
        return slide_meta


def register():
    """
    Registra o plugin V019 Markdown Reader no sistema de extensões.
    """
    return {
        'name': 'v019_markdown_reader',
        'version': '1.0.0',
        'description': 'Reader para arquivos Markdown gerados pelo Sistema V019 de semântica visual',
        'readers': [V019MarkdownReader()],
        'compatible_verba_version': '>=2.1.0',
    }

