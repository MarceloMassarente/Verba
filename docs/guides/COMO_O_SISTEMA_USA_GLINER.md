# 🔍 Como o Sistema Usa GLiNER

## Visão Geral

O **GLiNER** (Generalist and Lightweight model for Named Entity Recognition) é um modelo de NER (Named Entity Recognition) usado no VERBA para detectar **frameworks de negócio** em textos de forma mais precisa que keyword matching simples.

**Modelo utilizado:** `urchade/gliner_small-v2.1`

---

## 🎯 Objetivo do Uso

O GLiNER é usado especificamente para:

1. **Detecção de Frameworks de Negócio** em chunks de texto
2. **Complemento ao Keyword Matching** - quando GLiNER não está disponível, usa fallback
3. **Melhoria da Precisão** - reduz falsos positivos comparado a apenas regex/keywords

---

## 📍 Onde é Usado

### 1. **FrameworkDetector** (`verba_extensions/utils/framework_detector.py`)

**Classe principal que encapsula o uso do GLiNER:**

```python
class FrameworkDetector:
    def __init__(self):
        self.gliner_model = None
        self._load_models()  # Tenta carregar GLiNER aqui
    
    def _load_models(self):
        """Carrega modelos de NER se disponíveis"""
        try:
            from gliner import GLiNER
            self.gliner_model = GLiNER.from_pretrained("urchade/gliner_small-v2.1")
            msg.info("Gliner carregado para deteccao de frameworks")
        except ImportError:
            msg.info("Gliner nao disponivel - usando fallback para keywords")
        except Exception as e:
            msg.warn(f"Erro ao carregar Gliner: {str(e)} - usando fallback")
```

**Uso na detecção de frameworks:**

```python
def _detect_frameworks_in_text(self, text: str) -> List[str]:
    """Detecta frameworks usando Gliner ou keyword matching com aliases"""
    detected_names = set()
    
    # Tenta usar Gliner primeiro (mais preciso)
    if self.gliner_model:
        try:
            # Define labels para frameworks
            labels = ["framework", "business model", "strategic framework"]
            entities = self.gliner_model.predict_entities(text, labels, threshold=0.5)
            
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
        except Exception as e:
            msg.debug(f"Erro ao usar Gliner para frameworks: {str(e)}")
    
    # Keyword matching como fallback ou complemento
    # ... (código de fallback)
```

**Características importantes:**
- **Labels customizados**: `["framework", "business model", "strategic framework"]`
- **Threshold**: `0.5` (50% de confiança mínima)
- **Validação posterior**: As entidades encontradas pelo GLiNER são validadas contra aliases conhecidos de frameworks
- **Fallback gracioso**: Se GLiNER falhar ou não estiver disponível, usa keyword matching

---

### 2. **EntitySemanticChunker** (`verba_extensions/plugins/entity_semantic_chunker.py`)

**Usa FrameworkDetector durante o chunking:**

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

**Quando é executado:**
- Durante o processo de chunking de documentos
- Para cada chunk criado
- **Não bloqueia** o chunking se falhar (decorador não crítico)

---

### 3. **EntityAwareRetriever** (`verba_extensions/plugins/entity_aware_retriever.py`)

**Usa FrameworkDetector para detectar frameworks na query do usuário:**

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
        # ... aplica filtro na busca Weaviate
except Exception as e:
    msg.debug(f"Erro ao detectar frameworks na query: {str(e)}")
```

**Quando é executado:**
- Durante a busca/retrieval de chunks
- **Antes** de fazer a query no Weaviate
- Usa frameworks detectados para aplicar filtros na busca

---

## 🔄 Fluxo Completo de Uso

```
1. Inicialização do Sistema
   ↓
   FrameworkDetector.__init__()
   ↓
   _load_models()
   ↓
   Tenta carregar GLiNER:
   - GLiNER.from_pretrained("urchade/gliner_small-v2.1")
   - Se sucesso: self.gliner_model = modelo
   - Se falha: self.gliner_model = None (usa fallback)

2. Durante Import/Chunking (EntitySemanticChunker)
   ↓
   Para cada chunk criado:
   ↓
   framework_detector.detect_frameworks(chunk_text)
   ↓
   _detect_frameworks_in_text(text)
   ↓
   Se self.gliner_model existe:
   - GLiNER.predict_entities(text, labels=["framework", ...], threshold=0.5)
   - Valida entidades contra aliases conhecidos
   - Adiciona frameworks detectados
   ↓
   Fallback: Keyword matching (sempre executado como complemento)
   ↓
   Salva em chunk.meta["frameworks"]

3. Durante Busca/Retrieval (EntityAwareRetriever)
   ↓
   Usuário faz query: "o que se fala sobre SWOT e Porter?"
   ↓
   framework_detector.detect_frameworks(query)
   ↓
   GLiNER detecta: ["SWOT", "Porter"]
   ↓
   Aplica filtro Weaviate:
   WHERE frameworks CONTAINS ["SWOT Analysis", "Porter's Five Forces"]
   ↓
   Retorna apenas chunks que mencionam esses frameworks
```

---

## 🎛️ Configuração e Parâmetros

### Modelo GLiNER

- **Nome:** `urchade/gliner_small-v2.1`
- **Tamanho:** "small" (leve, rápido)
- **Versão:** v2.1

### Labels Utilizados

```python
labels = [
    "framework",              # Framework genérico
    "business model",         # Modelo de negócio
    "strategic framework"     # Framework estratégico
]
```

**Por que esses labels?**
- São labels genéricos que capturam diferentes tipos de frameworks
- Permitem ao GLiNER encontrar entidades mesmo que não estejam exatamente nos aliases do JSON
- Depois, o sistema valida se o texto encontrado corresponde a um framework conhecido

### Threshold

- **Valor:** `0.5` (50%)
- **Significado:** GLiNER só retorna entidades com confiança >= 50%
- **Razão:** Balanceia precisão vs recall

### Validação Posterior

Mesmo que GLiNER encontre uma entidade, ela só é aceita se:
1. Corresponder a um alias conhecido no `frameworks.json`
2. Match parcial ou completo (flexível)

```python
for alias, framework_name in self.frameworks_data.items():
    if alias in entity_lower or entity_lower in alias:
        detected_names.add(framework_name)
        break
```

---

## 🔀 Estratégia Híbrida: GLiNER + Keyword Matching

O sistema usa uma **estratégia híbrida** para máxima precisão:

### 1. GLiNER (Primário)
- ✅ Detecta frameworks mesmo em contexto variado
- ✅ Reduz falsos positivos
- ✅ Entende sinônimos e variações
- ⚠️ Requer instalação: `pip install gliner`

### 2. Keyword Matching (Fallback/Complemento)
- ✅ Sempre disponível (não requer instalação)
- ✅ Rápido e leve
- ✅ Usa aliases do `frameworks.json` (336+ aliases)
- ⚠️ Pode ter falsos positivos em contexto similar

**Estratégia combinada:**
```python
# 1. Tenta GLiNER primeiro
if self.gliner_model:
    entities = self.gliner_model.predict_entities(...)
    # Valida e adiciona

# 2. Keyword matching sempre executa (complemento)
for alias, framework_name in self.frameworks_data.items():
    # Busca por regex/keyword
    # Adiciona se encontrado

# 3. Retorna união (sem duplicatas)
return sorted(list(detected_names))
```

---

## 📊 Exemplo Prático

### Texto de Entrada

```
"Utilizamos análise SWOT e as 5 Forças de Porter para avaliar 
a posição competitiva da Apple no mercado de tecnologia."
```

### Processo de Detecção

1. **GLiNER processa o texto:**
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

3. **Keyword matching complementar:**
   - Busca "apple" → detecta empresa: "Apple"
   - Busca "tecnologia" → detecta setor: "technology"

4. **Resultado final:**
   ```python
   {
       "frameworks": ["SWOT Analysis", "Porter's Five Forces"],
       "companies": ["Apple"],
       "sectors": ["technology"],
       "confidence": 0.85
   }
   ```

---

## ⚠️ Limite de Tokens e Chunking Automático

### Limite de 384 Tokens

O GLiNER tem um **limite máximo de 384 tokens** por entrada. Se um texto exceder esse limite:

1. **Sem tratamento**: O texto seria truncado automaticamente pelo modelo
2. **Problema**: Frameworks no final do texto não seriam detectados
3. **Warning**: GLiNER emite warning: `"Sentence of length X has been truncated to 384"`

### Solução Implementada

O `FrameworkDetector` agora **divide automaticamente textos longos** antes de processar com GLiNER:

```python
# Estima tokens: ~3 caracteres por token (conservador)
estimated_tokens = self._estimate_token_count(text)

if estimated_tokens > 350:  # Margem de segurança (350 < 384)
    # Divide texto em chunks menores
    text_chunks = self._split_text_for_gliner(text, max_tokens=350)
    
    # Processa cada chunk separadamente
    all_entities = []
    for chunk in text_chunks:
        chunk_entities = self.gliner_model.predict_entities(chunk, labels, threshold=0.5)
        all_entities.extend(chunk_entities)
    
    # Combina resultados de todos os chunks
    entities = all_entities
```

### Divisão Inteligente

O algoritmo de divisão prioriza delimitadores naturais:

1. **Parágrafos** (`\n\n`) - melhor para preservar contexto
2. **Sentenças** (`. `, `! `, `? `) - bom para manter significado
3. **Vírgulas** (`, `) - melhor que cortar no meio de palavra
4. **Espaços** - último recurso

### Exemplo

**Antes (sem chunking):**
```
Texto de 500 tokens → GLiNER trunca para 384 tokens
→ PESTEL Analysis (no final) não é detectado ❌
```

**Depois (com chunking):**
```
Texto de 500 tokens → Dividido em 2 chunks de ~250 tokens cada
→ Chunk 1 processado: detecta SWOT, Porter ✅
→ Chunk 2 processado: detecta PESTEL ✅
→ Resultado combinado: todos os frameworks detectados ✅
```

---

## 🚨 Tratamento de Erros

### GLiNER não instalado

```python
try:
    from gliner import GLiNER
    self.gliner_model = GLiNER.from_pretrained("urchade/gliner_small-v2.1")
except ImportError:
    msg.info("Gliner nao disponivel - usando fallback para keywords")
    self.gliner_model = None
```

**Comportamento:** Sistema continua funcionando com keyword matching

### Erro ao carregar modelo

```python
except Exception as e:
    msg.warn(f"Erro ao carregar Gliner: {str(e)} - usando fallback")
    self.gliner_model = None
```

**Comportamento:** Sistema usa fallback, não quebra

### Erro durante predição

```python
try:
    entities = self.gliner_model.predict_entities(text, labels, threshold=0.5)
except Exception as e:
    msg.debug(f"Erro ao usar Gliner para frameworks: {str(e)}")
    # Continua com keyword matching
```

**Comportamento:** Falha silenciosa, continua com keyword matching

---

## 🔧 Como Instalar GLiNER

### Opção 1: Via pip

```bash
pip install gliner
```

### Opção 2: Via requirements.txt

```txt
gliner>=0.2.0
```

### Verificação

Após instalar, o sistema detecta automaticamente na próxima inicialização:

```python
# No log você verá:
"Gliner carregado para deteccao de frameworks"
```

Se não instalado:
```python
# No log:
"Gliner nao disponivel - usando fallback para keywords"
```

---

## 📈 Performance e Impacto

### Vantagens do GLiNER

1. **Maior Precisão**: Reduz falsos positivos
2. **Contexto-Aware**: Entende contexto da frase
3. **Sinônimos**: Detecta mesmo com variações linguísticas
4. **Robustez**: Funciona mesmo com texto mal formatado

### Desvantagens

1. **Requer Instalação**: Não é obrigatório, mas melhora resultados
2. **Latência**: Ligeiramente mais lento que keyword matching
3. **Memória**: Modelo ocupa ~100-200MB de RAM
4. **GPU**: Opcional (CPU funciona bem)

### Benchmarks (Estimados)

- **Com GLiNER**: ~95% precisão, ~200ms por chunk
- **Sem GLiNER**: ~85% precisão, ~10ms por chunk

---

## 🔍 Debugging e Logs

### Ativar logs de debug

```python
import logging
logging.getLogger("verba_extensions.utils.framework_detector").setLevel(logging.DEBUG)
```

### Logs importantes

1. **Carregamento:**
   ```
   "Gliner carregado para deteccao de frameworks"
   "Gliner nao disponivel - usando fallback para keywords"
   ```

2. **Durante detecção:**
   ```
   "[FrameworkDetector] Detectados: ['SWOT Analysis', 'Porter's Five Forces']"
   ```

3. **Erros:**
   ```
   "Erro ao usar Gliner para frameworks: {erro}"
   ```

---

## 📚 Referências

- **GLiNER GitHub**: https://github.com/urchade/gliner
- **Modelo HuggingFace**: https://huggingface.co/urchade/gliner_small-v2.1
- **Paper GLiNER**: [Generalist and Lightweight Model for Named Entity Recognition using Bidirectional Encoder](https://arxiv.org/abs/2309.11126)

---

## ✅ Resumo

O GLiNER é usado no VERBA como uma **melhoria opcional** para detecção de frameworks:

1. **Não é obrigatório** - sistema funciona sem ele
2. **Melhora precisão** - reduz falsos positivos
3. **Fallback gracioso** - se não disponível, usa keyword matching
4. **Uso híbrido** - GLiNER + keyword matching combinados
5. **Validação posterior** - só aceita frameworks conhecidos
6. **Não bloqueia** - erros não impedem funcionamento do sistema

O sistema foi projetado para ser **resiliente** e funcionar bem tanto com quanto sem GLiNER instalado.

