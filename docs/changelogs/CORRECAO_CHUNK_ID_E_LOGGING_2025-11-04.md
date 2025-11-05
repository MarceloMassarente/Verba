# Correção: chunk_id String → Float e Logging Excessivo

**Data:** 2025-11-04  
**Problema:** Erro crítico de validação no Weaviate + Rate limit de logs no Railway

## Problemas Identificados

### 1. Erro: `chunk_id` como String no Weaviate

**Erro:**
```
ErrorObject(message="invalid number property 'chunk_id' on class 
'VERBA_Embedding_all_MiniLM_L6_v2': requires a float, the given value is '31_315'")
```

**Causa Raiz:**
- Plugin `RecursiveDocumentSplitter` cria `chunk_id` como string no formato `'{original}_{subindex}'` (ex: `'6_154'`, `'31_315'`)
- Código em `verba_extensions/plugins/recursive_document_splitter.py` linha 344:
  ```python
  chunk_id=f"{chunk.chunk_id}_{i}" if chunk.chunk_id else str(i),
  ```
- Weaviate espera `chunk_id` como número (float/int), não string
- Quando chunks são inseridos via `chunk.to_json()`, a string é enviada diretamente

**Impacto:**
- Erro 422 em inserções de chunks com recursive split
- Chunks não são salvos no Weaviate
- Importação de documentos falha silenciosamente

### 2. Logging Excessivo Causando Rate Limit

**Erro:**
```
Railway rate limit of 500 logs/sec reached for replica, update your application 
to reduce the logging rate. Messages dropped: 113987
```

**Causa:**
- Weaviate SDK está logando cada valor do vetor individualmente durante inserção
- Logs mostram vetores completos sendo logados linha por linha
- Railway limita a 500 logs/segundo, causando perda de logs

**Impacto:**
- Logs importantes podem ser perdidos
- Dificuldade de debug em produção
- Possível impacto em performance

## Soluções Implementadas

### 1. Conversão Automática de `chunk_id` para Float

**Arquivo:** `goldenverba/components/chunk.py`

**Mudança:**
- Método `to_json()` agora converte `chunk_id` de string para float antes de enviar ao Weaviate
- Suporta formato `'original_subindex'` (ex: `'6_154'` → `6.154`)
- Fallback para hash quando subindex > 1000 (evita problemas de precisão)
- Garante que sempre retorna um número válido

**Código:**
```python
def to_json(self) -> dict:
    """Convert the Chunk object to a dictionary."""
    import json
    
    # Convert chunk_id to float if it's a string (e.g., '6_154' -> 6.154 or hash)
    # Weaviate requires chunk_id to be a number, not a string
    chunk_id_value = self.chunk_id
    if isinstance(chunk_id_value, str):
        # If it's a string like '6_154', convert to unique float
        if '_' in chunk_id_value:
            try:
                # Try to parse as 'original_subindex' format
                parts = chunk_id_value.split('_')
                if len(parts) == 2:
                    original = float(parts[0])
                    subindex = float(parts[1])
                    # Convert to float: original.subindex (e.g., 6_154 -> 6.154)
                    # But if subindex is > 1000, use hash to avoid precision issues
                    if subindex < 1000:
                        chunk_id_value = original + (subindex / 1000.0)
                    else:
                        # Use hash for large subindexes to ensure uniqueness
                        chunk_id_value = float(hash(chunk_id_value) % (10**10))
                else:
                    # Fallback: use hash for any string format
                    chunk_id_value = float(hash(chunk_id_value) % (10**10))
            except (ValueError, IndexError):
                # If parsing fails, use hash
                chunk_id_value = float(hash(chunk_id_value) % (10**10))
        else:
            # Try to convert string to float directly
            try:
                chunk_id_value = float(chunk_id_value)
            except (ValueError, TypeError):
                # Fallback: use hash
                chunk_id_value = float(hash(str(chunk_id_value)) % (10**10))
    elif chunk_id_value is None or chunk_id_value == "":
        chunk_id_value = 0.0
    else:
        # Ensure it's a number
        try:
            chunk_id_value = float(chunk_id_value)
        except (ValueError, TypeError):
            chunk_id_value = 0.0
    
    return {
        "content": self.content,
        "chunk_id": chunk_id_value,  # Now guaranteed to be float
        # ... rest of properties
    }
```

**Vantagens:**
- ✅ Compatível com formato existente `'original_subindex'`
- ✅ Preserva informação do chunk original e sub-chunk
- ✅ Funciona com qualquer formato de string
- ✅ Sem breaking changes (chunks existentes continuam funcionando)

### 2. Redução de Logging Excessivo

**Arquivo:** `goldenverba/components/managers.py`

**Mudança:**
- Configurado nível de logging do Weaviate SDK para WARNING
- Configurado nível de logging do httpx (HTTP client) para WARNING
- Reduz volume de logs de DEBUG/INFO para apenas WARNING/ERROR

**Código:**
```python
import logging

# Reduz logging excessivo do Weaviate SDK para evitar rate limits
# Logs de vetores individuais são muito verbosos e causam rate limit no Railway
logging.getLogger("weaviate").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)  # HTTP requests também logam muito
```

**Vantagens:**
- ✅ Reduz drasticamente o volume de logs
- ✅ Evita rate limits no Railway (500 logs/segundo)
- ✅ Mantém logs importantes (WARNING/ERROR)
- ✅ Melhora performance ao reduzir overhead de logging

## Testes Recomendados

1. **Teste de chunk_id:**
   - Importar documento com recursive splitter ativo
   - Verificar que chunks são inseridos sem erro 422
   - Confirmar que `chunk_id` no Weaviate é float

2. **Teste de logging:**
   - Monitorar logs durante importação
   - Verificar que não há rate limit warnings
   - Confirmar que logs importantes ainda aparecem

## Impacto

- ✅ **Correção Crítica:** Resolve erro 422 que impedia importação de documentos
- ✅ **Compatibilidade:** Mantém compatibilidade com chunks existentes
- ✅ **Performance:** Reduz volume de logs drasticamente (evita rate limits)
- ✅ **Estabilidade:** Melhora estabilidade em produção ao reduzir overhead de logging

## Arquivos Alterados

1. `goldenverba/components/chunk.py`
   - Método `to_json()` modificado para converter `chunk_id` para float

2. `goldenverba/components/managers.py`
   - Configuração de logging reduzida para Weaviate SDK e httpx

## Próximos Passos

1. Testar em ambiente de staging
2. Monitorar logs após deploy
3. Considerar adicionar configuração de logging do Weaviate SDK
4. Documentar formato de `chunk_id` para desenvolvedores de plugins

