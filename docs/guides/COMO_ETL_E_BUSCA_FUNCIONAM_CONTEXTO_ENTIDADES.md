# Como o ETL e a Busca Funcionam com Contexto de Entidades

## Cenário do Usuário

Imagine um artigo que:
- **Primeiro parágrafo**: Menciona "Apple" explicitamente
- **Parágrafos seguintes**: Fala de "iPhone", "Cupertino", "inovação", etc., mas **não menciona "Apple"** novamente
- **Mudança de assunto**: Depois começa a falar de "Microsoft"

**Pergunta**: O sistema entende que todos os chunks ainda falam de Apple até mudar para Microsoft?

## Como Funciona

### 1. Extração de Entidades pelo ETL

O ETL A2 extrai entidades em **3 níveis**:

#### a) **Entidades Locais** (`entities_local_ids`)
- Extraídas diretamente do **texto do chunk** via spaCy NER
- Exemplo: Se o chunk menciona "iPhone", "Apple", "Cupertino"
- **Limitação**: Se o chunk não menciona "Apple" explicitamente, não terá Apple aqui

#### b) **Entidades da Seção** (`section_entity_ids`)
- Derivadas do **contexto da seção** usando hierarquia:
  1. **`section_title`** (confiança 0.9) - Se o título da seção menciona Apple
  2. **`section_first_para`** (confiança 0.7) - Se o primeiro parágrafo da seção menciona Apple
  3. **`parent_entities`** (confiança 0.6) - Entidades herdadas do documento/artigo pai

#### c) **Entidade Primária** (`primary_entity_id`)
- A entidade mais importante do chunk
- Prioridade: `entities_local_ids[0]` > `section_entity_ids[0]`

### 2. Exemplo Prático

```
Artigo: "A História da Apple"

[Seção: "Inovação da Apple"]
Parágrafo 1: "Apple foi fundada em 1976..."
  → entities_local_ids: ["Q312"] (Apple)
  → section_entity_ids: ["Q312"] (do section_title)
  → primary_entity_id: "Q312"

Parágrafo 2: "O iPhone revolucionou o mercado..."
  → entities_local_ids: [] (nenhuma entidade detectada no texto)
  → section_entity_ids: ["Q312"] (herdado do section_title)
  → primary_entity_id: "Q312"

Parágrafo 3: "Em Cupertino, a empresa continua inovando..."
  → entities_local_ids: [] (Cupertino pode não estar no gazetteer como GPE)
  → section_entity_ids: ["Q312"] (herdado do section_title)
  → primary_entity_id: "Q312"

[Nova Seção: "Microsoft e a Competição"]
Parágrafo 4: "Microsoft lançou o Windows..."
  → entities_local_ids: ["Q2283"] (Microsoft)
  → section_entity_ids: ["Q2283"] (do novo section_title)
  → primary_entity_id: "Q2283"
```

### 3. Como a Busca Funciona

O **Entity-Aware Retriever** pode filtrar por diferentes propriedades:

#### Modo Padrão: `entities_local_ids`
```python
# Filtro aplicado
Filter.by_property("entities_local_ids").contains_any(["Q312"])
```

**Resultado**: 
- ✅ Chunk 1: **PEGA** (tem Apple em entities_local_ids)
- ❌ Chunk 2: **NÃO PEGA** (não tem Apple em entities_local_ids)
- ❌ Chunk 3: **NÃO PEGA** (não tem Apple em entities_local_ids)

#### Modo SectionScope: `section_entity_ids`
```python
# Filtro aplicado
Filter.by_property("section_entity_ids").contains_any(["Q312"])
```

**Resultado**:
- ✅ Chunk 1: **PEGA** (tem Apple em section_entity_ids)
- ✅ Chunk 2: **PEGA** (tem Apple em section_entity_ids via section_title)
- ✅ Chunk 3: **PEGA** (tem Apple em section_entity_ids via section_title)
- ❌ Chunk 4: **NÃO PEGA** (tem Microsoft, não Apple)

#### Modo Combinado (OR)
```python
# Filtro aplicado (busca em AMBAS as propriedades)
Filter.any_of([
    Filter.by_property("entities_local_ids").contains_any(["Q312"]),
    Filter.by_property("section_entity_ids").contains_any(["Q312"])
])
```

**Resultado**:
- ✅ Chunk 1: **PEGA** (tem em entities_local_ids)
- ✅ Chunk 2: **PEGA** (tem em section_entity_ids)
- ✅ Chunk 3: **PEGA** (tem em section_entity_ids)
- ❌ Chunk 4: **NÃO PEGA** (não tem Apple em nenhuma)

## Resposta Direta

### ❌ **Comportamento Atual (entities_local_ids apenas)**

**NÃO**, o sistema **não entende automaticamente** que todos os chunks falam de Apple se você usar apenas `entities_local_ids`.

**Por quê?**
- Chunks que mencionam apenas "iPhone" ou "Cupertino" não terão "Apple" em `entities_local_ids`
- A menos que o gazetteer tenha aliases como "iPhone → Apple" (o que é possível, mas não garantido)

### ✅ **Solução: Usar SectionScope**

**SIM**, o sistema **entende** se você usar `section_entity_ids` ou modo combinado.

**Como funciona:**
1. Se o **section_title** menciona "Apple" → todos os chunks daquela seção terão Apple em `section_entity_ids`
2. Se o **section_first_para** menciona "Apple" → todos os chunks daquela seção terão Apple em `section_entity_ids`
3. Quando muda para seção sobre "Microsoft" → os novos chunks terão Microsoft, não Apple

## Configuração Recomendada

### 1. Query Builder Inteligente

O `QueryBuilder` pode detectar automaticamente qual propriedade usar:

```python
# Se a query menciona entidade conhecida
query = "Apple e inovação"

# QueryBuilder detecta:
{
    "entity_property": "section_entity_ids",  # Usa section para contexto amplo
    "entities": ["Q312"],
    "semantic_query": "inovação"
}
```

### 2. Filtro Combinado

Para capturar contexto completo, use filtro combinado:

```python
# Busca chunks que têm Apple em ENTREGA propriedade
entity_filter = Filter.any_of([
    Filter.by_property("entities_local_ids").contains_any(["Q312"]),
    Filter.by_property("section_entity_ids").contains_any(["Q312"]),
    Filter.by_property("primary_entity_id").equal("Q312")
])
```

## Limitações e Melhorias

### Limitações Atuais

1. **Gazetteer necessário**: iPhone precisa estar mapeado como alias de Apple no gazetteer
2. **SectionScope depende de estrutura**: Funciona melhor com seções bem definidas
3. **Sem propagação automática entre chunks**: Cada chunk é processado independentemente

### Melhorias Possíveis

1. **Aliases no Gazetteer**: Adicionar "iPhone", "iPad", "Mac" como aliases de Apple
2. **Propagação de contexto**: Usar `parent_entities` para propagar entidades do artigo para chunks
3. **Inferência semântica**: Usar embeddings para detectar chunks relacionados mesmo sem menção explícita

## Exemplo Prático de Configuração

Para o seu caso de uso, configure:

```python
# No QueryBuilder ou EntityAwareRetriever
config = {
    "entity_property": "section_entity_ids",  # Usa contexto de seção
    "enable_entity_filter": True,
    "enable_semantic_search": True  # Combina com busca semântica
}
```

Isso garante que:
- ✅ Chunks que mencionam Apple explicitamente são encontrados
- ✅ Chunks do mesmo contexto (mesma seção) são encontrados
- ✅ Quando muda para Microsoft, os chunks de Microsoft são encontrados
- ✅ Busca semântica complementa quando não há menção explícita

## Conclusão

**Resposta curta**: O sistema **pode entender** que todos os chunks falam de Apple, mas **depende da configuração**:

- ❌ **Padrão (`entities_local_ids`)**: Não entende automaticamente
- ✅ **SectionScope (`section_entity_ids`)**: Entende via contexto de seção
- ✅ **Combinado**: Melhor cobertura, pega ambos os casos

**Recomendação**: Configure o QueryBuilder para usar `section_entity_ids` quando a query menciona uma entidade principal, garantindo que o contexto seja preservado.


