# Piloto: agentes de busca e leitura documental

## Objetivo
Validar o fluxo de negocio: centenas de documentos de conselho/comitês, com agentes analíticos que primeiro descobrem documentos relevantes e depois leem trechos, seções ou o documento completo (quando pequeno).

## Escopo do piloto
- Volume: 50 a 100 documentos reais ou anonimizados.
- Ciclos: 2 a 3 ciclos de reunião (pauta, pre-read, ata) por comitê distinto, quando possível.

## Endpoints (HTTP)
- `POST /api/agent/search_documents` - busca com agrupamento por `doc_uuid`, top hits por documento, opcionais `preset` e `advanced_search` (mesma semantica de `/api/query` quanto a retrieval; ver `AdvancedSearchOptions` em `goldenverba/server/types.py` e o guia `docs/API_GUIDE.md`).
- `POST /api/agent/read_document` - leitura controlada: `page`, `window`, `section`, `outline`, `full_if_small`.
- `POST /api/agent/read_context_around` - atalho para janela em torno de `chunk_id`.

Integracao externa: usar apenas estes endpoints Verba; nao expor o consumidor a queries diretas no Weaviate. A resposta pode incluir `search_options` e `debug_info` para confirmar preset, overrides e modo de busca final.

## Payloads
Definidos em `goldenverba/server/types.py` (`SearchDocumentsForAgentsPayload` inclui `advanced_search` opcional, `ReadDocumentForAgentsPayload`, `ReadContextAroundPayload`).

## Perguntas difíceis (exemplos)
1. Tema aberto, sem título: evolução de um assunto (ex.: investimento) ao longo de múltiplas reuniões.
2. Comparar pauta vs ata para o mesmo tema na mesma data.
3. Listar o que subiu a conselho a partir de pre-read, sem conhecer nomes de arquivos.
4. Síntese de riscos recorrentes em comitê específico.
5. Pergunta que exige 3+ documentos e leitura de seções longas (validar leitura por `section` e `page`).

## Criterio de sucesso
- O agente localiza documentos corretos via `search_documents` (top 5 por doc).
- O agente abre o documento com `read_document` (outline → section/page) sem estourar contexto.
- Respostas citam `doc_uuid` e, quando existir, `section_title` / `chunk_id`.
- `full_if_small` só retorna sucesso para documentos abaixo de `max_chars`.

## Propriedades de schema opcionais
Novos campos `gov_*` em chunks (ver `get_governance_properties` em `verba_extensions/integration/schema_updater.py`) podem ser preenchidos no ingest. Corpus genérico deixa vazio.

## Próximos passos
- Preencher `gov_document_type`, `gov_meeting_date`, `gov_committee` no pipeline de ingestão.
- Filtros por esses campos no `search_documents` (evolução futura: estender o payload e Weaviate filters).
