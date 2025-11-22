# 🔍 Diagnóstico: Por que o segundo arquivo quebra?

## Resumo
Você reportou que o primeiro arquivo foi processado com sucesso, mas o segundo arquivo quebrou. O erro inicial era `SyntaxError` que já foi corrigido. Agora vamos diagnosticar possíveis causas de falha no segundo arquivo.

## Possíveis Causas Identificadas

### 1. **Cliente Weaviate em estado inconsistente (ALTA PROBABILIDADE)**

**Localização:** `verba_extensions/integration/import_hook.py`, função `_is_client_connected()`

**Problema:**
```python
def _is_client_connected(client):
    try:
        _ = client.collections
        return True
    except Exception as e:
        # Qualquer erro retorna False
        return False
```

O cliente pode ficar em um estado "semi-conectado":
- Primeira requisição funciona (primeiro arquivo)
- Após tempo de inatividade ou muitas operações, falha silenciosamente
- Tentativa de reconexão via `_get_working_client()` pode não ser suficiente

**Sintoma esperado:**
```
[ETL-POST] Cliente fechado durante busca de chunks - ETL não será executado
```

### 2. **Estado global em `_etl_executions_in_progress` não limpo (MÉDIA PROBABILIDADE)**

**Localização:** `verba_extensions/integration/import_hook.py`, linha 18

**Problema:**
```python
_etl_executions_in_progress: Set[str] = set()  # Variável global
```

Se o primeiro import deixar um `doc_uuid` "marcado como em progresso":
- Segundo arquivo tenta usar o mesmo embedder/doc_uuid
- Encontra doc_uuid já em `_etl_executions_in_progress`
- Pula ETL silenciosamente (linha 334: `msg.info(f"[ETL] ℹ️ ETL já está em execução")`)

**Sintoma esperado:**
```
[ETL] ℹ️ ETL já está em execução para este doc_uuid
```

Ou pior: se houver exceção no finally block do primeiro import, o `_etl_executions_in_progress.discard(doc_uuid)` pode não ser executado.

### 3. **embedding_table compartilhado entre imports (BAIXA PROBABILIDADE, mas possível)**

**Localização:** `goldenverba/components/managers.py`, linha 177

**Problema:**
```python
class WeaviateManager:
    def __init__(self):
        self.embedding_table = {}  # Compartilhado entre todos os imports
```

O `VerbaManager` cria uma única instância:
```python
class VerbaManager:
    def __init__(self):
        self.weaviate_manager = WeaviateManager()  # Uma instância para todos
```

Se houver corrupção no `embedding_table` após o primeiro import (nome de collection inválido armazenado), afetará o segundo.

### 4. **Erro na verificação de schema ETL (MÉDIA PROBABILIDADE)**

**Localização:** `verba_extensions/plugins/a2_etl_hook.py`, linhas 238-263

**Problema:**
```python
# Verifica schema UMA VEZ no início
collection_config = await coll.config.get()
existing_prop_names = {p.name for p in collection_config.properties}
```

Se o cliente desconectar entre o primeiro e segundo import:
- `coll.config.get()` pode falhar com erro ambíguo
- Mensagem de erro não clara (pode parecer falha genérica)

## Recomendações para Investigação

### 1. **Habilitar logging verbose**
```python
# Adicionar ao startup:
logging.getLogger("weaviate").setLevel(logging.DEBUG)
logging.getLogger("httpx").setLevel(logging.DEBUG)
```

### 2. **Monitorar conexão entre imports**
Adicionar verificação antes do segundo import:
```python
if not await client.is_ready():
    msg.warn("❌ Cliente não está pronto para segundo import!")
    # Tentar reconectar explicitamente
    await client.connect()
```

### 3. **Limpar estado global após cada import**
No `import_hook.py`, após conclusão do ETL:
```python
def cleanup_etl_state(doc_uuid):
    """Garante limpeza mesmo com exceção"""
    _etl_executions_in_progress.discard(doc_uuid)
    _logger_registry.pop(doc_uuid, None)
```

## Cenários Mais Prováveis

### Cenário A: Timeout de conexão
1. Primeiro arquivo: import lento (1-2 minutos)
2. Conexão Weaviate tem timeout de ~300s
3. Segundo arquivo: cliente ainda está tentando operações do primeiro
4. Nova conexão não consegue ser estabelecida

**Solução:**
- Aumentar timeout: `Timeout(init=60, query=300, insert=300)` → `insert=600`
- Usar pool de conexões ao invés de reconexão manual

### Cenário B: Race condition em ETL background
1. Primeiro arquivo: ETL executado em background (asyncio.create_task)
2. Segundo arquivo começa enquanto primeiro ainda está em andamento
3. Ambos tentam atualizar mesma collection
4. Conflicts/locks no Weaviate

**Solução:**
- Usar semáforo para limitar concurrent ETL: `asyncio.Semaphore(1)`
- Await explicit do ETL anterior antes de iniciar novo

### Cenário C: Erro silencioso em ETL legado
1. Primeiro arquivo: ETL inteligente funciona
2. Segundo arquivo: módulo `ingestor.etl_a2_intelligent` não importa
3. Fallback para ETL legado
4. Gazetteer não carregado corretamente (já em memória do primeiro import)

**Solução:**
- Reinicializar `_nlp` e `_etl_module` a cada import
- Validar gazetteer antes de usar

## Próximas Etapas

1. **Testar com dois imports simples**
   - Dois arquivos PEQUENOS (< 100KB)
   - Mesma RAG config
   - Verificar logs completos

2. **Verificar recursos do servidor**
   - Disco do Weaviate: "disk usage currently at 83.43%, threshold set to 80.00%"
   - Memória disponível para Python
   - Conexões TCP abertas

3. **Adicionar health checks**
   - Verificar `await client.is_ready()` antes de cada import
   - Verificar collections existem após import
   - Validar embedding_table integridade

4. **Implementar retry logic robusto**
   - Retry exponential backoff para operações Weaviate
   - Timeout maior para imports grandes
   - Fallback para nova conexão após erro

## Código de Teste Recomendado

```python
async def test_sequential_imports():
    # Teste para validar dois imports seguidos
    client = await manager.connect(credentials)
    
    # First import
    await manager.import_document(client, fileConfig1, logger)
    assert await client.is_ready(), "Cliente deve estar pronto após primeiro import"
    
    # Small delay
    await asyncio.sleep(2)
    
    # Validate collections
    collections = await client.collections.list_all()
    assert "VERBA_DOCUMENTS" in collections, "Collection DOCUMENTS deve existir"
    
    # Second import
    await manager.import_document(client, fileConfig2, logger)
    assert await client.is_ready(), "Cliente deve estar pronto após segundo import"
    
    # Verify both documents imported
    doc_collection = client.collections.get("VERBA_DOCUMENTS")
    count = await doc_collection.aggregate.over_all(total_count=True)
    assert count.total_count >= 2, f"Deve ter 2+ documentos, tem {count.total_count}"
```

## Status Atual
✅ **Corrigido:** SyntaxError em `import_hook.py` (continue fora do loop)
⏳ **Pendente:** Diagnóstico do segundo arquivo

---
**Data:** Novembro 2025
**Afetado:** Segundo arquivo em import sequencial
**Prioridade:** ALTA - impede uso multi-arquivo

