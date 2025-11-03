"""
Plugin Manager - Gerencia extensões do Verba sem modificar código core
"""

import os
import importlib
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from wasabi import msg

class PluginManager:
    """
    Gerencia plugins/extensões do Verba usando hooks e monkey patching.
    Permite atualizar Verba sem perder as extensões.
    """
    
    def __init__(self, verba_base_path: Optional[str] = None):
        self.verba_base_path = verba_base_path or os.getenv("VERBA_BASE_PATH", "goldenverba")
        self.plugins: Dict[str, Any] = {}
        self.hooks_applied = False
        
    def load_plugin(self, plugin_path: str):
        """Carrega um plugin do sistema"""
        try:
            # Adiciona o diretório do plugin ao path
            plugin_dir = Path(plugin_path).parent
            if str(plugin_dir) not in sys.path:
                sys.path.insert(0, str(plugin_dir))
            
            # Importa o plugin
            module_name = Path(plugin_path).stem
            plugin_module = importlib.import_module(module_name)
            
            # Registra o plugin
            if hasattr(plugin_module, 'register'):
                plugin_info = plugin_module.register()
                self.plugins[plugin_info.get('name', module_name)] = {
                    'module': plugin_module,
                    'info': plugin_info,
                    'path': plugin_path
                }
                msg.good(f"Plugin carregado: {plugin_info.get('name', module_name)}")
                return True
            else:
                msg.warn(f"Plugin {module_name} não possui função register()")
                return False
        except Exception as e:
            msg.fail(f"Erro ao carregar plugin {plugin_path}: {str(e)}")
            return False
    
    def load_plugins_from_dir(self, plugins_dir: str = "verba_extensions/plugins"):
        """Carrega todos os plugins de um diretório"""
        plugins_path = Path(plugins_dir)
        if not plugins_path.exists():
            msg.warn(f"Diretório de plugins não encontrado: {plugins_dir}")
            return
        
        for plugin_file in plugins_path.glob("*.py"):
            if plugin_file.name.startswith("_") or plugin_file.name == "__init__.py":
                continue
            self.load_plugin(str(plugin_file))
    
    def apply_hooks(self):
        """Aplica hooks para injetar extensões no Verba sem modificar código core"""
        if self.hooks_applied:
            return
        
        # Hook 1: Adiciona novos retrievers
        self._hook_retrievers()
        
        # Hook 2: Adiciona novos generators
        self._hook_generators()
        
        # Hook 3: Adiciona novos readers
        self._hook_readers()
        
        # Hook 4: Modifica managers para incluir plugins
        self._hook_managers()
        
        self.hooks_applied = True
        msg.good("Hooks aplicados com sucesso")
    
    def _hook_retrievers(self):
        """Adiciona retrievers customizados aos managers"""
        try:
            from goldenverba.components import managers
            
            # Pega a lista original de retrievers
            original_retrievers = managers.retrievers.copy()
            
            # Adiciona retrievers dos plugins
            for plugin_name, plugin_data in self.plugins.items():
                if 'retrievers' in plugin_data['info']:
                    for retriever in plugin_data['info']['retrievers']:
                        if retriever not in original_retrievers:
                            original_retrievers.append(retriever)
                            msg.info(f"Retriever adicionado: {retriever.name}")
            
            managers.retrievers = original_retrievers
        except Exception as e:
            msg.warn(f"Erro ao aplicar hook de retrievers: {str(e)}")
    
    def _hook_generators(self):
        """Adiciona generators customizados aos managers"""
        try:
            from goldenverba.components import managers
            
            original_generators = managers.generators.copy()
            
            for plugin_name, plugin_data in self.plugins.items():
                if 'generators' in plugin_data['info']:
                    for generator in plugin_data['info']['generators']:
                        if generator not in original_generators:
                            original_generators.append(generator)
                            msg.info(f"Generator adicionado: {generator.name}")
            
            managers.generators = original_generators
        except Exception as e:
            msg.warn(f"Erro ao aplicar hook de generators: {str(e)}")
    
    def _hook_readers(self):
        """Adiciona readers customizados aos managers"""
        try:
            from goldenverba.components import managers
            
            original_readers = managers.readers.copy()
            
            for plugin_name, plugin_data in self.plugins.items():
                if 'readers' in plugin_data['info']:
                    for reader in plugin_data['info']['readers']:
                        if reader not in original_readers:
                            original_readers.append(reader)
                            msg.info(f"Reader adicionado: {reader.name}")
            
            managers.readers = original_readers
        except Exception as e:
            msg.warn(f"Erro ao aplicar hook de readers: {str(e)}")
    
    def _hook_managers(self):
        """Aplica patches nos managers se necessário"""
        # Placeholder para patches futuros nos managers
        pass
    
    def get_plugin(self, name: str):
        """Retorna um plugin específico"""
        return self.plugins.get(name)
    
    def list_plugins(self):
        """Lista todos os plugins carregados"""
        return list(self.plugins.keys())
    
    def reload_plugin(self, name: str):
        """Recarrega um plugin"""
        if name in self.plugins:
            plugin_path = self.plugins[name]['path']
            del self.plugins[name]
            return self.load_plugin(plugin_path)
        return False

