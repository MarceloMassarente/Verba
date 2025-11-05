# 🔍 Guia: Verificar Processamento ETL

## Como Executar

### **Opção 1: Localmente (conecta ao Weaviate remoto)**

```bash
# Configure variáveis de ambiente (Railway)
export WEAVIATE_HTTP_HOST=weaviate.railway.internal
export WEAVIATE_HTTP_PORT=8080
export WEAVIATE_GRPC_HOST=weaviate.railway.internal
export WEAVIATE_GRPC_PORT=50051
export WEAVIATE_API_KEY_VERBA=sua_api_key  # Se necessário

# Execute o script
python scripts/verify_etl_processing.py "Estudo Mercado Headhunting Brasil.pdf"
```

### **Opção 2: Via Railway CLI (dentro do container)**

Se você tiver acesso SSH ao Railway:

```bash
# Dentro do container Verba
python scripts/verify_etl_processing.py "Estudo Mercado Headhunting Brasil.pdf"
```

## O que o Script Verifica

### ✅ **1. Schema ETL-aware**
- Verifica se collections têm propriedades ETL
- Lista todas as propriedades ETL presentes

### ✅ **2. Chunks com ETL**
- Conta quantos chunks têm propriedades ETL preenchidas
- Verifica:
  - `entities_local_ids` (ETL pós-chunking)
  - `section_title`, `section_entity_ids` (Section Scope)
  - `primary_entity_id`, `entity_focus_score`
  - `etl_version`

### ✅ **3. Exemplos de Chunks**
- Mostra exemplos de chunks com ETL preenchido
- Exibe entidades encontradas

## Resultado Esperado

Se tudo funcionou corretamente, você deve ver:

```
✅ Schema ETL-aware presente
✅ X chunks encontrados
✅ ETL foi processado! X chunks têm propriedades ETL

📝 Exemplo de chunk com ETL:
   - Entidades (local): ['ent:loc:brasil', ...]
   - Primary Entity: ent:loc:brasil
   - Section Title: ...
   - ETL Version: entity_scope_v1
```

## Se Não Funcionou

Se o script mostrar `⚠️ Nenhum chunk tem propriedades ETL preenchidas`:

1. **Verifique logs**: Procure por `[ETL] ✅ ETL A2 concluído`
2. **Verifique se collection está correta**: O erro "Passage" foi corrigido
3. **Verifique se ETL foi habilitado**: `enable_etl=1` no documento

---

**Script criado**: `scripts/verify_etl_processing.py`

