"""
Startup script para inicializar extensões do Verba
Este arquivo é chamado antes do Verba iniciar para carregar plugins
"""

import os
import sys
from pathlib import Path
from wasabi import msg
# Fix: Adicionar método debug ao msg se não existir (compatibilidade)
# O objeto Printer do wasabi não tem método debug, mas alguns códigos podem tentar usá-lo
if not hasattr(msg, 'debug'):
    def debug_wrapper(*args, **kwargs):
        # Fallback para info se debug não existir
        msg.info(*args, **kwargs)
    msg.debug = debug_wrapper

def initialize_extensions():
    """
    Inicializa sistema de extensões do Verba
    Deve ser chamado ANTES de importar goldenverba.server.api
    """
    try:
        from verba_extensions.plugin_manager import PluginManager
        from verba_extensions.version_checker import VersionChecker
        
        # Inicializa managers
        plugin_manager = PluginManager()
        version_checker = VersionChecker()
        
        # Verifica compatibilidade
        version_info = version_checker.get_version_info()
        msg.info(f"Verba version: {version_info['verba_version']}")
        
        compatibility = version_checker.check_api_changes()
        for component, status in compatibility.items():
            if not status['compatible']:
                msg.warn(f"Incompatibilidade detectada em {component}: {', '.join(status['changes'])}")
        
        # Carrega plugins
        plugins_dir = os.getenv("VERBA_PLUGINS_DIR", "verba_extensions/plugins")
        plugin_manager.load_plugins_from_dir(plugins_dir)
        
        # Aplica hooks
        plugin_manager.apply_hooks()
        
        # Aplica compatibilidade com Weaviate v3 (se necessário)
        try:
            from verba_extensions.compatibility.weaviate_v3_patch import patch_weaviate_manager_for_v3
            patch_weaviate_manager_for_v3()
        except Exception as e:
            msg.warn(f"Patch de compatibilidade v3 não aplicado: {str(e)}")
        
        # Aplica hooks de integração (ETL)
        try:
            from verba_extensions.integration.import_hook import patch_weaviate_manager, patch_verba_manager
            patch_weaviate_manager()  # Hook principal no WeaviateManager
            patch_verba_manager()  # Hook adicional se necessário
        except Exception as e:
            msg.warn(f"Hook de integração ETL não aplicado: {str(e)}")
        
        # Aplica patch de schema ETL (adiciona propriedades automaticamente)
        try:
            from verba_extensions.integration.schema_updater import patch_weaviate_manager_verify_collection
            patch_weaviate_manager_verify_collection()
        except Exception as e:
            msg.warn(f"Patch de schema ETL não aplicado: {str(e)}")
        
        # Aplica patch Tika fallback (integra Tika como fallback no BasicReader)
        try:
            from verba_extensions.integration.tika_fallback_patch import patch_basic_reader_with_tika_fallback
            if patch_basic_reader_with_tika_fallback():
                msg.info("Tika fallback habilitado - formatos não suportados usarão Tika automaticamente")
        except Exception as e:
            msg.warn(f"Patch Tika fallback não aplicado: {str(e)}")
        
        # Executa registradores de hooks dos plugins
        for plugin_name, plugin_data in plugin_manager.plugins.items():
            if hasattr(plugin_data['module'], 'register_hooks'):
                try:
                    plugin_data['module'].register_hooks()
                except Exception as e:
                    msg.warn(f"Erro ao registrar hooks do plugin {plugin_name}: {str(e)}")
        
        # Salva instância global para uso posterior
        sys.modules['verba_extensions']._plugin_manager = plugin_manager
        sys.modules['verba_extensions']._version_checker = version_checker
        
        msg.good(f"Extensões inicializadas: {len(plugin_manager.list_plugins())} plugins carregados")
        
        return plugin_manager, version_checker
        
    except Exception as e:
        msg.warn(f"Erro ao inicializar extensões (continuando sem extensões): {str(e)}")
        return None, None

# Auto-inicializa se chamado diretamente ou via import
if __name__ != "__main__" or os.getenv("VERBA_AUTO_INIT_EXTENSIONS", "true").lower() == "true":
    _pm, _vc = initialize_extensions()
