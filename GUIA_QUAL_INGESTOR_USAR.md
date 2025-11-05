# 📚 Guia: Qual Ingestor Usar?

## 🎯 Resumo Rápido

| Tipo de Arquivo | Ingestor Recomendado | Motivo |
|----------------|---------------------|--------|
| **PDF único** | `Universal A2` ✅ ou `Default` | ETL automático + Tika para melhor extração |
| **PDF com vários artigos** | `Universal A2` ✅ ou `Default` | ETL automático + Tika para melhor extração |
| **PPTX, PPT** | `Universal A2` ✅ ou `Tika Reader` | Tika é necessário (não suportado nativamente) |
| **DOC, RTF, ODT** | `Universal A2` ✅ ou `Tika Reader` | Tika é necessário (não suportado nativamente) |
| **DOCX** | `Universal A2` ✅ ou `Default` | ETL automático + Tika como fallback |
| **URLs** | `A2 URL Ingestor` ✅ | Extrai de URLs e aplica ETL |
| **JSON com conteúdo já extraído** | `A2 Results Ingestor` ✅ | Processa results com ETL |
| **JSON genérico** | `Universal A2` ✅ ou `Default` | Leitura básica |

---

## 📋 Detalhamento por Ingestor

### 1. **A2 URL Ingestor** ✅ (Customizado)

**O que aceita:**
- ✅ **URLs** (uma por linha)
- ✅ Processa automaticamente:
  - Baixa o HTML
  - Extrai texto com `trafilatura`
  - Aplica ETL (NER + Section Scope) **se habilitado**

**NÃO aceita:**
- ❌ PDFs
- ❌ Arquivos locais
- ❌ JSON

**Formato de entrada:**
```
https://exemplo.com/artigo1
https://exemplo.com/artigo2
https://exemplo.com/artigo3
```

**Quando usar:**
- ✅ Você tem URLs de artigos web
- ✅ Quer ETL automático (entidades, seções)
- ✅ Conteúdo está online e acessível

---

### 2. **A2 Results Ingestor** ✅ (Customizado)

**O que aceita:**
- ✅ **JSON** com formato específico (veja abaixo)
- ✅ Conteúdo já extraído e estruturado
- ✅ Aplica ETL (NER + Section Scope) **se habilitado**

**NÃO aceita:**
- ❌ PDFs
- ❌ URLs
- ❌ Outros formatos

**Formato JSON esperado:**
```json
{
  "results": [
    {
      "url": "https://exemplo.com/artigo1",
      "title": "Título do Artigo 1",
      "content": "Texto completo do artigo aqui...",
      "published_at": "2025-01-15",
      "metadata": {
        "language": "pt",
        "author": "João Silva",
        "category": "Tecnologia"
      }
    },
    {
      "url": "https://exemplo.com/artigo2",
      "title": "Título do Artigo 2",
      "content": "Outro texto completo...",
      "published_at": "2025-01-16",
      "metadata": {
        "language": "pt"
      }
    }
  ]
}
```

**Campos obrigatórios:**
- `url` (string)
- `content` (string) - texto já extraído
- `title` (string, opcional mas recomendado)

**Campos opcionais:**
- `published_at` (string, formato ISO ou "YYYY-MM-DD")
- `metadata` (objeto com metadados extras)

**Quando usar:**
- ✅ Você já extraiu conteúdo de PDFs/URLs
- ✅ Tem múltiplos artigos em um JSON
- ✅ Quer ETL automático

---

### 3. **Default** (Padrão do Verba)

**O que aceita:**
- ✅ **PDFs** (únicos ou múltiplos)
- ✅ DOCX, TXT, CSV, Excel, JSON genérico
- ✅ Leitura básica sem ETL customizado

**NÃO tem:**
- ❌ ETL A2 (NER + Section Scope)
- ❌ Processamento especial de artigos

**Quando usar:**
- ✅ PDFs simples
- ✅ Documentos Word
- ✅ Não precisa de ETL customizado

---

### 4. **Upstage Parser** (Padrão do Verba)

**O que aceita:**
- ✅ **PDFs** com melhor extração
- ✅ Requer API key do Upstage
- ✅ Melhor para PDFs complexos

**Quando usar:**
- ✅ PDFs com layout complexo
- ✅ PDFs escaneados
- ✅ Precisa de extração avançada

---

## 🔄 Fluxos Recomendados

### Cenário 1: Você tem URLs

```
URLs → A2 URL Ingestor → ETL automático → Weaviate
```

**Passos:**
1. Escolha **"A2 URL Ingestor"** no dropdown
2. Cole as URLs (uma por linha)
3. Ative **"Enable ETL"**
4. Importe

---

### Cenário 2: Você tem PDFs

#### Opção A: PDF simples (sem ETL customizado)
```
PDF → Default → Chunking básico → Weaviate
```

#### Opção B: PDF com vários artigos (com ETL)
```
PDF → Extrair manualmente → JSON → A2 Results Ingestor → ETL → Weaviate
```

**Passos para Opção B:**
1. Extraia os PDFs manualmente (ou use `Upstage Parser`)
2. Converta para JSON no formato esperado:
   ```json
   {
     "results": [
       {"url": "doc://artigo1.pdf", "title": "...", "content": "..."},
       {"url": "doc://artigo2.pdf", "title": "...", "content": "..."}
     ]
   }
   ```
3. Use **"A2 Results Ingestor"**
4. Ative **"Enable ETL"**

---

### Cenário 3: Você tem JSON com conteúdo já extraído

```
JSON → A2 Results Ingestor → ETL → Weaviate
```

**Passos:**
1. Certifique-se que o JSON está no formato correto (veja acima)
2. Escolha **"A2 Results Ingestor"**
3. Cole o JSON ou faça upload do arquivo `.json`
4. Ative **"Enable ETL"**

---

## ⚠️ Perguntas Frequentes

### Q: Posso usar A2 Results Ingestor com PDF?

**R:** Não diretamente. Você precisa:
1. Extrair o conteúdo do PDF primeiro (use `Default` ou `Upstage Parser`)
2. Converter para o formato JSON esperado
3. Usar `A2 Results Ingestor`

### Q: E se meu PDF tem vários artigos?

**R:** 
- **Sem ETL:** Use `Default` - vai criar um documento único
- **Com ETL:** Extraia cada artigo separadamente e crie um JSON com múltiplos `results`

### Q: O A2 URL Ingestor funciona com PDFs hospedados?

**R:** Depende:
- ✅ Se a URL retorna HTML → Funciona
- ❌ Se a URL retorna PDF direto → Não funciona (use `Default` + upload direto)

### Q: Posso usar Default e depois aplicar ETL?

**R:** Não diretamente. O ETL A2 só funciona se:
- Você usar `A2 URL Ingestor` OU
- Você usar `A2 Results Ingestor`

O `Default` não aciona o hook de ETL customizado.

---

## 🚀 Recomendações Finais

### Para PDFs:
- **Simples**: `Default`
- **Complexos**: `Upstage Parser`
- **Com ETL**: Extraia primeiro → JSON → `A2 Results Ingestor`

### Para URLs:
- **Sempre**: `A2 URL Ingestor` (tem ETL integrado)

### Para JSON:
- **Formato A2**: `A2 Results Ingestor` (tem ETL)
- **Genérico**: `Default`

---

## 💡 Quer suporte para PDFs direto no A2?

Se você precisar processar PDFs diretamente no `A2 Results Ingestor`, posso:
1. Adicionar extração de PDF usando `PyPDF2` ou `pdfplumber`
2. Separar automaticamente múltiplos artigos em um PDF
3. Criar um `A2 PDF Reader` específico

**Diga-me se quer que eu implemente isso!** 🛠️

