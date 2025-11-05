# 🔧 Patches e Hooks - Documentação para Upgrades do Verba

## ⚠️ IMPORTANTE: Ao Atualizar Verba

**ESTES SÃO PATCHES/MONKEY PATCHES** que modificam o comportamento do Verba core sem alterar o código original.

Quando você atualizar o Verba, **verifique se estes patches ainda funcionam** e se precisam ser reaplicados.

---

## 📋 Lista de Patches Aplicados

### 1. **Schema ETL-Aware Universal** ⭐ NOVO - IMPORTANTE

**Arquivo:** `verba_extensions/integration/schema_updater.py`

**O que faz:**
- Patch em `WeaviateManager.verify_collection()` para criar collections com schema ETL-aware
- Schema inclui 20 propriedades: 13 padrão Verba + 7 ETL opcionais
- **Serve para AMBOS:** chunks normais (propriedades ETL vazias) e chunks ETL-aware (propriedades ETL preenchidas)
- Cria collections automaticamente com schema completo desde o início

**Onde é aplicado:**
- `verba_extensions/startup.py` linha ~57: Chama `patch_weaviate_manager_verify_collection()`
- Monkey patch: `managers.WeaviateManager.verify_collection = patched_verify_collection`

**Comportamento:**
1. Se collection existe → Verifica se tem propriedades ETL
2. Se collection não existe + é VERBA_Embedding → **Cria com schema ETL-aware completo**
3. Se collection não existe + não é embedding → Cria normalmente

**Propriedades criadas:**
- **Padrão Verba (13):** chunk_id, content, doc_uuid, title, labels, etc.
- **ETL (7 opcionais):** entities_local_ids, section_title, section_entity_ids, section_scope_confidence, primary_entity_id, entity_focus_score, etl_version

**Como verificar após upgrade:**
```python
# 1. Verificar se patch está aplicado:
from verba_extensions.integration.schema_updater import patch_weaviate_manager_verify_collection
from goldenverba.components import managers
# Verificar se método foi substituído
if hasattr(managers.WeaviateManager, 'verify_collection'):
    print('✅ verify_collection existe - patch pode ser aplicado')

# 2. Verificar se collection tem schema ETL:
from verba_extensions.integration.schema_updater import check_collection_has_etl_properties
has_etl = await check_collection_has_etl_properties(client, "VERBA_Embedding_all_MiniLM_L6_v2")
if has_etl:
    print('✅ Schema ETL-aware')
else:
    print('❌ Schema padrão (sem ETL)')
```

**Se precisar reaplicar:**
- Patch é aplicado automaticamente via `startup.py`
- Se não funcionar, verificar se `WeaviateManager.verify_collection()` ainda existe
- Verificar se `client.collections.create()` ainda aceita parâmetro `properties`

---

### 2. **ETL Pré-Chunking Hook** ✅

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

### 3. **Section-Aware Chunker Entity-Aware** ✅

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

### 4. **Import Hook (ETL Pós-Chunking)** ✅

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

2. **Schema ETL-Aware:**
   - Verificar se `WeaviateManager.verify_collection()` ainda existe
   - Verificar se `client.collections.create()` aceita parâmetro `properties`
   - Verificar se `client.collections.exists()` ainda funciona

3. **Import Hook:**
   - Verificar se `WeaviateManager.import_document()` ainda existe
   - Verificar assinatura do método (parâmetros mudaram?)

4. **Chunker:**
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

### Pré-Upgrade
- [ ] Backup do código atual
- [ ] Backup do Weaviate (se necessário)
- [ ] Documentar versão atual do Verba

### Atualização
- [ ] Atualizar Verba (git pull ou como você atualiza)
- [ ] Verificar imports básicos funcionam
- [ ] Verificar se `verba_extensions/` foi copiado

### Verificação de Estrutura
- [ ] Verificar se `verba_manager.py` ainda tem `process_single_document()`
- [ ] Verificar se `WeaviateManager.verify_collection()` ainda existe
- [ ] Verificar se `WeaviateManager.import_document()` ainda existe
- [ ] Verificar se `SectionAwareChunker` ainda funciona
- [ ] Verificar se `client.collections.create()` aceita `properties`

### Verificação de Patches
- [ ] Verificar se `startup.py` está sendo chamado
- [ ] Verificar logs: "Patch de schema ETL-aware aplicado"
- [ ] Verificar logs: "Hook de integração ETL aplicado"
- [ ] Testar criação de collection: deve criar com schema ETL-aware
- [ ] Verificar se collection tem 20 propriedades (13 padrão + 7 ETL)

### Testes Funcionais
- [ ] Testar import de documento pequeno
- [ ] Verificar logs: "[ETL-PRE] ✅ Entidades extraídas"
- [ ] Verificar logs: "[ENTITY-AWARE] Usando X entidades"
- [ ] Verificar logs: "[ETL-POST] ✅ ETL executado"
- [ ] Verificar se chunks têm propriedades ETL (se ETL ativado)
- [ ] Testar busca com EntityAware Retriever
- [ ] Verificar se queries por entity_id funcionam

---

## 🛠️ Como Reaplicar Manualmente (se necessário)

### **Patch 1: Schema ETL-Aware** ⭐ MAIS IMPORTANTE

**Local:** `verba_extensions/startup.py` (linha ~57)

**Na inicialização, chamar:**
```python
# Aplica patch de schema ETL (adiciona propriedades automaticamente)
try:
    from verba_extensions.integration.schema_updater import patch_weaviate_manager_verify_collection
    patch_weaviate_manager_verify_collection()
except Exception as e:
    msg.warn(f"Patch de schema ETL não aplicado: {str(e)}")
```

**Este patch é CRÍTICO** - sem ele, collections serão criadas sem propriedades ETL e não poderão ser atualizadas depois (Weaviate v4).

**Verificar se funcionou:**
- Ao criar collection, deve ver log: "Criando collection X com schema ETL-aware..."
- Collection deve ter 20 propriedades (verificar via `check_collection_has_etl_properties()`)

---

### **Patch 2: ETL Pré-Chunking**

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

---

### **Patch 3: Import Hook**

**Local:** `verba_extensions/startup.py` (linha ~49)

**Na inicialização, chamar:**
```python
# Aplica hooks de integração (ETL)
try:
    from verba_extensions.integration.import_hook import patch_weaviate_manager, patch_verba_manager
    patch_weaviate_manager()  # Hook principal no WeaviateManager
    patch_verba_manager()  # Hook adicional se necessário
except Exception as e:
    msg.warn(f"Hook de integração ETL não aplicado: {str(e)}")
```

---

### **Patch 4: Chunker Entity-Aware**

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
- `verba_extensions/integration/schema_updater.py` - **Schema ETL-aware (CRÍTICO)**
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

- ✅ **Schema ETL-Aware Universal**: Implementado e testado - **CRÍTICO**
  - Collections criadas automaticamente com schema completo (20 propriedades)
  - Serve para chunks normais E ETL-aware
  - Verificação automática na inicialização
- ✅ **ETL Pré-Chunking**: Implementado e testado
- ✅ **Chunker Entity-Aware**: Implementado e testado
- ✅ **ETL Pós-Chunking**: Mantido (já estava funcionando)
- ✅ **Documentação**: Este arquivo

**Última verificação de compatibilidade:** Verba 2.1.x (novembro 2024)

---

## 🚨 IMPORTANTE: Schema ETL-Aware

**O patch de schema é CRÍTICO** porque:

1. **Weaviate v4 não permite adicionar propriedades depois** que collection existe
2. **Collections criadas sem schema ETL** não podem ser atualizadas
3. **Schema ETL-aware serve para ambos os casos:**
   - Chunks normais: propriedades ETL ficam vazias
   - Chunks ETL-aware: propriedades ETL são preenchidas

**Ao atualizar Verba:**
1. ✅ Verificar se `patch_weaviate_manager_verify_collection()` está sendo chamado
2. ✅ Verificar logs: "Patch de schema ETL-aware aplicado"
3. ✅ Testar criação de collection: deve criar com 20 propriedades
4. ✅ Se collection existir sem ETL: deletar e recriar (ou usar script de migração)

**Documentação completa:** `SCHEMA_ETL_AWARE_UNIVERSAL.md`

