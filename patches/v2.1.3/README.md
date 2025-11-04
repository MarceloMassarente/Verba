# 🔧 Patches para Verba 2.1.3

Este diretório contém todos os patches necessários para aplicar as customizações no Verba versão 2.1.3.

## 📋 Patches Disponíveis

### 1. **api.py - Carregamento de Extensões**
- **Arquivo:** `goldenverba/server/api.py`
- **Linha:** ~44-55
- **Tipo:** Adição
- **Complexidade:** ⭐ Baixa
- **Status:** ✅ Automatizado (script)

### 2. **api.py - CORS Middleware**
- **Arquivo:** `goldenverba/server/api.py`
- **Linha:** ~72-150
- **Tipo:** Modificação
- **Complexidade:** ⭐⭐ Média
- **Status:** ⚠️ Manual (merge necessário)

### 3. **managers.py - SentenceTransformersEmbedder**
- **Arquivo:** `goldenverba/components/managers.py`
- **Linha:** ~105
- **Tipo:** Adição
- **Complexidade:** ⭐ Baixa
- **Status:** ✅ Automatizado (script)

### 4. **managers.py - connect_to_cluster()**
- **Arquivo:** `goldenverba/components/managers.py`
- **Linha:** ~170-258
- **Tipo:** Modificação
- **Complexidade:** ⭐⭐ Média
- **Status:** ⚠️ Manual

### 5. **managers.py - connect_to_custom()** 🚨
- **Arquivo:** `goldenverba/components/managers.py`
- **Linha:** ~271-460
- **Tipo:** Modificação Completa
- **Complexidade:** ⭐⭐⭐⭐⭐ Muito Alta
- **Status:** ⚠️ Manual (merge complexo)

### 6. **OpenAIGenerator.py - get_models()**
- **Arquivo:** `goldenverba/components/generation/OpenAIGenerator.py`
- **Linha:** ~127-146
- **Tipo:** Modificação
- **Complexidade:** ⭐ Baixa
- **Status:** ⚠️ Manual

### 7. **AnthropicGenerator.py - get_models()**
- **Arquivo:** `goldenverba/components/generation/AnthropicGenerator.py`
- **Linha:** ~24-94
- **Tipo:** Adição
- **Complexidade:** ⭐⭐ Média
- **Status:** ⚠️ Manual

## 🚀 Como Aplicar

### Opção 1: Script Automático (Recomendado)

```bash
# Aplicar patches automáticos (1, 3)
python scripts/apply_patches.py --version 2.1.3

# Verificar patches aplicados
./APLICAR_PATCHES.sh  # Linux/Mac
# ou
.\APLICAR_PATCHES.ps1  # Windows
```

### Opção 2: Manual (Patches Complexos)

Para patches que requerem merge manual (2, 4, 5, 6, 7):

1. **Ver documentação detalhada:**
   - `../../LOG_COMPLETO_MUDANCAS.md`
   - `../../PATCHES_VERBA_WEAVIATE_V4.md`
   - `../../GUIA_APLICAR_PATCHES_UPDATE.md`

2. **Aplicar seguindo os guias:**
   - Cada patch tem seção específica na documentação
   - Código antes/depois está documentado

3. **Verificar após aplicar:**
   ```bash
   python scripts/verify_patches.py --version 2.1.3
   ```

## 📝 Detalhes dos Patches

### Patch 1: Carregamento de Extensões

**Código a adicionar após `load_dotenv()`:**

```python
# Carrega extensões ANTES de criar managers
try:
    import verba_extensions.startup
    from verba_extensions.startup import initialize_extensions
    plugin_manager, version_checker = initialize_extensions()
    if plugin_manager:
        msg.good(f"Extensoes carregadas: {len(plugin_manager.list_plugins())} plugins")
except ImportError:
    msg.info("Extensoes nao disponiveis (continuando sem extensoes)")
except Exception as e:
    msg.warn(f"Erro ao carregar extensoes: {str(e)} (continuando sem extensoes)")
```

**Referência:** `../../LOG_COMPLETO_MUDANCAS.md` linha 49-71

---

### Patch 2: CORS Middleware

**Modificar função `check_same_origin()` adicionando no início:**

```python
# Permite origens do Railway automaticamente
if ".railway.app" in origin.lower():
    return

# Permite ALLOWED_ORIGINS do env
allowed_origins = os.getenv("ALLOWED_ORIGINS", "").split(",")
allowed_origins = [o.strip() for o in allowed_origins if o.strip()]
```

**Referência:** `../../LOG_COMPLETO_MUDANCAS.md` linha 77-106

---

### Patch 3: SentenceTransformersEmbedder

**Adicionar import:**
```python
from goldenverba.components.embedding.SentenceTransformersEmbedder import (
    SentenceTransformersEmbedder,
)
```

**Adicionar na lista de embedders:**
```python
embedders = [
    OllamaEmbedder(),
    SentenceTransformersEmbedder(),  # ← ADICIONAR
    WeaviateEmbedder(),
    # ...
]
```

**Referência:** `../../LOG_COMPLETO_MUDANCAS.md` linha 112-137

---

### Patch 4: connect_to_cluster()

**Adicionar no início da função (após verificação de URL):**

```python
# PRIORIDADE 1: Verificar configuração PaaS explícita
http_host = os.getenv("WEAVIATE_HTTP_HOST")
grpc_host = os.getenv("WEAVIATE_GRPC_HOST")

if http_host and grpc_host:
    # ... lógica completa de conexão PaaS ...
    return client
```

**Referência:** `../../PATCHES_VERBA_WEAVIATE_V4.md` linha 13-82

---

### Patch 5: connect_to_custom() 🚨

**ATENÇÃO:** Este é o patch mais complexo (~200 linhas reescritas).

**Opções:**

1. **Usar backup completo:**
   - Ver `connect_to_custom_backup.py` nesta pasta
   - Substituir método completo

2. **Merge manual:**
   - Seguir `../../PATCHES_VERBA_WEAVIATE_V4.md` linha 92-246
   - Aplicar mudanças incrementalmente

**Recomendação:** Ver `../../PATCHES_VERBA_WEAVIATE_V4.md` para detalhes completos.

---

### Patch 6: OpenAIGenerator.get_models()

**Modificar filtro de modelos para incluir todos modelos de chat:**

Ver `../../LOG_COMPLETO_MUDANCAS.md` linha 195-214 para detalhes.

---

### Patch 7: AnthropicGenerator.get_models()

**Adicionar método completo:**

Ver `../../LOG_COMPLETO_MUDANCAS.md` linha 225 para detalhes.

---

## ✅ Checklist de Aplicação

- [ ] Backup do código original
- [ ] Verificar versão do Verba (`pip show goldenverba`)
- [ ] Aplicar Patch 1 (automático)
- [ ] Aplicar Patch 2 (manual)
- [ ] Aplicar Patch 3 (automático)
- [ ] Aplicar Patch 4 (manual)
- [ ] Aplicar Patch 5 (manual - complexo)
- [ ] Aplicar Patch 6 (manual)
- [ ] Aplicar Patch 7 (manual)
- [ ] Verificar patches aplicados
- [ ] Testar conexão Weaviate
- [ ] Testar plugins
- [ ] Testar ETL

---

## 🔍 Verificação Pós-Patch

```bash
# Verificar se patches foram aplicados
python scripts/verify_patches.py --version 2.1.3

# Testar conexão Weaviate
python test_weaviate_access.py

# Testar sistema completo
python test_sistema_completo.py
```

---

## 📚 Documentação Relacionada

- `../../LOG_COMPLETO_MUDANCAS.md` - Lista completa de mudanças
- `../../PATCHES_VERBA_WEAVIATE_V4.md` - Detalhes técnicos Weaviate
- `../../GUIA_APLICAR_PATCHES_UPDATE.md` - Guia passo a passo
- `../../ANALISE_COMPARATIVA_VERBA_OFFICIAL_VS_CUSTOM.md` - Análise comparativa

---

## ⚠️ Troubleshooting

### Erro: Patch já aplicado

Se um patch já foi aplicado, o script avisará. Você pode:
- Continuar (patch idempotente)
- Verificar se há conflitos

### Erro: Arquivo não encontrado

Verifique se está no diretório correto e se a versão do Verba está correta.

### Erro: Merge conflitos

Para patches manuais com conflitos:
1. Ver diferenças entre versão oficial e customizada
2. Aplicar mudanças incrementalmente
3. Testar após cada mudança

---

**Versão do Verba:** 2.1.3  
**Data de criação:** 2025-11-04  
**Última atualização:** 2025-11-04

