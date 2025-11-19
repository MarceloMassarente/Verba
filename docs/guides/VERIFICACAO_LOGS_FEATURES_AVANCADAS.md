# Verificação de Logs - Features Avançadas Weaviate

## 📊 Análise dos Logs Fornecidos

### ✅ O que ESTÁ funcionando (confirmado pelos logs):

1. **ETL Pré-Chunking** ✅
   ```
   [ETL-PRE] ETL habilitado detectado - iniciando extração de entidades pré-chunking
   [ETL-PRE] Extraídas 79 entidades do documento completo
   [ETL-PRE] ✅ Entidades armazenadas no documento: 79 spans
   [ETL-PRE] ✅ Entidades extraídas antes do chunking - chunking será entity-aware
   ```

2. **Chunking** ✅
   ```
   [CHUNKING] Chunking concluído: 9 chunks criados (ETL será executado após import)
   ```

3. **ETL Pós-Chunking** ✅
   ```
   [ETL-POST] ✅ doc_uuid obtido após import (tentativa 1): 58b27cfd-e314-41e7-9325-2c1f93a0612e
   [ETL] ✅ 8 chunks encontrados - executando ETL A2 (NER + Section Scope) em background
   ✅ ETL inteligente concluído: 2 chunks processados
   ```

4. **Schema ETL-aware** ✅
   ```
   ✅ Collection VERBA_DOCUMENTS já tem schema ETL-aware
   ```

### ❌ O que NÃO aparece nos logs (features avançadas):

1. **Named Vectors** ❌
   - Não aparece: `[Named-Vectors] Extraindo textos especializados...`
   - Não aparece: `[Named-Vectors] Mapeando textos especializados...`
   - **Causa provável**: Named vectors não estão habilitados ou collection não tem `vectorConfig`

2. **Framework Mapping** ❌
   - Não aparece: `[Framework-Mapping] Mapeando frameworks...`
   - **Causa provável**: Collection não tem propriedades de framework OU logs são `debug` (não aparecem)

3. **Multi-Vector Search** ❌
   - Não aparece: `🎯 Multi-vector search habilitado`
   - **Causa provável**: Feature não foi usada (não há query de busca nos logs)

4. **Aggregation** ❌
   - Não aparece: `✅ Aggregation executada`
   - **Causa provável**: Feature não foi usada (não há query de agregação nos logs)

---

## 🔍 Por que os logs não aparecem?

### 1. Named Vectors

**Logs esperados:**
```
[Named-Vectors] Extraindo textos especializados...
[Named-Vectors] Mapeando textos especializados...
```

**Por que não aparecem:**
- ❌ `ENABLE_NAMED_VECTORS` não está configurado como `"true"`
- ❌ Collection `VERBA_Embedding_all_MiniLM_L6_v2` não tem `vectorConfig` (named vectors)
- ⚠️ Logs são `msg.debug()` - só aparecem se debug estiver habilitado

**Como verificar:**
```python
# Verificar se named vectors estão habilitados
import os
print(f"ENABLE_NAMED_VECTORS: {os.getenv('ENABLE_NAMED_VECTORS', 'NOT SET')}")

# Verificar se collection tem named vectors
collection = client.collections.get("VERBA_Embedding_all_MiniLM_L6_v2")
config = await collection.config.get()
if hasattr(config, 'vector_config') and config.vector_config:
    print("✅ Collection tem named vectors")
    print(f"Vetores: {list(config.vector_config.keys())}")
else:
    print("❌ Collection NÃO tem named vectors")
```

### 2. Framework Mapping

**Logs esperados:**
```
[Framework-Mapping] Mapeando frameworks...
```

**Por que não aparecem:**
- ⚠️ Logs são `msg.debug()` - só aparecem se debug estiver habilitado
- ❌ Collection não tem propriedades de framework (`frameworks`, `companies`, `sectors`)
- ⚠️ Chunks não têm frameworks detectados no `chunk.meta`

**Como verificar:**
```python
# Verificar se collection tem propriedades de framework
from verba_extensions.integration.schema_validator import collection_has_framework_properties
has_framework_props = await collection_has_framework_properties(
    client, 
    "VERBA_Embedding_all_MiniLM_L6_v2"
)
print(f"Collection tem framework props: {has_framework_props}")
```

### 3. Multi-Vector Search

**Logs esperados:**
```
🎯 Multi-vector search habilitado
🎯 Usando vetores: ['concept_vec', 'sector_vec']
```

**Por que não aparecem:**
- ❌ Feature não foi usada (não há query de busca nos logs fornecidos)
- ❌ "Enable Multi-Vector Search" não está habilitado no EntityAware Retriever
- ❌ Named vectors não estão habilitados (pré-requisito)

**Como verificar:**
- Fazer uma query no chat que combine múltiplos aspectos (ex: "estratégia digital para bancos")
- Verificar se "Enable Multi-Vector Search" está habilitado na interface

### 4. Aggregation

**Logs esperados:**
```
✅ Aggregation executada
```

**Por que não aparecem:**
- ❌ Feature não foi usada (não há query de agregação nos logs fornecidos)
- ❌ "Enable Aggregation" não está habilitado no EntityAware Retriever

**Como verificar:**
- Fazer uma query analítica (ex: "quantos documentos sobre SWOT?")
- Verificar se "Enable Aggregation" está habilitado na interface

---

## 🔧 Como Habilitar e Ver os Logs

### 1. Habilitar Named Vectors

**Passo 1: Configurar variável de ambiente**
```bash
# .env ou variáveis de ambiente
ENABLE_NAMED_VECTORS=true
```

**Passo 2: Recriar collection** (se já existe)
- Named vectors só podem ser adicionados na criação da collection
- Se collection já existe sem named vectors, precisa deletar e recriar

**Passo 3: Verificar logs**
- Logs de criação: `🎯 Named vectors habilitados`
- Logs de import: `[Named-Vectors] Extraindo textos especializados...`

### 2. Habilitar Logs de Debug

**Opção 1: Variável de ambiente**
```bash
# Habilitar debug do wasabi
export VERBA_DEBUG=true
```

**Opção 2: Modificar código temporariamente**
```python
# Em verba_extensions/integration/import_hook.py
# Trocar msg.debug() por msg.info() temporariamente para ver logs
msg.info(f"[Named-Vectors] Extraindo textos especializados...")
```

### 3. Habilitar Multi-Vector Search

**Na interface do Verba:**
1. Configurações → Retriever → EntityAware
2. Ativar "Enable Multi-Vector Search"
3. Salvar

**Fazer uma query que combine múltiplos aspectos:**
- Exemplo: "Estratégia digital para bancos"
- Deve aparecer: `🎯 Multi-vector search habilitado`

### 4. Habilitar Aggregation

**Na interface do Verba:**
1. Configurações → Retriever → EntityAware
2. Ativar "Enable Aggregation"
3. Salvar

**Fazer uma query analítica:**
- Exemplo: "Quantos documentos sobre SWOT?"
- Deve aparecer: `✅ Aggregation executada`

---

## 📋 Checklist de Verificação

### Named Vectors
- [ ] `ENABLE_NAMED_VECTORS=true` configurado
- [ ] Collection criada com named vectors (verificar `vectorConfig`)
- [ ] Logs de debug habilitados (se quiser ver logs detalhados)
- [ ] Import de documento executado
- [ ] Verificar se logs aparecem: `[Named-Vectors]`

### Framework Mapping
- [ ] Collection tem propriedades de framework (`frameworks`, `companies`, `sectors`)
- [ ] Chunker detecta frameworks (EntitySemanticChunker ou similar)
- [ ] Logs de debug habilitados (se quiser ver logs detalhados)
- [ ] Import de documento executado
- [ ] Verificar se logs aparecem: `[Framework-Mapping]`

### Multi-Vector Search
- [ ] Named vectors habilitados (pré-requisito)
- [ ] "Enable Multi-Vector Search" habilitado na interface
- [ ] Query feita que combina múltiplos aspectos
- [ ] Verificar se logs aparecem: `🎯 Multi-vector search habilitado`

### Aggregation
- [ ] "Enable Aggregation" habilitado na interface
- [ ] Query analítica feita ("quantos", "count", etc.)
- [ ] Verificar se logs aparecem: `✅ Aggregation executada`

---

## 🎯 Conclusão dos Logs Analisados

### Status Atual:
- ✅ **ETL funcionando**: Pré-chunking e pós-chunking estão OK
- ✅ **Schema ETL-aware**: Collection tem schema correto
- ❌ **Named Vectors**: Não habilitados (não aparecem nos logs)
- ❌ **Framework Mapping**: Logs não aparecem (provavelmente debug desabilitado ou collection não tem props)
- ❌ **Multi-Vector Search**: Não foi usado (não há queries de busca nos logs)
- ❌ **Aggregation**: Não foi usado (não há queries analíticas nos logs)

### Próximos Passos:
1. **Habilitar Named Vectors** (se quiser usar):
   - Configurar `ENABLE_NAMED_VECTORS=true`
   - Recriar collection
   - Reimportar documentos

2. **Habilitar Logs de Debug** (se quiser ver logs detalhados):
   - Configurar `VERBA_DEBUG=true` ou modificar código temporariamente

3. **Testar Multi-Vector Search**:
   - Habilitar na interface
   - Fazer query que combine múltiplos aspectos

4. **Testar Aggregation**:
   - Habilitar na interface
   - Fazer query analítica

---

**Última atualização:** Janeiro 2025

