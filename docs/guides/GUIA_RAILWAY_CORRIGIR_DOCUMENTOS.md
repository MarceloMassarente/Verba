# 🚀 Corrigir Documentos Corrompidos no Railway

## 🔴 Problema

Você tem 4 documentos no Verba que não consegue deletar, com erro:
```
the JSON object must be str, bytes or bytearray, not NoneType
```

**Causa:** Campo `meta` dos documentos está como `None`.

---

## ✅ Solução Rápida no Railway

### Opção 1: Corrigir (Recomendado)

```bash
# 1. Lista documentos corrompidos
railway run python scripts/fix_corrupted_documents_railway.py list

# 2. Corrige todos (cria meta padrão)
railway run python scripts/fix_corrupted_documents_railway.py fix

# 3. Agora você pode deletar pela UI normalmente!
```

### Opção 2: Deletar Diretamente

```bash
# Deleta todos os corrompidos (com confirmação)
railway run python scripts/fix_corrupted_documents_railway.py delete-all
```

---

## 📋 Passo a Passo Completo

### 1. Conecte ao Railway

```bash
# Se ainda não conectou
railway login
railway link
```

### 2. Execute o Script

```bash
# Lista documentos corrompidos
railway run python scripts/fix_corrupted_documents_railway.py list
```

**Saída esperada:**
```
Encontrados 4 documentos corrompidos:
  - Dossiê_Flow Executive Finders.pdf (uuid-1) - meta is None
  - Dossiê_Flow Executive Finders.pdf (uuid-2) - meta is None
  - Dossiê_Flow Executive Finders.pdf (uuid-3) - meta is None
  - Dossiê_Flow Executive Finders.pdf (uuid-4) - meta is None
```

### 3. Corrija os Documentos

```bash
railway run python scripts/fix_corrupted_documents_railway.py fix
```

**Saída esperada:**
```
Corrigindo documentos...
Corrigindo meta do documento uuid-1...
Meta corrigido para documento uuid-1
...
4/4 documentos corrigidos!
```

### 4. Verifique na UI

Agora você pode:
- ✅ Ver os documentos normalmente
- ✅ Deletá-los pela UI do Verba
- ✅ Sem erros de JSON

---

## 🔍 Alternativa: Via Railway Dashboard

Se preferir usar o terminal do Railway:

1. **Acesse Railway Dashboard**
2. **Vá em seu serviço Verba**
3. **Clique em "Deployments" → "View Logs"**
4. **Ou use "Shell" para acessar terminal**

No terminal:

```bash
python scripts/fix_corrupted_documents_railway.py list
python scripts/fix_corrupted_documents_railway.py fix
```

---

## ⚠️ Troubleshooting

### Erro: "Weaviate não está pronto"

**Verifica variáveis de ambiente:**
```bash
railway variables
```

Deve ter:
- `WEAVIATE_HTTP_HOST`
- `WEAVIATE_HTTP_PORT`
- `WEAVIATE_GRPC_HOST` (opcional)
- `WEAVIATE_GRPC_PORT` (opcional)
- `WEAVIATE_API_KEY_VERBA` (se usar auth)

### Erro: "Collection não encontrada"

**Verifica nome da collection:**
O script usa `VERBA_Document` (padrão). Se seu nome for diferente, edite o script.

### Script não encontra documentos

**Possíveis causas:**
1. Documentos já foram corrigidos
2. Collection name diferente
3. Weaviate não está acessível

**Verifica manualmente:**
```bash
railway run python -c "
import weaviate
client = weaviate.connect_to_custom(...)
print(client.collections.list_all())
"
```

---

## 📝 Notas

- **Corrigir vs Deletar:**
  - **Corrigir**: Mantém documentos, apenas adiciona `meta` padrão
  - **Deletar**: Remove documentos permanentemente

- **Chunks:**
  - Ao deletar, o script deleta chunks relacionados automaticamente
  - Busca em todas as collections de embedding

- **Backup:**
  - No Railway, você pode fazer snapshot do volume antes
  - Railway → Service → Settings → Volumes → Snapshot

---

## ✅ Resultado Esperado

Após executar `fix`:
- ✅ Documentos podem ser visualizados na UI
- ✅ Documentos podem ser deletados pela UI
- ✅ Campo `meta` está como JSON válido
- ✅ Erro "JSON object must be str" não aparece mais

---

**Última atualização:** 2025-01-XX

