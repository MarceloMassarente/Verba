# 🤖 Guia: Sentence Transformers no Verba

## ✅ Sentence Transformers está disponível!

O Verba **tem suporte** para Sentence Transformers, mas ele só aparece quando:
1. ✅ `VERBA_PRODUCTION` **não** está definido como `"Production"`
2. ✅ Biblioteca `sentence-transformers` está instalada

---

## 🔧 Como Ativar

### Opção 1: Desabilitar Modo Production (Recomendado para Railway)

No Railway → **Verba** → Settings → Variables:

```bash
# Remova ou comente esta variável:
# VERBA_PRODUCTION=Production

# OU defina como:
VERBA_PRODUCTION=Local
```

Ou simplesmente **não defina** `VERBA_PRODUCTION` (deixe vazio).

### Opção 2: Instalar sentence-transformers

Adicione ao `requirements-extensions.txt` ou instale manualmente:

```bash
pip install sentence-transformers
```

Para Railway, você pode adicionar ao Dockerfile:

```dockerfile
RUN pip install --no-cache-dir sentence-transformers
```

---

## 📋 Modelos Disponíveis

Quando Sentence Transformers estiver ativo, você terá acesso a:

| Modelo | Descrição | Tamanho |
|--------|-----------|---------|
| `all-MiniLM-L6-v2` | Rápido, bom para geral | ~80MB |
| `all-MiniLM-L12-v2` | Melhor qualidade | ~120MB |
| `all-mpnet-base-v2` | Alta qualidade | ~420MB |
| `mixedbread-ai/mxbai-embed-large-v1` | Multilíngue avançado | ~1.3GB |
| `BAAI/bge-m3` | Multilíngue (inclui PT) | ~1.5GB |
| `paraphrase-MiniLM-L6-v2` | Para parafraseamento | ~80MB |

---

## 🎯 Como Usar

1. **Configure no Railway** (se necessário):
   - Remova `VERBA_PRODUCTION=Production`
   - Adicione `sentence-transformers` às dependências

2. **Na UI do Verba**:
   - Vá em **Import Data** → **Config**
   - Em **Embedder**, escolha **SentenceTransformers**
   - Em **Model**, selecione o modelo desejado

3. **Primeira vez**: O modelo será baixado automaticamente do HuggingFace

---

## ⚠️ Problema Atual

No seu caso, Sentence Transformers **não aparece** porque:
- ❌ Modo Production está ativo (bloqueia embedders locais)
- ❌ Ou `sentence-transformers` não está instalado

**Solução**: Remova `VERBA_PRODUCTION=Production` do Railway!

---

## 🚀 Adicionando ao Dockerfile (Opcional)

Se quiser garantir que está instalado:

```dockerfile
# No Dockerfile, após instalar Verba:
RUN pip install --no-cache-dir sentence-transformers
```

Ou adicione ao `requirements-extensions.txt`:

```txt
sentence-transformers>=2.2.0
```

---

## 📊 Comparação com Outros Embedders

| Embedder | Tipo | Custo | Qualidade | Multilíngue |
|----------|------|-------|-----------|-------------|
| **SentenceTransformers** | Local | Gratuito | ⭐⭐⭐⭐ | ✅ (alguns modelos) |
| OpenAI | API | Pago | ⭐⭐⭐⭐⭐ | ✅ |
| Cohere | API | Pago | ⭐⭐⭐⭐ | ✅ |
| VoyageAI | API | Pago | ⭐⭐⭐⭐⭐ | ✅ |
| Weaviate | Serviço | Depende | ⭐⭐⭐ | ❌ |

**Sentence Transformers é ideal para**:
- ✅ Projetos sem orçamento para APIs
- ✅ Dados sensíveis (processa localmente)
- ✅ Alta performance (sem latência de rede)
- ✅ Português (modelos BAAI/bge-m3)

---

## 🎉 Próximos Passos

1. Remova `VERBA_PRODUCTION=Production` do Railway
2. Aguarde redeploy
3. Sentence Transformers aparecerá no dropdown!
4. Escolha um modelo e teste!

