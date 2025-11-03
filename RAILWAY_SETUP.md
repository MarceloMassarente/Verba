# 🚂 Setup Railway - Passo a Passo

## 📋 Situação Atual

Você tem:
- ✅ **Verba** rodando: `verba-production-c347.up.railway.app`
- ✅ **Weaviate** rodando em outro projeto: `weaviate-production-0d0e.up.railway.app`

**Isso está correto!** Cada serviço no Railway é um projeto separado.

---

## ⚙️ Configuração Necessária

### Passo 1: Configure Variáveis no Verba

No projeto **Verba** no Railway:

1. Vá em **Settings** (ícone de engrenagem)
2. Clique em **Variables**
3. Adicione:

```
WEAVIATE_URL_VERBA = https://weaviate-production-0d0e.up.railway.app
WEAVIATE_API_KEY_VERBA = (deixe vazio ou coloque sua key)
```

4. Salve (Railway faz redeploy automaticamente)

### Passo 2: Verifique Logs

Após redeploy, verifique os logs:

```
Railway → Verba → Deploy Logs
```

Procure por:
```
INFO: Connecting to Weaviate at https://weaviate-production-0d0e.up.railway.app
```

---

## 🔍 Por que só uma caixa?

No Railway:
- **Cada serviço = Um projeto**
- **Cada projeto = Uma caixa no dashboard**

Se você quiser ver ambos juntos:
1. Crie um **novo projeto** no Railway
2. Adicione **ambos serviços** nele
3. Aí sim aparecerão 2 caixas

Mas **não é necessário!** O atual (serviços separados) funciona perfeitamente.

---

## ✅ Resumo

| Item | Status | Ação |
|------|--------|------|
| Verba deployado | ✅ OK | Nada |
| Weaviate deployado | ✅ OK | Nada |
| Variáveis configuradas | ⚠️ Fazer | Adicionar `WEAVIATE_URL_VERBA` |
| Conexão funcionando | ❓ Verificar | Checar logs |

---

**Próximo passo**: Configure as variáveis de ambiente no Railway! 🚀

