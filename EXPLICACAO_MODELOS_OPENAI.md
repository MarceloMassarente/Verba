# 🤖 Por Que Só Aparecem Alguns Modelos OpenAI?

## 🔍 Como Funciona

O Verba busca modelos da OpenAI de **duas formas**:

### **1. Busca Dinâmica (Quando API Key Está Configurada):**

```python
# goldenverba/components/generation/OpenAIGenerator.py linha 127-146

def get_models(self, token: str, url: str):
    try:
        # Busca modelos da API da OpenAI
        response = requests.get(f"{url}/models", headers={
            "Authorization": f"Bearer {token}"
        })
        
        # Filtra apenas modelos de chat (remove embedding models)
        return [
            model["id"]
            for model in response.json()["data"]
            if not "embedding" in model["id"]
        ]
    except:
        # Se falhar, retorna lista padrão
        return ["gpt-4o", "gpt-3.5-turbo"]
```

**Se a API Key estiver configurada:**
- ✅ Busca modelos **diretamente da API da OpenAI**
- ✅ Mostra **todos os modelos disponíveis** na sua conta
- ✅ Inclui modelos novos automaticamente (quando lançados)

### **2. Lista Padrão (Fallback):**

**Se a API Key NÃO estiver configurada:**
- ❌ Retorna apenas: `["gpt-4o", "gpt-3.5-turbo"]`
- ❌ Não busca da API
- ❌ Não mostra modelos novos

---

## 🚨 Por Que Só Aparecem 2 Modelos?

### **Causa Provável:**

**API Key não está configurada ou não está sendo detectada**

Verifique:
1. **Na UI**: Campo "API Key" está vazio?
2. **Environment Variable**: `OPENAI_API_KEY` não está definida no Railway?
3. **Erro na busca**: Verifique logs para ver se há erro ao buscar modelos

---

## ✅ Solução

### **Opção 1: Configurar API Key na UI**

1. Na seção **Generator** → **OpenAI**
2. Preencha o campo **"API Key"** com sua chave
3. Clique em **"Save"**
4. **Recarregue a página** ou reinicie o Verba

O Verba irá:
- Buscar modelos diretamente da API
- Mostrar **todos os modelos disponíveis** na sua conta

### **Opção 2: Configurar via Environment Variable**

No **Railway → Verba → Settings → Variables**:

```bash
OPENAI_API_KEY=sk-...
```

Depois:
1. Redeploy
2. O Verba buscará modelos automaticamente

---

## 📋 Modelos Que Devem Aparecer (Se API Key Configurada)

Com API Key válida, você deve ver:

**Modelos de Chat:**
- ✅ `gpt-4o`
- ✅ `gpt-4o-mini`
- ✅ `gpt-4-turbo`
- ✅ `gpt-4`
- ✅ `gpt-3.5-turbo`
- ✅ `o1-preview` (se disponível)
- ✅ `o1-mini` (se disponível)
- ✅ Qualquer modelo novo que a OpenAI lançar!

**Modelos Filtrados (NÃO aparecem):**
- ❌ `text-embedding-*` (são embedding models, não chat)
- ❌ `whisper-*` (são modelos de áudio)
- ❌ `dall-e-*` (são modelos de imagem)

---

## ⚠️ Sobre GPT-5

**IMPORTANTE**: 
- **GPT-5 ainda não foi lançado** (até janeiro 2025)
- **GPT-5-mini também não existe** ainda
- Modelos mais recentes disponíveis: `gpt-4o`, `gpt-4o-mini`, `o1-preview`

**Quando GPT-5 for lançado:**
- Se você tiver API Key configurada → Aparecerá automaticamente
- Se não tiver API Key → Precisará atualizar a lista padrão no código

---

## 🔧 Como Atualizar Lista Padrão (Se Necessário)

Se você quiser adicionar modelos manualmente sem API Key:

```python
# goldenverba/components/generation/OpenAIGenerator.py linha 129

default_models = [
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4-turbo",
    "gpt-3.5-turbo",
    "o1-preview",  # Se disponível
    "o1-mini",      # Se disponível
]
```

Mas **recomendação**: Configure a API Key e deixe buscar automaticamente!

---

## 🔍 Verificação

### **Teste se API Key Está Funcionando:**

1. Configure API Key na UI
2. Verifique logs do Verba (Railway)
3. Deve aparecer: `✅ Fetched X OpenAI models from API`
4. Ou erro: `⚠️ Failed to fetch OpenAI models: ...`

### **Ver Quantos Modelos Foram Carregados:**

Após configurar API Key e recarregar:
- O dropdown deve mostrar **mais de 2 opções** (se sua conta tiver acesso)
- Se ainda mostra só 2 → API Key não está funcionando ou não tem acesso a mais modelos

---

## 💡 Recomendação

**Configure a API Key na UI ou via environment variable!**

Isso permite:
- ✅ Ver todos os modelos disponíveis automaticamente
- ✅ Novos modelos aparecem automaticamente quando lançados
- ✅ Não precisa atualizar código manualmente

---

**Resumo**: Se só aparecem 2 modelos, é porque a API Key não está configurada. Configure e todos os modelos disponíveis na sua conta aparecerão automaticamente! 🚀

