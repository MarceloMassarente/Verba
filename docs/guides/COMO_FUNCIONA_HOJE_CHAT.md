# 🔍 Como Funciona HOJE o Chat do Verba: A Verdade

## ⚡ **Resposta Direta**

**NENHUMA transformação!** A query vai **EXATAMENTE COMO O USUÁRIO DIGITOU** para o retriever.

```
Usuário digita: "apple e inovação"
                        ↓
            Frontend envia AS-IS
                        ↓
            Backend recebe: "apple e inovação"
                        ↓
            Retriever processa COM ESSA QUERY TEXTUAL
                        ↓
            ✅ SEM parser
            ✅ SEM query rewriting
            ✅ SEM LLM para transformar
```

---

## 🔗 **Fluxo Real: Passo a Passo**

### **1️⃣ Frontend (ChatInterface.tsx)**

```typescript
// frontend/app/components/Chat/ChatInterface.tsx:233

const sendUserMessage = async () => {
  const sendInput = userInput;  // ← Query EXATAMENTE COMO DIGITADA
  
  const data = await sendUserQuery(
    sendInput,           // ← "apple e inovação" (sem transformação!)
    RAGConfig,
    filterLabels,
    documentFilter,
    credentials
  );
};
```

**O que acontece:**
- ✅ Usuário digita: `"apple e inovação"`
- ✅ Frontend pega: `userInput`
- ✅ Envia direto para o backend: `sendUserQuery(sendInput, ...)`
- ❌ Sem processamento
- ❌ Sem parser
- ❌ Sem LLM

---

### **2️⃣ API Endpoint (/api/query)**

```python
# goldenverba/server/api.py:504

@app.post("/api/query")
async def query(payload: QueryPayload):
    msg.good(f"Received query: {payload.query}")  # ← Log mostra EXATAMENTE o que veio
    
    try:
        client = await client_manager.connect(payload.credentials)
        documents_uuid = [document.uuid for document in payload.documentFilter]
        
        # AQUI: Retrieval com a query original
        documents, context = await manager.retrieve_chunks(
            client, 
            payload.query,        # ← "apple e inovação" AS-IS
            payload.RAG, 
            payload.labels, 
            documents_uuid
        )
        
        return JSONResponse(
            content={"error": "", "documents": documents, "context": context}
        )
```

**O que acontece:**
- ✅ Query chega: `"apple e inovação"`
- ✅ Passa DIRETO para `manager.retrieve_chunks()`
- ❌ Sem parser
- ❌ Sem transformação

---

### **3️⃣ Manager (retrieve_chunks)**

```python
# goldenverba/verba_manager.py:705

async def retrieve_chunks(
    self,
    client,
    query: str,           # ← "apple e inovação"
    rag_config: dict,
    labels: list[str] = [],
    document_uuids: list[str] = [],
):
    retriever = rag_config["Retriever"].selected
    embedder = rag_config["Embedder"].selected
    
    # 1. Cria embedding da query TEXTUAL
    vector = await self.embedder_manager.vectorize_query(
        embedder, 
        query,     # ← MESMA QUERY, convertida para vetor
        rag_config
    )
    
    # 2. Passa para retriever COM A QUERY ORIGINAL
    documents, context = await self.retriever_manager.retrieve(
        client,
        retriever,
        query,     # ← "apple e inovação" SEM MODIFICAÇÃO
        vector,    # ← Vetor da query
        rag_config,
        self.weaviate_manager,
        labels,
        document_uuids,
    )
    
    return (documents, context)
```

**O que acontece:**
1. ✅ Query: `"apple e inovação"` entra
2. ✅ **Vetor**: `[0.234, 0.891, ...]` é criado do texto original
3. ✅ Query ORIGINAL passa para retriever
4. ❌ Sem parser
5. ❌ Sem transformação

---

### **4️⃣ Retriever (WindowRetriever - Padrão)**

```python
# goldenverba/components/retriever/WindowRetriever.py:46

async def retrieve(
    self,
    client,
    query,                 # ← "apple e inovação"
    vector,                # ← Vetor
    config,
    weaviate_manager,
    embedder,
    labels,
    document_uuids,
):
    search_mode = config["Search Mode"].value
    limit = int(config["Limit/Sensitivity"].value)
    
    # BUSCA HIBRIDA: Usa a query TEXTUAL + vetor
    chunks = await weaviate_manager.hybrid_chunks(
        client,
        embedder,
        query,               # ← "apple e inovação" AQUI TAMBÉM
        vector,              # ← Vetor criado
        limit_mode,
        limit,
        labels,
        document_uuids,
    )
    # ... resto do processamento
```

**O que acontece:**
- ✅ Query chega: `"apple e inovação"`
- ✅ Usa query + vetor para busca híbrida
- ✅ Sem parsing
- ✅ Sem transformação

---

### **5️⃣ Weaviate (Busca Híbrida)**

```python
# Pseudocódigo do que acontece internamente

chunks = weaviate_manager.hybrid_chunks(
    query="apple e inovação",   # ← Texto original
    vector=[0.234, 0.891, ...], # ← Vetor
    alpha=0.75                   # ← Mix de keyword (0.75) + vector (0.25)
)

# Busca no Weaviate:
# 1. BM25 (keyword): busca "apple" E "inovação" como TEXT (sem filtro)
# 2. Vector: busca semelhança com vetor
# 3. Combina: alpha * BM25_score + (1-alpha) * vector_score
```

---

## 📊 **Comparação: Hoje vs Com Query Parser**

| Etapa | HOJE (Sem Parser) | COM Parser (Novo) |
|-------|-------------------|-------------------|
| **Input** | `"apple e inovação"` | `"apple e inovação"` |
| **Parsing** | ❌ NENHUM | ✅ Separa em entidade + conceito |
| **EntityAwareRetriever** | Não usa | Filtra por entidade + semântica |
| **Resultado** | Chunks sobre Apple (qualquer contexto) | Chunks sobre Apple + inovação |
| **LLM recebe** | Contexto possivelmente incompleto | Contexto alinhado com query |

---

## 🎯 **O Que FALTA Hoje**

### **Problema 1: Query "apple e inovação"**

```
HOJE (SEM Parser):
- Busca por: "apple" E "inovação" (como TEXTO)
- Weaviate faz: BM25("apple e inovação") + Vector(["apple e inovação"])
- RESULTADO: Chunks que mencionam ambas palavras, mas sem entendimento de contexto
  
  Exemplo de chunk retornado:
  ❌ "A empresa não inova em relação à Apple" ← Tem ambas palavras, mas contexto errado!
```

---

### **Problema 2: EntityAwareRetriever Não Usa Query Parser**

```python
# Hoje: entity_aware_retriever.py

async def retrieve(self, query, ...):
    # Extrai entidades DIRETO da query
    entity_context = await global_hooks.execute_hook_async(
        'entity_aware.get_filters',
        query  # ← "apple e inovação"
    )
    
    # entity_aware_query_orchestrator.py
    entity_ids = extract_entities_from_query(query)
    # Resultado: ["Apple"]  ← "inovação" é IGNORADA!
```

---

## ✅ **O Que o Query Parser Vai Melhorar**

```python
# COM Query Parser (que criamos):

parsed = parse_query("apple e inovação")
# Resultado:
# {
#   "entities": [{"text": "Apple", "entity_id": "Q123"}],
#   "semantic_concepts": ["inovação"],
#   "intent": "COMBINATION"
# }

# EntityAwareRetriever USA:
entity_ids = ["Q123"]
semantic_query = "inovação"

# Busca:
chunks = weaviate_manager.hybrid_search(
    vector=embedding("inovação"),
    filters=WHERE(entities = "Q123"),  # ← Só Apple
    alpha=0.6
)
# Resultado: ✅ Chunks SOBRE Apple QUE MENCIONAM inovação
```

---

## 🎬 **Fluxo Resumido**

### **HOJE (Sem Query Parser)**

```
"apple e inovação"
        ↓
    SEM PARSING
        ↓
    Weaviate: BM25("apple e inovação") + Vector
        ↓
    ❌ Chunks com ambas palavras (contexto ruim)
```

### **COM Query Parser**

```
"apple e inovação"
        ↓
    parse_query()
    ├─ entidade: "Apple"
    └─ conceito: "inovação"
        ↓
    EntityAwareRetriever:
    ├─ WHERE: entities = "Apple"
    └─ Vector: "inovação"
        ↓
    ✅ Chunks sobre Apple que mencionam inovação
```

---

## 📋 **Tipos de Queries e Como Verba as Trata HOJE**

| Query | Parser Usado? | Resultado |
|-------|---------------|-----------|
| `"apple"` | ❌ NENHUM | Busca por "apple" (BM25 + Vector) |
| `"inovação"` | ❌ NENHUM | Busca por "inovação" (BM25 + Vector) |
| `"apple e inovação"` | ❌ NENHUM | Busca por ambas, sem separar entidade de conceito |
| `"apple vs microsoft"` | ❌ NENHUM | Busca por ambas (não entende "vs" como comparação) |
| `"qual é a estratégia da Apple?"` | ❌ NENHUM | Busca por texto completo (BM25 + Vector) |

---

## 💡 **Conclusão**

**HOJE NO VERBA:**

1. ✅ **Query chega textual** do usuário
2. ✅ **Sem parsing de entidades**
3. ✅ **Sem transformação LLM**
4. ✅ **Sem query rewriting**
5. ✅ **Vai direto para Weaviate** com busca híbrida (BM25 + Vector)
6. ✅ **LLM só entra DEPOIS** da retrieval para gerar resposta

**O Query Parser que criamos é para MELHORAR a qualidade dos chunks que o LLM vai receber, especialmente para queries complexas como "apple e inovação".**
