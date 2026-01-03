# Named Vectors - Guia Técnico Completo

## 🎯 O que são Named Vectors?

Named Vectors (ou Multi-Vector) é uma feature do Weaviate que permite ter **múltiplos embeddings** por objeto, cada um otimizado para um espaço semântico específico.

### Os 4 Vetores no Verba

| Vector Name | Dimensão | Texto Fonte | Propósito |
|-------------|----------|-------------|-----------|
| **`default`** | 384 | `content` (texto completo) | Busca semântica geral ✅ |
| **`company_vec`** | 384 | `company_text` | Matching de empresas/organizações |
| **`concept_vec`** | 384 | `concept_text` | Matching de conceitos de negócio |
| **`sector_vec`** | 384 | `sector_text` | Matching de setores/indústrias |

> **Modelo**: Todos usam `all-MiniLM-L6-v2` (SentenceTransformers)

---

## 🔄 Fluxo Completo de População

```
┌─────────────────────────────────────────────────────────────────┐
│                    FLUXO NAMED VECTORS                          │
└─────────────────────────────────────────────────────────────────┘

1. UNIVERSAL READER (universal_reader.py)
   ├─ Extrai texto bruto do documento
   ├─ Preserva estrutura (slides, seções)
   └─ Output: Document raw
        └─> text: "Caminhões a GNL são veículos..."

2. ENTITY SEMANTIC CHUNKER (entity_semantic_chunker.py)
   ├─ Quebra em chunks semânticos
   ├─ Detecta entidades (companies, frameworks, sectors)
   ├─ Preserva contexto de seção
   └─> Output: Chunks com metadata básica
        ├─ chunk.text: "Caminhões a GNL..."
        ├─ chunk.metadata.companies: ["Scania", "Volvo"]
        ├─ chunk.metadata.frameworks: ["TCO", "NPS"]
        └─ chunk.metadata.sectors: ["transportation"]

3. ETL A2 HOOK (a2_etl_hook.py)
   ├─ Enriquece metadados
   ├─ Extrai entidades adicionais (GLiNER)
   ├─ Cria textos especializados para cada vetor
   └─> Output: Metadados ETL-aware
        ├─ companies: ["Scania", "Volvo", "Iveco"]
        ├─ frameworks: ["TCO", "Total Cost Ownership"]
        ├─ sectors: ["transportation", "logistics"]
        ├─ company_text: "Scania Volvo Iveco fabricam..."
        ├─ concept_text: "TCO custo total propriedade..."
        └─ sector_text: "transporte logística automotivo..."

4. WEAVIATE SCHEMA (managers.py + schema_updater.py)
   ├─ Cria collection com 4 named vectors
   ├─ Popula campos de texto especializados
   └─> Weaviate armazena:
        ├─ content → embedding → default vector
        ├─ company_text → embedding → company_vec
        ├─ concept_text → embedding → concept_vec
        └─ sector_text → embedding → sector_vec
```

---

## 📝 População dos Campos - Exemplo Real

### Documento Original
```
Slide 1: Caminhões a GNL
A Scania e a Volvo desenvolveram caminhões movidos a gás 
natural liquefeito (GNL) para o setor de transporte.
O TCO (Total Cost of Ownership) é 20% menor...
```

### Após Entity Semantic Chunker

```python
chunk = {
    "text": "A Scania e a Volvo desenvolveram caminhões movidos a gás...",
    "metadata": {
        "companies": ["Scania", "Volvo"],
        "frameworks": ["TCO"],
        "sectors": [],  # Ainda vazio
        "section_title": "Caminhões a GNL",
        "chunk_lang": "pt"
    }
}
```

### Após ETL A2 Hook

```python
enriched_chunk = {
    "content": "A Scania e a Volvo desenvolveram caminhões movidos a gás...",  # ← VETOR DEFAULT
    
    # Textos especializados para cada vetor
    "company_text": "Scania Volvo fabricantes caminhões GNL",  # ← VETOR COMPANY
    "concept_text": "TCO Total Cost Ownership custo total propriedade análise financeira",  # ← VETOR CONCEPT
    "sector_text": "transporte transportation logistics automotivo trucking",  # ← VETOR SECTOR
    
    # Metadados estruturados
    "companies": ["Scania", "Volvo"],
    "frameworks": ["TCO", "Total Cost of Ownership"],
    "sectors": ["transportation", "logistics", "automotive"],
    
    # Contexto adicional
    "section_title": "Caminhões a GNL",
    "section_path": ["Caminhões a GNL"],
    "section_level": 1,
    "chunk_lang": "pt",
    
    # ETL tracking
    "etl_version": "2.0",
    "pattern_genetics": ["entity_boost", "concept_expansion"]
}
```

### No Weaviate (Schema Final)

```json
{
  "content": "A Scania e a Volvo desenvolveram caminhões movidos a gás...",
  "company_text": "Scania Volvo fabricantes caminhões GNL",
  "concept_text": "TCO Total Cost Ownership custo total propriedade",
  "sector_text": "transporte transportation logistics automotivo",
  
  "companies": ["Scania", "Volvo"],
  "frameworks": ["TCO", "Total Cost of Ownership"],
  "sectors": ["transportation", "logistics", "automotive"],
  
  "_vectors": {
    "default": [0.234, -0.123, 0.456, ...],      // 384 dims de "content"
    "company_vec": [0.567, 0.234, -0.089, ...],  // 384 dims de "company_text"
    "concept_vec": [-0.123, 0.678, 0.234, ...],  // 384 dims de "concept_text"
    "sector_vec": [0.345, -0.456, 0.123, ...]    // 384 dims de "sector_text"
  }
}
```

---

## 🔬 Código Real - Como é Criado o company_text

### 1. Entity Semantic Chunker (Detecta Entidades)

```python
# entity_semantic_chunker.py linha ~400
def _extract_entities(self, text: str, lang: str):
    """Extrai empresas, frameworks, etc do texto"""
    
    entities = {
        "companies": [],
        "frameworks": [],
        "sectors": []
    }
    
    # Detecta com spaCy
    if self.nlp_tools.get(lang):
        doc = self.nlp_tools[lang](text)
        for ent in doc.ents:
            if ent.label_ == "ORG":
                entities["companies"].append(ent.text)
    
    # Detecta com Gazetteer (lista conhecida)
    for framework in self.framework_gazetteer:
        if framework.lower() in text.lower():
            entities["frameworks"].append(framework)
    
    return entities
```

### 2. ETL Hook (Enriquece e Cria Textos Especializados)

```python
# a2_etl_hook.py linha ~250
async def enrich_chunk(self, chunk_data: dict):
    """Enriquece chunk com ETL e cria textos para named vectors"""
    
    # Extrai entidades adicionais com GLiNER
    companies = chunk_data.get("companies", [])
    if self.use_gliner:
        gliner_companies = await self.gliner_extract(chunk_data["content"], "company")
        companies.extend(gliner_companies)
    
    # Remove duplicatas
    companies = list(set(companies))
    
    # CRIA COMPANY_TEXT - texto especializado para company_vec
    company_text = self._build_company_text(companies, chunk_data["content"])
    # Exemplo: "Scania Volvo Iveco fabricantes caminhões GNL natural gas trucks"
    
    # CRIA CONCEPT_TEXT
    concept_text = self._build_concept_text(
        chunk_data.get("frameworks", []),
        chunk_data["content"]
    )
    # Exemplo: "TCO Total Cost Ownership custo total propriedade ROI investimento"
    
    # CRIA SECTOR_TEXT
    sector_text = self._build_sector_text(
        chunk_data.get("sectors", []),
        chunk_data["content"]
    )
    # Exemplo: "transportation logistics automotive trucking fleet management"
    
    return {
        **chunk_data,
        "company_text": company_text,
        "concept_text": concept_text,
        "sector_text": sector_text,
        "companies": companies,
        "etl_version": "2.0"
    }

def _build_company_text(self, companies: list, context: str):
    """Cria texto otimizado para embedding de empresas"""
    
    # Base: nomes das empresas
    text_parts = companies.copy()
    
    # Adiciona contexto relevante (palavras próximas às empresas no texto)
    for company in companies:
        context_words = self._extract_context_around(company, context, window=5)
        text_parts.extend(context_words)
    
    # Adiciona sinônimos e variações
    text_parts.extend(self._get_company_synonyms(companies))
    
    return " ".join(text_parts)
```

### 3. Schema Updater (Define Vetores no Weaviate)

```python
# schema_updater.py linha ~80
def get_etl_aware_schema():
    """Define schema com named vectors"""
    
    return {
        "class": "VERBA_Embedding",
        "vectorizer": "none",  # Embeddings manuais
        "vectorConfig": {
            # VETOR PADRÃO
            "default": {
                "vectorIndexType": "hnsw",
                "vectorIndexConfig": {
                    "ef": 512,
                    "maxConnections": 64
                }
            },
            # VETOR DE EMPRESAS
            "company_vec": {
                "vectorIndexType": "hnsw",
                "vectorIndexConfig": {
                    "ef": 512,
                    "maxConnections": 64
                }
            },
            # VETOR DE CONCEITOS
            "concept_vec": {
                "vectorIndexType": "hnsw",
                "vectorIndexConfig": {
                    "ef": 512,
                    "maxConnections": 64
                }
            },
            # VETOR DE SETORES
            "sector_vec": {
                "vectorIndexType": "hnsw",
                "vectorIndexConfig": {
                    "ef": 512,
                    "maxConnections": 64
                }
            }
        },
        "properties": [
            {"name": "content", "dataType": ["text"]},
            {"name": "company_text", "dataType": ["text"]},
            {"name": "concept_text", "dataType": ["text"]},
            {"name": "sector_text", "dataType": ["text"]},
            {"name": "companies", "dataType": ["text[]"]},
            {"name": "frameworks", "dataType": ["text[]"]},
            {"name": "sectors", "dataType": ["text[]"]},
            # ... mais 37 campos
        ]
    }
```

---

## 🎯 Quando Cada Vetor é Usado?

### Busca Atual (Default)

```python
# managers.py linha 1360
query = (
    collection.query
    .hybrid(
        query=query_text,
        vector=query_embedding,
        alpha=0.5,
        target_vector="default"  # ← USA SEMPRE DEFAULT
    )
)
```

**Por quê?** Porque o vetor `default` é criado do `content` completo e dá os melhores resultados gerais.

### Uso Futuro dos Outros Vetores (Potencial)

```python
# Exemplo hipotético - EntityAwareRetriever avançado
def search_by_company(self, company_name: str):
    """Busca focada em empresas usando company_vec"""
    
    # Embed só o nome da empresa
    company_embedding = self.embedder.embed(company_name)
    
    # Busca usando company_vec ao invés de default
    results = collection.query.hybrid(
        query=company_name,
        vector=company_embedding,
        target_vector="company_vec"  # ← USA VETOR ESPECIALIZADO
    )
    # Melhor precisão para matching de empresas!
```

---

## 💡 Benefícios dos Named Vectors

### 1. Precisão Especializada

**Sem Named Vectors:**
```
Query: "Scania"
Embedding do texto completo: [contexto de caminhões + Scania + GNL + TCO...]
Resultado: Pode misturar contextos diferentes
```

**Com Named Vectors:**
```
Query: "Scania"
Embedding só de company_text: [Scania + Volvo + fabricantes + caminhões]
Resultado: Foco laser em empresas similares
```

### 2. Flexibilidade de Busca

```python
# Busca híbrida usando múltiplos vetores
results = aggregate_search(
    query="custo TCO Scania",
    vectors={
        "default": 0.5,      # 50% peso - contexto geral
        "company_vec": 0.3,  # 30% peso - empresas
        "concept_vec": 0.2   # 20% peso - conceitos (TCO)
    }
)
```

### 3. Escalabilidade

- ✅ Mesmo documento, múltiplas representações semânticas
- ✅ Sem precisar duplicar documentos
- ✅ Queries especializadas sem reprocessar dados

---

## 📊 Estatísticas Reais do Schema

```
Collection: VERBA_Embedding_all_MiniLM_L6_v2

Total Objects: 16 chunks
Total Vectors: 64 (16 chunks × 4 vectors cada)

Campos Principais:
├─ content (text) → default vector
├─ company_text (text) → company_vec
├─ concept_text (text) → concept_vec
└─ sector_text (text) → sector_vec

Campos de Metadados ETL: 44 total
├─ Entities: companies[], frameworks[], sectors[]
├─ Context: section_title, section_path[], parent_section
├─ Tracking: etl_version, pattern_genetics[]
└─ IDs: entities_local_ids[], primary_entity_id
```

---

## 🔧 Como Ativar Named Vectors

### No Verba UI

1. Settings → Advanced
2. ✅ Enable Named Vectors
3. ⚠️ Requer recriar collection (apaga dados existentes)

### Via Código

```python
# Ao criar collection
from verba_extensions.integration.schema_updater import enable_named_vectors

collection = enable_named_vectors(
    client=weaviate_client,
    collection_name="VERBA_Embedding_all_MiniLM_L6_v2",
    base_embedder="all-MiniLM-L6-v2"
)
```

---

## ❓ FAQ

**P: Por que usar 4 vetores ao invés de 1?**  
R: Cada vetor é otimizado para um espaço semântico. `company_vec` é melhor para matching de empresas porque foi gerado de texto contendo **só** empresas + contexto relevante.

**P: Posso adicionar mais vetores?**  
R: Sim! Basta adicionar no schema: `person_vec` (pessoas), `location_vec` (lugares), etc.

**P: Qual o custo de memória?**  
R: ~3x mais memória (4 vetores vs 1), mas vale a pena para precision.

**P: Como sei qual vetor usar?**  
R: Por padrão, sempre `default`. Use outros vetores só se implementar lógica especializada.

**P: Por que company_text não é só a lista de empresas?**  
R: Porque o embedding precisa de contexto! "Scania Volvo fabricantes caminhões GNL" gera embedding melhor que só "Scania Volvo".

---

## 📚 Arquivos Relacionados

- **Schema**: `verba_extensions/integration/schema_updater.py`
- **ETL**: `verba_extensions/plugins/a2_etl_hook.py`
- **Chunker**: `verba_extensions/plugins/entity_semantic_chunker.py`
- **Retriever**: `goldenverba/components/managers.py` (linha 1360)
- **GraphQL**: `verba_extensions/utils/graphql_builder.py` (linha 189)

---

**Documentação atualizada**: 2026-01-03  
**Versão**: ETL 2.0 com Named Vectors
