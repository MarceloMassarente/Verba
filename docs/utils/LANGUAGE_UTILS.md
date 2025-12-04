# Módulo Utilitário Comum: language_utils

**Localização:** `verba_extensions/utils/language_utils.py`  
**Status:** ✅ Estável e em uso  
**Data:** 2025-01

---

## Visão Geral

O módulo `language_utils` consolida código duplicado de detecção de idioma e NLP que estava espalhado em múltiplos plugins. Elimina ~40% de código duplicado e fornece uma interface unificada para processamento de linguagem natural.

---

## Funcionalidades

### 1. Detecção de Idioma

```python
from verba_extensions.utils.language_utils import detect_query_language

language = detect_query_language("O que é inovação?")
# Retorna: "pt"

language = detect_query_language("What is innovation?")
# Retorna: "en"
```

**Características:**
- Usa `langdetect` se disponível (mais preciso)
- Fallback para heurística simples baseada em palavras comuns
- Suporta PT e EN (extensível para outros idiomas)
- Default: "pt" se não detectar

### 2. Carregamento de Modelos spaCy

```python
from verba_extensions.utils.language_utils import get_nlp

# Carrega modelo português (padrão)
nlp = get_nlp(language="pt")

# Carrega modelo inglês
nlp = get_nlp(language="en")

# Usa default da env var SPACY_MODEL
nlp = get_nlp()
```

**Características:**
- Cache global de modelos por idioma (não recarrega)
- Lazy loading (só carrega quando necessário)
- Fallback automático para português se modelo não disponível
- Suporta múltiplos idiomas simultaneamente

**Modelos suportados:**
- Português: `pt_core_news_sm`
- Inglês: `en_core_web_sm`

### 3. Stopwords

```python
from verba_extensions.utils.language_utils import (
    STOPWORDS_PT,
    STOPWORDS_EN,
    get_stopwords,
    get_all_stopwords
)

# Constantes globais
pt_stopwords = STOPWORDS_PT
en_stopwords = STOPWORDS_EN

# Função helper
stopwords = get_stopwords("pt")  # Retorna STOPWORDS_PT
stopwords = get_stopwords("en")  # Retorna STOPWORDS_EN

# Todas as stopwords combinadas
all_stopwords = get_all_stopwords()  # STOPWORDS_PT | STOPWORDS_EN
```

**Características:**
- Constantes globais imutáveis (sets)
- ~60 stopwords PT e ~50 stopwords EN
- Funções helper para acesso conveniente

---

## Plugins que Usam Este Módulo

### Atualizados para usar language_utils:

1. **`entity_aware_query_orchestrator.py`**
   - Usa: `detect_query_language()`, `get_nlp()`
   - Antes: Tinha implementação própria duplicada

2. **`a2_etl_hook.py`**
   - Usa: `get_nlp()`
   - Antes: Tinha `get_nlp()` próprio

3. **`bilingual_filter.py`**
   - Usa: `detect_query_language()`
   - Antes: Tinha `detect_query_language_simple()` próprio

4. **`adaptive_entropy.py`**
   - Usa: `STOPWORDS_PT`, `STOPWORDS_EN`, `get_all_stopwords()`
   - Antes: Tinha listas próprias de stopwords

5. **`query_rewriter.py`**
   - Usa: `STOPWORDS_PT`, `STOPWORDS_EN`
   - Antes: Tinha listas próprias de stopwords

---

## Benefícios da Consolidação

### Antes da Consolidação:
- ❌ Código duplicado em 5+ arquivos
- ❌ Inconsistências potenciais entre implementações
- ❌ Manutenção difícil (mudanças em múltiplos lugares)
- ❌ Cache de modelos spaCy duplicado (ineficiente)

### Depois da Consolidação:
- ✅ Código centralizado em um único módulo
- ✅ Implementação consistente em todos os plugins
- ✅ Manutenção fácil (mudanças em um lugar)
- ✅ Cache global eficiente (modelos carregados uma vez)
- ✅ ~40% menos código duplicado

---

## Exemplos de Uso

### Exemplo 1: Detecção de Idioma em Query

```python
from verba_extensions.utils.language_utils import detect_query_language

def process_query(query: str):
    language = detect_query_language(query)
    
    if language == "pt":
        # Processar em português
        pass
    elif language == "en":
        # Processar em inglês
        pass
```

### Exemplo 2: Processamento NLP com Cache

```python
from verba_extensions.utils.language_utils import get_nlp

def extract_entities(text: str, language: str = "pt"):
    nlp = get_nlp(language=language)
    if not nlp:
        return []
    
    doc = nlp(text)
    entities = [ent.text for ent in doc.ents if ent.label_ in ["ORG", "PERSON"]]
    return entities

# Primeira chamada: carrega modelo
entities1 = extract_entities("Apple é uma empresa", language="pt")

# Segunda chamada: usa cache (não recarrega)
entities2 = extract_entities("Microsoft também", language="pt")
```

### Exemplo 3: Filtro de Stopwords

```python
from verba_extensions.utils.language_utils import get_stopwords

def remove_stopwords(text: str, language: str = "pt"):
    stopwords = get_stopwords(language)
    words = text.lower().split()
    filtered = [w for w in words if w not in stopwords]
    return " ".join(filtered)

text = "O que é inovação da Apple?"
cleaned = remove_stopwords(text, language="pt")
# Resultado: "inovação Apple"
```

---

## Cache de Modelos

O módulo mantém cache global de modelos spaCy:

```python
_nlp_models = {
    "pt": <spaCy model pt_core_news_sm>,
    "en": <spaCy model en_core_web_sm>
}
```

**Vantagens:**
- Modelos carregados apenas uma vez por idioma
- Compartilhado entre todos os plugins
- Reduz uso de memória e tempo de carregamento

**Nota:** O cache persiste durante a execução do programa. Para recarregar modelos, reinicie o processo.

---

## Dependências

- `spacy` - Para modelos NLP (opcional, fallback gracioso se não disponível)
- `langdetect` - Para detecção de idioma (opcional, fallback para heurística)

**Instalação:**
```bash
# spaCy (requerido para NLP)
python -m spacy download pt_core_news_sm
python -m spacy download en_core_web_sm

# langdetect (opcional, melhora detecção)
pip install langdetect
```

---

## Extensibilidade

### Adicionar Novo Idioma

Para adicionar suporte a um novo idioma:

1. Adicionar stopwords em `STOPWORDS_XX`:
```python
STOPWORDS_ES = {"el", "la", "de", "que", ...}  # Espanhol
```

2. Adicionar modelo spaCy no `get_nlp()`:
```python
model_map = {
    "pt": "pt_core_news_sm",
    "en": "en_core_web_sm",
    "es": "es_core_news_sm",  # Novo
}
```

3. Atualizar `detect_query_language()` se necessário

---

## Troubleshooting

### Modelo spaCy não encontrado

**Erro:** `OSError: Can't find model 'pt_core_news_sm'`

**Solução:**
```bash
python -m spacy download pt_core_news_sm
```

### langdetect não disponível

**Comportamento:** Usa heurística simples baseada em palavras comuns

**Solução (opcional):**
```bash
pip install langdetect
```

### Cache não funcionando

**Causa:** Múltiplas instâncias do Python ou reinicialização

**Solução:** Cache é por processo. Se usar múltiplos processos, cada um terá seu próprio cache.

---

## Referências

- [spaCy Documentation](https://spacy.io/)
- [langdetect Documentation](https://github.com/Mimino666/langdetect)
- Consolidação realizada em: `docs/guides/RAG2_EXPERIMENTAL_PLUGINS.md`

