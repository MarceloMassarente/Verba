"""
LLMMetadataExtractor Plugin for Verba

Enriquece chunks com metadata estruturado via LLM durante indexação.
Extrai: empresas, tópicos, sentimento, relações entre entidades, resumos.
"""

import json
import asyncio
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from dataclasses import dataclass, field

# Imports Verba
from goldenverba.components.types import Chunk, VerbaPlugin
from goldenverba.components.generation.AnthrophicGenerator import AnthropicGenerator
from goldenverba.components.util import get_token
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# SCHEMAS PYDANTIC
# ============================================================================

class EntityRelationship(BaseModel):
    """Relação entre entidades"""
    entity: str = Field(..., description="Nome da entidade relacionada")
    relationship_type: str = Field(..., description="Tipo de relação (competitor, partner, etc)")
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)


class EnrichedMetadata(BaseModel):
    """Schema de metadata enriquecido para chunks"""
    companies: List[str] = Field(
        default_factory=list,
        description="Empresas mencionadas no chunk"
    )
    key_topics: List[str] = Field(
        default_factory=list,
        description="Tópicos principais abordados"
    )
    sentiment: str = Field(
        default="neutral",
        description="Sentimento do conteúdo (positive, negative, neutral)"
    )
    entities_relationships: List[EntityRelationship] = Field(
        default_factory=list,
        description="Relações entre entidades mencionadas"
    )
    summary: str = Field(
        default="",
        description="Resumo 1-2 linhas do chunk"
    )
    confidence_score: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Confiança geral da extração (0-1)"
    )
    keywords: List[str] = Field(
        default_factory=list,
        description="Palavras-chave principais para busca"
    )


# ============================================================================
# PLUGIN PRINCIPAL
# ============================================================================

class LLMMetadataExtractorPlugin(VerbaPlugin):
    """
    Plugin para extração e enriquecimento de metadata via LLM.
    
    Processa chunks durante indexação e enriquece com metadata estruturado.
    Suporta batch processing para eficiência e caching de resultados.
    """
    
    def __init__(self):
        self.name = "LLMMetadataExtractor"
        self.description = "Enriquece chunks com metadata estruturado via LLM"
        self.installed = True
        
        # Tentativa de carregar gerador Anthropic, mas não falha se não tiver chave
        try:
            self.generator = AnthropicGenerator()
            self.has_llm = get_token("ANTHROPIC_API_KEY") is not None
        except Exception as e:
            logger.warning(f"LLM não disponível: {e}. Plugin funcionará em modo degradado.")
            self.generator = None
            self.has_llm = False
        
        # Cache de extrações para não reprocessar chunks idênticos
        self.extraction_cache: Dict[str, Dict[str, Any]] = {}
        self.batch_size = 5
        self.max_retries = 3
    
    async def process_chunk(
        self,
        chunk: Chunk,
        config: Optional[Dict[str, Any]] = None
    ) -> Chunk:
        """
        Processa um único chunk e enriquece seu metadata.
        
        Args:
            chunk: Chunk a processar
            config: Configuração opcional
                - llm_model: str (default: "claude-3-5-sonnet-20241022")
                - enable_relationships: bool (default: True)
                - enable_summary: bool (default: True)
        
        Returns:
            Chunk com metadata enriquecido
        """
        if not self.has_llm:
            logger.debug(f"LLM não disponível, pulando enriquecimento de {chunk.uuid}")
            return chunk
        
        config = config or {}
        
        # Tenta extrair do cache
        cache_key = self._get_cache_key(chunk.content)
        if cache_key in self.extraction_cache:
            logger.debug(f"Cache hit para chunk {chunk.uuid}")
            enriched = self.extraction_cache[cache_key]
            chunk.meta["enriched"] = enriched
            return chunk
        
        try:
            # Extrai metadata estruturado
            enriched = await self._extract_metadata(
                chunk.content,
                config
            )
            
            # Cache resultado
            self.extraction_cache[cache_key] = enriched
            
            # Adiciona ao metadata do chunk
            if chunk.meta is None:
                chunk.meta = {}
            chunk.meta["enriched"] = enriched
            
            logger.debug(f"Enriquecido chunk {chunk.uuid}")
            
        except Exception as e:
            logger.error(f"Erro ao enriquecer chunk {chunk.uuid}: {e}")
            # Continua sem enriquecimento
            pass
        
        return chunk
    
    async def process_batch(
        self,
        chunks: List[Chunk],
        config: Optional[Dict[str, Any]] = None
    ) -> List[Chunk]:
        """
        Processa lote de chunks em paralelo para eficiência.
        
        Args:
            chunks: Lista de chunks a processar
            config: Configuração opcional
        
        Returns:
            Chunks processados
        """
        logger.info(f"Processando lote de {len(chunks)} chunks")
        
        tasks = [
            self.process_chunk(chunk, config)
            for chunk in chunks
        ]
        
        # Processa em paralelo mas limita concorrência
        processed = []
        for i in range(0, len(tasks), self.batch_size):
            batch = tasks[i:i + self.batch_size]
            batch_results = await asyncio.gather(*batch, return_exceptions=True)
            
            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"Erro em batch: {result}")
                else:
                    processed.append(result)
        
        logger.info(f"Lote processado: {len(processed)}/{len(chunks)} chunks")
        return processed
    
    # ========================================================================
    # MÉTODOS PRIVADOS
    # ========================================================================
    
    async def _extract_metadata(
        self,
        text: str,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Extrai metadata estruturado do texto usando LLM.
        
        Args:
            text: Conteúdo do chunk
            config: Configuração
        
        Returns:
            Dicionário com metadata enriquecido
        """
        if not self.has_llm:
            return {}
        
        # Limita tamanho do texto para não explodir tokens
        text_preview = text[:1000]
        
        prompt = self._build_extraction_prompt(text_preview)
        
        # Retenta com backoff em caso de erro
        for attempt in range(self.max_retries):
            try:
                response = await asyncio.to_thread(
                    self._call_llm,
                    prompt
                )
                
                # Parse JSON response
                enriched = self._parse_extraction_response(response)
                return enriched
                
            except json.JSONDecodeError as e:
                logger.warning(f"Erro parsing JSON (tentativa {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                else:
                    return {}
            except Exception as e:
                logger.error(f"Erro na extração (tentativa {attempt + 1}): {e}")
                if attempt == self.max_retries - 1:
                    return {}
                await asyncio.sleep(2 ** attempt)
        
        return {}
    
    def _call_llm(self, prompt: str) -> str:
        """
        Chama LLM sincronamente (será rodado em thread pool).
        
        Args:
            prompt: Prompt para LLM
        
        Returns:
            Resposta do LLM
        """
        if not self.generator:
            return "{}"
        
        try:
            # Usa gerador Anthropic com response format JSON
            response = self.generator.generate(
                prompt=prompt,
                max_tokens=500,
                temperature=0.3
            )
            return response if response else "{}"
        except Exception as e:
            logger.error(f"Erro LLM call: {e}")
            return "{}"
    
    def _build_extraction_prompt(self, text: str) -> str:
        """
        Constrói prompt para extração de metadata.
        
        Args:
            text: Conteúdo a analisar
        
        Returns:
            Prompt estruturado
        """
        return f"""Analise o seguinte texto e extraia metadata estruturado em JSON.

TEXTO:
{text}

Retorne um JSON com a seguinte estrutura (use apenas quando encontrar informações):
{{
    "companies": ["lista de empresas mencionadas"],
    "key_topics": ["tópicos principais abordados"],
    "sentiment": "positive|negative|neutral",
    "entities_relationships": [
        {{"entity": "nome da entidade", "relationship_type": "tipo de relação", "confidence": 0.8}}
    ],
    "summary": "resumo 1-2 linhas do conteúdo principal",
    "confidence_score": 0.8,
    "keywords": ["palavras-chave principais para busca"]
}}

Responda APENAS com o JSON, sem explicações adicionais.
Confie confiança baixa (0.5-0.7) para inferências, alta (0.8-1.0) para menções diretas."""
    
    def _parse_extraction_response(self, response: str) -> Dict[str, Any]:
        """
        Parse response JSON do LLM.
        
        Args:
            response: String JSON da resposta
        
        Returns:
            Dicionário com metadata validado
        """
        try:
            # Tenta fazer parse do JSON
            data = json.loads(response)
            
            # Valida com Pydantic
            enriched = EnrichedMetadata(**data)
            
            # Converte para dict para armazenar
            return enriched.model_dump()
        
        except json.JSONDecodeError:
            # Tenta extrair JSON do response se houver outros textos
            import re
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                return self._parse_extraction_response(match.group())
            raise
        except Exception as e:
            logger.error(f"Erro validação Pydantic: {e}")
            raise
    
    def _get_cache_key(self, content: str) -> str:
        """
        Gera chave de cache baseada no conteúdo.
        
        Args:
            content: Conteúdo do chunk
        
        Returns:
            Hash do conteúdo
        """
        import hashlib
        return hashlib.md5(content[:500].encode()).hexdigest()
    
    # ========================================================================
    # INTERFACE DO PLUGIN VERBA
    # ========================================================================
    
    def get_config(self) -> Dict[str, Any]:
        """Retorna configuração do plugin."""
        return {
            "name": self.name,
            "description": self.description,
            "cache_size": len(self.extraction_cache),
            "has_llm": self.has_llm,
            "batch_size": self.batch_size
        }
    
    def install(self) -> bool:
        """Instala o plugin."""
        self.installed = True
        logger.info("LLMMetadataExtractor instalado")
        return True
    
    def uninstall(self) -> bool:
        """Desinstala o plugin."""
        self.installed = False
        self.extraction_cache.clear()
        logger.info("LLMMetadataExtractor desinstalado")
        return True


# ============================================================================
# FACTORY
# ============================================================================

def create_llm_metadata_extractor() -> LLMMetadataExtractorPlugin:
    """Factory para criar instância do plugin."""
    return LLMMetadataExtractorPlugin()
