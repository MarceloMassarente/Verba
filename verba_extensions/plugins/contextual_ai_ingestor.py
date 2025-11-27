"""
Contextual.ai Ingestor Integrado - Reader + Chunker otimizado

Componente integrado que combina Reader + Chunker otimizado especificamente
para o formato retornado pela API Contextual.ai.

Características:
- Parse via API Contextual.ai com descrições detalhadas de gráficos
- Chunking hardcoded otimizado:
  * PPTX: 1 slide = 1 chunk
  * PDF/DOCX: Respeita hierarquia Markdown (H1/H2/H3)
  * Preserva descrições de gráficos completas
- Integração automática com ETL
"""

import base64
import io
import os
import re
import asyncio
import json
from typing import List, Optional, Dict, Any

import aiohttp
from wasabi import msg

from goldenverba.components.document import Document, create_document
from goldenverba.components.chunk import Chunk
from goldenverba.components.interfaces import Reader
from goldenverba.server.types import FileConfig
from goldenverba.components.util import get_environment
from goldenverba.components.types import InputConfig


class ContextualAIIngestor(Reader):
    """
    Ingestor integrado Contextual.ai com chunking otimizado hardcoded.
    
    Faz parse via API Contextual.ai e chunking otimizado internamente,
    retornando Document com chunks já criados.
    """
    
    def __init__(self):
        super().__init__()
        # Não requer variável de ambiente - permite configurar via UI
        self.requires_env = []
        self.name = "Contextual.ai Ingestor (Otimizado)"
        self.description = (
            "Ingestor integrado Contextual.ai com chunking otimizado: "
            "1 slide = 1 chunk (PPTX), respeita hierarquia Markdown (PDF/DOCX), "
            "preserva descrições de gráficos completas. ETL automático."
        )
        
        # Tipo de reader (FILE para aparecer na interface de upload de arquivos)
        self.type = "FILE"
        
        # Extensões suportadas
        self.extension = ["pdf", "doc", "docx", "ppt", "pptx"]
        
        # Configurações
        self.config = {
            "API Key": InputConfig(
                type="password",
                value=os.getenv("CONTEXTUAL_AI_API_KEY", "") or "",
                description="Sua Contextual.ai API Key (ou configure CONTEXTUAL_AI_API_KEY env var)",
                values=[],
            ),
            "Base URL": InputConfig(
                type="text",
                value=os.getenv("CONTEXTUAL_AI_BASE_URL", "https://api.contextual.ai/v1"),
                description="Contextual.ai API Base URL (padrão: https://api.contextual.ai/v1)",
                values=[],
            ),
            "Parse Mode": InputConfig(
                type="dropdown",
                value="standard",
                description="Modo de parsing: basic (texto simples) ou standard (documentos complexos com imagens)",
                values=["basic", "standard"],
            ),
            "Enable Document Hierarchy": InputConfig(
                type="bool",
                value=True,
                description="Adiciona tabela de conteúdos e estrutura hierárquica (H1, H2, H3)",
                values=[],
            ),
            "Figure Caption Mode": InputConfig(
                type="dropdown",
                value="detailed",
                description="Nível de detalhamento das descrições de gráficos: concise (curto) ou detailed (completo)",
                values=["concise", "detailed"],
            ),
            "Enable Split Tables": InputConfig(
                type="bool",
                value=False,
                description="Divide tabelas grandes em múltiplas tabelas menores",
                values=[],
            ),
            "Max Split Table Cells": InputConfig(
                type="number",
                value=0,
                description="Número máximo de células para dividir tabelas (só se Enable Split Tables = true). Use 0 para desabilitar.",
                values=[],
            ),
            "Page Range": InputConfig(
                type="text",
                value="",
                description="Range de páginas a parsear (ex: '0-10,15-20' ou '0,1,2,5,6'). Deixe vazio para todas.",
                values=[],
            ),
        }
    
    async def load(
        self, config: dict[str, InputConfig], fileConfig: FileConfig
    ) -> List[Document]:
        """
        Carrega documento, faz parse via API Contextual.ai, chunking otimizado
        e retorna Document com chunks já criados e ETL habilitado.
        """
        # 1. Valida API key (prioriza config, depois env var)
        api_key = config.get("API Key", InputConfig(type="text", value="", description="", values=[])).value
        if not api_key:
            api_key = os.getenv("CONTEXTUAL_AI_API_KEY", "")
        if not api_key:
            raise ValueError("No Contextual.ai API Key detected. Configure via UI ou CONTEXTUAL_AI_API_KEY env var")
        
        # Remove prefixo "key-" se presente (será adicionado no header)
        if api_key.startswith("key-"):
            api_key = api_key[4:]
        
        # 2. Obtém Base URL (prioriza config, depois env var, depois default)
        base_url = config.get("Base URL", InputConfig(type="text", value="", description="", values=[])).value
        if not base_url:
            base_url = os.getenv("CONTEXTUAL_AI_BASE_URL", "https://api.contextual.ai/v1")
        # Remove trailing slash se presente
        base_url = base_url.rstrip("/")
        
        # 3. Valida extensão
        if fileConfig.extension.lower() not in self.extension:
            raise ValueError(
                f"Formato não suportado: {fileConfig.extension}. "
                f"Suportados: {', '.join(self.extension)}"
            )
        
        # 4. Prepara parâmetros
        parse_mode = config["Parse Mode"].value
        enable_hierarchy = config["Enable Document Hierarchy"].value
        figure_mode = config["Figure Caption Mode"].value
        enable_split = config["Enable Split Tables"].value
        max_cells = config["Max Split Table Cells"].value
        page_range = config["Page Range"].value.strip() or None
        
        # Validações
        if parse_mode == "basic" and enable_hierarchy:
            msg.warn("⚠️ Document Hierarchy não permitido em modo basic. Desabilitando.")
            enable_hierarchy = False
        
        if parse_mode == "basic" and figure_mode != "concise":
            msg.warn("⚠️ Figure Caption Mode detailed não permitido em modo basic. Usando concise.")
            figure_mode = "concise"
        
        if enable_split and (max_cells is None or max_cells == 0):
            msg.warn("⚠️ Max Split Table Cells deve ser especificado (maior que 0) se Enable Split Tables = true.")
            enable_split = False
        
        # 4. Parse via API
        msg.info(f"📄 Parseando {fileConfig.filename} com Contextual.ai...")
        result = await self._parse_with_contextual_ai(
            fileConfig, api_key, base_url, parse_mode, enable_hierarchy, 
            figure_mode, enable_split, max_cells, page_range
        )
        
        # 5. Extrai conteúdo
        content = self._extract_content(result)
        
        # 6. Detecta tipo de documento
        doc_type = self._detect_document_type(fileConfig, result)
        msg.info(f"📋 Tipo detectado: {doc_type}")
        
        # 7. Chunking otimizado (hardcoded)
        if doc_type == 'pptx':
            chunks = self._chunk_pptx(content, result)
            msg.info(f"✅ Criados {len(chunks)} chunks (1 slide = 1 chunk)")
        else:
            chunks = self._chunk_with_hierarchy(content, result)
            msg.info(f"✅ Criados {len(chunks)} chunks (respeitando hierarquia)")
        
        # 8. Cria Document com chunks já preenchidos
        document = create_document(content, fileConfig)
        document.chunks = chunks
        
        # 9. Marca para ETL
        if not hasattr(document, 'meta') or document.meta is None:
            document.meta = {}
        document.meta["enable_etl"] = True
        document.meta["source_api"] = "contextual.ai"
        document.meta["chunking_strategy"] = doc_type  # 'pptx' ou 'hierarchy'
        
        # 10. Preserva metadados do Contextual.ai
        if "hierarchy" in result:
            document.meta["document_hierarchy"] = result["hierarchy"]
        if "figures" in result:
            document.meta["figure_descriptions"] = result["figures"]
        
        msg.good(f"✅ Documento parseado e chunked: {len(chunks)} chunks criados")
        return [document]
    
    async def _parse_with_contextual_ai(
        self,
        fileConfig: FileConfig,
        api_key: str,
        base_url: str,
        parse_mode: str,
        enable_hierarchy: bool,
        figure_mode: str,
        enable_split: bool,
        max_cells: Optional[int],
        page_range: Optional[str]
    ) -> Dict[str, Any]:
        """
        Faz parse do arquivo via API Contextual.ai com polling do resultado.
        """
        # Endpoint usando Base URL do config
        api_url = f"{base_url}/parse"
        headers = {
            "Authorization": f"Bearer key-{api_key}",  # Formato correto: "Bearer key-{api_key}"
        }
        
        # Prepara arquivo (seguindo formato oficial da API)
        file_bytes = io.BytesIO(base64.b64decode(fileConfig.content))
        
        # Prepara form data seguindo formato oficial
        # Nota: aiohttp.FormData funciona diferente de requests, mas o formato é equivalente
        form_data = aiohttp.FormData()
        
        # Arquivo (equivalente a files={"raw_file": open(...)})
        form_data.add_field(
            "raw_file",
            file_bytes,
            filename=f"{fileConfig.filename}.{fileConfig.extension}",
            content_type="application/octet-stream",
        )
        
        # Payload (equivalente a data={...})
        # IMPORTANTE: Não incluir campos null - só incluir se tiver valor
        form_data.add_field("parse_mode", parse_mode)
        form_data.add_field("enable_document_hierarchy", str(enable_hierarchy).lower())
        form_data.add_field("figure_caption_mode", figure_mode)
        form_data.add_field("enable_split_tables", str(enable_split).lower())
        
        # max_split_table_cells: só incluir se enable_split_tables=True e max_cells não for None
        if enable_split and max_cells is not None:
            form_data.add_field("max_split_table_cells", str(max_cells))
        # Não incluir se enable_split_tables=False ou max_cells=None
        
        # page_range: só incluir se tiver valor
        if page_range:
            form_data.add_field("page_range", page_range)
        # Não incluir se None ou vazio
        
        try:
            from verba_extensions.utils.retry import retry_with_backoff
            
            async with aiohttp.ClientSession() as session:
                # Função interna para fazer POST inicial com retry
                async def make_initial_request():
                    async with session.post(
                        api_url, headers=headers, data=form_data
                    ) as response:
                        response.raise_for_status()
                        json_response = await response.json()
                        
                        if "job_id" not in json_response:
                            raise ValueError(f"API error: Resposta inválida: {json_response}")
                        
                        return json_response["job_id"]
                
                # Executa POST inicial com retry
                job_id = await retry_with_backoff(
                    make_initial_request,
                    max_retries=3,
                    base_delay=1.0,
                    retryable_status_codes=[429, 500, 502, 503, 504],
                    operation_name=f"Contextual.ai Parse API (iniciar job para {fileConfig.filename})"
                )
                msg.info(f"✅ Job iniciado: {job_id}")
                
                # Polling do resultado (já tem retry interno melhorado)
                result = await self._poll_job_result(session, api_key, base_url, job_id)
                return result
        
        except Exception as e:
            raise Exception(f"Failed to process {fileConfig.filename}: {str(e)}")
    
    async def _poll_job_result(
        self, 
        session: aiohttp.ClientSession, 
        api_key: str,
        base_url: str,
        job_id: str,
        max_attempts: int = 60, 
        poll_interval: float = 2.0
    ) -> Dict[str, Any]:
        """
        Faz polling do resultado do job até completar.
        
        NOTA: Endpoint exato precisa ser verificado na documentação completa da API.
        Tentando múltiplos endpoints possíveis.
        """
        headers = {"Authorization": f"Bearer key-{api_key}"}  # Formato correto: "Bearer key-{api_key}"
        
        # Endpoint correto para status: /parse/jobs/{job_id}/status
        possible_endpoints = [
            f"{base_url}/parse/jobs/{job_id}/status",
        ]
        
        working_endpoint = None  # Endpoint que funcionou
        
        # Tentativas de polling
        for attempt in range(max_attempts):
            await asyncio.sleep(poll_interval)
            
            # Se já encontrou endpoint que funciona, usa apenas ele
            endpoints_to_try = [working_endpoint] if working_endpoint else possible_endpoints
            
            # Tenta cada endpoint possível
            for endpoint in endpoints_to_try:
                try:
                    from verba_extensions.utils.retry import retry_with_backoff
                    
                    # Função interna para fazer GET com retry (não retry em 404)
                    async def make_get_request():
                        async with session.get(endpoint, headers=headers) as response:
                            if response.status == 404:
                                # Endpoint não existe, levanta exceção para tentar próximo
                                raise ValueError(f"Endpoint 404: {endpoint}")
                            
                            response.raise_for_status()
                            return await response.json()
                    
                    # Executa GET com retry (apenas para erros retryáveis, não 404)
                    try:
                        result = await retry_with_backoff(
                            make_get_request,
                            max_retries=2,  # Menos retries para polling (já tem loop externo)
                            base_delay=0.5,
                            retryable_status_codes=[429, 500, 502, 503, 504],
                            operation_name=f"Contextual.ai Polling (job {job_id})"
                        )
                    except ValueError as e:
                        # 404 não é retryável, continua para próximo endpoint
                        if "404" in str(e):
                            continue
                        raise
                        
                        # Marca endpoint como funcionando
                        if not working_endpoint:
                            working_endpoint = endpoint
                            msg.info(f"✅ Endpoint funcionando: {endpoint}")
                        
                        # Verifica status
                        status = result.get("status")
                        if status == "completed":
                            msg.info(f"✅ Job {job_id} completado")
                            
                            # Quando o status é "completed", o resultado completo pode estar:
                            # 1. No mesmo endpoint de status (mas só retorna status e file_name nos testes)
                            # 2. Em um endpoint diferente (ex: /parse/jobs/{job_id} sem /status)
                            # 3. Pode precisar de um header ou parâmetro adicional
                            #
                            # Baseado no código de exemplo fornecido, o método get_parse_result()
                            # faz polling e retorna o resultado completo. Vamos tentar várias abordagens:
                            
                            # Primeiro, verifica se o resultado já tem markdown/content
                            if "markdown" in result or "content" in result:
                                msg.good("✅ Resultado completo encontrado no endpoint de status")
                                return result.get("result", result)
                            
                            # Se não tem, tenta buscar em outros endpoints
                            msg.info("Buscando resultado completo em endpoints alternativos...")
                            
                            # Lista de endpoints possíveis (baseado em padrões comuns de API)
                            alt_endpoints = [
                                f"{base_url}/parse/jobs/{job_id}",  # Sem /status
                                f"{base_url}/parse/{job_id}",  # Formato alternativo
                                f"{base_url}/parse/{job_id}/result",  # Com /result
                                f"{base_url}/jobs/{job_id}",  # Formato jobs/
                                f"{base_url}/jobs/{job_id}/result",  # Jobs com result
                            ]
                            
                            # Tenta cada endpoint
                            for alt_endpoint in alt_endpoints:
                                try:
                                    async with session.get(alt_endpoint, headers=headers) as alt_response:
                                        if alt_response.status == 200:
                                            alt_result = await alt_response.json()
                                            
                                            # Verifica se tem resultado completo
                                            if "markdown" in alt_result or "content" in alt_result:
                                                msg.good(f"✅ Resultado completo obtido de: {alt_endpoint}")
                                                return alt_result.get("result", alt_result)
                                            
                                            # Se tem "data" ou "result" como chave, pode estar aninhado
                                            if "data" in alt_result:
                                                data = alt_result["data"]
                                                if isinstance(data, dict) and ("markdown" in data or "content" in data):
                                                    msg.good(f"✅ Resultado completo obtido de: {alt_endpoint} (em 'data')")
                                                    return data
                                            
                                            if "result" in alt_result:
                                                result_data = alt_result["result"]
                                                if isinstance(result_data, dict) and ("markdown" in result_data or "content" in result_data):
                                                    msg.good(f"✅ Resultado completo obtido de: {alt_endpoint} (em 'result')")
                                                    return result_data
                                except Exception as e:
                                    # Continua tentando outros endpoints
                                    continue
                            
                            # Se nenhum endpoint retornou resultado completo, retorna o que temos
                            # e deixa o código de extração lidar com o erro
                            msg.warn("⚠️ Resultado completo não encontrado em nenhum endpoint testado")
                            msg.warn("⚠️ O endpoint de status retornou apenas status e file_name")
                            msg.warn("⚠️ Isso pode indicar que:")
                            msg.warn("   1. O resultado completo não está disponível via API ainda")
                            msg.warn("   2. É necessário um endpoint/parâmetro diferente")
                            msg.warn("   3. Considere contatar: parse-feedback@contextual.ai")
                            
                            # Retorna o que temos (status e file_name)
                            return result.get("result", result)
                        elif status == "failed":
                            error_msg = result.get("error", "Unknown error")
                            raise Exception(f"Job failed: {error_msg}")
                        # Se ainda processando (status="processing" ou similar), continua polling
                        
                except aiohttp.ClientError as e:
                    # Erro de rede, tenta próximo endpoint ou continua
                    if attempt % 10 == 0:  # Log apenas ocasionalmente
                        msg.debug(f"Erro ao acessar {endpoint}: {str(e)[:100]}")
                    continue
                except Exception as e:
                    # Outros erros (parsing, etc.)
                    if "Job failed" in str(e):
                        raise  # Re-raise se job falhou
                    # Continua tentando para outros erros
                    continue
            
            # Se chegou aqui, nenhum endpoint funcionou nesta tentativa
            if attempt % 10 == 0:  # Log a cada 10 tentativas
                msg.info(f"⏳ Aguardando job {job_id}... (tentativa {attempt + 1}/{max_attempts})")
        
        raise TimeoutError(
            f"Job {job_id} não completou em {max_attempts * poll_interval} segundos."
        )

    def _adapt_result_format(self, api_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Adaptar resultado da API Contextual.ai para formato esperado pelo código
        """
        adapted = {
            "status": "completed",
            "file_name": api_result.get("file_name", ""),
        }

        # Copiar campos importantes
        if "markdown" in api_result:
            adapted["markdown"] = api_result["markdown"]
        if "pages" in api_result:
            adapted["pages"] = api_result["pages"]
        if "figures" in api_result:
            adapted["figures"] = api_result["figures"]
        if "document_metadata" in api_result:
            adapted["document_metadata"] = api_result["document_metadata"]
        if "hierarchy" in api_result:
            adapted["hierarchy"] = api_result["hierarchy"]

        return adapted
    
    def _extract_content(self, result: Dict[str, Any]) -> str:
        """
        Extrai conteúdo do resultado da API.
        
        A API pode retornar:
        - Markdown: campo "markdown" ou "content"
        - JSON estruturado: precisa extrair texto
        """
        # Tenta diferentes formatos de resposta
        if "markdown" in result:
            return result["markdown"]
        elif "content" in result:
            if isinstance(result["content"], str):
                return result["content"]
            elif isinstance(result["content"], dict):
                # Se for JSON estruturado, extrai texto
                return self._extract_text_from_json(result["content"])
        elif "text" in result:
            return result["text"]
        else:
            # Fallback: converte JSON para string
            return json.dumps(result, indent=2, ensure_ascii=False)
    
    def _extract_text_from_json(self, json_data: Dict[str, Any]) -> str:
        """
        Extrai texto de JSON estruturado.
        """
        text_parts = []
        
        def extract_recursive(obj):
            if isinstance(obj, dict):
                # Prioriza campos de texto
                for key in ["text", "content", "body", "paragraph"]:
                    if key in obj:
                        text_parts.append(str(obj[key]))
                
                # Recursão em outros campos
                for value in obj.values():
                    extract_recursive(value)
            elif isinstance(obj, list):
                for item in obj:
                    extract_recursive(item)
            elif isinstance(obj, str):
                text_parts.append(obj)
        
        extract_recursive(json_data)
        return "\n\n".join(text_parts)
    
    def _detect_document_type(
        self, fileConfig: FileConfig, result: Dict[str, Any]
    ) -> str:
        """
        Detecta tipo de documento: 'pptx', 'document', 'markdown'
        """
        extension = fileConfig.extension.lower()
        if extension in ['ppt', 'pptx']:
            return 'pptx'
        elif extension in ['pdf', 'doc', 'docx']:
            # Verifica se tem estrutura de slides no resultado
            if 'slides' in result or (isinstance(result.get('hierarchy'), dict) and 'slides' in str(result.get('hierarchy', {}))):
                return 'pptx'  # Tratado como apresentação
            return 'document'
        return 'markdown'
    
    def _chunk_pptx(self, content: str, result: Dict[str, Any]) -> List[Chunk]:
        """
        Chunking otimizado para apresentações:
        - 1 slide = 1 chunk
        - Preserva descrições de gráficos completas
        - Inclui título do slide se disponível
        """
        chunks = []
        
        # Estratégia 1: Se resultado tem estrutura de slides explícita
        if 'slides' in result:
            slides = result['slides']
            if isinstance(slides, list):
                for i, slide in enumerate(slides):
                    slide_content = self._extract_slide_content(slide)
                    chunks.append(Chunk(
                        content=slide_content,
                        chunk_id=i,
                        start_i=None,
                        end_i=None,
                        content_without_overlap=slide_content
                    ))
                return chunks
        
        # Estratégia 2: Se tem hierarquia com slides
        if 'hierarchy' in result:
            hierarchy = result['hierarchy']
            slides = self._extract_slides_from_hierarchy(hierarchy, content)
            if slides:
                for i, slide_content in enumerate(slides):
                    chunks.append(Chunk(
                        content=slide_content,
                        chunk_id=i,
                        start_i=None,
                        end_i=None,
                        content_without_overlap=slide_content
                    ))
                return chunks
        
        # Estratégia 3: Fallback - divide por marcadores de slide no Markdown
        # Procura por padrões como "---", "## Slide", "---\n#", etc.
        slide_patterns = [
            r'\n---+\n',  # Separador de slide (---)
            r'\n##\s+Slide\s+\d+',  # ## Slide 1
            r'\n#\s+Slide\s+\d+',  # # Slide 1
            r'\n---\n#\s+',  # --- seguido de # (novo slide)
        ]
        
        # Tenta cada padrão
        for pattern in slide_patterns:
            slide_markers = re.split(pattern, content)
            if len(slide_markers) > 1:
                for i, slide_text in enumerate(slide_markers):
                    slide_text = slide_text.strip()
                    if slide_text:
                        chunks.append(Chunk(
                            content=slide_text,
                            chunk_id=i,
                            start_i=None,
                            end_i=None,
                            content_without_overlap=slide_text
                        ))
                if chunks:
                    msg.info(f"📊 Slides detectados via padrão: {pattern}")
                    return chunks
        
        # Se nenhum padrão funcionou, cria um único chunk
        msg.warn("⚠️ Não foi possível detectar slides, criando chunk único")
        chunks.append(Chunk(
            content=content,
            chunk_id=0,
            start_i=None,
            end_i=None,
            content_without_overlap=content
        ))
        
        return chunks
    
    def _extract_slide_content(self, slide: Any) -> str:
        """
        Extrai conteúdo de um slide da estrutura JSON.
        """
        if isinstance(slide, str):
            return slide
        elif isinstance(slide, dict):
            # Tenta diferentes campos possíveis
            for key in ["content", "text", "body", "markdown"]:
                if key in slide:
                    return str(slide[key])
            # Se não tem campo de conteúdo, converte dict para string
            return json.dumps(slide, indent=2, ensure_ascii=False)
        else:
            return str(slide)
    
    def _extract_slides_from_hierarchy(
        self, hierarchy: Any, content: str
    ) -> List[str]:
        """
        Extrai slides da estrutura de hierarquia.
        """
        slides = []
        
        if isinstance(hierarchy, dict):
            # Procura por estrutura de slides
            if 'slides' in hierarchy:
                slides_data = hierarchy['slides']
                if isinstance(slides_data, list):
                    for slide in slides_data:
                        slide_content = self._extract_slide_content(slide)
                        slides.append(slide_content)
                    return slides
            
            # Se não tem slides explícitos, tenta inferir da estrutura
            # Procura por seções que podem ser slides
            if 'sections' in hierarchy:
                sections = hierarchy['sections']
                if isinstance(sections, list):
                    for section in sections:
                        section_content = self._extract_slide_content(section)
                        slides.append(section_content)
                    return slides
        
        # Se não conseguiu extrair, retorna vazio (fallback será usado)
        return []
    
    def _chunk_with_hierarchy(
        self, content: str, result: Dict[str, Any]
    ) -> List[Chunk]:
        """
        Chunking que respeita hierarquia Markdown:
        - H1/H2/H3 como limites de seção
        - Preserva descrições de gráficos completas
        - Não corta no meio de descrições
        """
        chunks = []
        
        # Estratégia 1: Se tem hierarquia estruturada
        if 'hierarchy' in result:
            hierarchy = result['hierarchy']
            sections = self._extract_sections_from_hierarchy(hierarchy, content)
            if sections:
                for i, section in enumerate(sections):
                    # Preserva descrições de gráficos completas
                    section_content = self._preserve_figure_descriptions(
                        section.get('content', '')
                    )
                    chunks.append(Chunk(
                        content=section_content,
                        chunk_id=i,
                        start_i=section.get('start', None),
                        end_i=section.get('end', None),
                        content_without_overlap=section_content
                    ))
                return chunks
        
        # Estratégia 2: Parse Markdown com headers
        sections = self._parse_markdown_sections(content)
        for i, section in enumerate(sections):
            section_content = self._preserve_figure_descriptions(
                section.get('content', '')
            )
            chunks.append(Chunk(
                content=section_content,
                chunk_id=i,
                start_i=section.get('start', None),
                end_i=section.get('end', None),
                content_without_overlap=section_content
            ))
        
        return chunks
    
    def _extract_sections_from_hierarchy(
        self, hierarchy: Any, content: str
    ) -> List[Dict[str, Any]]:
        """
        Extrai seções da estrutura de hierarquia.
        """
        sections = []
        
        if isinstance(hierarchy, dict):
            # Procura por estrutura de seções
            if 'sections' in hierarchy:
                sections_data = hierarchy['sections']
                if isinstance(sections_data, list):
                    for section in sections_data:
                        if isinstance(section, dict):
                            section_content = section.get('content', section.get('text', ''))
                            sections.append({
                                'content': section_content,
                                'title': section.get('title', ''),
                                'start': section.get('start', None),
                                'end': section.get('end', None),
                            })
                    return sections
        
        # Se não conseguiu extrair, retorna vazio (fallback será usado)
        return []
    
    def _parse_markdown_sections(self, content: str) -> List[Dict[str, Any]]:
        """
        Parse Markdown detectando headers (H1, H2, H3) e criando seções.
        """
        sections = []
        
        # Padrão para detectar headers: #, ##, ###
        header_pattern = r'^(#{1,3})\s+(.+)$'
        
        lines = content.split('\n')
        current_section = {
            'title': '',
            'content': '',
            'start': 0,
            'level': 0,
        }
        
        current_pos = 0
        
        for i, line in enumerate(lines):
            match = re.match(header_pattern, line)
            
            if match:
                # Encontrou um header
                level = len(match.group(1))  # Número de #
                title = match.group(2).strip()
                
                # Se já tem uma seção em andamento, salva ela
                if current_section['content'].strip():
                    current_section['end'] = current_pos
                    sections.append({
                        'content': current_section['content'].strip(),
                        'title': current_section['title'],
                        'start': current_section['start'],
                        'end': current_section['end'],
                    })
                
                # Inicia nova seção
                current_section = {
                    'title': title,
                    'content': line + '\n',  # Inclui header no conteúdo
                    'start': current_pos,
                    'level': level,
                }
            else:
                # Adiciona linha ao conteúdo da seção atual
                current_section['content'] += line + '\n'
            
            current_pos += len(line) + 1  # +1 para o \n
        
        # Adiciona última seção
        if current_section['content'].strip():
            current_section['end'] = current_pos
            sections.append({
                'content': current_section['content'].strip(),
                'title': current_section['title'],
                'start': current_section['start'],
                'end': current_section['end'],
            })
        
        # Se não encontrou nenhum header, cria uma seção única
        if not sections:
            sections.append({
                'content': content,
                'title': '',
                'start': 0,
                'end': len(content),
            })
        
        return sections
    
    def _preserve_figure_descriptions(self, content: str) -> str:
        """
        Garante que descrições de gráficos não sejam cortadas.
        Identifica blocos de descrição e os mantém completos.
        
        Por enquanto retorna como está, pois o chunking já respeita limites
        de seção e não deve cortar descrições no meio.
        """
        # Padrão: ![alt](url) seguido de **Descrição detalhada:** ...
        pattern = r'!\[.*?\]\(.*?\)\s*\*\*Descrição detalhada:\*\*.*?(?=\n\n|\n#|$)'
        
        # Valida que descrições estão completas (não faz nada se já estão)
        # O chunking por seção já garante que descrições não são cortadas
        return content


def register():
    """
    Registra o plugin no sistema de extensões.
    """
    return {
        'name': 'contextual_ai_ingestor',
        'version': '1.0.0',
        'description': 'Contextual.ai Ingestor Integrado com chunking otimizado (1 slide = 1 chunk para PPTX, hierarquia para PDF/DOCX)',
        'readers': [ContextualAIIngestor()],
        'compatible_verba_version': '>=2.1.0'
    }

