# 🔧 Integração Docling no UniversalA2Reader

## 📋 Visão Geral

O **UniversalA2Reader** agora suporta **Docling** como opção de parsing estruturado, similar ao suporte Tika existente.

### **Hierarquia de Decisão:**
```
1. Docling (se habilitado e disponível) → Parsing estruturado com mapeamento por página
2. Tika (se habilitado e disponível) → Extração texto + metadados
3. BasicReader → Fallback padrão
```

---

## 🚀 Como Usar

### **1. Configurar Docling**

#### **Opção A: Via Variáveis de Ambiente**
```bash
export DOCLING_API_URL="https://api.docling.ai/v1"
export DOCLING_API_KEY="sua-api-key-aqui"
```

#### **Opção B: Via UI do Verba**
1. Escolha **"Universal A2 (ETL Automático)"** como Reader
2. Configure:
   - ✅ **Use Docling When Available**: `True`
   - **Docling API URL**: `https://api.docling.ai/v1` (ou sua URL)
   - **Docling API Key**: `sua-api-key`

### **2. Importar Documento**

1. Faça upload do arquivo (PDF, DOCX, PPTX, etc.)
2. O Universal Reader:
   - ✅ Verifica se Docling está disponível
   - ✅ Se sim e formato é benéfico → usa Docling
   - ✅ Se não → tenta Tika ou BasicReader

---

## ⚙️ Formatos que Usam Docling

Docling é usado automaticamente para:
- ✅ **PDF** - Parsing estruturado com mapeamento por página
- ✅ **PPTX/PPT** - Slides estruturados
- ✅ **DOCX/DOC** - Documentos Word estruturados

**Outros formatos:**
- Continuam usando Tika (se disponível) ou BasicReader

---

## 📊 O que o Docling Faz

### **1. Parsing Estruturado**

Retorna:
- ✅ **Markdown completo** (`md_content`)
- ✅ **JSON estruturado** (`json_content`) com:
  - `texts[]` - Textos com `prov[].page_no`
  - `pages{}` - Metadados de páginas
  - `groups[]` - Grupos/slides (`slide-0` = página 1)
  - `tables[]` - Tabelas com `prov[].page_no`

### **2. Mapeamento por Página**

```python
# Mapeia conteúdo usando texts[].prov[].page_no
pages_content = {
    1: "Conteúdo da página 1...",
    2: "Conteúdo da página 2...",
    ...
}
```

**Salvo em:**
- `document.meta["docling_pages_content"]` - Dict {page_no: content}
- `document.meta["docling_pages_mapped"]` - Número de páginas mapeadas

### **3. Metadados Preservados**

```python
document.meta = {
    "source_api": "docling",
    "json_content": {...},  # Estrutura completa
    "docling_pages_count": 10,
    "docling_texts_count": 45,
    "docling_groups_count": 3,
    "docling_tables_count": 2,
    "docling_pages_content": {...},  # Mapeamento por página
    "enable_etl": True
}
```

---

## 🔄 Fluxo de Processamento

```
Arquivo PDF/DOCX/PPTX
  ↓
UniversalA2Reader.load()
  ↓
Verifica: Use Docling When Available?
  ↓ [SIM]
Verifica: Docling disponível (API URL + Key)?
  ↓ [SIM]
Verifica: Formato benéfico para Docling?
  ↓ [SIM]
Chama Docling API:
  - to_formats: ['md', 'json']
  - do_ocr: true
  - do_table_structure: true
  ↓
Recebe:
  - md_content (Markdown)
  - json_content (Estrutura completa)
  ↓
Mapeia conteúdo por página:
  - texts[].prov[].page_no → pages_content
  ↓
Cria Document:
  - content = md_content
  - meta = {json_content, pages_content, ...}
  - enable_etl = True
  ↓
Retorna Document pronto para chunking + ETL
```

---

## 📝 Configurações Disponíveis

| Configuração | Tipo | Padrão | Descrição |
|-------------|------|--------|-----------|
| **Use Docling When Available** | bool | `False` | Habilitar Docling quando disponível |
| **Docling API URL** | text | `""` ou `DOCLING_API_URL` | URL da API Docling |
| **Docling API Key** | password | `""` ou `DOCLING_API_KEY` | API Key do Docling |
| **Use Tika When Available** | bool | `True` | Habilitar Tika quando disponível (fallback) |
| **Enable ETL** | bool | `True` | Aplicar ETL A2 automaticamente |
| **Language Hint** | text | `"pt"` | Idioma para NER |

---

## ⚠️ Notas Importantes

### **1. Endpoint da API**

O endpoint padrão é: `{api_url}/parse`

**Se sua API Docling usar outro endpoint**, ajuste em `_extract_with_docling_sync()`:
```python
parse_url = f"{api_url.rstrip('/')}/parse"  # Ajustar se necessário
```

### **2. Formato do Payload**

O payload segue práticas recomendadas:
```python
{
    "target_type": "inbody",
    "to_formats": ["md", "json"],  # Array direto
    "do_ocr": "true",
    "do_table_structure": "true",
    "table_mode": "accurate",
    "include_images": "false"
}
```

### **3. Estrutura de Resposta Esperada**

```json
{
    "document": {
        "md_content": "...",
        "json_content": {
            "texts": [...],
            "pages": {...},
            "groups": [...],
            "tables": [...]
        }
    }
}
```

**Se sua API retornar formato diferente**, ajuste em `_extract_with_docling_sync()`:
```python
document = result.get("document", {})
md_content = document.get("md_content", "")
json_content = document.get("json_content", {})
```

---

## ✅ Vantagens do Docling vs. Tika

| Característica | Docling | Tika |
|---------------|---------|------|
| **Estrutura JSON** | ✅ Completa | ❌ Apenas texto |
| **Mapeamento por página** | ✅ `texts[].prov[].page_no` | ❌ Não tem |
| **Grupos/Slides** | ✅ `groups[]` | ❌ Não tem |
| **Tabelas estruturadas** | ✅ `tables[]` com `page_no` | ❌ Não tem |
| **Bounding boxes** | ✅ `bbox` em `prov[]` | ❌ Não tem |
| **Suporte formatos** | ✅ PDF, DOCX, PPTX | ✅ 1000+ formatos |

**Use Docling quando:**
- ✅ Precisa de mapeamento preciso por página
- ✅ Precisa de estrutura JSON rica
- ✅ Trabalha com slides/grupos
- ✅ Precisa de tabelas estruturadas

**Use Tika quando:**
- ✅ Trabalha com formatos exóticos (ODT, RTF, etc.)
- ✅ Não precisa de estrutura JSON
- ✅ Precisa apenas de texto + metadados básicos

---

## 🔍 Debug

### **Ver Logs do Docling**

Os logs mostram:
- ✅ Quando Docling é usado
- ✅ Quantos caracteres foram extraídos
- ✅ Quantas páginas/grupos/tabelas foram encontrados
- ⚠️ Erros e warnings

**Exemplo de logs:**
```
[UNIVERSAL-READER] Usando Docling para 'documento.pdf' (formato: .pdf)
[UNIVERSAL-READER] Chamando Docling API: https://api.docling.ai/v1/parse
[UNIVERSAL-READER] Docling extraiu: 15234 caracteres (md), JSON com 8 chaves
[UNIVERSAL-READER] Metadados Docling extraídos: 8 campos
[UNIVERSAL-READER] Documento extraído via Docling: 15234 caracteres (md)
```

---

## 📚 Referências

- [Práticas Recomendadas Docling](./ANALISE_DOCLING_INTEGRACAO.md)
- [Análise Ingestores Customizados](./ANALISE_INGESTORES_CUSTOMIZADOS.md)
- [Guia Universal Reader](./GUIA_INGESTOR_UNIVERSAL.md)

---

**Última atualização**: Janeiro 2025  
**Status**: Implementado e funcional  
**Compatibilidade**: Verba 2.1.x + UniversalA2Reader












