# Como `section_entity_ids` é Definido - O Problema da Priorização

## A Pergunta

Se o título da seção menciona "Apple em Cupertino", como o sistema sabe que a entidade principal é **Apple** e não **Cupertino**?

## Como Funciona Atualmente

### 1. Função `match_aliases`

```python
def match_aliases(text: str, gaz: Dict) -> List[str]:
    """Encontra entity_ids que correspondem a aliases no texto"""
    t_lower = text.lower()
    hits = []
    
    for eid, aliases in gaz.items():
        for alias in aliases:
            if alias.lower() in t_lower:
                hits.append(eid)
                break
    
    return sorted(set(hits))  # ⚠️ ORDENA ALFABETICAMENTE!
```

**Problema**: Retorna **TODAS** as entidades encontradas, ordenadas **alfabeticamente**.

### 2. Exemplo Prático

**Section Title**: "Apple em Cupertino"

**Gazetteer**:
```json
{
  "ent:org:apple": ["Apple", "iPhone", "iPad"],
  "ent:loc:cupertino": ["Cupertino", "Cupertino, CA"]
}
```

**Resultado do `match_aliases`**:
```python
h_hits = ["ent:loc:cupertino", "ent:org:apple"]  # ⚠️ Ordem alfabética!
```

**O que acontece**:
```python
# No ETL
sect_ids = h_hits  # ["ent:loc:cupertino", "ent:org:apple"]
primary = sect_ids[0]  # "ent:loc:cupertino" ❌ ERRADO!
```

### 3. Código Atual

```python
# verba_extensions/etl/etl_a2.py linha 116-120
h_hits = match_aliases(sect_title, gaz)  # ["ent:loc:cupertino", "ent:org:apple"]

if h_hits:
    sect_ids, scope_conf = h_hits, 0.9  # ✅ TODAS as entidades
    # sect_ids = ["ent:loc:cupertino", "ent:org:apple"]

# Primary entity escolhe o primeiro
primary = local_ids[0] if local_ids else (sect_ids[0] if sect_ids else None)
# primary = "ent:loc:cupertino" ❌ Pode não ser a entidade principal!
```

## Problemas Identificados

### ❌ Problema 1: Ordem Alfabética
- Se ambas entidades estão no texto, a ordem é **alfabética**, não por importância
- "Cupertino" vem antes de "Apple" alfabeticamente
- Entidade de **localização** pode ser escolhida em vez da entidade **principal**

### ❌ Problema 2: Sem Priorização por Tipo
- Não há lógica que prioriza:
  - ORG > LOC (organização é mais importante que localização)
  - PERSON > GPE (pessoa é mais importante que local)
  - Entidades principais vs secundárias

### ❌ Problema 3: Sem Contexto Semântico
- Não considera qual entidade é mais "central" ao assunto
- Não usa embeddings para entender hierarquia

## Como Funciona na Prática

### Cenário 1: Uma Entidade
```
Section Title: "A História da Apple"
→ match_aliases: ["ent:org:apple"]
→ section_entity_ids: ["ent:org:apple"] ✅
→ primary_entity_id: "ent:org:apple" ✅
```

### Cenário 2: Múltiplas Entidades (Problema)
```
Section Title: "Apple em Cupertino"
→ match_aliases: ["ent:loc:cupertino", "ent:org:apple"]  # Ordem alfabética
→ section_entity_ids: ["ent:loc:cupertino", "ent:org:apple"]  # Ambas
→ primary_entity_id: "ent:loc:cupertino" ❌ (deveria ser Apple)
```

### Cenário 3: Busca com Filtro
```python
# Busca por Apple usando section_entity_ids
Filter.by_property("section_entity_ids").contains_any(["ent:org:apple"])

# Resultado:
# ✅ Chunk com section_title "Apple em Cupertino" É ENCONTRADO
#    Porque section_entity_ids contém ["ent:loc:cupertino", "ent:org:apple"]
#    E "ent:org:apple" está na lista
```

**Importante**: A busca funciona porque `contains_any` verifica se **qualquer** entidade da lista corresponde, não apenas a primeira!

## Soluções Possíveis

### ✅ Solução 1: Priorizar por Tipo de Entidade

```python
def match_aliases_prioritized(text: str, gaz: Dict, entity_types: Dict) -> List[str]:
    """Encontra entity_ids com priorização por tipo"""
    t_lower = text.lower()
    hits_by_type = {
        "ORG": [],
        "PERSON": [],
        "GPE": [],
        "LOC": []
    }
    
    for eid, aliases in gaz.items():
        entity_type = entity_types.get(eid, "LOC")  # Default
        for alias in aliases:
            if alias.lower() in t_lower:
                hits_by_type[entity_type].append(eid)
                break
    
    # Prioriza: ORG > PERSON > GPE > LOC
    prioritized = (
        hits_by_type["ORG"] +
        hits_by_type["PERSON"] +
        hits_by_type["GPE"] +
        hits_by_type["LOC"]
    )
    
    return prioritized
```

### ✅ Solução 2: Priorizar por Primeira Menção

```python
def match_aliases_by_position(text: str, gaz: Dict) -> List[str]:
    """Encontra entity_ids e ordena por posição no texto"""
    t_lower = text.lower()
    hits_with_position = []
    
    for eid, aliases in gaz.items():
        for alias in aliases:
            pos = t_lower.find(alias.lower())
            if pos >= 0:
                hits_with_position.append((pos, eid))
                break
    
    # Ordena por posição (primeira menção primeiro)
    hits_with_position.sort(key=lambda x: x[0])
    return [eid for _, eid in hits_with_position]
```

### ✅ Solução 3: Usar Gazetteer com Prioridade

Estrutura do gazetteer com campo de prioridade:

```json
[
  {
    "entity_id": "ent:org:apple",
    "aliases": ["Apple", "iPhone", "iPad"],
    "priority": 10,  // Alta prioridade
    "type": "ORG"
  },
  {
    "entity_id": "ent:loc:cupertino",
    "aliases": ["Cupertino"],
    "priority": 5,   // Baixa prioridade
    "type": "LOC"
  }
]
```

```python
def match_aliases_by_priority(text: str, gaz: Dict) -> List[str]:
    """Encontra entity_ids e ordena por prioridade"""
    t_lower = text.lower()
    hits_with_priority = []
    
    for eid, aliases in gaz.items():
        priority = gaz[eid].get("priority", 0)
        for alias in aliases:
            if alias.lower() in t_lower:
                hits_with_priority.append((priority, eid))
                break
    
    # Ordena por prioridade (maior primeiro)
    hits_with_priority.sort(key=lambda x: x[0], reverse=True)
    return [eid for _, eid in hits_with_priority]
```

### ✅ Solução 4: Usar `entities_local_ids` como Prioridade

Se o chunk menciona Apple explicitamente, priorizar:

```python
# Se entities_local_ids tem Apple, usar ela como primary
if "ent:org:apple" in local_ids:
    primary = "ent:org:apple"
    # Reordenar section_entity_ids para colocar Apple primeiro
    sect_ids = ["ent:org:apple"] + [e for e in sect_ids if e != "ent:org:apple"]
```

## Comportamento Atual: Resumo

### O que funciona ✅
- **Busca com `contains_any`**: Funciona porque verifica se **qualquer** entidade da lista corresponde
- **Múltiplas entidades preservadas**: `section_entity_ids` contém **todas** as entidades
- **Contexto de seção**: Chunks herdam todas as entidades da seção

### O que não funciona bem ❌
- **Primary entity**: Pode escolher entidade errada (ex: Cupertino em vez de Apple)
- **Priorização**: Sem lógica inteligente para escolher entidade principal
- **Hierarquia**: Não diferencia entre entidades principais e secundárias

## Recomendação

### Para Busca
Use `contains_any` que já funciona bem:
```python
# ✅ Funciona mesmo com múltiplas entidades
Filter.by_property("section_entity_ids").contains_any(["ent:org:apple"])
```

### Para Primary Entity
Implementar uma das soluções acima, ou:
1. **Usar `entities_local_ids` primeiro**: Se o chunk menciona Apple, priorizar
2. **Priorizar por tipo**: ORG > PERSON > GPE > LOC
3. **Usar ordem do gazetteer**: Primeira entidade no gazetteer = maior prioridade

## Conclusão

**Resposta direta**: O sistema **não sabe** que Apple é mais importante que Cupertino. Ele apenas:
1. Encontra **todas** as entidades no texto
2. Ordena **alfabeticamente**
3. Escolhe a **primeira** da lista para `primary_entity_id`

**Porém**, a busca funciona porque usa `contains_any`, que verifica se **qualquer** entidade corresponde. Então mesmo que Cupertino venha primeiro, a busca por Apple ainda encontra os chunks.

**Melhoria necessária**: Implementar priorização inteligente para `primary_entity_id`, mas não é crítico para a busca funcionar.

