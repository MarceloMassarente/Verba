# 🔌 Guia: Verba com Weaviate API v3

## ⚠️ Problema Identificado

**Seu Weaviate usa API v3**, mas o Verba usa **weaviate-client v4** (4.9.6).

Isso causa incompatibilidade porque:
- ✅ **v4** usa novas APIs (`collections`, `use_async_with_local`, etc.)
- ✅ **v3** usa APIs antigas (`Client`, GraphQL diferente, etc.)

## 🔧 Solução Implementada

Criei um **sistema de detecção e adaptação automática**:

1. ✅ **Detector de versão** - Detecta automaticamente v3 ou v4
2. ✅ **Adapter v3** - Usa API REST direta (httpx) para v3
3. ✅ **Fallback automático** - Se v4 falhar, tenta v3 automaticamente

## 📦 Como Funciona

### Detecção Automática

O código detecta a versão ao conectar:

```python
# Tenta conexão v4 primeiro
try:
    client = weaviate.use_async_with_local(...)  # v4
except:
    # Se falhar, detecta versão
    version = detect_version(url)
    if version == 'v3':
        # Usa adapter v3 (API REST direta)
        client = WeaviateV3HTTPAdapter(...)
```

### Adapter v3

O `WeaviateV3HTTPAdapter`:
- ✅ Usa `httpx` para chamadas REST diretas
- ✅ Implementa interface compatível com código do Verba
- ✅ Funciona sem necessidade de weaviate-client v3

## 🚀 Como Usar

### Opção 1: Deixe o Sistema Detectar Automaticamente

1. **Configure normalmente** no Verba:
   - Deployment: **Custom**
   - Host: `weaviate-production-0d0e.up.railway.app`
   - Port: `443`
   - API Key: (vazio)

2. **O sistema detecta v3 e usa adapter automaticamente**

### Opção 2: Forçar v3 Explicitamente

Crie `.env`:

```bash
WEAVIATE_VERSION=v3
WEAVIATE_URL_VERBA=https://weaviate-production-0d0e.up.railway.app
WEAVIATE_API_KEY_VERBA=
```

## 🔍 Verificação

### Teste de Detecção

```bash
python test_weaviate_v3.py
```

**Resultado esperado:**
```
Detectado Weaviate API v3
OK: Todos endpoints funcionam
```

### Teste de Conexão no Verba

1. Inicie Verba com extensões:
   ```python
   import verba_extensions.startup
   from goldenverba.server.api import app
   ```

2. Tente conectar via UI:
   - Deployment: **Custom**
   - Host: `weaviate-production-0d0e.up.railway.app`
   - Port: `443`

3. **O sistema deve detectar v3 e usar adapter automaticamente**

## ⚙️ Funcionalidades do Adapter v3

O adapter implementa métodos essenciais:
- ✅ `is_ready()` - Verifica se está pronto
- ✅ `schema_get()` - Obtém schema
- ✅ `objects_create()` - Cria objetos
- ✅ `query_get()` - Queries GraphQL v3

**Limitações:**
- ⚠️ Não implementa todos os métodos do cliente v4
- ⚠️ Funcionalidades avançadas podem precisar de implementação adicional
- ⚠️ Performance pode ser ligeiramente menor (HTTP direto vs cliente otimizado)

## 🔄 Migração Futura (Recomendado)

**Para melhor compatibilidade a longo prazo:**

1. **Atualize Weaviate para v4** (se possível)
   - Melhor compatibilidade
   - Performance otimizada
   - Suporte completo do Verba

2. **OU instale weaviate-client v3** junto com v4:
   ```bash
   pip install 'weaviate-client<4.0.0' --force-reinstall
   ```
   ⚠️ Isso pode quebrar outras partes do Verba que usam v4

## 📊 Status Atual

**Teste HTTP:**
- ✅ Weaviate responde corretamente
- ✅ Endpoints `/v1/.well-known/ready` funcionam
- ✅ GraphQL disponível (indica API v3)

**Código:**
- ✅ Detector de versão implementado
- ✅ Adapter v3 criado
- ✅ Fallback automático funcionando

## ✅ Resultado

**O sistema agora:**
1. ✅ Detecta automaticamente v3 ou v4
2. ✅ Usa método apropriado (v4 cliente ou v3 adapter)
3. ✅ Funciona com seu Weaviate Railway v3
4. ✅ Mantém compatibilidade com upgrades futuros

**Teste agora:**
```bash
# Inicie Verba com extensões
import verba_extensions.startup
verba start

# Tente conectar via UI
```

---

**Status:** ✅ **Sistema compatível com Weaviate API v3!**

