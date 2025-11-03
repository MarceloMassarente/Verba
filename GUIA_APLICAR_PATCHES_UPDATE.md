# 🔄 Guia: Aplicar Patches Após Update do Verba

## 🎯 Objetivo

Replicar todas as mudanças customizadas após atualizar o Verba para uma versão nova.

---

## 📋 Pré-requisitos

1. ✅ Backup do código atual
2. ✅ Nova versão do Verba baixada
3. ✅ Acesso aos arquivos modificados

---

## 🔧 Passo a Passo

### **PASSO 1: Backup**

```bash
# Antes de atualizar, faça backup
cp -r goldenverba goldenverba_backup
cp goldenverba/server/api.py goldenverba/server/api.py.backup
cp goldenverba/components/managers.py goldenverba/components/managers.py.backup
```

---

### **PASSO 2: Atualizar Verba**

```bash
# Puxar nova versão do Verba
git pull upstream main  # ou como você atualiza

# OU clonar nova versão
git clone https://github.com/weaviate/verba.git verba_new
```

---

### **PASSO 3: Aplicar Mudanças Core**

#### **Mudança 1: Carregamento de Extensões**

**Arquivo**: `goldenverba/server/api.py`

**Localização**: Logo após `load_dotenv()`, antes de criar `VerbaManager`

**Adicionar**:
```python
# Carrega extensões ANTES de criar managers
# Isso garante que plugins apareçam na lista de componentes
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

---

#### **Mudança 2: CORS Middleware para Railway**

**Arquivo**: `goldenverba/server/api.py`

**Localização**: Função `check_same_origin()` (dentro do middleware)

**Modificar função para incluir**:
```python
def check_same_origin(request: Request):
    """Verifica se requisição vem do mesmo origin, com suporte a Railway"""
    origin = request.headers.get("origin")
    if not origin:
        return
    
    # Normaliza URLs (ignora http/https)
    def normalize_url(url: str) -> str:
        return url.replace("https://", "").replace("http://", "").lower().rstrip("/")
    
    # Permite origens do Railway automaticamente
    if ".railway.app" in origin.lower():
        return
    
    # Permite ALLOWED_ORIGINS do env
    allowed_origins = os.getenv("ALLOWED_ORIGINS", "").split(",")
    allowed_origins = [o.strip() for o in allowed_origins if o.strip()]
    
    # ... resto da lógica original ...
```

**⚠️ Importante**: Manter lógica original, apenas adicionar essas checagens no início!

---

#### **Mudança 3: SentenceTransformers Embedder**

**Arquivo**: `goldenverba/components/managers.py`

**Localização**: Lista `embedders` quando `production != "Production"`

**Adicionar import**:
```python
from goldenverba.components.embedding.SentenceTransformersEmbedder import (
    SentenceTransformersEmbedder,
)
```

**Adicionar na lista**:
```python
embedders = [
    OllamaEmbedder(),
    SentenceTransformersEmbedder(),  # ← ADICIONAR AQUI
    WeaviateEmbedder(),
    # ... resto
]
```

---

#### **Mudança 4: Método `connect_to_custom()`**

**Arquivo**: `goldenverba/components/managers.py`

**⚠️ ATENÇÃO**: Este método foi completamente reescrito. Duas opções:

**Opção A: Substituir Método Completo**
- Copiar método completo do backup
- Verificar se Verba adicionou melhorias no método original
- Fazer merge manual se necessário

**Opção B: Adicionar Lógica Incremental**
- Manter método original do Verba
- Adicionar nossa lógica no início/fim
- Ver `CONNECT_TO_CUSTOM_PATCH.md` para detalhes

**Recomendação**: Use a versão completa do backup se não houver mudanças no método original no update.

---

### **PASSO 4: Copiar Arquivos Novos**

```bash
# Copiar sistema de extensões
cp -r verba_extensions/ verba_nova/

# Copiar scripts
cp -r scripts/ verba_nova/

# Copiar documentação (opcional)
cp *.md verba_nova/

# Copiar Dockerfiles modificados
cp Dockerfile verba_nova/
cp docker-compose.yml verba_nova/
cp requirements-extensions.txt verba_nova/
```

---

### **PASSO 5: Verificar Dependências**

```bash
# Verificar se requirements-extensions.txt está atualizado
# Adicionar novas dependências se necessário

# Atualizar Dockerfile se Verba mudou estrutura
```

---

### **PASSO 6: Testar**

```bash
# 1. Testar conexão Weaviate
python -c "from goldenverba.components.managers import WeaviateManager; ..."

# 2. Testar carregamento de plugins
python -c "from verba_extensions.startup import initialize_extensions; ..."

# 3. Testar sistema completo
python test_sistema_completo.py
```

---

## 📝 Script de Patch Automático (Opcional)

Podemos criar um script Python que aplica patches automaticamente:

```python
# apply_patches.py
# Lê LOG_COMPLETO_MUDANCAS.md e aplica patches automaticamente
```

Quer que eu crie esse script? 🛠️

---

## 🔍 Verificação Pós-Patch

Após aplicar todos os patches:

1. ✅ Verificar logs: "Extensoes carregadas: X plugins"
2. ✅ Verificar UI: Plugins aparecem nos dropdowns?
3. ✅ Testar conexão Weaviate
4. ✅ Testar import com ETL
5. ✅ Testar EntityAware Retriever

---

## ⚠️ Conflitos Comuns

### **Conflito 1: Verba mudou `connect_to_custom()`**

**Solução**:
1. Comparar versões (original vs nossa)
2. Manter melhorias do Verba
3. Adicionar nossa lógica de Railway/v3

### **Conflito 2: Verba mudou estrutura de `api.py`**

**Solução**:
1. Localizar onde está `load_dotenv()` na nova versão
2. Adicionar nosso código logo após
3. Ajustar imports se necessário

### **Conflito 3: Verba mudou lista de embedders**

**Solução**:
1. Encontrar lista `embedders` na nova versão
2. Adicionar `SentenceTransformersEmbedder()` na mesma posição
3. Verificar imports

---

## 💡 Dicas

1. **Use git diff**: Compare backup vs nova versão
2. **Use git merge**: Se possível, faça merge ao invés de substituir
3. **Teste incrementalmente**: Aplique um patch, teste, continue
4. **Mantenha logs**: Documente qualquer ajuste adicional necessário

---

## 📋 Checklist Final

- [ ] Backup feito
- [ ] Verba atualizado
- [ ] Mudança 1 aplicada (extensões)
- [ ] Mudança 2 aplicada (CORS)
- [ ] Mudança 3 aplicada (SentenceTransformers)
- [ ] Mudança 4 aplicada (connect_to_custom)
- [ ] Arquivos novos copiados
- [ ] Dependências atualizadas
- [ ] Testes passando
- [ ] Documentação atualizada

---

**Pronto para aplicar patches em qualquer update do Verba!** 🚀

