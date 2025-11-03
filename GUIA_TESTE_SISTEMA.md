# 🧪 Guia: Teste Geral do Sistema

## 📋 O que o teste verifica:

### 1. Estrutura Base das Extensões
- ✅ Import de `verba_extensions`
- ✅ `PluginManager` funcionando
- ✅ Sistema de hooks base
- ✅ `VersionChecker`

### 2. Carregamento de Plugins
- ✅ Diretório de plugins encontrado
- ✅ Plugins individuais importáveis
- ✅ Plugins registrados corretamente

### 3. Adapters de Compatibilidade v3
- ✅ `WeaviateV3HTTPAdapter`
- ✅ `WeaviateVersionDetector`
- ✅ Patch v3

### 4. Sistema de Hooks
- ✅ Registro de hooks
- ✅ Execução de hooks
- ✅ Hooks de integração

### 5. Plugins Específicos
- ✅ `EntityAwareHybridRetriever` (se weaviate v4)
- ✅ `A2URLReader` e `A2ResultsReader`
- ✅ `A2ETLHook`

### 6. Integração de Startup
- ✅ `startup.py` importável
- ✅ Função `initialize_extensions`

### 7. Recursos
- ✅ Gazetteer.json existe e é válido

### 8. Integração com Verba Core
- ✅ `WeaviateManager` importável
- ✅ Patch v3 aplicável

## 🚀 Como executar:

```bash
python test_sistema_completo.py
```

## ✅ Resultado Esperado:

**Com weaviate-client v4 instalado:**
- 7-8/8 testes devem passar

**Sem weaviate-client v4:**
- 4-5/8 testes devem passar
- Avisos sobre versão incompatível

## 📊 Interpretação dos Resultados:

### ✅ OK = Componente funcionando completamente
### ⚠️ AVISO = Funciona mas tem dependências ou limitações
### ❌ FALHOU = Erro que precisa correção

---

**Arquivo criado**: `test_sistema_completo.py`

