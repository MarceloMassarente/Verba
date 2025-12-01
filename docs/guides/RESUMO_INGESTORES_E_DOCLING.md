# 📋 Resumo Executivo: Ingestores e Docling

## ✅ Ingestores Atuais (Nenhum usa Docling)

| Ingestor | API/Serviço | Estrutura JSON | Mapeamento por Página | Status Docling |
|----------|-------------|----------------|----------------------|----------------|
| **ContextualAIIngestor** | Contextual.ai | ❌ Não | ❌ Não | ❌ Não usa |
| **UniversalA2Reader** | Tika/BasicReader | ❌ Não | ❌ Não | ❌ Não usa |
| **TikaReader** | Apache Tika | ❌ Não | ❌ Não | ❌ Não usa |
| **A2ResultsReader** | JSON A2 format | ❌ Não | ❌ Não | ❌ Não usa |

## 🎯 Práticas Recomendadas Docling (do Documento Fornecido)

### **1. Solicitar MD + JSON**
```python
to_formats: ['md', 'json']  # Array direto (sem json.dumps)
```

### **2. Estrutura `json_content`**
```json
{
  "texts": [{"text": "...", "prov": [{"page_no": 1, ...}]}],
  "pages": {"1": {...}, "2": {...}},
  "groups": [{"name": "slide-0", "children": [...]}],
  "tables": [{"prov": [{"page_no": 14}]}]
}
```

### **3. Mapear por Página**
```python
# Usar texts[].prov[].page_no para mapeamento preciso
for text in json_content['texts']:
    page_no = text['prov'][0]['page_no']
    # Agrupar textos por page_no
```

## ⚠️ Problema Identificado

**Nenhum ingestor atual:**
- ❌ Usa `json_content` estruturado
- ❌ Mapeia conteúdo por `page_no`
- ❌ Usa estrutura `groups` (slide-0 = página 1)
- ❌ Processa `tables` com `prov[].page_no`

## ✅ Recomendação

**Criar `DoclingReader`** seguindo práticas recomendadas:
- Solicitar `to_formats: ['md', 'json']`
- Mapear conteúdo por `texts[].prov[].page_no`
- Dividir markdown por página usando mapeamento preciso
- Preservar estrutura `groups` e `tables`

---

**Próximo passo:** Criar `DoclingReader` ou melhorar `ContextualAIIngestor` para usar Docling?

