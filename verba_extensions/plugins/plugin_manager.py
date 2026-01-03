
import os
from verba_extensions.extension_loader import ExtensionLoader

_manager_instance = None

def get_plugin_manager():
    """
    Returns the singleton instance of ExtensionLoader (acting as PluginManager).
    """
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = ExtensionLoader()
        # Initialize plugins if needed, or just return the loader
        # For the test environment, we might want to load explicitly
    return _manager_instance
