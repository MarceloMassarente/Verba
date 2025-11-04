"""
Plugin Manager for Verba

Gerencia plugins que processam chunks durante indexação.
Carrega automaticamente plugins disponíveis e os aplica no pipeline.
"""

import os
import importlib
import logging
from typing import List, Dict, Any, Optional
from goldenverba.components.chunk import Chunk
from goldenverba.components.document import Document

logger = logging.getLogger(__name__)


class PluginManager:
    """
    Gerencia plugins que enriquecem chunks durante indexação.
    
    Plugins devem implementar:
    - async process_chunk(chunk: Chunk, config: Optional[Dict]) -> Chunk
    - async process_batch(chunks: List[Chunk], config: Optional[Dict]) -> List[Chunk]
    - installed: bool
    """
    
    def __init__(self):
        self.plugins: List[Any] = []
        self.enabled_plugins: List[str] = []
        self._load_plugins()
    
    def _load_plugins(self):
        """Carrega plugins disponíveis em verba_extensions/plugins/"""
        plugins_dir = os.path.join(
            os.path.dirname(__file__),
            "..",
            "plugins"
        )
        
        if not os.path.exists(plugins_dir):
            logger.warning(f"Plugins directory not found: {plugins_dir}")
            return
        
        # Plugins conhecidos para carregar
        known_plugins = [
            "llm_metadata_extractor",
            "recursive_document_splitter",
            "reranker",
        ]
        
        for plugin_name in known_plugins:
            try:
                module_path = f"verba_extensions.plugins.{plugin_name}"
                module = importlib.import_module(module_path)
                
                # Procura por factory function ou classe principal
                factory = getattr(module, f"create_{plugin_name}", None)
                if factory:
                    plugin = factory()
                    if hasattr(plugin, "installed") and plugin.installed:
                        self.plugins.append(plugin)
                        self.enabled_plugins.append(plugin_name)
                        logger.info(f"Loaded plugin: {plugin_name}")
                    else:
                        logger.debug(f"Plugin {plugin_name} not installed")
                else:
                    # Tenta criar diretamente se não houver factory
                    plugin_class = getattr(module, f"{plugin_name.title().replace('_', '')}Plugin", None)
                    if plugin_class:
                        plugin = plugin_class()
                        if hasattr(plugin, "installed") and plugin.installed:
                            self.plugins.append(plugin)
                            self.enabled_plugins.append(plugin_name)
                            logger.info(f"Loaded plugin: {plugin_name}")
            except ImportError as e:
                logger.debug(f"Plugin {plugin_name} not available: {e}")
            except Exception as e:
                logger.warning(f"Error loading plugin {plugin_name}: {e}")
    
    async def process_chunks(
        self,
        chunks: List[Chunk],
        config: Optional[Dict[str, Any]] = None
    ) -> List[Chunk]:
        """
        Processa chunks através de todos os plugins habilitados.
        
        Args:
            chunks: Lista de chunks a processar
            config: Configuração opcional por plugin
        
        Returns:
            Chunks processados e enriquecidos
        """
        if not self.plugins:
            logger.debug("No plugins available, returning chunks unchanged")
            return chunks
        
        processed_chunks = chunks
        
        for plugin in self.plugins:
            try:
                if hasattr(plugin, "process_batch"):
                    # Processa em batch se disponível
                    processed_chunks = await plugin.process_batch(
                        processed_chunks,
                        config=config
                    )
                elif hasattr(plugin, "process_chunk"):
                    # Processa individualmente se batch não disponível
                    processed = []
                    for chunk in processed_chunks:
                        processed_chunk = await plugin.process_chunk(
                            chunk,
                            config=config
                        )
                        processed.append(processed_chunk)
                    processed_chunks = processed
                else:
                    logger.warning(f"Plugin {plugin.name} has no process_chunk or process_batch method")
            except Exception as e:
                logger.error(f"Error processing chunks with plugin {plugin.name}: {e}")
                # Continua com próximos plugins mesmo se um falhar
                continue
        
        return processed_chunks
    
    async def process_document_chunks(
        self,
        document: Document,
        config: Optional[Dict[str, Any]] = None
    ) -> Document:
        """
        Processa todos os chunks de um documento através dos plugins.
        
        Args:
            document: Documento com chunks a processar
            config: Configuração opcional
        
        Returns:
            Documento com chunks processados
        """
        if not document.chunks:
            return document
        
        document.chunks = await self.process_chunks(document.chunks, config=config)
        return document
    
    def get_enabled_plugins(self) -> List[str]:
        """Retorna lista de plugins habilitados."""
        return self.enabled_plugins.copy()
    
    def get_plugin_configs(self) -> Dict[str, Dict[str, Any]]:
        """Retorna configuração de todos os plugins."""
        configs = {}
        for plugin in self.plugins:
            if hasattr(plugin, "get_config"):
                configs[plugin.name] = plugin.get_config()
            else:
                configs[plugin.name] = {"status": "active"}
        return configs


# Singleton instance
_plugin_manager: Optional[PluginManager] = None


def get_plugin_manager() -> PluginManager:
    """Retorna instância singleton do PluginManager."""
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = PluginManager()
    return _plugin_manager

