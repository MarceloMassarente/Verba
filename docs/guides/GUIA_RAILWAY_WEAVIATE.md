# 🚂 Guia: Configurar Weaviate no Railway

## 📋 Como Funciona no Railway

No Railway, **cada serviço é um projeto separado**. Então você tem:

```
Projeto 1: Verba (verba-production-c347.up.railway.app)
  └─ Caixa única: Verba

Projeto 2: Weaviate (weaviate-production-0d0e.up.railway.app)  
  └─ Caixa única: Weaviate
```

**Isso está correto!** Não precisa aparecer Weaviate na mesma caixa do Verba.

---

## ✅ Configuração Correta

### 1. Verba deve usar Weaviate Externo

O Verba precisa se conectar ao Weaviate que está **em outro projeto** via variáveis de ambiente.

### 2. Configure no Railway

No projeto **Verba** no Railway:

1. Vá em **Settings** → **Variables**
2. Adicione estas variáveis:

```
WEAVIATE_URL_VERBA=https://weaviate-production-0d0e.up.railway.app
WEAVIATE_API_KEY_VERBA=  (deixe vazio se não tiver)
```

**OU** use o domínio público do Weaviate se estiver configurado.

### 3. Verifique Connection String

O Railway pode usar **variáveis privadas** entre serviços. Se ambos estão no mesmo projeto/workspace, você pode usar:

```
WEAVIATE_URL_VERBA=${{Weaviate.RAILWAY_PRIVATE_DOMAIN}}
```

Mas como estão em projetos separados, use a URL pública:

```
WEAVIATE_URL_VERBA=https://weaviate-production-0d0e.up.railway.app
```

---

## 🔍 Verificação

### Nos Logs do Verba

Você deve ver algo como:

```
INFO: Connecting to Weaviate Custom
INFO: Connecting to Weaviate at https://weaviate-production-0d0e.up.railway.app
```

Se aparecer erro de conexão, verifique:
1. A URL está correta?
2. O Weaviate está rodando?
3. Firewall/Rede permite conexão?

---

## 🎯 Resumo Visual

```
┌─────────────────────────────────────┐
│  Railway Dashboard                 │
├─────────────────────────────────────┤
│                                     │
│  Projeto: Verba                     │
│  ┌──────────────┐                  │
│  │   Verba      │ ──┐              │
│  │              │   │              │
│  └──────────────┘   │              │
│                     │              │
│  Projeto: Weaviate  │              │
│  ┌──────────────┐   │              │
│  │  Weaviate    │ ←─┘ (conecta via │
│  │              │      variável env)│
│  └──────────────┘                  │
└─────────────────────────────────────┘
```

---

## ⚙️ Dockerfile para Railway

O Dockerfile que criamos já está correto. Mas no Railway, como usa Weaviate externo:

1. **Não precisa do serviço weaviate no docker-compose** (Railway não usa docker-compose)
2. **Use variáveis de ambiente** no Railway Settings
3. **O Dockerfile já instala tudo necessário**

---

## 📝 Checklist Railway

- [x] Verba deployado (caixa única - correto!)
- [ ] Variável `WEAVIATE_URL_VERBA` configurada no Verba
- [ ] Variável `WEAVIATE_API_KEY_VERBA` configurada (ou vazia)
- [ ] Weaviate está rodando em outro projeto
- [ ] Logs do Verba mostram conexão bem-sucedida

---

## 🚨 Se não conectar

### Erro: "Couldn't connect to Weaviate"

1. Verifique URL no Settings → Variables:
   ```
   WEAVIATE_URL_VERBA=https://weaviate-production-0d0e.up.railway.app
   ```

2. Teste se Weaviate está acessível:
   ```bash
   curl https://weaviate-production-0d0e.up.railway.app/v1/.well-known/ready
   ```

3. Verifique logs do Verba:
   - Railway → Verba → Deploy Logs
   - Procure por mensagens de conexão

---

## ✅ Status Atual

Baseado nas imagens que você mostrou:

- ✅ Verba está deployado e rodando
- ✅ Build logs mostram instalação correta
- ✅ Aplicação iniciou com sucesso
- ⚠️ Falta configurar variáveis do Weaviate

**Próximo passo**: Configure `WEAVIATE_URL_VERBA` nas variáveis de ambiente do Railway!

