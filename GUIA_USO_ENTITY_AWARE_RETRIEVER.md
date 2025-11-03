# 🔍 Guia: Como Usar Entity-Aware Retriever no Chat

## ✅ Sim, temos um Retriever Customizado!

O **EntityAwareRetriever** já está implementado como plugin. Ele aplica filtros baseados em entidades para evitar contaminação entre empresas/tópicos.

---

## 🎯 O que o EntityAwareRetriever Faz

### **Filtros Automáticos por Entidade:**

Quando você faz uma query no chat, o retriever:

1. **Extrai entidades da query** (via SpaCy + Gazetteer)
   - Ex: Query "inovação da Apple" → detecta "Apple" → entity_id "Q312"

2. **Aplica filtro where no Weaviate:**
   ```python
   Filter.by_property("entities_local_ids").contains_any(["Q312"])
   # OU
   Filter.by_property("section_entity_ids").contains_any(["Q312"])
   ```

3. **Retorna apenas chunks relacionados à entidade**
   - Evita contaminação com Microsoft, Google, etc.

---

## 🚀 Como Usar no Chat

### **Passo 1: Selecionar o Retriever**

Na UI do Verba → **Settings** → Seção **Retriever**:

1. No dropdown, escolha: **"EntityAware"** (ao invés de "Window")
2. Configure:
   - **Enable Entity Filter**: ✅ Ativado (recomendado)
   - **Limit/Sensitivity**: 32 (ajuste conforme necessário)
   - **Chunk Window**: 1 (chunks adjacentes)
   - **Alpha**: 0.6 (balance entre keyword/vector search)

3. Clique em **"Save Config"**

### **Passo 2: Usar no Chat**

Agora, quando você fizer queries no chat:

```
Query: "inovação da Apple"
→ EntityAwareRetriever detecta "Apple" (Q312)
→ Aplica filtro: entities_local_ids contains "Q312"
→ Retorna apenas chunks sobre Apple
```

```
Query: "parcerias da Microsoft"
→ Detecta "Microsoft" (Q2283)
→ Aplica filtro: entities_local_ids contains "Q2283"
→ Retorna apenas chunks sobre Microsoft
```

---

## ⚙️ Onde a Cláusula WHERE é Construída

A cláusula `where` é construída no método `_build_entity_filter()` do `EntityAwareRetriever`:

```python
# verba_extensions/plugins/entity_aware_retriever.py

def _build_entity_filter(self, entity_context: Dict) -> Optional[Any]:
    """Constrói filtro Weaviate baseado em entity IDs"""
    entity_ids = entity_context['entity_ids']
    
    # Para Weaviate v4:
    filters = [
        Filter.by_property("entities_local_ids").contains_any(entity_ids),
        Filter.by_property("section_entity_ids").contains_any(entity_ids)
    ]
    
    # Combina com AND
    return filters[0] & filters[1]
```

**Este filtro é aplicado ANTES da busca híbrida**, garantindo que apenas chunks relevantes sejam considerados.

---

## 🔧 Orquestrador de Query (Novo)

Para que funcione automaticamente, foi criado um **orquestrador** que:

1. **Extrai entidades da query** usando SpaCy
2. **Normaliza via Gazetteer** (aliases → entity_ids)
3. **Fornece ao retriever** via hook `entity_aware.get_filters`

**Status**: Plugin criado (`entity_aware_query_orchestrator.py`)

---

## 📋 Como Funciona Internamente

### **Fluxo Completo:**

```
1. Usuário digita: "inovação da Apple"
   ↓
2. Chat envia query para backend
   ↓
3. VerbaManager.retrieve_chunks() é chamado
   ↓
4. RetrieverManager usa EntityAwareRetriever
   ↓
5. EntityAwareRetriever chama hook 'entity_aware.get_filters'
   ↓
6. Orquestrador extrai entidades:
   - SpaCy detecta "Apple" como ORG
   - Gazetteer mapeia "Apple" → "Q312"
   ↓
7. Retorna entity_context = {'entity_ids': ['Q312']}
   ↓
8. EntityAwareRetriever constrói filtro where:
   Filter.by_property("entities_local_ids").contains_any(["Q312"])
   ↓
9. Busca híbrida com filtro aplicado
   ↓
10. Retorna apenas chunks sobre Apple ✅
```

---

## 🎯 Exemplos de Uso

### **Exemplo 1: Query com Nome de Empresa**

```
Query: "novidades da Apple"
→ Entity IDs: ["Q312"]
→ Filtro: entities_local_ids contains "Q312"
→ Resultado: Só chunks que mencionam Apple
```

### **Exemplo 2: Query com Nome de Pessoa**

```
Query: "opinião de Tim Cook"
→ Entity IDs: ["Q312"] (Apple via contexto)
→ Filtro aplicado
→ Resultado: Chunks sobre Apple/Tim Cook
```

### **Exemplo 3: Query Sem Entidade Clara**

```
Query: "inovação tecnológica"
→ Entity IDs: [] (nenhuma entidade detectada)
→ Sem filtro entity-aware
→ Resultado: Busca normal (todos os chunks)
```

---

## ⚠️ Requisitos

Para o EntityAwareRetriever funcionar completamente:

1. ✅ **Retriever registrado** (já está)
2. ✅ **ETL executado** (entidades nos chunks via ETL A2)
3. ✅ **Orquestrador registrado** (plugin criado)
4. ✅ **SpaCy instalado** (`python -m spacy download pt_core_news_sm`)
5. ✅ **Gazetteer configurado** (`verba_extensions/resources/gazetteer.json`)

---

## 🔍 Verificando se Está Funcionando

### **Nos Logs do Railway:**

Após fazer uma query, você deve ver:
```
✅ Entidades detectadas na query 'inovação da Apple': 1 entidades
✅ ETL A2: X passages atualizados
```

### **Na UI:**

1. Escolha **EntityAware** no dropdown de Retriever
2. Faça uma query com nome de empresa
3. Verifique se retorna apenas chunks relevantes (sem contaminação)

---

## 💡 Dicas

### **Ativar/Desativar Filtro:**

Na configuração do retriever:
- **Enable Entity Filter**: ✅ = Filtro ativo
- **Enable Entity Filter**: ❌ = Busca normal (sem filtro entity)

### **Ajustar Sensibilidade:**

- **Limit/Sensitivity**: Aumente para mais chunks, diminua para menos
- **Chunk Window**: Adicione chunks adjacentes ao contexto

---

## 🚀 Próximos Passos

1. **Aguarde redeploy** (~2-5 min)
2. **Teste no chat** com queries que mencionam empresas
3. **Compare resultados**:
   - Window Retriever (sem filtro) vs
   - EntityAware Retriever (com filtro)

**Agora você pode usar busca por entidades diretamente no chat!** 🎉

