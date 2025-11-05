# Scripts Directory

Este diretório contém scripts utilitários organizados por categoria.

## Estrutura

### 📁 `fixes/`
Scripts para corrigir problemas e bugs no sistema:
- `fix_corrupted_documents_railway.py` - Corrige documentos corrompidos no Railway
- `fix_corrupted_documents.py` - Corrige documentos corrompidos
- `fix_corrupted_simple.py` - Versão simplificada para correção de documentos
- `fix_collections_schema.py` - Corrige schemas de collections

### 📁 `diagnostics/`
Scripts para análise e diagnóstico do sistema:
- `check_collection_schema.py` - Verifica schema de collections
- `check_dependencies.py` - Verifica dependências
- `check_document_processing.py` - Verifica processamento de documentos
- `check_weaviate_content.py` - Verifica conteúdo do Weaviate
- `check_weaviate_rest.py` - Verifica REST API do Weaviate
- `analyze_pdf_extraction.py` - Analisa extração de PDFs
- `compare_pdf_readers.py` - Compara diferentes leitores de PDF
- `find_chunks_for_document.py` - Encontra chunks para um documento
- `find_repetition_pattern.py` - Encontra padrões de repetição
- `show_line_context.py` - Mostra contexto de linhas

### 📁 `tests/`
Scripts de teste:
- `test_chunking_impact.py` - Testa impacto do chunking
- `test_etl_chunk_local_http.py` - Testa ETL chunk via HTTP local
- `test_etl_utility_comprehensive.py` - Teste abrangente de utilitários ETL
- `test_graphql_builder_integration.py` - Testa integração do GraphQL builder
- `test_phase1_phase2_optimizations.py` - Testa otimizações de fase 1 e 2
- `test_tika_local_file.py` - Testa Tika com arquivo local
- `test_tika_metadata.py` - Testa metadados do Tika
- `test_tika_simple.py` - Teste simples do Tika
- `test_verba_pipeline.py` - Testa pipeline do Verba

### 📁 `validations/`
Scripts para validação:
- `validate_etl_meta.py` - Valida metadados ETL
- `validate_etl_pre_chunking.py` - Valida ETL pré-chunking
- `verify_etl_processing_http.py` - Verifica processamento ETL via HTTP
- `verify_etl_processing.py` - Verifica processamento ETL
- `verify_patches.py` - Verifica patches

### 📁 `migrations/`
Scripts para migração e gerenciamento de schema:
- `create_schema.py` - Cria schema
- `create_collection_etl_from_scratch.py` - Cria collection ETL do zero
- `create_and_test_collection_etl.py` - Cria e testa collection ETL
- `update_verba_schema_etl.py` - Atualiza schema Verba ETL
- `migrate_collection_with_etl.py` - Migra collection com ETL
- `recreate_collections_etl_aware.py` - Recria collections com ETL

### 📁 `utils/`
Scripts utilitários diversos:
- `apply_patches.py` - Aplica patches
- `pdf_to_a2_json.py` - Converte PDF para JSON A2

## Uso

Para executar scripts, use o caminho relativo:
```bash
python scripts/fixes/fix_corrupted_documents_railway.py
python scripts/diagnostics/check_collection_schema.py
python scripts/tests/test_verba_pipeline.py
```

