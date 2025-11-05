# 🔌 Guia de Conexão - Weaviate Railway

## ✅ Status do Teste

**Seu Weaviate está funcionando!** ✅

- ✅ URL responde: `https://weaviate-production-0d0e.up.railway.app`
- ✅ Endpoint `/v1/.well-known/ready` retorna 200
- ✅ Endpoint `/v1/meta` retorna informações válidas
- ✅ **Não precisa de API Key** (acesso público)

## 🔧 Como Conectar no Verba

### Opção 1: Via UI do Verba (Recomendado)

1. **Abra Verba UI** (localhost:8000)
2. **Tela de Login/Deployment:**
   - Selecione **"Custom"** como deployment type
   - **URL/Host**: `weaviate-production-0d0e.up.railway.app`
   - **Port**: `443`
   - **API Key**: (deixe vazio)
3. Clique em **Conectar**

### Opção 2: Via Variáveis de Ambiente

Crie um arquivo `.env`:

```bash
WEAVIATE_URL_VERBA=https://weaviate-production-0d0e.up.railway.app
WEAVIATE_API_KEY_VERBA=
DEFAULT_DEPLOYMENT=Custom
```

**OU** configure diretamente:

```bash
export WEAVIATE_URL_VERBA="https://weaviate-production-0d0e.up.railway.app"
export WEAVIATE_API_KEY_VERBA=""  # Vazio
export DEFAULT_DEPLOYMENT="Custom"
```

## 🔍 Verificação

### Teste HTTP (Já Funcionou)

```bash
python test_http.py
```

**Resultado esperado:**
```
OK: Weaviate esta respondendo!
```

### Teste com Verba (Se Versão Compatível)

O código que corrigimos (`goldenverba/components/managers.py`) suporta conexão sem API key para deployment "Custom".

**Configuração:**
- Deployment: **Custom**
- Host: `weaviate-production-0d0e.up.railway.app`
- Port: `443`
- API Key: (vazio)

## ⚠️ Possíveis Problemas

### 1. Versão weaviate-client Incompatível

Se der erro `cannot import name 'WeaviateAsyncClient'`:

```bash
# Atualiza weaviate-client
pip install --upgrade weaviate-client==4.9.6
```

### 2. HTTPS não Suportado

O código atual do Verba pode ter problemas com HTTPS direto. Neste caso:

**Solução:** Use proxy reverso ou configure Railway para aceitar HTTP também (não recomendado para produção).

### 3. Porta Incorreta

Railway pode usar porta customizada. Verifique:

```bash
# No Railway, vá em Settings → Networking
# Veja a porta pública configurada
```

## ✅ Checklist de Conexão

- [ ] Weaviate responde HTTP (teste: `python test_http.py`)
- [ ] Deployment type: **Custom**
- [ ] Host correto: `weaviate-production-0d0e.up.railway.app`
- [ ] Port: **443** (para HTTPS)
- [ ] API Key: **vazio** (se não tiver autenticação)
- [ ] Verba versão compatível (>=2.1.0)

## 🎯 Exemplo de Uso no Código

```python
from goldenverba.components.managers import WeaviateManager

manager = WeaviateManager()

client = await manager.connect(
    deployment="Custom",
    weaviateURL="weaviate-production-0d0e.up.railway.app",
    weaviateAPIKey="",  # Vazio
    port="443"
)

if await client.is_ready():
    print("Conectado com sucesso!")
```

## 📊 Informações do Weaviate

Baseado no teste HTTP, seu Weaviate tem:
- ✅ Módulos generativos instalados (Anthropic, Cohere, AWS, etc.)
- ✅ API REST funcionando
- ✅ Sem autenticação configurada (acesso público)

## 🔒 Segurança (Importante)

**⚠️ Seu Weaviate está sem autenticação!**

Recomendações:
1. Configure autenticação no Railway se possível
2. Use rede privada se possível
3. Limite acesso por IP se necessário

Para produção, considere adicionar autenticação.

---

**Status:** ✅ **Weaviate funcionando e acessível!**

A conexão deve funcionar com o código corrigido do Verba.

