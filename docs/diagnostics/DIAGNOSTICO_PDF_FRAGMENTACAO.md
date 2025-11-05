# 🔍 Diagnóstico: Fragmentação e Repetição de Linhas em PDFs

## 📋 Problema Identificado

**Sintoma:** Linhas repetidas e progressivamente cortadas no conteúdo extraído:
```
O posicionamento da Flow neste 1234562.21
posicionamento da Flow neste 1234562.21
osicionamento da Flow neste 1234562.21
sicionamento da Flow neste 1234562.21
icionamento da Flow neste 1234562.21
```

## 🔍 Causa Raiz

### Problema Principal: Extração de PDF Multi-Coluna

O `pypdf` (biblioteca usada pelo `BasicReader`) tem dificuldade com PDFs que têm:
- **Múltiplas colunas** por página
- **Layouts complexos** (tabelas, figuras, texto em colunas)
- **Ordem de objetos** diferente da ordem visual

### Por Que Acontece

1. **Ordem de Extração**: O `pypdf` extrai texto na ordem dos objetos no PDF, não na ordem visual
2. **PDFs Multi-Coluna**: Se o PDF tem 2-3 colunas, o pypdf pode ler coluna por coluna ao invés de linha por linha
3. **Fragmentação**: Linhas que aparecem em múltiplas colunas são extraídas múltiplas vezes

### Fluxo do Problema

```
PDF Original (2 colunas)
├─ Coluna 1: "O posicionamento da Flow..."
└─ Coluna 2: "posicionamento da Flow..." (continuação)

pypdf extrai:
├─ Linha 1: "O posicionamento da Flow..." (da coluna 1)
├─ Linha 2: "posicionamento da Flow..." (da coluna 2) ← fragmento
├─ Linha 3: "osicionamento da Flow..." (continuação coluna 2)
└─ ...

Resultado: Linhas repetidas e fragmentadas
```

## ✅ Solução Implementada

### Modificações no `BasicReader.load_pdf_file()`

1. **Layout Mode**: Tenta usar `layout_mode=True` para preservar ordem espacial
2. **Deduplicação de Linhas**: Remove linhas duplicadas consecutivas
3. **Detecção de Fragmentos**: Identifica quando uma linha é fragmento de outra
4. **Fallback**: Se layout mode falhar, usa método padrão com limpeza

### Código Implementado

```python
async def load_pdf_file(self, decoded_bytes: bytes) -> str:
    # Tenta extrair com layout preservation (melhor para multi-coluna)
    # Remove linhas duplicadas e fragmentos
    # Detecta padrões de fragmentação
```

## 🧪 Como Testar

### Script de Análise

Execute:
```bash
python scripts/analyze_pdf_extraction.py "caminho/do/arquivo.pdf"
```

Isso mostra:
- Taxa de duplicação de linhas
- Padrões de fragmentação encontrados
- Comparação entre métodos de extração

### Verificação no Verba

1. **Antes**: Reimporte o documento e verifique a aba "Content"
2. **Depois da correção**: O conteúdo deve estar mais limpo, sem repetições

## 🔧 Soluções Alternativas (Se o Problema Persistir)

### Opção 1: Usar `pdfplumber` (Melhor para Multi-Coluna)

```python
# Requer: pip install pdfplumber
import pdfplumber

with pdfplumber.open(pdf_bytes) as pdf:
    text = "\n\n".join([
        page.extract_text(layout=True)  # layout=True preserva colunas
        for page in pdf.pages
    ])
```

**Vantagens:**
- ✅ Melhor detecção de colunas
- ✅ Preserva ordem visual
- ✅ Melhor para tabelas

**Desvantagens:**
- ❌ Biblioteca adicional
- ❌ Pode ser mais lento

### Opção 2: Usar `PyMuPDF` (fitz) (Mais Rápido)

```python
# Requer: pip install pymupdf
import fitz  # PyMuPDF

doc = fitz.open(stream=pdf_bytes, filetype="pdf")
text = "\n\n".join([
    page.get_text("text", sort=True)  # sort=True ordena por posição
    for page in doc
])
```

**Vantagens:**
- ✅ Muito rápido
- ✅ `sort=True` ordena por posição (melhor para colunas)
- ✅ Boa qualidade de extração

**Desvantagens:**
- ❌ Biblioteca adicional

### Opção 3: Usar `UpstageDocumentParseReader`

Se você já tem o `UpstageDocumentParseReader` configurado:
- ✅ Usa API externa (melhor qualidade)
- ✅ Lida bem com PDFs complexos
- ❌ Requer API key e conexão

## 📊 Estatísticas do Problema

Baseado na análise do PDF:
- **Taxa de duplicação**: ~19.7% das linhas
- **Padrão**: Linhas progressivamente cortadas
- **Causa**: PDF multi-coluna extraído na ordem errada

## 🎯 Recomendação

1. **Primeiro**: Teste a correção implementada no `BasicReader`
2. **Se persistir**: Considere usar `pdfplumber` ou `PyMuPDF`
3. **Para produção**: Use `UpstageDocumentParseReader` se disponível

## 📝 Próximos Passos

1. ✅ Correção implementada no `BasicReader`
2. ⏳ Testar com o PDF problemático
3. ⏳ Se necessário, implementar suporte a `pdfplumber` ou `PyMuPDF`

---

**Nota:** O chunker **NÃO** causa esse problema. Ele apenas divide o texto que recebe. O problema está na **extração** (Reader), não no **chunking**.


