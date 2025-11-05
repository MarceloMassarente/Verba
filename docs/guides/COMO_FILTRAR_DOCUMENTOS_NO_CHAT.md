# 🔍 Como Filtrar Documentos e Collections no Chat

## ✅ **SIM, você pode selecionar documentos específicos para pesquisar!**

O Verba oferece **2 formas de filtrar** documentos na busca:

1. **Por Labels (Tags)** - filtro por categorias/tags
2. **Por Documentos Específicos** - selecionar documentos individuais

---

## 🎯 **Método 1: Filtrar por Labels (Tags)**

### **Como Funciona:**

1. **Adicionar Labels aos Documentos:**
   - Na seção **Documents**, abra um documento
   - Clique em **"+ Label"** para adicionar tags
   - Exemplos: `empresa-A`, `2024`, `confidencial`, etc.

2. **Filtrar por Labels no Chat:**
   - No chat, você verá labels disponíveis
   - Selecione as labels que deseja filtrar
   - A busca retornará apenas chunks de documentos com essas labels

### **Exemplo:**

```
Documentos:
  - "Relatório Apple 2024" → labels: ["empresa-A", "2024"]
  - "Relatório Microsoft 2024" → labels: ["empresa-B", "2024"]
  - "Relatório Google 2023" → labels: ["empresa-C", "2023"]

Chat com filtro "empresa-A":
  ✅ Retorna apenas chunks de "Relatório Apple 2024"
  ❌ Não retorna chunks de Microsoft ou Google
```

---

## 🎯 **Método 2: Filtrar por Documentos Específicos**

### **Como Funciona:**

1. **Na Seção Documents:**
   - Abra um documento
   - Clique em **"Add to Chat"**
   - O documento será adicionado ao filtro do chat

2. **No Chat:**
   - Você verá os documentos selecionados como "chips" (botões pequenos)
   - A busca retornará apenas chunks desses documentos específicos
   - Pode remover clicando no "X" do chip

### **Exemplo:**

```
Documentos disponíveis:
  - "Relatório Apple 2024"
  - "Relatório Microsoft 2024"
  - "Relatório Google 2023"

Chat com "Relatório Apple 2024" selecionado:
  ✅ Retorna apenas chunks de "Relatório Apple 2024"
  ❌ Não retorna chunks de outros documentos
```

---

## 📋 **Como Usar na Prática**

### **Passo a Passo:**

#### **1. Filtrar por Labels:**

1. **Adicionar Labels:**
   - Vá em **Documents**
   - Abra um documento
   - Clique em **"+ Label"**
   - Digite a label (ex: `empresa-A`)
   - Enter para adicionar

2. **Usar no Chat:**
   - Vá em **Chat**
   - Selecione labels desejadas (se disponível na UI)
   - OU os filtros são aplicados automaticamente se configurados

#### **2. Filtrar por Documentos Específicos:**

1. **Adicionar Documento ao Chat:**
   - Vá em **Documents**
   - Abra o documento desejado
   - Clique em **"Add to Chat"** (botão no documento)
   - Documento aparece como chip no chat

2. **Verificar no Chat:**
   - No chat, você verá chips mostrando documentos selecionados
   - Pode remover clicando no "X" do chip
   - Clique em **"Clear"** para remover todos os filtros

3. **Fazer Busca:**
   - Digite sua query normalmente
   - A busca será limitada aos documentos selecionados

---

## 🔍 **Como Funciona Técnicamente**

### **Backend (API):**

```python
# goldenverba/verba_manager.py (linha 848-875)

async def retrieve_chunks(
    self,
    client,
    query: str,
    rag_config: dict,
    labels: list[str] = [],          # ← Filtro por labels
    document_uuids: list[str] = [],  # ← Filtro por documentos
):
    # Vectoriza query
    vector = await self.embedder_manager.vectorize_query(...)
    
    # Busca com filtros
    documents, context = await self.retriever_manager.retrieve(
        ...,
        labels=labels,              # ← Filtro aplicado
        document_uuids=document_uuids,  # ← Filtro aplicado
    )
```

### **Frontend (UI):**

```typescript
// frontend/app/api.ts (linha 245-274)

export const sendUserQuery = async (
  query: string,
  RAG: RAGConfig | null,
  labels: string[],              // ← Labels selecionadas
  documentFilter: DocumentFilter[], // ← Documentos selecionados
  credentials: Credentials
) => {
  // Envia para /api/query
  body: JSON.stringify({
    query: query,
    RAG: RAG,
    labels: labels,              // ← Enviado
    documentFilter: documentFilter, // ← Enviado
  })
}
```

### **Filtros no Weaviate:**

```python
# goldenverba/components/managers.py (linha 1106-1143)

if await self.verify_embedding_collection(client, embedder):
    embedder_collection = client.collections.get(...)
    
    filters = []
    
    # Filtro por labels
    if labels:
        filters.append(Filter.by_property("labels").contains_all(labels))
    
    # Filtro por documentos
    if document_uuids:
        filters.append(
            Filter.by_property("doc_uuid").contains_any(document_uuids)
        )
    
    # Busca com filtros aplicados
    chunks = await embedder_collection.query.hybrid(
        query=query,
        vector=vector,
        filters=apply_filters,  # ← Filtros aplicados aqui
    )
```

---

## 📊 **Exemplos de Uso**

### **Exemplo 1: Buscar apenas em documentos de uma empresa**

```
1. Adicionar label "Apple" aos documentos da Apple
2. No chat, selecionar label "Apple"
3. Query: "inovação"
4. Resultado: Apenas chunks de documentos da Apple que mencionam "inovação"
```

### **Exemplo 2: Buscar em documentos específicos**

```
1. Documentos:
   - "Relatório Q1 2024"
   - "Relatório Q2 2024"
   - "Relatório Q3 2024"

2. No chat, adicionar "Relatório Q1 2024" e "Relatório Q2 2024"
3. Query: "receita"
4. Resultado: Apenas chunks dos relatórios Q1 e Q2 que mencionam "receita"
```

### **Exemplo 3: Combinar Labels + Documentos**

```
1. Label "confidencial" em alguns documentos
2. Selecionar label "confidencial" + documento específico "Relatório X"
3. Query: "estratégia"
4. Resultado: Chunks do "Relatório X" que têm label "confidencial" e mencionam "estratégia"
```

---

## ⚠️ **Limitações Atuais**

### **O que funciona:**
- ✅ Filtrar por labels (tags)
- ✅ Filtrar por documentos específicos (UUIDs)
- ✅ Combinar múltiplos filtros
- ✅ Remover filtros facilmente

### **O que não funciona (ainda):**
- ❌ Filtrar por collection de embedding diretamente (mas isso é automático via embedder)
- ❌ Grupos/categorias de documentos (mas pode usar labels para isso)
- ❌ Filtros temporais na UI (mas EntityAware Retriever pode fazer isso)

### **Workaround para Grupos de Documentos:**

**Use Labels como "collections virtuais":**

```
Labels podem representar grupos:
  - "projeto-X" → todos documentos do projeto X
  - "cliente-Y" → todos documentos do cliente Y
  - "2024" → todos documentos de 2024
  - "confidencial" → todos documentos confidenciais
```

---

## 🎯 **Resumo**

| Filtro | Como Adicionar | Como Usar | Resultado |
|--------|----------------|-----------|-----------|
| **Labels** | "+ Label" no documento | Selecionar labels no chat | Chunks de documentos com essas labels |
| **Documentos** | "Add to Chat" no documento | Aparece como chip no chat | Chunks apenas desses documentos |

---

## ✅ **Conclusão**

**SIM, você pode selecionar documentos e collections para pesquisar!**

- ✅ **Labels:** Use para categorizar documentos (empresas, projetos, anos, etc.)
- ✅ **Documentos Específicos:** Adicione documentos individualmente ao chat
- ✅ **Ambos:** Podem ser combinados para filtros mais precisos

**A busca será limitada aos documentos/labels selecionados!** 🎉

