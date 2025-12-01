# Contextual.ai Ingestor Integrado - Guia de Uso

## 📋 Visão Geral

O **Contextual.ai Ingestor Integrado** é um componente único que combina Reader + Chunker otimizado especificamente para o formato retornado pela API Contextual.ai.

**Destaques:**
- ✅ Chunking hardcoded otimizado (não precisa escolher chunker)
- ✅ PPTX: 1 slide = 1 chunk (ideal para apresentações)
- ✅ PDF/DOCX: Respeita hierarquia Markdown (H1/H2/H3 como limites)
- ✅ Preserva descrições de gráficos completas
- ✅ ETL automático integrado

---

## 🚀 Quick Start

### 1. Configuração

**Variável de ambiente:**
```bash
CONTEXTUAL_AI_API_KEY=your_api_key_here
```

**Ou configure na interface do Verba:**
- O campo "API Key" aparecerá se não estiver configurado

### 2. Uso na Interface

1. Vá em **"Import Data"**
2. Selecione **"Contextual.ai Ingestor (Otimizado)"** como Reader
3. Configure parâmetros (opcional):
   - **Parse Mode**: `standard` (recomendado para documentos com gráficos)
   - **Figure Caption Mode**: `detailed` (descrições completas de gráficos)
   - **Enable Document Hierarchy**: `true` (preserva estrutura H1/H2/H3)
4. Faça upload do arquivo (PDF, DOCX, PPTX)
5. Clique em **"Import"**

**Nota:** Você não precisa escolher um chunker - o chunking já está integrado e otimizado!

---

## 📊 Como Funciona o Chunking

### Para PPTX (Apresentações)

**Estratégia: 1 slide = 1 chunk**

O ingestor detecta slides de três formas:

1. **Estrutura explícita:** Se a API retorna `result['slides']`
2. **Hierarquia:** Se a API retorna `result['hierarchy']['slides']`
3. **Fallback:** Divide por marcadores no Markdown (`---`, `## Slide`, etc.)

**Exemplo:**
```
Apresentação com 10 slides
→ 10 chunks criados (1 por slide)
→ Cada chunk contém conteúdo completo do slide + descrições de gráficos
```

### Para PDF/DOCX (Documentos)

**Estratégia: Respeita hierarquia Markdown (H1/H2/H3)**

O ingestor cria chunks respeitando a estrutura do documento:

1. **Hierarquia estruturada:** Se a API retorna `result['hierarchy']['sections']`
2. **Parse Markdown:** Detecta headers (`#`, `##`, `###`) e cria seções

**Exemplo:**
```markdown
# Título Principal
Conteúdo da seção principal...

## Subtítulo 1
Conteúdo do subtítulo 1...

### Sub-subtítulo
Conteúdo do sub-subtítulo...

## Subtítulo 2
Conteúdo do subtítulo 2...
```

**Resultado:**
- Chunk 1: Título Principal + Conteúdo
- Chunk 2: Subtítulo 1 + Conteúdo
- Chunk 3: Sub-subtítulo + Conteúdo
- Chunk 4: Subtítulo 2 + Conteúdo

---

## 🎨 Preservação de Descrições de Gráficos

### Como Funciona

Quando `figure_caption_mode=detailed`, a API Contextual.ai gera descrições completas de gráficos:

```markdown
![Gráfico: Vendas por Trimestre](figure_1.png)
**Descrição detalhada:** Este gráfico mostra as vendas da Apple por trimestre em 2024.
O Q1 teve $95 bilhões, Q2 teve $81 bilhões, Q3 teve $81.8 bilhões, e Q4 teve $89.5 bilhões.
Observa-se uma tendência de crescimento no final do ano.
```

**O ingestor preserva essas descrições:**
- ✅ Descrições completas são mantidas no chunk
- ✅ Chunking não corta descrições no meio
- ✅ ETL detecta entidades mencionadas nas descrições (ex: "Apple")

---

## 🔄 Integração com ETL

### Fluxo Automático

```
1. Contextual.ai Ingestor
   ↓
2. Parse via API + Chunking Otimizado
   ↓
3. Document com chunks + enable_etl=True
   ↓
4. Chunker padrão detecta chunks existentes → Pula chunking
   ↓
5. Embedding (vetorização)
   ↓
6. Import no Weaviate
   ↓
7. ETL Pós-Chunking (background)
   - Extrai entidades de cada chunk
   - Detecta seções
   - Atualiza chunks no Weaviate
```

### Metadados Preservados

O ingestor preserva metadados do Contextual.ai em `document.meta`:

```python
document.meta = {
    "enable_etl": True,
    "source_api": "contextual.ai",
    "chunking_strategy": "pptx",  # ou "hierarchy"
    "document_hierarchy": {...},  # Se enable_document_hierarchy=true
    "figure_descriptions": [...],  # Se figure_caption_mode=detailed
}
```

---

## ⚙️ Configurações

### Parse Mode

- **`basic`**: Texto simples (não permite hierarchy nem detailed figures)
- **`standard`**: Documentos complexos com imagens (recomendado)

### Figure Caption Mode

- **`concise`**: Descrições curtas
- **`detailed`**: Descrições completas (recomendado para RAG)

### Enable Document Hierarchy

- **`true`**: Preserva estrutura H1/H2/H3 (recomendado)
- **`false`**: Não preserva hierarquia

### Enable Split Tables

- **`true`**: Divide tabelas grandes em múltiplas
- **`false`**: Mantém tabelas inteiras (padrão)

### Page Range

- Formato: `"0-10,15-20"` ou `"0,1,2,5,6"`
- Vazio: Processa todas as páginas

---

## 📝 Exemplos de Uso

### Exemplo 1: PPTX com Gráficos

**Input:** `apresentacao_vendas.pptx` (10 slides, 3 com gráficos)

**Processo:**
1. Ingestor faz parse via API
2. Detecta 10 slides
3. Cria 10 chunks (1 por slide)
4. Chunks com gráficos contêm descrições completas

**Resultado:**
- 10 chunks no Weaviate
- Chunks 3, 5, 8 têm descrições de gráficos
- ETL detecta entidades mencionadas (ex: "Apple", "Microsoft")

### Exemplo 2: PDF com Hierarquia

**Input:** `relatorio_empresas.pdf` (com H1/H2/H3)

**Processo:**
1. Ingestor faz parse via API
2. Detecta hierarquia (H1/H2/H3)
3. Cria chunks respeitando seções
4. Preserva descrições de gráficos

**Resultado:**
- Chunks organizados por seção
- Cada seção (H1/H2/H3) vira chunk ou múltiplos chunks
- ETL detecta entidades por seção

---

## 🔍 Busca Entity-Aware

Após importação, você pode usar o **Entity-Aware Retriever** para buscar:

**Query:** "gráficos sobre vendas da Apple"

**Resultado:**
- Chunks com descrições de gráficos sobre Apple
- Filtrados por entidade (sem contaminação)
- Descrições completas disponíveis para o LLM

---

## ⚠️ Limitações e Pontos de Atenção

### 1. Endpoint de Resultado

**Problema:** Endpoint exato para buscar resultado do job precisa ser verificado.

**Solução:** O ingestor tenta múltiplos endpoints possíveis:
- `GET /parse/{job_id}`
- `GET /parse/status/{job_id}`
- `GET /jobs/{job_id}`

### 2. Detecção de Slides

**Problema:** Para PPTX, pode ser necessário inferir estrutura se API não retornar explícita.

**Solução:** Fallback para padrões de Markdown (`---`, `## Slide`, etc.)

### 3. Chunking Hardcoded

**Característica:** Chunking não é configurável via UI - é otimizado especificamente para Contextual.ai.

**Vantagem:** Sempre usa a melhor estratégia para o formato.

**Desvantagem:** Não pode customizar chunking (use Reader separado se precisar).

### 4. Limitações da API

- **Tamanho máximo:** 100MB por arquivo
- **Páginas máximas:** 400 páginas
- **Formatos:** PDF, DOC/DOCX, PPT/PPTX

---

## 🆚 Comparação: Ingestor vs Reader Separado

| Característica | Ingestor Integrado | Reader Separado |
|----------------|-------------------|-----------------|
| **Chunking** | Hardcoded otimizado | Escolhe chunker manualmente |
| **PPTX** | 1 slide = 1 chunk | Depende do chunker escolhido |
| **Hierarquia** | Respeita H1/H2/H3 | Depende do chunker escolhido |
| **Configuração** | Menos opções | Mais opções |
| **Uso** | Ideal para Contextual.ai | Ideal para customização |

**Recomendação:**
- Use **Ingestor Integrado** para PPTX e quando quer chunking otimizado automaticamente
- Use **Reader Separado** quando quer escolher chunker customizado (Entity-Semantic, etc.)

---

## 📚 Referências

- [Análise Contextual.ai Integration](../analyses/ANALISE_CONTEXTUAL_AI_INTEGRATION.md) - Análise completa da API
- [Integração Contextual.ai com ETL](./INTEGRACAO_CONTEXTUAL_AI_ETL.md) - Integração detalhada com ETL
- [Contextual.ai API Documentation](https://docs.contextual.ai/api-reference/parse/parse-file) - Documentação oficial

---

**Última atualização**: Janeiro 2025  
**Status**: Implementado e funcional  
**Compatibilidade**: Verba 2.1.x + ETL A2 Inteligente









