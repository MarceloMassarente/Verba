# 🔧 Fix: SentenceTransformers Embedder - Meta Tensor Issue

## 🎯 Problema Resolvido

**Erro original:**
```
Cannot copy out of meta tensor; no data!
Please use torch.nn.Module.to_empty() instead of torch.nn.Module.to() when moving 
module from meta to a different device.
```

**Causa raiz:** Modelo SentenceTransformer sendo instanciado múltiplas vezes em batch vectorization, causando conflitos de device placement e meta tensor state.

---

## ✅ Solução Implementada

Modificações em `goldenverba/components/embedding/SentenceTransformersEmbedder.py`:

### 1. **Model Caching** - Evita recarregamento

```python
def __init__(self):
    # ...
    self._model_cache = {}  # Cache de modelos para evitar recarregamento
```

**Benefício:** Modelo é carregado uma única vez e reutilizado em todos os batches.

### 2. **Device Detection** - Detecção segura de dispositivo

```python
def _get_device(self) -> str:
    """Detecta device disponível de forma segura."""
    try:
        import torch
        if torch.cuda.is_available():
            try:
                _ = torch.zeros(1).to("cuda")
                return "cuda"
            except Exception:
                pass
    except Exception:
        pass
    return "cpu"
```

**Benefício:** 
- Verifica CUDA com fallback seguro
- CPU é default (evita meta tensor issues em GPU)
- Testa device antes de usar

### 3. **Explicit Device Parameter** - Força device no carregamento

```python
model = SentenceTransformer(
    model_name,
    device=device,  # ← Explicit device
    trust_remote_code=True
)
model.eval()  # ← Modo de inferência
```

**Benefício:** Remove ambiguidade de device, evita lazy loading issues.

### 4. **Convert to Tensor = False** - Evita conversão automática

```python
embeddings = model.encode(
    content,
    convert_to_tensor=False,  # ← Retorna numpy array
    show_progress_bar=False
)
```

**Benefício:** Evita que SentenceTransformers tente converter tensores automaticamente.

### 5. **Better Error Handling** - Logging detalhado

```python
except Exception as e:
    msg.fail(f"[SentenceTransformersEmbedder] ❌ Erro na vetorização: {str(e)}")
    import traceback
    msg.fail(f"[SentenceTransformersEmbedder] Traceback: {traceback.format_exc()}")
    raise Exception(f"Failed to vectorize chunks: {str(e)}")
```

**Benefício:** Logs com contexto completo para debug.

---

## 📊 Comparação Antes vs Depois

| Aspecto | Antes | Depois |
|--------|-------|--------|
| **Modelo carregado por** | Batch (3x para 3 batches) | Primeira vez + cache |
| **Device handling** | Implícito/Auto | Explícito + fallback |
| **Tensor conversion** | Automática | Manual (numpy) |
| **Error messages** | Genérico | Contexto + traceback |
| **Meta tensor risk** | 🔴 Alto | 🟢 Baixo |
| **Performance** | ❌ Lento (reload) | ✅ Rápido (cached) |

---

## 🧪 Como Testar

### 1. **Teste Local - Single Chunk**

```python
from goldenverba.components.embedding.SentenceTransformersEmbedder import SentenceTransformersEmbedder
from goldenverba.components.types import InputConfig

embedder = SentenceTransformersEmbedder()
config = {
    "Model": InputConfig(type="dropdown", value="all-MiniLM-L6-v2")
}

# Test single chunk
embeddings = embedder._vectorize_sync(config, ["Hello world"])
print(f"✅ Single chunk: {len(embeddings[0])} dims")
```

### 2. **Teste Local - Batch com 10 Chunks**

```python
content = ["Chunk " + str(i) for i in range(10)]
embeddings = embedder._vectorize_sync(config, content)
print(f"✅ 10 chunks: {len(embeddings)} embeddings, {len(embeddings[0])} dims")
```

### 3. **Teste Local - 3 Batches Paralelos**

```python
import asyncio

async def test_parallel_batches():
    embedder = SentenceTransformersEmbedder()
    config = {"Model": InputConfig(type="dropdown", value="all-MiniLM-L6-v2")}
    
    # Simular 3 batches como em batch_vectorize
    batches = [
        ["Batch 1 - " + str(i) for i in range(10)],
        ["Batch 2 - " + str(i) for i in range(10)],
        ["Batch 3 - " + str(i) for i in range(10)],
    ]
    
    tasks = [
        asyncio.create_task(
            asyncio.get_event_loop().run_in_executor(
                None, embedder._vectorize_sync, config, batch
            )
        )
        for batch in batches
    ]
    
    results = await asyncio.gather(*tasks)
    print(f"✅ 3 batches paralelos: {len(results)} resultados")

asyncio.run(test_parallel_batches())
```

### 4. **Teste End-to-End via Web Interface**

1. Acessar `https://verba-production-c347.up.railway.app/` ou local
2. Upload de documento (PDF/DOCX)
3. Selecionar embedder SentenceTransformers
4. Iniciar ingestion
5. Monitorar logs para:
   - ✅ `[SentenceTransformersEmbedder] Carregando modelo`
   - ✅ `[SentenceTransformersEmbedder] ✅ Modelo carregado em device: cpu`
   - ✅ `[SentenceTransformersEmbedder] Vetorizando N chunks`
   - ✅ `[BATCH_VECTORIZE] Vectorizing X chunks in Y batches`
   - ❌ Sem erros de meta tensor

---

## 🚀 Deployment Steps

### 1. **Aplicar patch**
```bash
cd /path/to/Verba
git add goldenverba/components/embedding/SentenceTransformersEmbedder.py
git commit -m "fix: SentenceTransformers meta tensor issue with model caching"
```

### 2. **Test local**
```bash
python -m pytest tests/embedding/test_sentence_transformers.py -v
```

### 3. **Deploy para produção**
```bash
git push
# Rebuild container
docker-compose down
docker-compose up --build
```

### 4. **Verificar produção**
- Testar ingestion via web interface
- Monitorar logs em tempo real
- Validar que chunks foram vetorizados com sucesso

---

## 📝 Checklist de Validação

- [ ] Código compila sem erros
- [ ] Teste local: single chunk ✅
- [ ] Teste local: 10 chunks ✅
- [ ] Teste local: 3 batches paralelos ✅
- [ ] Teste web: upload de documento ✅
- [ ] Logs mostram device correto ✅
- [ ] Sem erros de meta tensor ✅
- [ ] Documento importado com sucesso ✅
- [ ] Search funciona com chunks importados ✅

---

## 🔗 Arquivos Relacionados

- `goldenverba/components/embedding/SentenceTransformersEmbedder.py` - **MODIFICADO**
- `goldenverba/components/managers.py:EmbeddingManager.batch_vectorize()` - Chama vectorize()
- `ANALISE_LOGS_INGESTION_FALHA_VETORIZACAO.md` - Análise detalhada do problema

---

## 📞 Suporte

Se o erro persistir após o fix:

1. Verificar versões:
```bash
pip show torch sentence-transformers
```

2. Verificar device:
```python
import torch
print(f"CUDA available: {torch.cuda.is_available()}")
print(f"CUDA device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A'}")
```

3. Testar modelo isoladamente:
```python
from sentence_transformers import SentenceTransformer
model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
embeddings = model.encode(["test"], convert_to_tensor=False)
print(embeddings.shape)
```

4. Abrir issue com logs completos de erro

---

**Data do fix:** 2025-12-02
**Status:** ✅ IMPLEMENTADO
**Prioridade:** 🔴 CRÍTICA



