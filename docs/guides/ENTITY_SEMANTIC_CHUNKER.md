# Entity-Semantic Chunker - Guia Completo

## 📋 Visão Geral

O **Entity-Semantic Chunker** é um chunker híbrido que combina o melhor de três abordagens:

1. **Section-aware**: Delimita por seções (títulos/primeiro parágrafo) para evitar contaminação entre assuntos
2. **Entity guardrails**: Usa `entity_spans` do ETL-PRE para não cortar entidades no meio
3. **Semantic breakpoints**: Quebras semânticas intra-seção (reaproveita configs do SemanticChunker)

**Ideal para:** Artigos, URLs e documentos que falam de múltiplas empresas/entidades.

---

## 🎯 Por Que Usar?

### Problema que Resolve

Artigos que falam de múltiplas empresas podem ter chunks "contaminados":

```
[Seção: "Empresa 1 - Inovação"]
Parágrafo: "A empresa tem desenvolvido soluções inovadoras..."
→ Chunk 1: "A empresa tem desenvolvido soluções inovadoras..."

[Seção: "Empresa 2 - Tecnologia"]  
Parágrafo: "A empresa tem desenvolvido soluções inovadoras..." ← MESMO TEXTO!
→ Chunk 2: "A empresa tem desenvolvido soluções inovadoras..."
```

**Sem delimitação por seção:**
- Busca por "Empresa 2 e inovação" pode retornar Chunk 1 (sobre Empresa 1) ❌
- Chunks semânticamente similares mas sobre empresas diferentes são misturados

**Com Entity-Semantic Chunker:**
- ✅ Delimita por seções automaticamente
- ✅ Evita contaminação entre empresas
- ✅ Mantém coerência semântica dentro de cada seção
- ✅ Não corta entidades no meio

---

## ⚙️ Como Funciona

### Fluxo de Processamento

```
1. Documento Completo
   ↓
2. ETL Pré-Chunking (se enable_etl=True)
   - Extrai entity_spans do documento completo
   - Armazena em document.meta["entity_spans"]
   ↓
3. Detecção de Seções
   - Usa detect_sections() para identificar títulos e seções
   - Se não detectar seções, trata documento inteiro como uma seção
   ↓
4. Para cada seção:
   a. Filtra sentenças dentro da seção
   b. Gera embeddings das sentenças (se numpy/sklearn disponíveis)
   c. Calcula breakpoints semânticos (cosine similarity drop)
   d. Ajusta breakpoints para não cortar entidades (usando entity_spans)
   e. Aplica cap por tamanho máximo (fallback)
   ↓
5. Cria chunks respeitando:
   - Limites de seção
   - Guard-rails de entidade
   - Breakpoints semânticos
```

### Algoritmo de Ajuste de Boundary

Quando um breakpoint semântico propõe cortar uma entidade no meio:

```python
# 1. Detecta se entidade cruza boundary proposto
if entity_crosses_boundary(entity_spans, boundary_char):
    # 2. Tenta avançar 1 sentença
    if not entity_crosses_boundary(entity_spans, next_sentence_end):
        boundary = next_sentence_end
    # 3. Se não funcionar, tenta recuar 1 sentença
    elif not entity_crosses_boundary(entity_spans, prev_sentence_end):
        boundary = prev_sentence_end
    # 4. Se ainda cruzar, mantém boundary original (melhor que nada)
```

---

## 📊 Configuração

### Configs Disponíveis

O Entity-Semantic Chunker reaproveita as configs do SemanticChunker:

| Config | Tipo | Padrão | Descrição |
|--------|------|--------|-----------|
| **Breakpoint Percentile Threshold** | number | 80 | Percentil do drop de similaridade para split (menor → mais splits) |
| **Max Sentences Per Chunk** | number | 20 | Máximo de sentenças por chunk (fallback/capping) |
| **Overlap** | number | 0 | Overlap em sentenças entre chunks (opcional) |

### Exemplo de Configuração

```python
config = {
    "Breakpoint Percentile Threshold": {"value": 80},  # Mais conservador
    "Max Sentences Per Chunk": {"value": 20},          # Cap de tamanho
    "Overlap": {"value": 2}                            # 2 sentenças de overlap
}
```

**Recomendações:**
- **Breakpoint Percentile Threshold**: 75-85 (menor = mais chunks menores)
- **Max Sentences Per Chunk**: 15-25 (depende do tamanho médio das sentenças)
- **Overlap**: 0-3 sentenças (mais overlap = mais contexto, mas mais duplicação)

---

## 🔧 Requisitos

### Bibliotecas Opcionais

- **numpy**: Para cálculos de percentil (fallback se não disponível)
- **sklearn**: Para cosine similarity (fallback se não disponível)

**Fallback:**
- Se numpy/sklearn não disponíveis, usa apenas cap por tamanho máximo de sentenças
- Chunking ainda funciona, mas sem breakpoints semânticos

### ETL Pré-Chunking (Recomendado)

Para aproveitar entity guardrails, habilite ETL pré-chunking:

```python
# Em goldenverba/verba_manager.py
enable_etl_pre_chunking = True  # Já habilitado por padrão
```

**Resultado:**
- `entity_spans` são extraídos antes do chunking
- Chunker usa esses spans para evitar cortar entidades

---

## 📈 Performance

### Benchmarks Esperados

| Métrica | Valor |
|---------|-------|
| **Tempo de chunking** (documento médio) | 2-5s |
| **Overhead vs Section-Aware** | +0.5-1s (cálculo de embeddings) |
| **Overhead vs Semantic** | +0.3-0.5s (detecção de seções + entity guardrails) |

**Nota:** Overhead é aceitável considerando os benefícios de evitar contaminação.

---

## 🎯 Casos de Uso

### ✅ Ideal Para

1. **Artigos de análise de mercado**
   - Falam de múltiplas empresas
   - Precisam de delimitação por empresa
   - Exemplo: "Análise de Mercado Tech 2024"

2. **URLs/Web scraping**
   - Páginas que mencionam várias empresas
   - Estrutura de seções bem definida
   - Exemplo: Página de comparação de produtos

3. **Documentos com estrutura hierárquica**
   - Títulos de seção claros
   - Múltiplos assuntos/entidades
   - Exemplo: Relatórios anuais

### ❌ Não Ideal Para

1. **Documentos sem estrutura de seções**
   - Texto corrido sem títulos
   - Neste caso, use Section-Aware ou Semantic puro

2. **Documentos muito pequenos**
   - < 500 palavras
   - Overhead pode não valer a pena

3. **Documentos técnicos específicos**
   - Código, JSON, Markdown estruturado
   - Use chunkers específicos (CodeChunker, JSONChunker, etc.)

---

## 🔍 Verificação

### Como Verificar se Está Funcionando

1. **Verificar se plugin está carregado:**
```python
from verba_extensions.plugin_manager import get_plugin_manager
pm = get_plugin_manager()
if 'entity_semantic_chunker' in pm.plugins:
    print('✅ Entity-Semantic Chunker carregado')
```

2. **Verificar se está disponível:**
```python
from goldenverba.components import managers
if 'Entity-Semantic' in managers.chunkers:
    print('✅ Entity-Semantic disponível')
```

3. **Verificar se é padrão:**
```python
from goldenverba.verba_manager import VerbaManager
vm = VerbaManager()
config = vm.create_config()
if config['Chunker']['selected'] == 'Entity-Semantic':
    print('✅ Entity-Semantic é padrão')
```

4. **Verificar logs durante chunking:**
```
[ETL-PRE] ✅ Entidades armazenadas no documento: X spans
[ENTITY-AWARE] ✅ Usando X entidades pré-extraídas
[Entity-Semantic] Processando seção: "Empresa X - Tecnologia"
[Entity-Semantic] Breakpoints semânticos calculados: Y breakpoints
```

---

## 🆚 Comparação com Outros Chunkers

| Chunker | Seções | Entidades | Semântica | Contaminação | Qualidade |
|---------|--------|-----------|-----------|---------------|-----------|
| **Entity-Semantic** ⭐ | ✅ | ✅ | ✅ | ✅ Baixa | ⭐⭐⭐⭐⭐ |
| **Section-Aware** | ✅ | ✅ | ❌ | ✅ Baixa | ⭐⭐⭐⭐⭐ |
| **Semantic** | ❌ | ❌ | ✅ | ⚠️ Média | ⭐⭐⭐⭐ |
| **Token/Sentence** | ❌ | ❌ | ❌ | ⚠️ Alta | ⭐⭐⭐ |

---

## 🚀 Próximos Passos

1. **Testar com seus documentos**
   - Importe um artigo/URL com múltiplas empresas
   - Verifique se chunks estão delimitados por seção
   - Verifique se não há contaminação entre empresas

2. **Ajustar configurações**
   - Ajuste Breakpoint Percentile Threshold se chunks muito pequenos/grandes
   - Ajuste Max Sentences Per Chunk se necessário
   - Considere overlap se precisar de mais contexto

3. **Verificar busca**
   - Teste busca por "Empresa X e tema Y"
   - Verifique se não retorna chunks de outras empresas
   - Use EntityAwareRetriever com `section_entity_ids` para melhor resultado

---

## 📚 Documentação Relacionada

- `docs/guides/SOLUCAO_CONTAMINACAO_ENTRE_EMPRESAS.md` - Solução completa de contaminação
- `docs/guides/COMO_ETL_FUNCIONA_POR_CHUNKER.md` - Como ETL funciona com chunkers
- `verba_extensions/patches/README_PATCHES.md` - Documentação de patches

---

**Última atualização:** Janeiro 2025

