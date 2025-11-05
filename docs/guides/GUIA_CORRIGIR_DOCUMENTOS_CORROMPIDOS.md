# 🔧 Guia: Corrigir Documentos Corrompidos no Weaviate

## 🔴 Problema

Você tem documentos no Verba que não consegue deletar, com erro:
```
the JSON object must be str, bytes or bytearray, not NoneType
```

**Causa:** O campo `meta` do documento está como `None` quando deveria ser uma string JSON válida.

---

## ✅ Solução

Use o script `fix_corrupted_documents.py` para identificar e corrigir/deletar documentos corrompidos.

---

## 🚀 Como Usar

### 1. Listar Documentos Corrompidos

```bash
cd C:\Users\marce\VERBA\Verba
python scripts/fix_corrupted_documents.py list
```

**Saída esperada:**
```
⚠️  Encontrados 4 documentos corrompidos:
  - Dossiê_Flow Executive Finders.pdf (uuid-1) - meta is None
  - Dossiê_Flow Executive Finders.pdf (uuid-2) - meta is None
  - Dossiê_Flow Executive Finders.pdf (uuid-3) - meta is None
  - Dossiê_Flow Executive Finders.pdf (uuid-4) - meta is None
```

---

### 2. Corrigir Documentos (Recomendado)

Cria um `meta` padrão para cada documento corrompido:

```bash
python scripts/fix_corrupted_documents.py fix
```

**O que faz:**
- Cria um campo `meta` padrão com embedder `all-MiniLM-L6-v2`
- Documentos podem ser deletados normalmente depois
- Chunks não são afetados

---

### 3. Deletar Documento Específico

Se você souber o UUID do documento:

```bash
python scripts/fix_corrupted_documents.py delete <uuid>
```

**Exemplo:**
```bash
python scripts/fix_corrupted_documents.py delete abc-123-def-456
```

---

### 4. Deletar TODOS os Documentos Corrompidos

**⚠️ ATENÇÃO:** Isso deleta todos os documentos corrompidos sem confirmação individual!

```bash
python scripts/fix_corrupted_documents.py delete-all
```

Vai pedir confirmação digitando `SIM`.

---

## 📋 Passo a Passo Completo

### Opção A: Corrigir (Recomendado)

```bash
# 1. Lista documentos corrompidos
python scripts/fix_corrupted_documents.py list

# 2. Corrige todos
python scripts/fix_corrupted_documents.py fix

# 3. Agora você pode deletar pela UI do Verba normalmente
```

### Opção B: Deletar Diretamente

```bash
# 1. Lista documentos corrompidos
python scripts/fix_corrupted_documents.py list

# 2. Copia os UUIDs que quer deletar

# 3. Deleta um por um
python scripts/fix_corrupted_documents.py delete <uuid-1>
python scripts/fix_corrupted_documents.py delete <uuid-2>
python scripts/fix_corrupted_documents.py delete <uuid-3>
python scripts/fix_corrupted_documents.py delete <uuid-4>

# OU deleta todos de uma vez (com confirmação)
python scripts/fix_corrupted_documents.py delete-all
```

---

## 🔍 Verificação

Após corrigir, verifique:

1. **Lista documentos novamente:**
   ```bash
   python scripts/fix_corrupted_documents.py list
   ```
   Deve mostrar: `✅ Nenhum documento corrompido encontrado!`

2. **Tenta deletar pela UI do Verba:**
   - Vá em Documents
   - Clique no ícone de lixeira
   - Deve funcionar agora!

---

## 🐛 Troubleshooting

### Erro: "Weaviate não está pronto"

**Solução:**
```bash
# Verifica variáveis de ambiente
echo $WEAVIATE_URL_VERBA
echo $WEAVIATE_API_KEY_VERBA

# Ou configure manualmente
export WEAVIATE_URL_VERBA="http://weaviate:8080"
export WEAVIATE_API_KEY_VERBA="sua-chave"
```

### Erro: "Não foi possível importar módulos do Verba"

**Solução:**
```bash
# Instala dependências
pip install -r requirements.txt

# Ou se estiver usando extensões
pip install -r requirements-extensions.txt
```

### Script não encontra documentos

**Possíveis causas:**
1. Collection name diferente (script usa padrão `VERBA_Document`)
2. Documentos não estão realmente corrompidos
3. Erro de conexão com Weaviate

**Verifica manualmente:**
```python
# Conecta ao Weaviate e verifica
from weaviate import Client
client = Client("http://weaviate:8080")
collection = client.collections.get("VERBA_Document")
# Verifica documentos
```

---

## 📝 Notas

- **Corrigir vs Deletar:**
  - **Corrigir**: Mantém documentos, apenas adiciona `meta` padrão
  - **Deletar**: Remove documentos permanentemente (inclui chunks)

- **Chunks:**
  - Ao deletar, o script tenta deletar chunks relacionados
  - Se não encontrar o embedder correto, deleta de todos os embedders possíveis
  - Isso é seguro (não afeta outros documentos)

- **Backup:**
  - Se possível, faça backup do Weaviate antes de deletar
  - No Railway, você pode fazer snapshot do volume

---

## 🚨 Para Railway

Se estiver rodando no Railway:

1. **Acesse o terminal do serviço Verba:**
   ```bash
   railway connect
   ```

2. **Execute o script:**
   ```bash
   python scripts/fix_corrupted_documents.py list
   python scripts/fix_corrupted_documents.py fix
   ```

3. **Ou use Railway CLI:**
   ```bash
   railway run python scripts/fix_corrupted_documents.py fix
   ```

---

## ✅ Resultado Esperado

Após executar `fix`:
- ✅ Documentos podem ser visualizados na UI
- ✅ Documentos podem ser deletados pela UI
- ✅ Campo `meta` está como JSON válido
- ✅ Erro "JSON object must be str" não aparece mais

---

**Última atualização:** 2025-01-XX

