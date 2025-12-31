# 📚 Índice Centralizado de Documentação

Este documento serve como índice centralizado de toda a documentação do projeto Verba customizado.

## 🎯 Documentação Essencial

### 📁 **Organização e Navegação**
- **[INDICE_DOCUMENTACAO.md](INDICE_DOCUMENTACAO.md)** ⭐ Este arquivo - Índice centralizado
- **[README_ORGANIZACAO.md](README_ORGANIZACAO.md)** ⭐ Guia de organização do projeto
- **[README_PATCHES.md](README_PATCHES.md)** ⭐ Guia rápido de patches

### 📋 **Análise e Comparação**
- **[ANALISE_COMPARATIVA_VERBA_OFFICIAL_VS_CUSTOM.md](ANALISE_COMPARATIVA_VERBA_OFFICIAL_VS_CUSTOM.md)** ⭐
  - Comparação detalhada com Verba oficial
  - Avaliação de documentação e organização
  - Recomendações de melhoria

- **[RESUMO_COMPARACAO_VERBA.md](RESUMO_COMPARACAO_VERBA.md)** ⭐
  - Resumo executivo da comparação
  - Principais pontos e avaliações

- **[COMPARACAO_VERBA_NATIVO_VS_ATUAL.md](COMPARACAO_VERBA_NATIVO_VS_ATUAL.md)**
  - Comparação funcional detalhada
  - Métricas de performance

### 🔧 **Patches e Mudanças**
- **[README_PATCHES.md](README_PATCHES.md)** ⭐ Guia rápido de patches
- **[patches/README.md](patches/README.md)** ⭐ Sistema de versionamento
- **[patches/v2.1.3/README.md](patches/v2.1.3/README.md)** ⭐ Patches por versão
- **[LOG_COMPLETO_MUDANCAS.md](LOG_COMPLETO_MUDANCAS.md)** ⭐ ESSENCIAL
  - Lista completa de todas as mudanças no core
  - Código antes/depois
  - Localização exata de cada mudança

- **[PATCHES_VERBA_WEAVIATE_V4.md](PATCHES_VERBA_WEAVIATE_V4.md)** ⭐ ESSENCIAL
  - Patches detalhados para Weaviate v4
  - Código completo de cada patch
  - Troubleshooting

- **[GUIA_APLICAR_PATCHES_UPDATE.md](GUIA_APLICAR_PATCHES_UPDATE.md)** ⭐ ESSENCIAL
  - Guia passo a passo para aplicar patches
  - Checklist completo
  - Resolução de conflitos

- **[patches/v2.1.3/README.md](patches/v2.1.3/README.md)** ⭐
  - Patches específicos para versão 2.1.3
  - Instruções de aplicação
  - Verificação pós-patch

### 🚀 **Sistema de Extensões**
- **[README_EXTENSOES.md](README_EXTENSOES.md)** ⭐ ESSENCIAL
  - Guia completo do sistema de extensões
  - Como criar plugins
  - Exemplos práticos

- **[GUIA_UPGRADE_AUTOMATICO.md](GUIA_UPGRADE_AUTOMATICO.md)**
  - Sistema de upgrade automático
  - Estratégias de compatibilidade
  - Versionamento de extensões

### 🔌 **Plugins e Componentes**
- **[GUIA_ENTITY_AWARE_RETRIEVER.md](GUIA_ENTITY_AWARE_RETRIEVER.md)**
  - Como usar EntityAware Retriever
  - Configuração e exemplos

- **[GUIA_USO_ENTITY_AWARE_RETRIEVER.md](GUIA_USO_ENTITY_AWARE_RETRIEVER.md)**
  - Guia de uso prático
  - Exemplos de queries

- **[verba_extensions/plugins/INTEGRATION_README.md](verba_extensions/plugins/INTEGRATION_README.md)**
  - Documentação de integração de plugins

- **[verba_extensions/plugins/LLM_METADATA_EXTRACTOR_README.md](verba_extensions/plugins/LLM_METADATA_EXTRACTOR_README.md)**
  - Documentação do LLM Metadata Extractor

### 📥 **ETL e Ingestão**
- **[GUIA_INGESTOR_UNIVERSAL.md](GUIA_INGESTOR_UNIVERSAL.md)**
  - Guia do ingestor universal
  - Como usar

- **[EXPLICACAO_FLUXO_COMPLETO_ETL.md](EXPLICACAO_FLUXO_COMPLETO_ETL.md)**
  - Fluxo completo do ETL
  - Explicação detalhada

- **[GUIA_QUAL_INGESTOR_USAR.md](GUIA_QUAL_INGESTOR_USAR.md)**
  - Qual ingestor usar em cada caso

- **[GUIA_CONVERTER_PDF_PARA_JSON.md](GUIA_CONVERTER_PDF_PARA_JSON.md)**
  - Como converter PDF para JSON A2

- **[ANALISE_ETL_ENTITIES.md](ANALISE_ETL_ENTITIES.md)**
  - Análise do sistema ETL de entidades

- **[ANALISE_ETL_ANTES_CHUNKING.md](ANALISE_ETL_ANTES_CHUNKING.md)** ⭐ NOVO
  - Análise de viabilidade ETL pré-chunking
  - Entity-aware chunking
  - Proposta de implementação

- **[verba_extensions/patches/README_PATCHES.md](verba_extensions/patches/README_PATCHES.md)** ⭐ NOVO
  - **Documentação completa de patches ETL e hooks**
  - Guia de reaplicação após upgrade
  - Troubleshooting de patches

- **[COMO_ETL_FUNCIONA_POR_CHUNKER.md](COMO_ETL_FUNCIONA_POR_CHUNKER.md)** ⭐ NOVO
- **[SCHEMA_ETL_AWARE_UNIVERSAL.md](SCHEMA_ETL_AWARE_UNIVERSAL.md)** ⭐ NOVO - Schema único para chunks normais E ETL-aware
  - **Como o ETL funciona baseado no chunker escolhido**
  - Diferenças entre chunkers
  - Qual chunker aproveita melhor o ETL pré-chunking

### 🗄️ **Weaviate e Conexão**
- **[PATCHES_VERBA_WEAVIATE_V4.md](PATCHES_VERBA_WEAVIATE_V4.md)** ⭐ ESSENCIAL
  - Patches para Weaviate v4

- **[GUIA_WEAVIATE_V3.md](GUIA_WEAVIATE_V3.md)**
  - Como usar com Weaviate v3

- **[REFATORACAO_WEAVIATE_V4.md](REFATORACAO_WEAVIATE_V4.md)**
  - Refatoração para Weaviate v4

- **[CORRECAO_CONEXAO_WEAVIATE.md](CORRECAO_CONEXAO_WEAVIATE.md)**
  - Correções de conexão

- **[CONFIGURACAO_WEAVIATE_RAILWAY.md](CONFIGURACAO_WEAVIATE_RAILWAY.md)**
  - Configuração para Railway

### 🚂 **Railway e Deploy**
- **[GUIA_DEPLOY_RAILWAY.md](GUIA_DEPLOY_RAILWAY.md)**
  - Guia de deploy no Railway

- **[GUIA_CONEXAO_RAILWAY.md](GUIA_CONEXAO_RAILWAY.md)**
  - Como conectar no Railway

- **[GUIA_RAILWAY_WEAVIATE.md](GUIA_RAILWAY_WEAVIATE.md)**
  - Configuração Weaviate no Railway

- **[RAILWAY_SETUP.md](RAILWAY_SETUP.md)**
  - Setup completo Railway

- **[CONFIGURACAO_FINAL_RAILWAY.md](CONFIGURACAO_FINAL_RAILWAY.md)**
  - Configuração final

### 🐳 **Docker**
- **[GUIA_DOCKER.md](GUIA_DOCKER.md)**
  - Guia Docker

- **[INSTALACAO_DOCKER.md](INSTALACAO_DOCKER.md)**
  - Instalação Docker

- **[GUIA_WEAVIATE_DOCKER.md](GUIA_WEAVIATE_DOCKER.md)**
  - Weaviate com Docker

- **[README_DOCKER_WEAVIATE.md](README_DOCKER_WEAVIATE.md)**
  - Docker e Weaviate

- **[DOCKERFILE_VS_COMPOSE.md](DOCKERFILE_VS_COMPOSE.md)**
  - Diferenças Dockerfile vs Compose

### 🔍 **Análises e Arquitetura**
- **[ANALISE_PROJETO.md](ANALISE_PROJETO.md)**
  - Análise completa do projeto

- **[TECHNICAL.md](TECHNICAL.md)**
  - Documentação técnica oficial

- **[FRONTEND.md](FRONTEND.md)**
  - Documentação do frontend

### 💬 **Chat e Queries**
- **[COMO_FUNCIONA_HOJE_CHAT.md](COMO_FUNCIONA_HOJE_CHAT.md)**
  - Como funciona o chat

- **[FLUXO_COMPLETO_CHAT.md](FLUXO_COMPLETO_CHAT.md)**
  - Fluxo completo do chat

- **[VERBA_QUERIES_AVANCADAS.md](VERBA_QUERIES_AVANCADAS.md)**
  - Queries avançadas

- **[QUERY_PARSING_STRATEGY.md](QUERY_PARSING_STRATEGY.md)**
  - Estratégia de parsing de queries

- **[ENTIDADE_VS_SEMANTICA.md](ENTIDADE_VS_SEMANTICA.md)**
  - Entidade vs semântica

- **[PROBLEMA_QUERY_SEMANTICA.md](PROBLEMA_QUERY_SEMANTICA.md)**
  - Problemas de query semântica

### 🧪 **Testes e Validação**
- **[GUIA_TESTE_SISTEMA.md](GUIA_TESTE_SISTEMA.md)**
  - Como testar o sistema

- **[RESULTADO_TESTES.md](RESULTADO_TESTES.md)**
  - Resultados de testes

- **[RESUMO_TESTES.md](RESUMO_TESTES.md)**
  - Resumo de testes

### 📊 **Resumos e Roadmaps**
- **[RESUMO_FINAL.md](RESUMO_FINAL.md)**
  - Resumo final do projeto

- **[RESUMO_IMPLEMENTACAO.md](RESUMO_IMPLEMENTACAO.md)**
  - Resumo da implementação

- **[RESUMO_REFATORACAO.md](RESUMO_REFATORACAO.md)**
  - Resumo da refatoração

- **[RESUMO_AFINACAO_COMPLETA.md](RESUMO_AFINACAO_COMPLETA.md)**
  - Resumo de afinação

- **[HAYSTACK_ROADMAP_RESUMO.md](HAYSTACK_ROADMAP_RESUMO.md)**
  - Roadmap Haystack

### 🛠️ **Scripts e Automação**
- **[SCRIPTS_README.md](SCRIPTS_README.md)** ⭐ Documentação completa de scripts
- `scripts/apply_patches.py` - Aplicador de patches (melhorado)
- `scripts/verify_patches.py` - Verificador de patches (novo)

### 🔧 **Configuração e Uso**
- **[GUIA_SENTENCE_TRANSFORMERS.md](GUIA_SENTENCE_TRANSFORMERS.md)**
  - Como usar SentenceTransformers

- **[SOLUCAO_SENTENCE_TRANSFORMERS.md](SOLUCAO_SENTENCE_TRANSFORMERS.md)**
  - Solução SentenceTransformers

- **[EXPLICACAO_MODELOS_OPENAI.md](EXPLICACAO_MODELOS_OPENAI.md)**
  - Explicação dos modelos OpenAI

- **[GUIA_USO_LABELS_CHAT.md](GUIA_USO_LABELS_CHAT.md)**
  - Como usar labels no chat

- **[GUIA_AFINACAO_SISTEMA.md](GUIA_AFINACAO_SISTEMA.md)**
  - Como afinar o sistema

### 📝 **Documentação Técnica**
- **[PYTHON_TUTORIAL.md](PYTHON_TUTORIAL.md)**
  - Tutorial Python

- **[CONTRIBUTING.md](CONTRIBUTING.md)**
  - Guia de contribuição

- **[CHANGELOG.md](CHANGELOG.md)**
  - Changelog do projeto

- **[README.md](README.md)**
  - README principal

## 🗂️ Organização por Categoria

### 📋 **Essencial para Updates**
1. `LOG_COMPLETO_MUDANCAS.md` ⭐
2. `PATCHES_VERBA_WEAVIATE_V4.md` ⭐
3. `GUIA_APLICAR_PATCHES_UPDATE.md` ⭐
4. `patches/v2.1.3/README.md` ⭐
5. `ANALISE_COMPARATIVA_VERBA_OFFICIAL_VS_CUSTOM.md` ⭐

### 🚀 **Sistema de Extensões**
1. `README_EXTENSOES.md` ⭐
2. `GUIA_UPGRADE_AUTOMATICO.md`
3. `GUIA_ENTITY_AWARE_RETRIEVER.md`

### 🔧 **Configuração e Deploy**
1. `GUIA_DEPLOY_RAILWAY.md`
2. `GUIA_DOCKER.md`
3. `CONFIGURACAO_WEAVIATE_RAILWAY.md`
4. `SCRIPTS_README.md` ⭐ (Novos scripts de verificação)

### 📚 **Referência Técnica**
1. `TECHNICAL.md`
2. `ANALISE_PROJETO.md`
3. `FRONTEND.md`

## 🔍 Busca Rápida

### Por Tópico

**Patches:**
- `LOG_COMPLETO_MUDANCAS.md`
- `PATCHES_VERBA_WEAVIATE_V4.md`
- `GUIA_APLICAR_PATCHES_UPDATE.md`
- `patches/v2.1.3/README.md`

**Extensões:**
- `README_EXTENSOES.md`
- `GUIA_UPGRADE_AUTOMATICO.md`

**Weaviate:**
- `PATCHES_VERBA_WEAVIATE_V4.md`
- `GUIA_WEAVIATE_V3.md`
- `REFATORACAO_WEAVIATE_V4.md`

**Railway:**
- `GUIA_DEPLOY_RAILWAY.md`
- `GUIA_CONEXAO_RAILWAY.md`
- `CONFIGURACAO_WEAVIATE_RAILWAY.md`

**Docker:**
- `GUIA_DOCKER.md`
- `INSTALACAO_DOCKER.md`
- `GUIA_WEAVIATE_DOCKER.md`

**ETL:**
- `GUIA_INGESTOR_UNIVERSAL.md`
- `EXPLICACAO_FLUXO_COMPLETO_ETL.md`
- `ANALISE_ETL_ENTITIES.md`
- `ANALISE_ETL_ANTES_CHUNKING.md` ⭐ NOVO
- `verba_extensions/patches/README_PATCHES.md` ⭐ NOVO
- `COMO_ETL_FUNCIONA_POR_CHUNKER.md` ⭐ NOVO

## 📖 Guias de Leitura

### Para Desenvolvedores
1. `ANALISE_COMPARATIVA_VERBA_OFFICIAL_VS_CUSTOM.md`
2. `LOG_COMPLETO_MUDANCAS.md`
3. `README_EXTENSOES.md`
4. `TECHNICAL.md`

### Para Aplicar Updates
1. `RESUMO_COMPARACAO_VERBA.md` (resumo rápido)
2. `GUIA_APLICAR_PATCHES_UPDATE.md` (passo a passo)
3. `patches/v2.1.3/README.md` (patches específicos)

### Para Usar Extensões
1. `README_EXTENSOES.md`
2. `GUIA_ENTITY_AWARE_RETRIEVER.md`
3. `GUIA_USO_ENTITY_AWARE_RETRIEVER.md`

### Para Deploy
1. `GUIA_DEPLOY_RAILWAY.md`
2. `GUIA_DOCKER.md`
3. `CONFIGURACAO_WEAVIATE_RAILWAY.md`

## 🔄 Atualizações

Este índice é atualizado sempre que:
- Nova documentação é criada
- Documentação é reorganizada
- Nova versão de patches é adicionada

**Última atualização:** 2025-12-31

---

**Dica:** Use Ctrl+F (ou Cmd+F) para buscar rapidamente um tópico específico neste documento.

