# 🎬 Fluxo Completo do Chat: Query → Retrieval → LLM → Resposta

## 📊 **Visão Geral**

```
┌────────────────────────────────────────────────────────────────────┐
│ USUÁRIO digita no chat: "apple e inovação"                        │
└────────────────────┬───────────────────────────────────────────────┘
                     │
        ┌────────────┴────────────┐
        ↓                         ↓
  ┌──────────────┐      ┌──────────────────────┐
  │ RETRIEVAL    │      │ LLM GENERATION       │
  │ (Nosso foco) │      │ (AnthropicGenerator) │
  └──────────────┘      └──────────────────────┘
        │                         ↑
        └─────────────────────────┘
        Chunks + Contexto

                     ↓

┌────────────────────────────────────────────────────────────────────┐
│ RESPOSTA GERADA: "Apple é conhecida pela inovação em..."         │
└────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 **Fluxo Detalhado: 4 Etapas**

### **ETAPA 1️⃣: Chat Interface (Frontend)**

```
┌─────────────────────────────────────────────────────────────┐
│ Frontend (React)                                            │
│                                                             │
│ [Usuário digita]: "apple e inovação"                       │
│ [Clica em Send]                                             │
│                                                             │
│ → Envia via WebSocket para backend                         │
│   POST /ws/generate_stream                                  │
│   {                                                         │
│     "query": "apple e inovação",                           │
│     "rag_config": {...},                                    │
│     "context": "",                                          │
│     "conversation": []                                      │
│   }                                                         │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ↓
```

**Código:** `frontend/app/components/Chat/ChatInterface.tsx`
```typescript
const sendUserMessage = async () => {
  const sendInput = userInput;  // "apple e inovação"
  
  const data = await sendUserQuery(
    sendInput,           // ← Query
    RAGConfig,           // ← Config do retriever
    filterLabels,
    documentFilter,
    credentials
  );
};
```

---

### **ETAPA 2️⃣: Retrieval (Busca de Documentos) ⭐ AQUI É O QUERY PARSING**

```
┌─────────────────────────────────────────────────────────────┐
│ Backend - Retrieval Stage                                   │
│                                                             │
│ /api/query endpoint (goldenverba/server/api.py:504)       │
│                                                             │
│ ✅ FLUXO DE RETRIEVAL                                      │
│                                                             │
│ 1. Query chega: "apple e inovação"                        │
│    ↓                                                        │
│ 2. EntityAwareRetriever.retrieve()                         │
│    ├─ Chama hook: entity_aware.get_filters                │
│    │                                                        │
│    └─→ QueryOrchestrator executa:                         │
│        • extract_entities_from_query()  ← spaCy NER       │
│          Resultado: ["Apple"] (ORG)                       │
│                                                             │
│        • parse_query() ← [NOVO - Query Parser]            │
│          Separa: entidades vs semântica                   │
│          Resultado: {                                     │
│            entities: ["Apple"],                           │
│            semantic_concepts: ["inovação"]                │
│          }                                                 │
│    ↓                                                        │
│ 3. Weaviate Busca Híbrida                                 │
│    ├─ WHERE filter: entities = "Apple" (rápido)          │
│    └─ Vector search: "inovação" (relevância)             │
│    ↓                                                        │
│ 4. Retorna chunks relevantes                              │
│    {                                                       │
│      "documents": [                                        │
│        {                                                   │
│          "uuid": "doc-123",                               │
│          "title": "Apple Innovation Strategy",            │
│          "chunks": [                                       │
│            "Apple investe em inovação de IA...",          │
│            "A estratégia de inovação foca em..."          │
│          ]                                                 │
│        }                                                   │
│      ],                                                    │
│      "context": "Apple Innovation Strategy... [chunks]"   │
│    }                                                       │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ↓ (Chunks + Context)
```

**Código:** `goldenverba/server/api.py`
```python
@app.post("/api/query")
async def query(payload: QueryPayload):
    documents, context = await manager.retrieve_chunks(
        client, 
        payload.query,           # ← "apple e inovação"
        payload.RAG,             # ← EntityAware Retriever config
        payload.labels, 
        documents_uuid
    )
    return {
        "documents": documents,  # ← Chunks encontrados
        "context": context       # ← Texto concatenado
    }
```

---

### **ETAPA 3️⃣: LLM Generation (Geração de Resposta) ⭐ AQUI USA O AGENTE**

```
┌─────────────────────────────────────────────────────────────┐
│ Backend - Generation Stage                                  │
│                                                             │
│ manager.generate_stream_answer()                            │
│                                                             │
│ ✅ FLUXO DE GERAÇÃO                                        │
│                                                             │
│ 1. Recebe chunks do retrieval:                             │
│    "Apple Innovation Strategy... [chunks]"                 │
│    ↓                                                        │
│ 2. Constrói prompt:                                        │
│    """                                                      │
│    You are a helpful assistant.                            │
│    Use the following context to answer.                    │
│                                                             │
│    Context:                                                │
│    Apple Innovation Strategy...                            │
│    [chunks sobre apple + inovação]                         │
│                                                             │
│    User Question: apple e inovação                         │
│    """                                                      │
│    ↓                                                        │
│ 3. Envia para LLM (AnthropicGenerator) 🤖                 │
│    ├─ Model: claude-3-sonnet (ou configurado)             │
│    ├─ Temperature: config                                  │
│    ├─ Max tokens: config                                  │
│    └─ Streaming: SIM (em tempo real)                      │
│    ↓                                                        │
│ 4. LLM processa:                                           │
│    Lê os chunks sobre Apple + inovação                    │
│    Gera resposta coerente                                  │
│    Envia chunk por chunk (streaming)                       │
│    ↓                                                        │
│ 5. Resposta:                                               │
│    "Apple é conhecida por sua constante inovação          │
│     em design e tecnologia. A empresa investe..."          │
│                                                             │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ↓ (Streaming chunks)
```

**Código:** `goldenverba/components/generation/AnthropicGenerator.py`
```python
class AnthropicGenerator(LLM):
    async def generate_answer(self, prompt: str, config: Dict):
        """Gera resposta usando API Anthropic"""
        
        client = Anthropic(api_key=self.api_key)
        
        # Streaming
        with client.messages.stream(
            model="claude-3-sonnet-20240229",
            max_tokens=config.get("Max Tokens", 1024),
            messages=[{"role": "user", "content": prompt}]
        ) as stream:
            for text in stream.text_stream:
                yield text  # ← Envia em tempo real
```

**Exemplo de Prompt Construído:**
```
System: You are a helpful AI assistant specialized in answering questions based on provided context.

Context (from retrieved documents):
---
Apple Inc. has a strategic focus on innovation across its product lines. 
The company invests heavily in R&D for new technologies including AI, 
machine learning, and sustainable materials...

[Mais 10-20 chunks similares]
---

User: apple e inovação

```

---

### **ETAPA 4️⃣: Frontend Recebe Resposta (Streaming)**

```
┌─────────────────────────────────────────────────────────────┐
│ WebSocket /ws/generate_stream                               │
│                                                             │
│ ✅ FLUXO DE RECEPÇÃO (STREAMING)                           │
│                                                             │
│ 1. Frontend conectado no WebSocket                          │
│    Aguardando chunks da resposta                            │
│    ↓                                                        │
│ 2. Backend envia chunks em tempo real:                      │
│    {                                                        │
│      "message": "Apple",                                    │
│      "finish_reason": null                                  │
│    }                                                        │
│    {                                                        │
│      "message": " é conhecida",                             │
│      "finish_reason": null                                  │
│    }                                                        │
│    {                                                        │
│      "message": " pela inovação...",                        │
│      "finish_reason": null                                  │
│    }                                                        │
│    {                                                        │
│      "message": "",                                         │
│      "finish_reason": "stop"                                │
│    }                                                        │
│    ↓                                                        │
│ 3. Frontend renderiza em tempo real                         │
│    Usuário vê a resposta aparecer palavra por palavra       │
│    ↓                                                        │
│ 4. Resposta Final:                                          │
│    "Apple é conhecida pela inovação em design, tecnologia   │
│     e sustentabilidade. A empresa investe bilhões em        │
│     pesquisa e desenvolvimento para trazer produtos         │
│     inovadores ao mercado."                                 │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Código:** `goldenverba/server/api.py`
```python
@app.websocket("/ws/generate_stream")
async def websocket_generate_stream(websocket: WebSocket):
    await websocket.accept()
    while True:
        data = await websocket.receive_text()
        payload = GeneratePayload.model_validate_json(data)
        
        full_text = ""
        async for chunk in manager.generate_stream_answer(
            payload.rag_config,
            payload.query,           # ← "apple e inovação"
            payload.context,         # ← Chunks do retrieval
            payload.conversation,
        ):
            full_text += chunk["message"]
            if chunk["finish_reason"] == "stop":
                chunk["full_text"] = full_text
            await websocket.send_json(chunk)  # ← Envia em tempo real
```

---

## 🧠 **Resumo: Quem Faz o Quê**

| Componente | Função | Tecnologia | Exemplo |
|---|---|---|---|
| **QueryParser** | Separa entidades de conceitos | spaCy NER + POS | "apple" (entidade) + "inovação" (conceito) |
| **EntityAwareRetriever** | Busca chunks relevantes | Weaviate WHERE + Vector | Retorna chunks sobre Apple + inovação |
| **AnthropicGenerator** | Gera resposta usando LLM | Claude 3 API | "Apple é conhecida pela inovação..." |
| **Frontend** | Exibe resposta | React + WebSocket | Mostra em tempo real (streaming) |

---

## 🎯 **Onde Entra o Query Parser**

```
Usuário: "apple e inovação"
      ↓
[QueryParser]  ← NOVO!
      ├─ Extrai: entidade="Apple", conceito="inovação"
      └─ Classifica: intent="COMBINATION"
      ↓
[EntityAwareRetriever]
      ├─ Aplica filtro WHERE: entities = "Apple"
      └─ Busca vetorial: "inovação"
      ↓
[Weaviate]
      → Retorna chunks sobre (Apple AND inovação)
      ↓
[AnthropicGenerator]
      → Lê chunks, gera resposta
      ↓
[Frontend]
      → Exibe streaming da resposta
```

---

## 📋 **Comparação: Com vs Sem Query Parser**

### **SEM Query Parser (Hoje - Limitado)**

```
Query: "apple e inovação"
     ↓
extract_entities_from_query()
     → Encontra: ["Apple"]
     → Ignora: "inovação"
     ↓
Weaviate: WHERE entities = "Apple"
     → Retorna: Chunks sobre Apple (em qualquer contexto)
     → PROBLEMA: Pode incluir chunks que não falam de inovação
     ↓
LLM recebe contexto incorreto
     → Resposta pode não abordar "inovação" adequadamente
```

### **COM Query Parser (Novo - Completo)**

```
Query: "apple e inovação"
     ↓
parse_query()
     → Entidades: ["Apple"]
     → Conceitos: ["inovação"]
     → Intent: "COMBINATION"
     ↓
Weaviate: WHERE entities = "Apple" AND vector_search("inovação")
     → Retorna: Chunks sobre Apple que mencionam inovação
     → ✅ CORRETO: Contextualmente relevante
     ↓
LLM recebe contexto perfeito
     → Resposta aborda Apple + inovação de forma coerente
```

---

## 🔗 **Arquitetura Visual Completa**

```
                    ┌──────────────┐
                    │   Usuário    │
                    │   (Chat)     │
                    └───────┬──────┘
                            │
                    ┌───────▼──────────┐
                    │  Frontend        │
                    │  (React)         │
                    │  ChatInterface   │
                    └───────┬──────────┘
                            │ Query: "apple e inovação"
        ┌───────────────────┴───────────────────┐
        │                                       │
    ┌───▼─────────────────────────────────┐    │
    │ /api/query (Retrieval Stage)        │    │
    │                                     │    │
    │  1. QueryParser                     │    │
    │     ├─ entities: ["Apple"]          │    │
    │     └─ concepts: ["inovação"]       │    │
    │                                     │    │
    │  2. EntityAwareRetriever            │    │
    │     ├─ WHERE filter: entities       │    │
    │     └─ Vector: concepts             │    │
    │                                     │    │
    │  3. Weaviate                        │    │
    │     → Chunks relevantes             │    │
    │                                     │    │
    └───┬─────────────────────────────────┘    │
        │ {documents, context}                 │
        │                                       │
    ┌───▼─────────────────────────────────┐    │
    │ /ws/generate_stream (Generation)    │    │
    │                                     │    │
    │  1. AnthropicGenerator              │    │
    │     • Model: Claude 3               │    │
    │     • Prompt: context + query       │    │
    │     • Streaming: SIM                │    │
    │                                     │    │
    │  2. LLM API (Anthropic)             │    │
    │     → Resposta gerada               │    │
    │                                     │    │
    └───┬─────────────────────────────────┘    │
        │ {message, finish_reason}             │
        │                                       │
        └───────────────────────────────────────┘
                    │
            ┌───────▼──────────┐
            │  Frontend        │
            │  (Streaming)     │
            │  Mostra resposta  │
            │  em tempo real    │
            └──────────────────┘
                    │
                    ↓
            ┌──────────────────┐
            │   Usuário vê:    │
            │  "Apple é        │
            │   conhecida      │
            │   pela inovação  │
            │   em..."         │
            └──────────────────┘
```

---

## 💡 **Resposta Direta: Sim, Usa LLM!**

**A sequência é:**

1. **QueryParser** → Entende o que procurar (entidade vs conceito)
2. **Retriever** → Busca chunks relevantes
3. **LLM (Claude)** → **Gera a resposta usando esses chunks**
4. **Frontend** → Exibe em streaming

O Query Parser é apenas o **primeiro passo** para melhorar a qualidade dos chunks que o LLM vai receber. Sem o Query Parser, o LLM recebe chunks de má qualidade. Com ele, recebe chunks perfeitamente alinhados com a intenção do usuário.
