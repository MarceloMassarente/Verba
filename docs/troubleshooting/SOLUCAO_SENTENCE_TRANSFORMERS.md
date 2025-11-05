# 🔧 Solução: Sentence Transformers Não Aparece

## 🔴 Problema

Sentence Transformers não aparece no dropdown de Embedders porque:
1. **Modo Production ativo** - `VERBA_PRODUCTION=Production` bloqueia embedders locais
2. **Sentence Transformers é embedder local** - Requer processamento local (não é API)

---

## ✅ Solução

### Opção 1: Remover Modo Production (Recomendado)

No **Railway → Verba → Settings → Variables**:

1. **Remova ou comente**:
   ```bash
   # VERBA_PRODUCTION=Production
   ```

2. **OU altere para**:
   ```bash
   VERBA_PRODUCTION=Local
   ```

3. **Salve** (Railway faz redeploy automático)

### Opção 2: Verificar se sentence-transformers está instalado

Mesmo sem modo Production, precisa estar instalado. Já foi adicionado ao Dockerfile:
```dockerfile
RUN pip install --no-cache-dir sentence-transformers || true
```

Mas verifique se foi instalado nos logs do Railway.

---

## 🔍 Verificação

Após remover `VERBA_PRODUCTION=Production`, nos logs do Railway você deve ver:

```
Verba runs in Local mode
✅ Extensoes carregadas: 3 plugins
```

E na UI, no dropdown de Embedders, você verá:
- ✅ Ollama
- ✅ **SentenceTransformers** ← Deve aparecer agora!
- ✅ Weaviate
- ✅ Upstage
- ✅ VoyageAI
- ✅ Cohere
- ✅ OpenAI

---

## 📋 Checklist

- [ ] `VERBA_PRODUCTION` não está definido OU está como `Local`
- [ ] `sentence-transformers` foi instalado (verificar logs de build)
- [ ] Redeploy completo feito no Railway
- [ ] Limpar cache do navegador (Ctrl+F5)

---

## ⚠️ Por que Modo Production Bloqueia?

O Verba bloqueia embedders locais em modo Production porque:
- **Ollama** - Requer servidor local
- **SentenceTransformers** - Baixa modelos grandes (pode ser lento em produção)

Mas se você tem recursos no Railway, pode usar normalmente!

---

**Próximo passo**: Remova `VERBA_PRODUCTION=Production` do Railway e aguarde redeploy! 🚀

