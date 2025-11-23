# 📋 Lista das 27 Propriedades do Schema ETL-Aware

## ✅ Resumo

O schema ETL-aware completo tem **27 propriedades** (sem named vectors) ou **30 propriedades** (com named vectors).

---

## 1️⃣ Propriedades Padrão do Verba (13 propriedades)

| # | Nome | Tipo | Descrição |
|---|------|------|-----------|
| 1 | `chunk_id` | NUMBER | ID único do chunk |
| 2 | `end_i` | NUMBER | Índice final no documento |
| 3 | `chunk_date` | TEXT | Data do chunk (ISO format) - **indexFilterable** |
| 4 | `meta` | TEXT | Metadados serializados em JSON |
| 5 | `content` | TEXT | Conteúdo do chunk - **indexSearchable** |
| 6 | `uuid` | TEXT | UUID do chunk |
| 7 | `doc_uuid` | UUID | UUID do documento pai - **indexFilterable** |
| 8 | `content_without_overlap` | TEXT | Conteúdo sem overlap |
| 9 | `pca` | NUMBER_ARRAY | Coordenadas PCA para visualização 3D |
| 10 | `labels` | TEXT_ARRAY | Labels do chunk - **indexFilterable** |
| 11 | `title` | TEXT | Título do documento - **indexSearchable** |
| 12 | `start_i` | NUMBER | Índice inicial no documento |
| 13 | `chunk_lang` | TEXT | Código de idioma (pt, en, etc.) - **indexFilterable** |

---

## 2️⃣ Propriedades de ETL (10 propriedades)

### ETL Pré-Chunking (4 propriedades)

| # | Nome | Tipo | Descrição |
|---|------|------|-----------|
| 14 | `entities_local_ids` | TEXT_ARRAY | Entity IDs localizadas no chunk - **indexFilterable** |
| 15 | `entity_mentions` | TEXT | JSON array de entidades detectadas |
| 16 | `section_first_para` | TEXT | Primeiro parágrafo da seção (contexto) |
| 17 | `parent_entities` | TEXT_ARRAY | Entity IDs do documento pai (herança) |

### ETL Pós-Chunking (6 propriedades)

| # | Nome | Tipo | Descrição |
|---|------|------|-----------|
| 18 | `section_title` | TEXT | Título da seção identificada |
| 19 | `section_entity_ids` | TEXT_ARRAY | Entity IDs relacionadas à seção |
| 20 | `section_scope_confidence` | NUMBER | Confiança na identificação da seção (0.0-1.0) |
| 21 | `primary_entity_id` | TEXT | Entity ID primária do chunk - **indexFilterable** |
| 22 | `entity_focus_score` | NUMBER | Score de foco da entidade primária (0.0-1.0) |
| 23 | `etl_version` | TEXT | Versão do ETL aplicado |

---

## 3️⃣ Propriedades de Framework (4 propriedades)

| # | Nome | Tipo | Descrição |
|---|------|------|-----------|
| 24 | `frameworks` | TEXT_ARRAY | Frameworks detectados (SWOT, Porter, BCG, etc.) - **indexFilterable** |
| 25 | `companies` | TEXT_ARRAY | Empresas mencionadas no chunk - **indexFilterable** |
| 26 | `sectors` | TEXT_ARRAY | Setores/indústrias mencionados - **indexFilterable** |
| 27 | `framework_confidence` | NUMBER | Confiança na detecção de frameworks (0.0-1.0) |

---

## ✅ Total: 27 Propriedades (sem named vectors)

**Breakdown:**
- ✅ 13 propriedades padrão do Verba
- ✅ 10 propriedades de ETL
- ✅ 4 propriedades de framework
- **= 27 propriedades totais**

---

## 🎯 Propriedades Adicionais (Named Vectors - opcional)

Se **named vectors** estiverem habilitados, adiciona-se **+3 propriedades**:

| # | Nome | Tipo | Descrição |
|---|------|------|-----------|
| 28 | `concept_text` | TEXT | Texto focado em conceitos abstratos (frameworks, estratégias) - **indexSearchable** |
| 29 | `sector_text` | TEXT | Texto focado em setores/indústrias - **indexSearchable** |
| 30 | `company_text` | TEXT | Texto focado em empresas específicas - **indexSearchable** |

**Total com named vectors: 30 propriedades**

---

## 📊 Resumo Visual

```
Schema ETL-Aware Completo
├── Propriedades Padrão Verba (13)
│   ├── chunk_id, end_i, chunk_date, meta
│   ├── content, uuid, doc_uuid
│   ├── content_without_overlap, pca, labels
│   └── title, start_i, chunk_lang
│
├── Propriedades ETL (10)
│   ├── Pré-Chunking (4)
│   │   ├── entities_local_ids, entity_mentions
│   │   └── section_first_para, parent_entities
│   └── Pós-Chunking (6)
│       ├── section_title, section_entity_ids
│       ├── section_scope_confidence
│       ├── primary_entity_id, entity_focus_score
│       └── etl_version
│
├── Propriedades Framework (4)
│   ├── frameworks, companies, sectors
│   └── framework_confidence
│
└── Propriedades Named Vectors (3) [OPCIONAL]
    ├── concept_text, sector_text
    └── company_text

TOTAL: 27 (sem named vectors) ou 30 (com named vectors)
```

---

## 🔍 Notas Importantes

1. **Todas as propriedades ETL são OPCIONAIS** - chunks normais podem deixá-las vazias
2. **Schema serve para AMBOS os casos:**
   - ✅ Chunks normais (sem ETL): propriedades ETL ficam vazias
   - ✅ Chunks ETL-aware (com ETL): propriedades ETL são preenchidas
3. **Propriedades com indexFilterable** são otimizadas para filtros rápidos
4. **Propriedades com indexSearchable** são otimizadas para busca BM25 (híbrida)
5. **Named vectors** só são incluídos se `include_named_vectors=True` na criação do schema

---

## 📝 Referência no Código

- **Arquivo:** `verba_extensions/integration/schema_updater.py`
- **Função:** `get_all_embedding_properties(include_named_vectors=False)`
- **Composição:**
  ```python
  properties = (
      get_verba_standard_properties() +  # 13 propriedades
      get_etl_properties() +              # 10 propriedades
      get_framework_properties()          # 4 propriedades
  )  # = 27 propriedades
  
  if include_named_vectors:
      properties += get_named_vector_text_properties()  # +3 propriedades
  # = 30 propriedades
  ```

