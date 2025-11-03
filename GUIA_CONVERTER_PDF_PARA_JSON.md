# 📄 Guia: Converter PDF para JSON A2

## 🎯 Objetivo

Converter PDFs (um ou múltiplos artigos) para o formato JSON esperado pelo **A2 Results Ingestor**, permitindo usar ETL customizado.

---

## 🚀 Método 1: Script Automático (Recomendado)

### Instalação

```bash
pip install pypdf
```

### Uso Básico

```bash
python scripts/pdf_to_a2_json.py seu_arquivo.pdf
```

Isso cria `seu_arquivo_a2.json` automaticamente.

### Opções Avançadas

```bash
# Forçar separação em múltiplos artigos
python scripts/pdf_to_a2_json.py revista.pdf --split

# Tratar como um único artigo (mesmo se houver quebras)
python scripts/pdf_to_a2_json.py artigo.pdf --no-split

# Especificar arquivo de saída
python scripts/pdf_to_a2_json.py documento.pdf --output resultado.json
```

---

## 📋 Método 2: Manual (para casos específicos)

### Passo 1: Extrair Texto do PDF

Use qualquer método:
- **Verba Default Reader**: Faça upload do PDF → escolha "Default" → exporte o texto
- **Online**: https://www.ilovepdf.com/pdf_to_txt
- **Python**: Use o script acima (mas não salve JSON ainda)

### Passo 2: Criar JSON Manualmente

Crie um arquivo `artigos.json`:

```json
{
  "results": [
    {
      "url": "doc://artigo1.pdf",
      "title": "Título do Primeiro Artigo",
      "content": "Texto completo do primeiro artigo aqui...\n\nPode ter múltiplos parágrafos.",
      "published_at": "2025-01-15",
      "metadata": {
        "language": "pt",
        "author": "João Silva",
        "category": "Tecnologia"
      }
    },
    {
      "url": "doc://artigo2.pdf",
      "title": "Título do Segundo Artigo",
      "content": "Texto completo do segundo artigo...",
      "published_at": "2025-01-16",
      "metadata": {
        "language": "pt"
      }
    }
  ]
}
```

### Passo 3: Importar no Verba

1. Abra Verba → **Import Data**
2. Escolha **"A2 Results Ingestor"** no dropdown
3. Faça upload do `artigos.json`
4. Ative **"Enable ETL"**
5. Importe!

---

## 📝 Formato JSON Esperado

### Campos Obrigatórios:
- `url` (string): Identificador do documento
  - Exemplos: `"doc://artigo.pdf"`, `"https://exemplo.com"`, `"file://local.pdf"`
- `content` (string): Texto completo já extraído

### Campos Opcionais (mas recomendados):
- `title` (string): Título do artigo
- `published_at` (string): Data no formato `"YYYY-MM-DD"` ou ISO
- `metadata` (objeto): Metadados extras
  - `language` (string): Idioma, ex: `"pt"`, `"en"`
  - Qualquer outro campo customizado

### Estrutura:
```json
{
  "results": [
    {
      "url": "...",
      "title": "...",
      "content": "...",
      "published_at": "...",
      "metadata": {
        "language": "pt",
        ...
      }
    }
  ]
}
```

---

## 🔍 Detalhamento: Detecção Automática de Múltiplos Artigos

O script `pdf_to_a2_json.py` detecta múltiplos artigos baseado em:

1. **Quebras duplas/triplas**: `\n\n\n` (múltiplas linhas vazias)
2. **Padrões de título**: Linhas curtas (<100 chars) que não terminam com ponto
3. **Estrutura do PDF**: Divisão natural do documento

### Como funciona:

```
PDF com 3 artigos:
[Artigo 1 - texto completo]
\n\n\n
[Artigo 2 - texto completo]
\n\n\n
[Artigo 3 - texto completo]
```

Resultado:
```json
{
  "results": [
    {"url": "doc://pdf.pdf#article1", "title": "Artigo 1", "content": "..."},
    {"url": "doc://pdf.pdf#article2", "title": "Artigo 2", "content": "..."},
    {"url": "doc://pdf.pdf#article3", "title": "Artigo 3", "content": "..."}
  ]
}
```

---

## 💡 Dicas

### Para PDFs Bem Formatados:
```bash
python scripts/pdf_to_a2_json.py documento.pdf --split
```

### Para PDFs Escaneados ou Mal Formatados:
1. Use **Upstage Parser** no Verba primeiro (melhor extração)
2. Copie o texto extraído
3. Crie JSON manualmente

### Para PDFs com Muitos Artigos:
```bash
# O script detecta automaticamente
python scripts/pdf_to_a2_json.py revista_completa.pdf
```

### Para Ajustar Metadados:

Após gerar o JSON, edite manualmente:
```json
{
  "results": [
    {
      "url": "doc://artigo.pdf",
      "title": "Título Correto",
      "content": "...",
      "published_at": "2025-01-15",  // ← Ajuste a data
      "metadata": {
        "language": "en",  // ← Ajuste o idioma
        "author": "John Doe",  // ← Adicione autor
        "category": "Technology"  // ← Adicione categoria
      }
    }
  ]
}
```

---

## ⚠️ Limitações

1. **Detecção de artigos**: Pode não funcionar perfeitamente para PDFs complexos
2. **Formatação**: Texto extraído pode perder formatação (negrito, itálico)
3. **Tabelas/Imagens**: Não são extraídas automaticamente

### Soluções:
- Para PDFs complexos: Use **Upstage Parser** primeiro
- Para múltiplos artigos: Use `--split` e revise o resultado
- Para ajustes finos: Edite o JSON manualmente após gerar

---

## ✅ Checklist de Conversão

- [ ] PDF extraído com sucesso
- [ ] JSON criado no formato correto
- [ ] Todos os artigos incluídos no array `results`
- [ ] Campos `url` e `content` preenchidos
- [ ] Metadados ajustados (`language`, `published_at`, etc.)
- [ ] Arquivo `.json` salvo
- [ ] Pronto para upload no Verba → A2 Results Ingestor

---

## 🚀 Fluxo Completo Recomendado

```
1. PDF original
   ↓
2. python scripts/pdf_to_a2_json.py documento.pdf
   ↓
3. Revisar documento_a2.json (ajustar títulos, datas, etc.)
   ↓
4. Verba → Import Data → A2 Results Ingestor
   ↓
5. Upload documento_a2.json
   ↓
6. Ativar "Enable ETL"
   ↓
7. Importar → ETL executa automaticamente (NER + Section Scope)
   ↓
8. ✅ Artigos no Weaviate com metadados de entidades e seções!
```

---

**Pronto! Agora você pode converter qualquer PDF para o formato A2 e usar ETL customizado!** 🎉

