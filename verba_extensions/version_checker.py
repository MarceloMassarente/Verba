"""
Version Checker - Verifica compatibilidade com versões do Verba
"""

import importlib
import inspect
from typing import Dict, List, Optional, Tuple
from wasabi import msg

class VersionChecker:
    """
    Verifica compatibilidade de extensões com versões do Verba
    e detecta mudanças na API que possam quebrar extensões
    """
    
    def __init__(self):
        self.verba_version = self._get_verba_version()
        self.api_signatures = {}
        
    def _get_verba_version(self) -> str:
        """Obtém a versão do Verba instalado"""
        try:
            import goldenverba
            if hasattr(goldenverba, '__version__'):
                return goldenverba.__version__
            
            # Tenta pegar do setup.py
            import setup
            if hasattr(setup, 'version'):
                return setup.version
                
            return "unknown"
        except:
            return "unknown"
    
    def check_interface_compatibility(self, component_type: str) -> Tuple[bool, List[str]]:
        """
        Verifica se a interface de um componente mudou
        Retorna (compatível, lista_de_mudanças)
        """
        try:
            from goldenverba.components import interfaces
            
            # Mapeia tipos para classes
            type_map = {
                'Retriever': interfaces.Retriever,
                'Generator': interfaces.Generator,
                'Reader': interfaces.Reader,
                'Chunker': interfaces.Chunker,
                'Embedding': interfaces.Embedding,
            }
            
            if component_type not in type_map:
                return False, [f"Tipo desconhecido: {component_type}"]
            
            cls = type_map[component_type]
            required_methods = self._get_required_methods(cls)
            actual_methods = self._get_actual_methods(cls)
            
            changes = []
            compatible = True
            
            for method_name, signature in required_methods.items():
                if method_name not in actual_methods:
                    changes.append(f"Método {method_name} removido")
                    compatible = False
                elif actual_methods[method_name] != signature:
                    changes.append(f"Assinatura de {method_name} mudou")
                    compatible = False
            
            return compatible, changes
            
        except Exception as e:
            msg.warn(f"Erro ao verificar compatibilidade: {str(e)}")
            return False, [str(e)]
    
    def _get_required_methods(self, cls) -> Dict[str, inspect.Signature]:
        """Obtém métodos requeridos de uma classe"""
        methods = {}
        for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
            if not name.startswith('_'):
                methods[name] = inspect.signature(method)
        return methods
    
    def _get_actual_methods(self, cls) -> Dict[str, inspect.Signature]:
        """Obtém métodos atuais de uma classe"""
        return self._get_required_methods(cls)
    
    def check_api_changes(self) -> Dict[str, bool]:
        """
        Verifica mudanças críticas na API do Verba
        Retorna dict com status de compatibilidade por módulo
        """
        checks = {}
        
        # Verifica interfaces principais
        for component_type in ['Retriever', 'Generator', 'Reader']:
            compatible, changes = self.check_interface_compatibility(component_type)
            checks[component_type] = {
                'compatible': compatible,
                'changes': changes
            }
        
        return checks
    
    def suggest_migration(self, incompatible_checks: Dict) -> List[str]:
        """Sugere migrações baseadas em incompatibilidades detectadas"""
        suggestions = []
        
        for component, status in incompatible_checks.items():
            if not status['compatible']:
                suggestions.append(f"{component}: {', '.join(status['changes'])}")
        
        return suggestions
    
    def get_version_info(self) -> Dict:
        """Retorna informações de versão"""
        return {
            'verba_version': self.verba_version,
            'extensions_version': "1.0.0",
            'compatibility_checks': self.check_api_changes()
        }

