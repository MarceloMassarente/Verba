"""
Hooks System - Sistema de hooks para interceptar chamadas do Verba
"""

from typing import Callable, Any, Dict, List
from functools import wraps
import inspect

class VerbaHooks:
    """
    Sistema de hooks que permite interceptar e modificar comportamento
    do Verba sem alterar código core
    """
    
    def __init__(self):
        self.hooks: Dict[str, List[Callable]] = {}
        
    def register_hook(self, hook_name: str, callback: Callable, priority: int = 100):
        """
        Registra um hook
        
        Args:
            hook_name: Nome do hook (ex: 'retrieve.before', 'retrieve.after')
            callback: Função callback
            priority: Prioridade (menor = executa primeiro)
        """
        if hook_name not in self.hooks:
            self.hooks[hook_name] = []
        
        self.hooks[hook_name].append({
            'callback': callback,
            'priority': priority
        })
        
        # Ordena por prioridade
        self.hooks[hook_name].sort(key=lambda x: x['priority'])
    
    def execute_hook(self, hook_name: str, *args, **kwargs) -> Any:
        """
        Executa todos os callbacks de um hook (sync)
        Para hooks async, use execute_hook_async
        """
        if hook_name not in self.hooks:
            return None
        
        result = None
        
        for hook in self.hooks[hook_name]:
            try:
                callback = hook['callback']
                hook_result = callback(*args, **kwargs)
                
                # Se for coroutine (async), retorna None e avisa
                # Caller deve usar execute_hook_async para hooks async
                if inspect.iscoroutine(hook_result):
                    import warnings
                    warnings.warn(f"Hook {hook_name} is async but called with sync execute_hook. Use execute_hook_async instead.")
                    return None
                else:
                    result = hook_result
                
                # Se retornar algo que não seja None, para a execução (apenas para sync hooks)
                if result is not None and not inspect.iscoroutine(result) and hook_name.startswith('before'):
                    return result
            except Exception as e:
                print(f"Erro ao executar hook {hook_name}: {str(e)}")
        
        return result
    
    async def execute_hook_async(self, hook_name: str, *args, **kwargs) -> Any:
        """
        Executa hooks de forma assíncrona
        Aguarda todos os hooks async e executa sync normalmente
        """
        if hook_name not in self.hooks:
            return None
        
        result = None
        for hook in self.hooks[hook_name]:
            try:
                callback = hook['callback']
                
                # Verifica se callback é async
                if inspect.iscoroutinefunction(callback):
                    hook_result = await callback(*args, **kwargs)
                else:
                    hook_result = callback(*args, **kwargs)
                
                result = hook_result
                
                # Se retornar algo que não seja None, para a execução
                if result is not None and hook_name.startswith('before'):
                    return result
            except Exception as e:
                print(f"Erro ao executar hook {hook_name}: {str(e)}")
        
        return result
    
    def wrap_method(self, obj: Any, method_name: str, hook_before: str = None, hook_after: str = None):
        """Envolve um método com hooks"""
        original_method = getattr(obj, method_name)
        
        @wraps(original_method)
        def wrapper(*args, **kwargs):
            # Hook before
            if hook_before:
                self.execute_hook(hook_before, *args, **kwargs)
            
            # Executa método original
            result = original_method(*args, **kwargs)
            
            # Hook after
            if hook_after:
                self.execute_hook(hook_after, result, *args, **kwargs)
            
            return result
        
        setattr(obj, method_name, wrapper)
        return wrapper

# Instância global de hooks
global_hooks = VerbaHooks()

