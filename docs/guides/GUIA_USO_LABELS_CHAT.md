# 🏷️ Guia: Como Usar Labels no Chat do Verba

## ✅ Resposta Rápida

**Sim! O Verba permite filtrar por labels no chat.** Você pode selecionar labels para limitar a busca apenas aos documentos que têm essas tags.

---

## 🎯 Como Funciona

### **1. Preparação: Adicionar Labels aos Documentos**

Antes de usar labels no chat, você precisa adicioná-los aos documentos durante a importação:

1. **Durante a Importação:**
   - Vá em **Import Data** → Selecione seu arquivo
   - Na seção **"File Settings"** → **"Labels"**
   - Digite uma label (ex: "empresas", "tecnologia", "financeiro")
   - Clique em **"Add"**
   - Repita para adicionar mais labels
   - Clique em **"Import Selected"**

**Exemplo:**
- Documento 1: Labels `["empresas", "tecnologia"]`
- Documento 2: Labels `["empresas", "financeiro"]`
- Documento 3: Labels `["noticias"]`

---

### **2. Usar Labels no Chat**

#### **Passo 1: Abrir o Chat**
1. Vá em **Chat** (no topo da interface)

#### **Passo 2: Selecionar Labels**
1. Acima da área de mensagens, você verá um botão **"Label"** (com ícone ➕)
2. Clique no botão **"Label"**
3. Um dropdown aparecerá com **todos os labels disponíveis** no sistema
4. Clique em um label para adicioná-lo ao filtro (ex: "empresas")
5. Repita para selecionar múltiplos labels

#### **Passo 3: Verificar Labels Selecionados**
- Os labels selecionados aparecem como **"pills"** (botões pequenos) acima da área de chat
- Cada pill mostra o nome do label
- Para remover um label, clique no **X** na pill

#### **Passo 4: Fazer a Query**
- Digite sua pergunta normalmente
- O chat vai buscar **apenas em documentos que têm TODOS os labels selecionados**
- Exemplo:
  - Labels selecionados: `["empresas", "tecnologia"]`
  - Query: "inovação da Apple"
  - Resultado: Busca apenas em documentos que têm AMBOS os labels "empresas" E "tecnologia"

#### **Passo 5: Limpar Filtros**
- Clique no botão **"Clear"** (ao lado do botão Label) para remover todos os filtros
- Ou clique no **X** em cada label individualmente

---

## 📊 Exemplo Prático

### **Cenário: Organizar Documentos por Empresa**

**1. Durante Importação:**
```
Documento "apple_relatorio.pdf":
  Labels: ["empresas", "apple", "tecnologia"]

Documento "microsoft_parcerias.pdf":
  Labels: ["empresas", "microsoft", "tecnologia"]

Documento "google_anuncio.pdf":
  Labels: ["empresas", "google", "tecnologia"]
```

**2. No Chat - Buscar Apenas sobre Apple:**
```
1. Clique em "Label"
2. Selecione "apple"
3. Digite: "Quais são as principais inovações?"
4. Resultado: Busca apenas em "apple_relatorio.pdf"
```

**3. No Chat - Buscar sobre Todas as Empresas de Tecnologia:**
```
1. Clique em "Label"
2. Selecione "empresas" e "tecnologia"
3. Digite: "Quais são as principais inovações?"
4. Resultado: Busca em todos os 3 documentos (Apple, Microsoft, Google)
```

**4. No Chat - Buscar sem Filtros:**
```
1. Não selecione nenhum label (ou clique em "Clear")
2. Digite: "Quais são as principais inovações?"
3. Resultado: Busca em TODOS os documentos do sistema
```

---

## 🔍 Como Funciona Tecnicamente

### **Filtro por Labels:**

Quando você seleciona labels no chat:

1. **Frontend envia:**
   ```typescript
   {
     query: "inovação da Apple",
     labels: ["empresas", "tecnologia"],  // ← Labels selecionados
     RAG: {...},
     documentFilter: [...]
   }
   ```

2. **Backend aplica filtro:**
   ```python
   # goldenverba/components/managers.py
   if labels:
       filter = Filter.by_property("labels").contains_all(labels)
   ```
   
   - **`contains_all`**: Documento deve ter TODOS os labels selecionados
   - Se você seleciona `["empresas", "tecnologia"]`, o documento precisa ter ambos

3. **Busca no Weaviate:**
   - O Verba busca chunks apenas de documentos que correspondem ao filtro
   - Os chunks são usados para gerar a resposta

---

## 💡 Dicas de Uso

### **1. Organização por Tópicos:**
```
Labels: "noticias", "relatorios", "artigos", "pesquisas"
```

### **2. Organização por Empresa:**
```
Labels: "apple", "microsoft", "google", "amazon"
```

### **3. Organização por Categoria:**
```
Labels: "tecnologia", "financeiro", "marketing", "rh"
```

### **4. Organização por Data:**
```
Labels: "2024", "2023", "q1-2024", "q2-2024"
```

### **5. Organização por Fonte:**
```
Labels: "site-oficial", "noticias", "redes-sociais", "analise"
```

---

## ⚠️ Comportamento Importante

### **Filtro AND (E lógico):**
- Se você seleciona múltiplos labels, o documento precisa ter **TODOS** eles
- Exemplo: Labels `["empresas", "tecnologia"]` → documento precisa ter ambos

### **Sem Labels Selecionados:**
- Se nenhum label estiver selecionado, busca em **TODOS** os documentos
- É o comportamento padrão

### **Labels + DocumentFilter:**
- Você pode combinar labels com filtro por documentos específicos
- Ambos os filtros são aplicados simultaneamente

---

## 🚀 Combinando com EntityAware Retriever

Os labels podem ser combinados com o **EntityAware Retriever** para filtros ainda mais precisos:

```
Labels selecionados: ["empresas", "tecnologia"]
Query: "inovação da Apple"
EntityAware detecta: "Apple" (Q312)

Resultado:
- Filtro por labels: documentos com "empresas" E "tecnologia"
- Filtro por entidade: chunks sobre "Apple" (Q312)
- Busca apenas em chunks que satisfazem AMBOS os filtros
```

---

## 📝 Resumo

✅ **Como Adicionar Labels:**
- Durante importação → File Settings → Labels → Add

✅ **Como Usar no Chat:**
1. Chat → Botão "Label" → Selecionar labels
2. Labels aparecem como pills acima do chat
3. Fazer query normalmente
4. Chat busca apenas em documentos com os labels selecionados

✅ **Como Limpar:**
- Botão "Clear" ou clicar no X em cada label

✅ **Comportamento:**
- Labels múltiplos = AND (documento precisa ter todos)
- Sem labels = busca em todos os documentos
- Pode combinar com EntityAware Retriever

---

## 🎯 Exemplo Visual

```
┌─────────────────────────────────────┐
│ Chat                                │
├─────────────────────────────────────┤
│ [Label ➕] [Clear]                   │
│ [empresas ✕] [tecnologia ✕]        │ ← Labels selecionados
├─────────────────────────────────────┤
│                                     │
│ Mensagens do chat...                │
│                                     │
│ [Digite sua pergunta...] [Send]     │
└─────────────────────────────────────┘
```

Quando você clica em "Label", aparece um dropdown:
```
┌─────────────────┐
│ empresas        │ ← Clique para adicionar
│ tecnologia      │
│ financeiro      │
│ noticias        │
│ apple           │
│ microsoft       │
└─────────────────┘
```

---

## 🆘 Troubleshooting

### **Problema: Não vejo o botão "Label"**
- Verifique se está na página **Chat** (não em Import Data ou Documents)
- O botão fica acima da área de mensagens

### **Problema: Dropdown está vazio**
- Você precisa ter documentos com labels importados primeiro
- Vá em **Import Data** e adicione labels aos documentos

### **Problema: Labels não estão funcionando**
- Verifique se os documentos realmente têm os labels
- Vá em **Documents** e veja os labels de cada documento
- Verifique se está usando os nomes exatos dos labels (case-sensitive)

### **Problema: Não encontro documentos mesmo com labels**
- Lembre-se: múltiplos labels = AND (documento precisa ter todos)
- Tente selecionar apenas 1 label para ver se funciona
- Verifique se os documentos realmente têm esses labels

---

## 📚 Referências

- **Documentação API:** `POST /api/query` aceita campo `labels`
- **Código Frontend:** `frontend/app/components/Chat/ChatInterface.tsx`
- **Código Backend:** `goldenverba/components/managers.py` (método `retrieve`)

