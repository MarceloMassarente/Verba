# 🔧 Patches e Hooks - Documentação para Upgrades do Verba

## ⚠️ IMPORTANTE: Ao Atualizar Verba

**ESTES SÃO PATCHES/MONKEY PATCHES** que modificam o comportamento do Verba core sem alterar o código original.

Quando você atualizar o Verba, **verifique se estes patches ainda funcionam** e se precisam ser reaplicados.

---

## 📋 Lista de Patches Aplicados

### 1. **ETL Pré-Chunking Hook** ✅

**Arquivo:** `verba_extensions/integration/chunking_hook.py`

**O que faz:**
- Extrai entidades do documento completo ANTES do chunking
- Permite chunking entity-aware que evita cortar entidades no meio
- Armazena `entity_spans` no `document.meta` para chunkers usarem

**Onde é aplicado:**
- `goldenverba/verba_manager.py` linha ~241: Chama `apply_etl_pre_chunking()` antes do chunking

**Dependências:**
- `verba_extensions/plugins/a2_etl_hook.py` (funções de NER)
- spaCy instalado
- Gazetteer disponível (opcional)

**Como verificar após upgrade:**
```python
# Teste se ainda funciona:
from verba_extensions.integration.chunking_hook import apply_etl_pre_chunking
# Se importar sem erro, está OK
```

---

### 2. **Section-Aware Chunker Entity-Aware** ✅

**Arquivo:** `verba_extensions/plugins/section_aware_chunker.py`

**O que faz:**
- Modifica `SectionAwareChunker` para usar `entity_spans` pré-extraídos
- Evita cortar entidades no meio durante chunking
- Mantém entidades completas no mesmo chunk

**Alterações específicas:**
- Linha ~135: Lê `entity_spans` de `document.meta`
- Linha ~186-211: Lógica para evitar cortar entidades em seções grandes
- Linha ~284-297: Método `_chunk_by_sentences_entity_aware()` adicionado

**Como verificar após upgrade:**
1. Verificar se `SectionAwareChunker.chunk()` ainda aceita documentos com `entity_spans`
2. Testar chunking de documento com entidades conhecidas

---

### 3. **Import Hook (ETL Pós-Chunking)** ✅

**Arquivo:** `verba_extensions/integration/import_hook.py`

**O que faz:**
- Patch em `WeaviateManager.import_document()` para capturar `passage_uuids`
- Dispara ETL A2 após importação dos chunks
- Mantém ETL pós-chunking para section scope refinado

**Como é aplicado:**
- Chamado em `verba_extensions/startup.py` durante inicialização
- Monkey patch: `managers.WeaviateManager.import_document = patched_import_document`

**Como verificar após upgrade:**
```python
# Verificar se método ainda existe:
from goldenverba.components import managers
original_method = managers.WeaviateManager.import_document
# Se existir, patch pode ser reaplicado
```

---

## 🔄 Processo de Reaplicação Após Upgrade

### **Passo 1: Verificar Compatibilidade**

```bash
# 1. Atualizar Verba
git pull origin main  # ou como você atualiza

# 2. Verificar se estrutura ainda existe
python -c "
from goldenverba.verba_manager import VerbaManager
from goldenverba.components.document import Document
print('✅ Estruturas básicas OK')
"

# 3. Verificar se hooks ainda funcionam
python -c "
from verba_extensions.integration.chunking_hook import apply_etl_pre_chunking
from verba_extensions.integration.import_hook import patch_weaviate_manager
print('✅ Hooks OK')
"
```

### **Passo 2: Reaplicar Patches (se necessário)**

Se algum patch falhar, verifique:

1. **ETL Pré-Chunking:**
   - Verificar se `verba_manager.py` ainda tem `process_single_document()`
   - Verificar se ainda aceita `document.meta`

2. **Import Hook:**
   - Verificar se `WeaviateManager.import_document()` ainda existe
   - Verificar assinatura do método (parâmetros mudaram?)

3. **Chunker:**
   - Verificar se `SectionAwareChunker` ainda funciona
   - Verificar se `document.meta` ainda é acessível

### **Passo 3: Testar**

```bash
# Teste básico: importar documento com ETL
# Deve ver logs:
# [ETL-PRE] ✅ Entidades extraídas antes do chunking
# [ENTITY-AWARE] Usando X entidades pré-extraídas
# [ETL] ✅ X chunks encontrados - executando ETL A2
```

---

## 📝 Checklist de Upgrade

- [ ] Backup do código atual
- [ ] Atualizar Verba (git pull ou como você atualiza)
- [ ] Verificar imports básicos funcionam
- [ ] Verificar se `verba_manager.py` ainda tem estrutura esperada
- [ ] Verificar se `WeaviateManager.import_document()` ainda existe
- [ ] Verificar se `SectionAwareChunker` ainda funciona
- [ ] Testar import de documento pequeno
- [ ] Verificar logs de ETL pré-chunking aparecem
- [ ] Verificar logs de ETL pós-chunking aparecem
- [ ] Testar busca com EntityAware Retriever

---

## 🛠️ Como Reaplicar Manualmente (se necessário)

### **Patch 1: ETL Pré-Chunking**

**Local:** `goldenverba/verba_manager.py` (linha ~238-248)

**Antes do chunking, adicionar:**
```python
# FASE 1: ETL Pré-Chunking (extrai entidades do documento completo)
if enable_etl:
    try:
        from verba_extensions.integration.chunking_hook import apply_etl_pre_chunking
        document = apply_etl_pre_chunking(document, enable_etl=True)
        msg.info(f"[ETL-PRE] ✅ Entidades extraídas antes do chunking")
    except Exception as e:
        msg.warn(f"[ETL-PRE] Erro (não crítico): {str(e)}")
```

### **Patch 2: Import Hook**

**Local:** `verba_extensions/startup.py` ou `verba_extensions/integration/import_hook.py`

**Na inicialização, chamar:**
```python
from verba_extensions.integration.import_hook import patch_weaviate_manager
patch_weaviate_manager()
```

### **Patch 3: Chunker Entity-Aware**

**Local:** `verba_extensions/plugins/section_aware_chunker.py`

**No método `chunk()`, adicionar:**
```python
# Pega entidades pré-extraídas
entity_spans = []
if hasattr(document, 'meta') and document.meta:
    entity_spans = document.meta.get("entity_spans", [])
```

**No chunking de seções grandes, adicionar lógica para evitar cortar entidades.**

---

## 📚 Arquivos Relacionados

### **Core (não modificar diretamente):**
- `goldenverba/verba_manager.py` - Usa hook de ETL pré-chunking
- `goldenverba/components/managers.py` - Patchado via monkey patch

### **Extensions (nossos patches):**
- `verba_extensions/integration/chunking_hook.py` - ETL pré-chunking
- `verba_extensions/integration/import_hook.py` - ETL pós-chunking
- `verba_extensions/plugins/section_aware_chunker.py` - Chunker entity-aware
- `verba_extensions/plugins/a2_etl_hook.py` - Funções de NER (usado por ambos)

### **Startup:**
- `verba_extensions/startup.py` - Aplica patches na inicialização

---

## 🔍 Como Identificar se Precisa Reaplicar

### **Sintomas de que precisa reaplicar:**

1. **Erro: `ModuleNotFoundError: verba_extensions.integration.chunking_hook`**
   - ✅ Arquivo existe? Verificar caminho
   - ✅ Import está correto?

2. **Erro: `'VerbaManager' object has no attribute 'process_single_document'`**
   - ⚠️ Método mudou de nome ou estrutura
   - ✅ Verificar estrutura atual do VerbaManager

3. **Erro: `'WeaviateManager' object has no attribute 'import_document'`**
   - ⚠️ Método mudou de nome ou estrutura
   - ✅ Verificar estrutura atual do WeaviateManager

4. **Logs não mostram `[ETL-PRE]`**
   - ⚠️ Hook não está sendo chamado
   - ✅ Verificar se `apply_etl_pre_chunking()` está sendo executado

5. **Chunks ainda cortam entidades no meio**
   - ⚠️ Chunker não está usando `entity_spans`
   - ✅ Verificar se `document.meta["entity_spans"]` está sendo lido

---

## 🎯 Estratégia de Upgrade Seguro

### **Opção 1: Feature Flag (Recomendado)**

Adicionar flag para desabilitar patches se necessário:

```python
# verba_extensions/startup.py
ENABLE_ETL_PRE_CHUNKING = os.getenv("ENABLE_ETL_PRE_CHUNKING", "true").lower() == "true"

if ENABLE_ETL_PRE_CHUNKING:
    # Aplica patches
    ...
```

### **Opção 2: Version Check**

Verificar versão do Verba antes de aplicar patches:

```python
# verba_extensions/startup.py
import goldenverba
verba_version = getattr(goldenverba, '__version__', 'unknown')

if verba_version.startswith('2.1'):
    # Patches compatíveis
    apply_patches()
else:
    msg.warn(f"Verba versão {verba_version} - verificar compatibilidade dos patches")
```

---

## 📞 Suporte

Se após upgrade os patches não funcionarem:

1. **Verificar logs** para erros específicos
2. **Comparar estrutura** do Verba atual vs esperada
3. **Reaplicar patches** manualmente se necessário
4. **Documentar mudanças** encontradas para próxima vez

---

## ✅ Status Atual

- ✅ **ETL Pré-Chunking**: Implementado e testado
- ✅ **Chunker Entity-Aware**: Implementado e testado
- ✅ **ETL Pós-Chunking**: Mantido (já estava funcionando)
- ✅ **Documentação**: Este arquivo

**Última verificação de compatibilidade:** Verba 2.1.x (novembro 2024)

