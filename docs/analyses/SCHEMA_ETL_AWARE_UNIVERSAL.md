# 🎯 Schema ETL-Aware Universal - Um Schema para Todos

## ✅ Resposta à Pergunta

**Sim! O schema ETL-aware serve para AMBOS os casos:**

- ✅ **Chunks normais** (sem ETL): Propriedades ETL ficam vazias (None/[]/0.0/"")
- ✅ **Chunks ETL-aware** (com ETL): Propriedades ETL são preenchidas

**Por quê?** As propriedades ETL são **opcionais** no Weaviate. Chunks normais simplesmente não preenchem essas propriedades.

## 🔧 Como Funciona

### Schema Criado Automaticamente

Quando o Verba inicia, o patch `patch_weaviate_manager_verify_collection()` é aplicado via `startup.py`.

**Comportamento:**
1. **Collection existe** → Verifica se tem propriedades ETL
   - ✅ Tem ETL: Usa normalmente
   - ❌ Não tem: Avisa (mas funciona com chunks normais)

2. **Collection não existe + é VERBA_Embedding** → **Cria com schema ETL-aware completo**
   - 13 propriedades padrão do Verba
   - 7 propriedades de ETL
   - **Total: 20 propriedades**

3. **Collection não existe + não é embedding** → Cria normalmente (sem ETL)

### Propriedades do Schema

#### Propriedades Padrão do Verba (13)
```python
chunk_id              # NUMBER
end_i                 # NUMBER
chunk_date            # TEXT
meta                  # TEXT (JSON serializado)
content               # TEXT
uuid                  # TEXT
doc_uuid              # UUID
content_without_overlap # TEXT
pca                   # NUMBER_ARRAY
labels                # TEXT_ARRAY
title                 # TEXT
start_i               # NUMBER
chunk_lang            # TEXT
```

#### Propriedades de ETL (7) - OPCIONAIS
```python
entities_local_ids      # TEXT_ARRAY (opcional)
section_title          # TEXT (opcional)
section_entity_ids     # TEXT_ARRAY (opcional)
section_scope_confidence # NUMBER (opcional)
primary_entity_id      # TEXT (opcional)
entity_focus_score     # NUMBER (opcional)
etl_version            # TEXT (opcional)
```

## 📋 Exemplo de Uso

### Chunk Normal (sem ETL)
```python
chunk_props = {
    "content": "Texto do chunk",
    "chunk_id": 1.0,
    "doc_uuid": "...",
    # Propriedades ETL não são preenchidas (ou ficam vazias)
    "entities_local_ids": [],  # Vazio
    "section_title": "",        # Vazio
    # ...
}
```

### Chunk ETL-Aware (com ETL)
```python
chunk_props = {
    "content": "Texto do chunk",
    "chunk_id": 1.0,
    "doc_uuid": "...",
    # Propriedades ETL são preenchidas
    "entities_local_ids": ["Q312", "Q123"],
    "section_title": "Introdução",
    "section_entity_ids": ["Q312"],
    "section_scope_confidence": 0.9,
    "primary_entity_id": "Q312",
    "entity_focus_score": 1.0,
    "etl_version": "entity_scope_v1",
}
```

**Ambos funcionam no mesmo schema!** ✅

## 🚀 No Railway

Quando o Verba sobe no Railway:

1. **Startup** → `startup.py` executa
2. **Patch aplicado** → `patch_weaviate_manager_verify_collection()`
3. **Primeira conexão** → Verifica collections
4. **Collection não existe** → Cria com schema ETL-aware automaticamente
5. **Collection existe sem ETL** → Avisa (mas funciona)

**Resultado:** Todas as collections de embedding serão criadas com schema ETL-aware desde o início!

## 🔍 Verificação

### Como Verificar se Schema tem ETL

```python
from verba_extensions.integration.schema_updater import check_collection_has_etl_properties

has_etl = await check_collection_has_etl_properties(client, "VERBA_Embedding_all_MiniLM_L6_v2")
if has_etl:
    print("✅ Schema ETL-aware")
else:
    print("❌ Schema padrão (sem ETL)")
```

### Logs Esperados

Quando collection é criada:
```
🔧 Criando collection VERBA_Embedding_all_MiniLM_L6_v2 com schema ETL-aware...
   📋 Total de propriedades: 20
   📝 Schema serve para chunks normais E ETL-aware (propriedades ETL são opcionais)
✅ Collection VERBA_Embedding_all_MiniLM_L6_v2 criada com schema ETL-aware!
   ✅ Chunks normais podem usar (propriedades ETL opcionais)
   ✅ Chunks ETL-aware podem usar (propriedades ETL preenchidas)
```

Quando collection já existe:
```
✅ Collection VERBA_Embedding_all_MiniLM_L6_v2 já tem schema ETL-aware
```

## 📊 Benefícios

1. **Um único schema** para todos os casos
2. **Compatibilidade retroativa** - chunks normais funcionam
3. **Extensibilidade** - chunks ETL-aware podem usar propriedades
4. **Criação automática** - não precisa configurar manualmente
5. **Flexível** - propriedades ETL são opcionais

## ⚠️ Limitações

- **Weaviate v4** não permite adicionar propriedades depois
- Se collection já existe **sem ETL**, precisa deletar e recriar
- Propriedades ETL devem ser inicializadas (mesmo que vazias) quando inserir chunks

## ✅ Checklist

- [x] Patch aplicado automaticamente no startup
- [x] Schema criado com todas as propriedades (padrão + ETL)
- [x] Funciona para chunks normais
- [x] Funciona para chunks ETL-aware
- [x] Verificação automática de schema existente
- [x] Logs informativos

## 🎯 Conclusão

**Sim, um único schema ETL-aware serve para ambos os casos!** 

O patch garante que:
- ✅ Collections são criadas com schema completo desde o início
- ✅ Chunks normais funcionam (propriedades ETL opcionais)
- ✅ Chunks ETL-aware funcionam (propriedades ETL preenchidas)
- ✅ Sistema funciona automaticamente no Railway

**Não precisa de dois schemas diferentes!** 🎉

