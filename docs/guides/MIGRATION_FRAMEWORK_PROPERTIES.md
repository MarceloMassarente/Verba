# Guia de Migração: Propriedades de Framework

Este guia explica como migrar collections existentes do Weaviate para incluir propriedades de framework (frameworks, companies, sectors, framework_confidence).

## Contexto

O Weaviate v4 **não permite adicionar propriedades** a collections existentes. Para adicionar propriedades de framework, é necessário:

1. Fazer backup da collection
2. Criar nova collection com schema atualizado
3. Migrar dados
4. Validar integridade
5. (Opcional) Deletar collection antiga

## Pré-requisitos

- Acesso ao Weaviate (URL e API key)
- Python 3.8+
- Dependências do Verba instaladas
- Espaço em disco suficiente para backup

## Passo a Passo

### 1. Fazer Backup

**IMPORTANTE:** Sempre faça backup antes de migrar!

```bash
python scripts/migrate_collection_schema.py VERBA_Embedding_sua_collection --backup-dir backups
```

O script fará backup automático antes de migrar.

### 2. Verificar Schema Atual

Verifique se a collection já tem propriedades de framework:

```python
from verba_extensions.integration.schema_validator import collection_has_framework_properties

has_props = await collection_has_framework_properties(client, "VERBA_Embedding_sua_collection")
print(f"Tem propriedades de framework: {has_props}")
```

### 3. Executar Migração

```bash
python scripts/migrate_collection_schema.py VERBA_Embedding_sua_collection
```

O script irá:
- Fazer backup automático
- Criar nova collection com schema atualizado
- Migrar dados em batches
- Validar integridade
- Oferecer opção de deletar collection antiga

### 4. Validar Migração

Após migração, valide:

```python
from verba_extensions.integration.schema_validator import get_schema_compatibility_report

report = await get_schema_compatibility_report(client, "VERBA_Embedding_sua_collection_migrated")
print(report)
```

### 5. Atualizar Referências

Após migração bem-sucedida, você precisa:

1. **Atualizar código** que referencia a collection antiga
2. **Ou recriar** a collection com nome original (deletando a antiga primeiro)

```python
# Opção 1: Deletar collection antiga e renomear (manual)
await client.collections.delete("VERBA_Embedding_sua_collection")
# Recriar com nome original (copiar dados da migrada)

# Opção 2: Atualizar referências no código
# Usar "VERBA_Embedding_sua_collection_migrated" em vez de "VERBA_Embedding_sua_collection"
```

## Rollback

Se algo der errado, você pode restaurar do backup:

```python
from verba_extensions.utils.weaviate_backup import restore_collection

await restore_collection(
    client,
    "backups/VERBA_Embedding_sua_collection_backup_20250101_120000.json",
    "VERBA_Embedding_sua_collection"
)
```

## Troubleshooting

### Erro: "Collection não existe"

- Verifique o nome da collection
- Use `client.collections.list_all()` para listar collections

### Erro: "Propriedade não encontrada"

- Collection antiga não tem propriedades de framework
- Use fallback (frameworks ficam em `meta` JSON)
- Ou migre a collection

### Erro: "Backup inválido"

- Verifique integridade do backup: `python -c "from verba_extensions.utils.weaviate_backup import verify_backup_file; import asyncio; print(asyncio.run(verify_backup_file('backup.json')))"`
- Se backup está corrompido, não é possível fazer rollback

### Performance Lenta

- Migração pode levar tempo para collections grandes
- Use `--batch-size` menor se houver problemas de memória
- Processo é feito em batches para não sobrecarregar

## Collections Novas

Collections **novas** criadas após esta atualização **automaticamente** terão propriedades de framework. Não é necessário migrar collections novas.

## Verificação Pós-Migração

Após migração, teste:

1. **Busca funciona:** Faça uma busca normal
2. **Filtros de framework funcionam:** Busque por "SWOT" ou nome de empresa
3. **Chunks têm frameworks:** Verifique chunks migrados têm propriedades preenchidas

```python
# Verificar chunk tem frameworks
chunk = await collection.query.fetch_object_by_id(chunk_uuid)
print(chunk.properties.get("frameworks", []))
print(chunk.properties.get("companies", []))
```

## Suporte

Se encontrar problemas:

1. Verifique logs do script de migração
2. Valide backup antes de restaurar
3. Consulte documentação do Weaviate v4
4. Abra issue no repositório do Verba

## Notas Importantes

- **Sempre faça backup** antes de migrar
- **Valide backup** antes de prosseguir
- **Teste em ambiente de desenvolvimento** primeiro
- **Migração pode levar tempo** para collections grandes
- **Não delete collection antiga** até validar migração

