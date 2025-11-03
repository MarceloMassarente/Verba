# Solução: Conectar Verba ao Weaviate no Railway sem API Key

## Problema Identificado

O código original do Verba **exigia API key obrigatória** quando usava o deployment type "Weaviate", mesmo que seu Weaviate no Railway não tenha autenticação configurada.

## Solução Aplicada

Foi corrigido o método `connect_to_cluster` em `goldenverba/components/managers.py` para permitir conexão **sem API key** quando ela não for fornecida.

## Como Usar Agora

### Opção 1: Deployment "Weaviate" (Recomendado após a correção)

1. No frontend do Verba, selecione **"Weaviate"** como deployment type
2. Informe a **URL completa** do seu Weaviate no Railway (ex: `https://seu-weaviate.railway.app`)
3. **Deixe o campo API Key vazio** ou não preencha
4. Clique em conectar

### Opção 2: Deployment "Custom" (Alternativa)

1. Selecione **"Custom"** como deployment type
2. Informe o **hostname** do Weaviate (ex: `seu-weaviate.railway.app`)
3. Informe a **porta** (geralmente `443` para HTTPS ou `8080` para HTTP)
4. **Deixe o campo API Key vazio**
5. Clique em conectar

## Configuração no Railway

### Variáveis de Ambiente Recomendadas

No seu serviço Verba no Railway, configure:

```bash
WEAVIATE_URL_VERBA=https://seu-weaviate.railway.app
WEAVIATE_API_KEY_VERBA=  # Deixe vazio ou não configure se não tiver API key
```

### Verificando a URL do Weaviate

1. No Railway, vá para o serviço do Weaviate
2. Vá em **Settings** → **Networking**
3. Copie a URL pública (geralmente algo como `https://seu-app.up.railway.app`)
4. Use essa URL no Verba

## Troubleshooting

### Erro: "No URL or API Key provided"
- ✅ **Solução**: A correção permite conexão sem API key agora

### Erro: "Failed to connect"
- Verifique se a URL está correta
- Verifique se o Weaviate está rodando no Railway
- Verifique se a porta está correta (443 para HTTPS, 8080 para HTTP)
- Tente usar deployment "Custom" em vez de "Weaviate"

### Erro: Connection timeout
- Verifique o firewall do Railway
- Certifique-se que o Weaviate aceita conexões externas
- Verifique as configurações de networking no Railway

### Ainda não conecta?

1. Use deployment type **"Custom"**
2. Separe hostname e porta:
   - Host: `seu-weaviate.railway.app` (sem https://)
   - Port: `443` ou `8080`
   - API Key: vazio

## Mudanças Técnicas Realizadas

### Arquivo: `goldenverba/components/managers.py`

**Antes:**
```python
async def connect_to_cluster(self, w_url, w_key):
    if w_url is not None and w_key is not None:
        # Conecta com auth
    else:
        raise Exception("No URL or API Key provided")  # ❌ Sempre exigia API key
```

**Depois:**
```python
async def connect_to_cluster(self, w_url, w_key):
    if w_url is None or w_url == "":
        raise Exception("No URL provided")
    
    if w_key is not None and w_key != "":
        # Conecta com auth
    else:
        # ✅ Conecta sem auth para Railway e outros deployments
        # Extrai host e porta da URL e conecta via use_async_with_local
```

## Testando a Conexão

Após fazer o deploy da correção:

1. Inicie o Verba
2. Vá para a tela de login
3. Selecione deployment "Weaviate"
4. Cole a URL do seu Weaviate no Railway
5. Deixe API key vazio
6. Clique em conectar

Se tudo estiver correto, você verá: `"Succesfully Connected to Weaviate"`

## Notas Importantes

- ⚠️ **Segurança**: Se seu Weaviate não tem autenticação, certifique-se de que ele não está exposto publicamente ou use autenticação
- ⚠️ **Railway**: Alguns serviços Railway podem requerer configurações específicas de networking
- ✅ **Múltiplos Deployments**: O código agora suporta Weaviate com ou sem autenticação

---

**Status**: ✅ Corrigido
**Versão**: 2.1.3+ (com correção)

