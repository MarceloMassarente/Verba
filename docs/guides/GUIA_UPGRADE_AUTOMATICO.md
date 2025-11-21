# Guia: Sistema de Upgrade Automático do Verba com Extensões

## 🎯 Objetivo

Manter suas extensões funcionando automaticamente quando o Verba é atualizado, **sem precisar reescrever código**.

## 🏗️ Arquitetura de Extensibilidade

### Estrutura de Diretórios

```
projeto/
├── goldenverba/              # Verba original (atualizado via pip/git)
├── verba_extensions/         # SEU código de extensões
│   ├── __init__.py
│   ├── plugin_manager.py    # Gerenciador de plugins
│   ├── version_checker.py   # Verificador de compatibilidade
│   ├── hooks.py             # Sistema de hooks
│   ├── startup.py           # Auto-inicialização
│   └── plugins/
│       ├── entity_aware_retriever.py
│       └── (seus plugins aqui)
├── verba_extensions/etl/     # Sistema ETL integrado
│   ├── app.py
│   ├── etl_a2.py
│   └── ...
├── verba_patch/             # Patches mínimos
│   └── auto_load_extensions.py
└── requirements-extensions.txt
```

## 🔄 Fluxo de Upgrade Automático

### 1. Atualização do Verba

```bash
# Atualiza Verba
pip install --upgrade goldenverba

# OU se for fork
git pull upstream main  # ou a branch principal do Verba
```

### 2. Verificação Automática de Compatibilidade

O `VersionChecker` detecta automaticamente:

- ✅ **Mudanças em interfaces** (Retriever, Generator, etc.)
- ✅ **Novos métodos obrigatórios**
- ✅ **Mudanças em assinaturas**

### 3. Adaptação Automática

```python
# verba_extensions/version_checker.py detecta mudanças
compatibility = version_checker.check_api_changes()

# Se incompatível, sugere migração
if not compatible:
    suggestions = version_checker.suggest_migration(incompatibilities)
    # Logs ou warnings para você ajustar
```

## 📦 Como Criar Extensões Compatíveis

### Plugin Básico

```python
# verba_extensions/plugins/meu_plugin.py

from goldenverba.components.interfaces import Retriever
from goldenverba.components.types import InputConfig

class MeuRetriever(Retriever):
    def __init__(self):
        super().__init__()
        self.name = "MeuRetriever"
        self.description = "Descrição"
        # ... implementa interface padrão
    
    async def retrieve(self, client, query, vector, config, weaviate_manager, embedder, labels, document_uuids):
        # Sua lógica aqui
        pass

def register():
    return {
        'name': 'meu_plugin',
        'version': '1.0.0',
        'retrievers': [MeuRetriever()],  # ou generators, readers, etc.
        'compatible_verba_version': '>=2.1.0',  # Especifica versão mínima
    }
```

### Plugin com Hooks

```python
from verba_extensions.hooks import global_hooks

def before_retrieve(query, **kwargs):
    # Modifica query antes da busca
    return modified_query

global_hooks.register_hook('retrieve.before', before_retrieve, priority=50)
```

## 🚀 Inicialização Automática

### Opção 1: Via Variável de Ambiente

```bash
# .env ou export
VERBA_AUTO_INIT_EXTENSIONS=true
VERBA_PLUGINS_DIR=verba_extensions/plugins
```

### Opção 2: Via Patch no Verba

```python
# No início do seu código, ANTES de importar goldenverba.server.api
import verba_patch.auto_load_extensions
# Agora pode importar normalmente
from goldenverba.server.api import app
```

### Opção 3: Manual

```python
from verba_extensions.startup import initialize_extensions
plugin_manager, version_checker = initialize_extensions()
```

## 🔍 Monitoramento de Compatibilidade

### Verificar Status

```python
from verba_extensions.version_checker import VersionChecker

vc = VersionChecker()
info = vc.get_version_info()

print(f"Verba: {info['verba_version']}")
print(f"Extensões: {info['extensions_version']}")

# Verifica compatibilidade
checks = vc.check_api_changes()
for component, status in checks.items():
    if status['compatible']:
        print(f"✅ {component}: OK")
    else:
        print(f"❌ {component}: {status['changes']}")
```

### Logs Automáticos

O sistema loga automaticamente:

```
ℹ️ Verba version: 2.1.3
⚠️ Incompatibilidade detectada em Retriever: Método retrieve mudou
✅ Extensões inicializadas: 2 plugins carregados
```

## 🛠️ Estratégias de Compatibilidade

### 1. **Interface Adapter Pattern**

Se a interface mudar, crie um adapter:

```python
class CompatibleRetriever(Retriever):
    def __init__(self, old_retriever):
        self.old = old_retriever
    
    async def retrieve(self, client, query, vector, config, weaviate_manager, embedder, labels, document_uuids):
        # Adapta chamada antiga para nova interface
        return await self.old.retrieve_legacy(...)
```

### 2. **Feature Detection**

Detecta features disponíveis:

```python
from goldenverba.components import interfaces

# Verifica se método existe
if hasattr(interfaces.Retriever, 'new_method'):
    # Usa novo método
    result = await retriever.new_method(...)
else:
    # Fallback para método antigo
    result = await retriever.old_method(...)
```

### 3. **Version Guards**

```python
from verba_extensions.version_checker import VersionChecker

vc = VersionChecker()
verba_version = vc.verba_version

if verba_version >= "2.2.0":
    # Usa API nova
    pass
elif verba_version >= "2.1.0":
    # Usa API intermediária
    pass
else:
    # Usa API antiga
    pass
```

## 🔧 Manutenção Contínua

### Checklist de Upgrade

1. ✅ **Backup** do estado atual (config, dados)
2. ✅ **Teste** em ambiente de desenvolvimento primeiro
3. ✅ **Atualiza** Verba: `pip install --upgrade goldenverba`
4. ✅ **Verifica** logs de compatibilidade
5. ✅ **Ajusta** plugins se necessário (versões guardadas)
6. ✅ **Testa** funcionalidades críticas
7. ✅ **Deploy** em produção

### Script de Upgrade Automatizado

```bash
#!/bin/bash
# upgrade_verba.sh

set -e

echo "🔄 Atualizando Verba..."
pip install --upgrade goldenverba

echo "🔍 Verificando compatibilidade..."
python -c "
from verba_extensions.version_checker import VersionChecker
vc = VersionChecker()
info = vc.get_version_info()
checks = vc.check_api_changes()

compatible = all(s['compatible'] for s in checks.values())
if compatible:
    print('✅ Compatível!')
    exit(0)
else:
    print('⚠️ Incompatibilidades detectadas:')
    for comp, status in checks.items():
        if not status['compatible']:
            print(f'  - {comp}: {status[\"changes\"]}')
    exit(1)
"

if [ $? -eq 0 ]; then
    echo "✅ Upgrade concluído com sucesso!"
else
    echo "⚠️ Verifique os warnings acima"
fi
```

## 📊 Versionamento de Extensões

### Compatibilidade Semântica

```python
# verba_extensions/plugins/meu_plugin.py

def register():
    return {
        'name': 'meu_plugin',
        'version': '1.2.3',
        'compatible_verba_version': '>=2.1.0,<3.0.0',  # Range compatível
        'dependencies': {
            'goldenverba': '>=2.1.0,<3.0.0',
            'weaviate-client': '>=4.9.0'
        }
    }
```

## 🎓 Exemplos Práticos

### Exemplo 1: Entity-Aware Retriever (já criado)

✅ Usa interface padrão `Retriever`  
✅ Compatível com qualquer versão do Verba que suporta `Retriever`  
✅ Hook para injetar filtros entity-aware

### Exemplo 2: Custom Generator

```python
class MinhaGenerator(Generator):
    # Implementa interface padrão
    # Funciona automaticamente com qualquer versão compatível
```

### Exemplo 3: API Wrapper

```python
# Wrapper que abstrai mudanças na API do Verba
class VerbaAPIWrapper:
    def __init__(self):
        self.vc = VersionChecker()
        self.verba_version = self.vc.verba_version
    
    def get_retriever_manager(self, verba_manager):
        # Adapta baseado na versão
        if self.verba_version >= "2.2.0":
            return verba_manager.retriever_manager_v2()
        else:
            return verba_manager.retriever_manager
```

## 🚨 Troubleshooting

### Problema: Plugin não carrega após upgrade

**Solução:**
```python
# Verifica compatibilidade manualmente
from verba_extensions.version_checker import VersionChecker
vc = VersionChecker()
vc.check_interface_compatibility('Retriever')
```

### Problema: Método não encontrado

**Solução:** Use feature detection
```python
if hasattr(obj, 'new_method'):
    result = obj.new_method()
else:
    result = obj.old_method()  # Fallback
```

### Problema: Interface mudou

**Solução:** Crie adapter
```python
class CompatibleAdapter:
    def __init__(self, old_impl):
        self.old = old_impl
    
    # Adapta nova interface para antiga implementação
```

## ✅ Checklist de Compatibilidade

- [ ] Extensões usam apenas interfaces públicas do Verba
- [ ] Plugins registrados via função `register()`
- [ ] Version guards para APIs que mudaram
- [ ] Feature detection para novos recursos
- [ ] Testes com múltiplas versões do Verba
- [ ] Logs informativos sobre compatibilidade

---

**Resultado:** Você pode atualizar o Verba sem perder suas extensões! 🎉

