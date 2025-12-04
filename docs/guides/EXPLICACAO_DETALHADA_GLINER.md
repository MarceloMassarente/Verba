# 🔍 Explicação Detalhada: Como o GLiNER é Usado no Sistema

## 📋 Índice

1. [Visão Geral](#visão-geral)
2. [Como o GLiNER é Carregado e Parametrizado](#como-o-gliner-é-carregado-e-parametrizado)
3. [Relação com Spacy](#relação-com-spacy)
4. [Onde os Resultados são Armazenados](#onde-os-resultados-são-armazenados)
5. [Fluxo Completo de Uso](#fluxo-completo-de-uso)
6. [Exemplos Práticos](#exemplos-práticos)

---

## 🎯 Visão Geral

O **GLiNER** (Generalist and Lightweight model for Named Entity Recognition) é um modelo de NER usado especificamente para **detecção de frameworks de negócio** em textos. Ele funciona como uma camada de precisão adicional sobre o keyword matching tradicional.

**Arquivo principal:** `verba_extensions/utils/framework_detector.py`

**Classe responsável:** `FrameworkDetector`

---

## ⚙️ Como o GLiNER é Carregado e Parametrizado

### 1. Inicialização e Carregamento

O GLiNER é carregado durante a inicialização do `FrameworkDetector`:

```python
class FrameworkDetector:
    def __init__(self):
        self.gliner_model = None
        self.spacy_nlp = None
        self._load_models()  # Carrega GLiNER e spaCy aqui
    
    def _load_models(self):
        """Carrega modelos de NER se disponíveis"""
        # Tenta carregar Gliner
        try:
            from gliner import GLiNER
            self.gliner_model = GLiNER.from_pretrained("urchade/gliner_small-v2.1")
            msg.info("Gliner carregado para deteccao de frameworks")
        except ImportError:
            msg.info("Gliner nao disponivel - usando fallback para keywords")
            self.gliner_model = None
        except Exception as e:
            msg.warn(f"Erro ao carregar Gliner: {str(e)} - usando fallback")
            self.gliner_model = None
```

**Características do carregamento:**
- **Modelo:** `urchade/gliner_small-v2.1` (versão "small" - leve e rápida)
- **Fallback gracioso:** Se não estiver instalado ou houver erro, `self.gliner_model = None` e o sistema continua funcionando
- **Singleton:** O `FrameworkDetector` é uma instância singleton (carregado uma vez, reutilizado)

### 2. Parâmetros de Uso

Quando o GLiNER é usado para detectar frameworks, os seguintes parâmetros são aplicados:

```python
def _detect_frameworks_in_text(self, text: str) -> List[str]:
    if self.gliner_model:
        # Define labels para frameworks
        labels = ["framework", "business model", "strategic framework"]
        
        # Chama GLiNER com threshold
        entities = self.gliner_model.predict_entities(
            text, 
            labels=labels, 
            threshold=0.5  # 50% de confiança mínima
        )
```

**Parâmetros principais:**

| Parâmetro | Valor | Descrição |
|-----------|-------|-----------|
| **Modelo** | `urchade/gliner_small-v2.1` | Modelo pré-treinado do HuggingFace |
| **Labels** | `["framework", "business model", "strategic framework"]` | Tipos de entidades a detectar |
| **Threshold** | `0.5` (50%) | Confiança mínima para aceitar detecção |
| **Limite de Tokens** | `384 tokens` | Limite máximo por entrada (tratado automaticamente) |

### 3. Tratamento de Textos Longos

O GLiNER tem um limite de **384 tokens** por entrada. O sistema trata isso automaticamente:

```python
# Estima tokens: ~3 caracteres por token (conservador)
estimated_tokens = self._estimate_token_count(text)

if estimated_tokens > 350:  # Margem de segurança (350 < 384)
    # Divide texto em chunks menores
    text_chunks = self._split_text_for_gliner(text, max_tokens=350)
    
    # Processa cada chunk separadamente
    all_entities = []
    for chunk in text_chunks:
        chunk_entities = self.gliner_model.predict_entities(
            chunk, 
            labels, 
            threshold=0.5
        )
        all_entities.extend(chunk_entities)
    
    entities = all_entities
else:
    # Texto cabe no limite, processa normalmente
    entities = self.gliner_model.predict_entities(text, labels, threshold=0.5)
```

**Algoritmo de divisão:**
1. **Parágrafos** (`\n\n`) - prioridade máxima
2. **Sentenças** (`. `, `! `, `? `) - segunda prioridade
3. **Vírgulas** (`, `) - terceira prioridade
4. **Espaços** - último recurso

### 4. Validação Posterior

Mesmo que o GLiNER encontre uma entidade, ela só é aceita se corresponder a um framework conhecido:

```python
# Processa entidades encontradas pelo GLiNER
for entity in entities:
    entity_text = entity.get("text", "").strip()
    if entity_text:
        entity_lower = entity_text.lower()
        # Verifica se corresponde a algum alias conhecido
        for alias, framework_name in self.frameworks_data.items():
            # Match parcial ou completo
            if alias in entity_lower or entity_lower in alias:
                detected_names.add(framework_name)
                break
```

**Fonte de validação:** `verba_extensions/resources/frameworks.json` (336+ aliases de frameworks)

---

## 🔗 Relação com Spacy

O GLiNER e o spaCy **não competem** - eles têm **propósitos diferentes** e são usados de forma **complementar**:

### GLiNER: Detecção de Frameworks

**Propósito:** Detectar frameworks de negócio (SWOT, Porter, BCG, etc.)

**Onde é usado:**
- `FrameworkDetector._detect_frameworks_in_text()` - detecção de frameworks
- Labels: `["framework", "business model", "strategic framework"]`

**Exemplo:**
```python
# GLiNER detecta frameworks
text = "Utilizamos análise SWOT e as 5 Forças de Porter"
entities = gliner_model.predict_entities(text, labels=["framework"], threshold=0.5)
# Resultado: [{"text": "análise SWOT", "label": "framework", "score": 0.87}, ...]
```

### spaCy: Detecção de Entidades Nomeadas (ORG, PERSON, LOC)

**Propósito:** Detectar entidades nomeadas (empresas, pessoas, localizações)

**Onde é usado:**
- `FrameworkDetector._detect_companies_in_text()` - detecção de empresas
- `extract_entities_pre_chunking()` - extração de entidades para ETL
- `extract_entities_from_query()` - extração de entidades da query do usuário

**Exemplo:**
```python
# spaCy detecta entidades nomeadas
text = "Apple lançou novo iPhone. Steve Jobs fundou a empresa."
doc = spacy_nlp(text)
# Resultado: 
# - "Apple" (ORG)
# - "Steve Jobs" (PERSON)
```

### Comparação Lado a Lado

| Aspecto | GLiNER | spaCy |
|---------|--------|-------|
| **Propósito** | Frameworks de negócio | Entidades nomeadas (ORG, PERSON, LOC) |
| **Labels** | `["framework", "business model"]` | `["ORG", "PERSON", "GPE", "LOC"]` |
| **Uso no sistema** | Detecção de frameworks | Detecção de empresas + ETL de entidades |
| **Modelo** | `urchade/gliner_small-v2.1` | `pt_core_news_sm` ou `en_core_web_sm` |
| **Threshold** | 0.5 (50%) | Não aplicado (usa todas as entidades) |
| **Validação** | Valida contra `frameworks.json` | Valida contra gazetteer (opcional) |

### Uso Conjunto no FrameworkDetector

Ambos são carregados na mesma classe, mas usados para propósitos diferentes:

```python
class FrameworkDetector:
    def __init__(self):
        self.gliner_model = None  # Para frameworks
        self.spacy_nlp = None     # Para empresas
        self._load_models()
    
    def _load_models(self):
        # Carrega GLiNER para frameworks
        try:
            from gliner import GLiNER
            self.gliner_model = GLiNER.from_pretrained("urchade/gliner_small-v2.1")
        except:
            self.gliner_model = None
        
        # Carrega spaCy para empresas
        try:
            import spacy
            self.spacy_nlp = spacy.load("pt_core_news_sm")
        except:
            self.spacy_nlp = None
    
    async def detect_frameworks(self, text: str) -> Dict[str, any]:
        """Detecta frameworks, empresas e setores"""
        # GLiNER para frameworks
        frameworks = self._detect_frameworks_in_text(text)  # Usa GLiNER
        
        # spaCy para empresas
        companies = await self._detect_companies_in_text(text)  # Usa spaCy
        
        # Keywords para setores
        sectors = self._detect_sectors_in_text(text)  # Usa keywords
        
        return {
            "frameworks": frameworks,
            "companies": companies,
            "sectors": sectors,
            "confidence": self._calculate_confidence(...)
        }
```

---

## 💾 Onde os Resultados são Armazenados

Os resultados do GLiNER são armazenados em **múltiplos níveis**:

### 1. Durante o Chunking (EntitySemanticChunker)

**Arquivo:** `verba_extensions/plugins/entity_semantic_chunker.py`

**Quando:** Durante o processo de chunking de documentos

**Onde:** `chunk.meta` (dicionário Python)

```python
# Detecta frameworks, empresas e setores (opcional, não bloqueia se falhar)
try:
    from verba_extensions.utils.framework_detector import get_framework_detector
    framework_detector = get_framework_detector()
    framework_data = await framework_detector.detect_frameworks(chunk_text)
    
    # Enriquece metadata do chunk
    if not hasattr(chunk, "meta") or chunk.meta is None:
        chunk.meta = {}
    
    chunk.meta["frameworks"] = framework_data.get("frameworks", [])
    chunk.meta["companies"] = framework_data.get("companies", [])
    chunk.meta["sectors"] = framework_data.get("sectors", [])
    chunk.meta["framework_confidence"] = framework_data.get("confidence", 0.0)
except Exception as e:
    # Falha na detecção não bloqueia chunking
    msg.debug(f"[Entity-Semantic] Erro ao detectar frameworks (não crítico): {str(e)}")
```

**Estrutura em `chunk.meta`:**
```python
chunk.meta = {
    "frameworks": ["SWOT Analysis", "Porter's Five Forces"],
    "companies": ["Apple", "Microsoft"],
    "sectors": ["technology"],
    "framework_confidence": 0.85
}
```

### 2. Durante o Import (Weaviate)

**Arquivo:** `verba_extensions/integration/import_hook.py`

**Quando:** Durante o import do documento para o Weaviate

**Onde:** Propriedades do Weaviate (se schema suporta) ou `meta` JSON (fallback)

#### 2.1. Se Collection tem Propriedades de Framework

Se a collection do Weaviate foi criada com propriedades de framework (via `schema_updater.py`):

```python
# Propriedades no schema Weaviate:
Property(name="frameworks", data_type=DataType.TEXT_ARRAY, ...)
Property(name="companies", data_type=DataType.TEXT_ARRAY, ...)
Property(name="sectors", data_type=DataType.TEXT_ARRAY, ...)
Property(name="framework_confidence", data_type=DataType.NUMBER, ...)
```

**Mapeamento:**
```python
async def _map_framework_properties_to_weaviate(
    client,
    collection_name: str,
    chunk_properties: Dict[str, Any]
) -> Dict[str, Any]:
    # Extrai meta do chunk
    meta = json.loads(chunk_properties.get("meta", "{}"))
    
    frameworks = meta.get("frameworks", [])
    companies = meta.get("companies", [])
    sectors = meta.get("sectors", [])
    framework_confidence = meta.get("framework_confidence", 0.0)
    
    # Se collection tem propriedades de framework, adiciona diretamente
    if has_framework_props:
        chunk_properties["frameworks"] = frameworks
        chunk_properties["companies"] = companies
        chunk_properties["sectors"] = sectors
        chunk_properties["framework_confidence"] = framework_confidence
    
    return chunk_properties
```

**Estrutura no Weaviate:**
```json
{
  "uuid": "chunk-123",
  "properties": {
    "text": "Apple lança novo iPhone...",
    "frameworks": ["SWOT Analysis", "Porter's Five Forces"],
    "companies": ["Apple"],
    "sectors": ["technology"],
    "framework_confidence": 0.85,
    "doc_uuid": "doc-456"
  },
  "vector": [0.123, -0.456, ...]
}
```

#### 2.2. Se Collection NÃO tem Propriedades de Framework (Fallback)

Se a collection não tem propriedades de framework, os dados são mantidos em `meta` JSON:

```python
# Fallback: salva em meta JSON
if frameworks or companies or sectors:
    meta["frameworks"] = frameworks
    meta["companies"] = companies
    meta["sectors"] = sectors
    meta["framework_confidence"] = framework_confidence
    chunk_properties["meta"] = json.dumps(meta)
```

**Estrutura no Weaviate (fallback):**
```json
{
  "uuid": "chunk-123",
  "properties": {
    "text": "Apple lança novo iPhone...",
    "meta": "{\"frameworks\": [\"SWOT Analysis\"], \"companies\": [\"Apple\"]}",
    "doc_uuid": "doc-456"
  },
  "vector": [0.123, -0.456, ...]
}
```

### 3. Durante a Busca (EntityAwareRetriever)

**Arquivo:** `verba_extensions/plugins/entity_aware_retriever.py`

**Quando:** Durante a busca/retrieval de chunks (quando usuário faz query)

**Onde:** Usado para **filtrar** a busca, não armazenado

```python
# Detecta frameworks mencionados na query
try:
    from verba_extensions.utils.framework_detector import get_framework_detector
    framework_detector = get_framework_detector()
    framework_data = await framework_detector.detect_frameworks(query)
    
    detected_frameworks = framework_data.get("frameworks", [])
    detected_companies = framework_data.get("companies", [])
    detected_sectors = framework_data.get("sectors", [])
    
    # Usa frameworks detectados para filtrar busca
    if detected_frameworks:
        framework_filter = Filter.by_property("frameworks").contains_any(detected_frameworks)
        # Aplica filtro na busca Weaviate
except Exception as e:
    msg.debug(f"Erro ao detectar frameworks na query: {str(e)}")
```

**Exemplo:**
```python
# Query do usuário: "o que se fala sobre SWOT e Porter?"
# GLiNER detecta: ["SWOT Analysis", "Porter's Five Forces"]
# Aplica filtro Weaviate:
WHERE frameworks CONTAINS ["SWOT Analysis", "Porter's Five Forces"]
# Retorna apenas chunks que mencionam esses frameworks
```

---

## 🔄 Fluxo Completo de Uso

### Fluxo 1: Durante Import/Chunking

```
1. Documento é lido pelo Reader
   ↓
2. EntitySemanticChunker.chunk() é chamado
   ↓
3. Para cada chunk criado:
   ↓
4. framework_detector.detect_frameworks(chunk_text)
   ↓
5. FrameworkDetector._detect_frameworks_in_text(text)
   ↓
6. Se self.gliner_model existe:
   - GLiNER.predict_entities(text, labels=["framework", ...], threshold=0.5)
   - Valida entidades contra aliases conhecidos (frameworks.json)
   - Adiciona frameworks detectados
   ↓
7. Fallback: Keyword matching (sempre executado como complemento)
   ↓
8. Salva em chunk.meta["frameworks"]
   ↓
9. Durante import para Weaviate:
   - _map_framework_properties_to_weaviate() mapeia para propriedades
   - Se collection tem propriedades: frameworks, companies, sectors
   - Se não: mantém em meta JSON
```

### Fluxo 2: Durante Busca/Retrieval

```
1. Usuário faz query: "o que se fala sobre SWOT e Porter?"
   ↓
2. EntityAwareRetriever.retrieve() é chamado
   ↓
3. framework_detector.detect_frameworks(query)
   ↓
4. GLiNER detecta: ["SWOT Analysis", "Porter's Five Forces"]
   ↓
5. Aplica filtro Weaviate:
   WHERE frameworks CONTAINS ["SWOT Analysis", "Porter's Five Forces"]
   ↓
6. Retorna apenas chunks que mencionam esses frameworks
```

---

## 📊 Exemplos Práticos

### Exemplo 1: Detecção Durante Chunking

**Texto de entrada:**
```
"Utilizamos análise SWOT e as 5 Forças de Porter para avaliar 
a posição competitiva da Apple no mercado de tecnologia."
```

**Processo:**
1. **GLiNER processa:**
   ```python
   labels = ["framework", "business model", "strategic framework"]
   entities = gliner_model.predict_entities(text, labels, threshold=0.5)
   # Resultado:
   # [
   #   {"text": "análise SWOT", "label": "framework", "score": 0.87},
   #   {"text": "5 Forças de Porter", "label": "framework", "score": 0.92}
   # ]
   ```

2. **Validação contra aliases:**
   - "análise SWOT" → match com alias "swot" → Framework: "SWOT Analysis"
   - "5 Forças de Porter" → match com alias "5 forças" → Framework: "Porter's Five Forces"

3. **spaCy detecta empresas:**
   ```python
   doc = spacy_nlp(text)
   # "Apple" (ORG) → detectado
   ```

4. **Resultado final em `chunk.meta`:**
   ```python
   {
       "frameworks": ["SWOT Analysis", "Porter's Five Forces"],
       "companies": ["Apple"],
       "sectors": ["technology"],
       "framework_confidence": 0.85
   }
   ```

5. **Armazenado no Weaviate:**
   ```json
   {
     "properties": {
       "text": "Utilizamos análise SWOT...",
       "frameworks": ["SWOT Analysis", "Porter's Five Forces"],
       "companies": ["Apple"],
       "sectors": ["technology"],
       "framework_confidence": 0.85
     }
   }
   ```

### Exemplo 2: Uso Durante Busca

**Query do usuário:**
```
"o que se fala sobre SWOT e Porter?"
```

**Processo:**
1. **GLiNER detecta frameworks na query:**
   ```python
   framework_data = await framework_detector.detect_frameworks(query)
   # Resultado: {"frameworks": ["SWOT Analysis", "Porter's Five Forces"], ...}
   ```

2. **Aplica filtro Weaviate:**
   ```python
   framework_filter = Filter.by_property("frameworks").contains_any(
       ["SWOT Analysis", "Porter's Five Forces"]
   )
   ```

3. **Busca no Weaviate:**
   ```python
   results = await collection.query.fetch_objects(
       where=framework_filter,
       limit=10
   )
   ```

4. **Retorna apenas chunks que mencionam esses frameworks**

---

## 📝 Resumo

### GLiNER: Parâmetros e Configuração

| Aspecto | Detalhes |
|---------|----------|
| **Modelo** | `urchade/gliner_small-v2.1` |
| **Labels** | `["framework", "business model", "strategic framework"]` |
| **Threshold** | `0.5` (50% confiança mínima) |
| **Limite de Tokens** | `384 tokens` (tratado automaticamente com chunking) |
| **Validação** | Valida contra `frameworks.json` (336+ aliases) |
| **Fallback** | Keyword matching se GLiNER não disponível |

### Relação com spaCy

| Aspecto | GLiNER | spaCy |
|---------|--------|-------|
| **Propósito** | Frameworks de negócio | Entidades nomeadas (ORG, PERSON, LOC) |
| **Uso** | Detecção de frameworks | Detecção de empresas + ETL |
| **Complementar** | ✅ Sim - não competem, trabalham juntos |

### Armazenamento de Resultados

| Nível | Localização | Formato |
|-------|-------------|---------|
| **Chunking** | `chunk.meta` | Dicionário Python |
| **Weaviate (com schema)** | Propriedades diretas | `frameworks`, `companies`, `sectors` |
| **Weaviate (sem schema)** | `meta` JSON | String JSON serializada |
| **Busca** | Filtros Weaviate | WHERE clauses |

---

## 🔗 Referências

- **GLiNER GitHub**: https://github.com/urchade/gliner
- **Modelo HuggingFace**: https://huggingface.co/urchade/gliner_small-v2.1
- **Paper GLiNER**: [Generalist and Lightweight Model for Named Entity Recognition](https://arxiv.org/abs/2309.11126)
- **Documentação Framework Detection**: `docs/guides/FRAMEWORK_DETECTION.md`
- **Documentação COMO_O_SISTEMA_USA_GLINER**: `docs/guides/COMO_O_SISTEMA_USA_GLINER.md`

