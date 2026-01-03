# 👔 Manual: Consulting RAG (Unified Ingestor & Voyage Contextual)

Este manual documenta as capacidades avançadas de RAG para consultoria implementadas no Verba, focando na ingestão de documentos complexos (PPTX/PDF) e embeddings contextuais.

---

## 1. 📥 Unified Consulting Ingestor for Verba

O **Unified Consulting Ingestor** é um reader universal projetado para lidar com apresentações e documentos complexos de consultoria.

### 🔄 Modos de Operação

O ingestor opera em 3 modos distintos, configuráveis na interface de **Import**, dependendo da sua necessidade de qualidade vs. custo.

| Modo | Configuração UI | Descrição | Custo | Qualidade Semântica |
|------|-----------------|-----------|-------|---------------------|
| **1. Visual API Premium** | `Enable Visual Analysis` = **ON** | Usa APIs avançadas (Contextual.AI, GPT-4V) para "ler" slides visualmente (gráficos, diagramas). | $$$ | ⭐⭐⭐⭐⭐ (Máxima) |
| **2. Docling API Remota** | `Enable Visual Analysis` = **OFF**<br>`Use Docling API` = **ON** | Envia o arquivo para um servidor Docling remoto (ex: self-hosted). Ótimo para OCR complexo sem custo de API externa. | $ (Infra) | ⭐⭐⭐⭐ (Alta) |
| **3. Extração Local (Padrão)** | `Enable Visual Analysis` = **OFF**<br>`Use Docling API` = **OFF** | Processamento 100% local usando `python-pptx` (PPTX) ou `pypdf` (PDF). Rápido e gratuito. | Grátis | ⭐⭐⭐ (Boa para texto) |

### ⚙️ Configuração detalhada

Ao selecionar "Unified Consulting Ingestor" na aba **Import**, você verá as seguintes opções:

*   **Enable Visual Analysis**: Liga o modo Premium.
    *   **Visual API Provider**: Escolha entre `Contextual.AI`, `GPT-4V`, etc.
    *   **Visual API URL**: Endpoint da API (ex: `https://api.contextual.ai/v1/documents`).
    *   **Visual API Key**: Sua chave de API.
*   **Use Docling API**: Liga o modo Docling Remoto (se Visual Analysis estiver OFF).
    *   **Docling API URL**: Endpoint do seu servidor Docling (ex: `http://localhost:5000`).
*   **Enable ETL**: (Padrão: ON) Habilita o enriquecimento automático de metadados.

### 📝 Formatos Suportados
*   **.pptx**: Extração slide-a-slide preservando estrutura.
*   **.pdf**: Extração de texto (OCR se via Docling/Visual API).
*   **.md**: Markdown estruturado (formato V019).

---

## 2. 🧠 Voyage Contextual Embeddings

O sistema utiliza os modelos **Voyage AI** de última geração, especificamente otimizados para RAG com contexto.

### 🚀 Modelo: `voyage-context-3`

Diferente de embeddings tradicionais que vetorizam chunks isoladamente, o `voyage-context-3`:
1.  Recebe o **chunk** E o **contexto do documento** (título, resumo, slides vizinhos).
2.  Gera um vetor que "sabe" de onde o chunk veio.
3.  Melhora drasticamente a recuperação de slides que dependem de contexto (ex: um slide com título "Resultados" ganha o contexto de "Resultados do Projeto X").

### 🔌 Hybrid Embedder Configuration

O **HybridConsultingEmbedder** gerencia isso automaticamente:

1.  **Voyage Model**: Selecione `voyage-context-3` (Recomendado).
2.  **Embedder Type**:
    *   **Voyage AI (Contextual)**: Usa a API oficial da Voyage para gerar embeddings contextuais.
    *   **Hybrid (Voyage + MiniLM)**: (Avançado) Usa Voyage para busca semântica e MiniLM local para vetores nomeados (named vectors) para economizar custos.

### 🔑 Requisitos
*   Environment Variable: `VOYAGE_API_KEY` deve estar configurada no `.env` ou no painel do Railway/Docker.

---

## 3. 🛠️ Solução de Problemas Comuns

### "Import failed with 0 documents" (PPTX)
*   **Causa**: O modo local (`python-pptx`) pode não conseguir ler imagens puras.
*   **Solução**:
    1.  Verifique se o PPTX contém texto selecionável, não apenas prints.
    2.  Se for scan/imagem, use o modo **Docling API** ou **Visual API Premium**.

### "API Key Error"
*   Verifique se a `VOYAGE_API_KEY` está correta.
*   Se usar Visual Analysis, verifique a `Visual API Key`.

---

**Versão da Documentação**: 1.1 (Atualizado em Jan 2026)
