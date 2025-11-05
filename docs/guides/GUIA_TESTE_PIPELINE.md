# 🧪 Guia de Teste Completo do Pipeline Verba

## Objetivo

Validar todo o pipeline: **ingest → chunking → vetorização → ETL → extração de entidades → queries**

## Pré-requisitos

1. **API Verba rodando** (local ou remota)
2. **Weaviate configurado e acessível**
3. **Arquivo PDF** para teste no diretório atual

## Opções de Execução

### Opção 1: Teste no Ambiente de Produção (Railway/Cloud)

```powershell
# Configure variáveis de ambiente
$env:VERBA_API_URL='https://seu-verba.railway.app'
$env:WEAVIATE_URL='http://weaviate.railway.internal:8080'
$env:WEAVIATE_API_KEY=''

# Execute o teste
python test_pipeline_simples.py
```

### Opção 2: Teste Local

```powershell
# Terminal 1: Inicie o servidor
verba start --host 0.0.0.0 --port 8000

# Terminal 2: Execute o teste
python test_pipeline_simples.py
```

### Opção 3: Teste com Docker

```bash
# Inicie containers
docker-compose up -d

# Execute teste dentro do container
docker-compose exec verba python test_pipeline_simples.py
```

## O que o Teste Valida

### ✅ Etapas do Teste

1. **Verificação da API** - Confirma que servidor está respondendo
2. **Conexão ao Verba** - Testa conexão com Weaviate
3. **Importação do PDF** - Envia arquivo via WebSocket e monitora progresso
4. **Verificação do Documento** - Confirma que documento foi salvo no Weaviate
5. **Verificação de Chunks** - Valida que chunks foram criados e vetorizados
6. **Verificação de ETL** - **Valida extração de entidades:**
   - `entities_local_ids` - Entidades encontradas no chunk
   - `section_entity_ids` - Entidades da seção
   - `primary_entity_id` - Entidade principal
   - `etl_version` - Versão do ETL executado
7. **Teste de Query 1** - Valida busca semântica
8. **Teste de Query 2** - Valida segunda busca

### 📊 Validações Específicas de ETL

O teste verifica:

- ✅ **Propriedades ETL presentes** nos chunks
- ✅ **Entidades extraídas** (local e seção)
- ✅ **Primary entity** identificada
- ✅ **Contagem de entidades** por chunk
- ✅ **Exemplos de entidades** encontradas

## Exemplo de Saída Esperada

```
============================================================
🚀 TESTE COMPLETO DO PIPELINE VERBA
============================================================

[1/8] Verificando API
✅ API está rodando: Alive!

[2/8] Conectando ao Verba
✅ Conectado ao Verba com sucesso

[3/8] Importando arquivo PDF
📄 Arquivo: Mercado de Leadership Advisory... (2.5 MB)
📊 [STARTING] Import iniciado
📊 [LOADING] Carregando documento...
📊 [CHUNKING] Criando chunks...
📊 [EMBEDDING] Vetorizando chunks...
📊 [INGESTING] Inserindo no Weaviate...
📊 [NER] Extraindo entidades...
📊 [COMPLETED] Import concluído
✅ Importação concluída em 45.23s

[4/8] Verificando documento importado
✅ Documento encontrado: Mercado de Leadership Advisory...
   UUID: abc123-def456-...

[5/8] Verificando chunks criados
✅ 10 chunks encontrados (página 1 de 15)
   Total estimado: ~150 chunks
   Primeiro chunk ID: 0
   Conteúdo (150 chars): O mercado de Leadership Advisory...

[6/8] Verificando ETL e extração de entidades
✅ ETL executado - propriedades encontradas
   ETL version: entity_scope_v1
✅ Entidades encontradas no chunk
   Entities locais: 5
   Entities seção: 3
   Primary entity: Q12345
✅ Entidades extraídas: 8 encontradas
   Exemplos: Q12345, Q67890, Q11111

[7/8] Testando query 1
✅ Query retornou 5 documentos
   Context: O mercado brasileiro de Leadership Advisory...

[8/8] Testando query 2
✅ Query retornou 5 documentos
   Context: Os principais players incluem...

============================================================
📊 RESUMO DO TESTE
============================================================
✅ Importação: SUCESSO
✅ Documento: ENCONTRADO
✅ Chunks: 10 (total estimado: ~150)
✅ ETL/Entidades: OK
   Total de entidades: 8
✅ Query 1: OK
✅ Query 2: OK
============================================================
🎉 TESTE COMPLETO: SUCESSO!
✅ ETL validado com 8 entidades extraídas
```

## Troubleshooting

### API não responde

```powershell
# Verifique se servidor está rodando
netstat -an | findstr :8000

# Ou inicie manualmente
verba start
```

### Erro de conexão Weaviate

```powershell
# Verifique variáveis de ambiente
$env:WEAVIATE_URL
$env:WEAVIATE_API_KEY

# Teste conexão direta
python -c "import weaviate; print('OK')"
```

### ETL não encontrado

- ETL pode estar rodando em background (aguarde alguns segundos)
- Verifique se ETL está habilitado na configuração
- Verifique logs do servidor para erros de ETL

### Arquivo não encontrado

```powershell
# Verifique se PDF está no diretório
Get-ChildItem *.pdf

# Ou ajuste o nome no script
# PDF_FILE = "seu-arquivo.pdf"
```

## Scripts Disponíveis

1. **`test_pipeline_simples.py`** - Teste via API (recomendado)
2. **`test_pipeline_completo.py`** - Teste direto (requer dependências)
3. **`run_test_completo.py`** - Auto-inicia servidor se necessário

## Próximos Passos

Após validar o teste:

1. ✅ Verificar logs de ETL para confirmar extração
2. ✅ Validar queries com diferentes termos
3. ✅ Testar com múltiplos documentos
4. ✅ Verificar performance com documentos grandes

