"""
Verba Extensions - Plugin System para Extensões do Verba
Mantém compatibilidade com atualizações futuras do Verba sem modificar código core
"""

__version__ = "1.0.0"

from .plugin_manager import PluginManager
from .version_checker import VersionChecker
from .hooks import VerbaHooks

__all__ = ["PluginManager", "VersionChecker", "VerbaHooks"]

