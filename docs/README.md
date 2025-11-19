# Documentação Verba

Esta pasta contém toda a documentação do projeto Verba, organizada por categoria.

## Estrutura

### 📁 `guides/`
Guias práticos e tutoriais:
- Guias de configuração (Railway, Docker, Weaviate)
- Guias de uso (Entity Aware Retriever, Labels, etc.)
- Guias de teste e verificação
- Explicações de funcionalidades
- **ADVANCED_WEAVIATE_FEATURES.md** - Features avançadas Weaviate (Named Vectors, Multi-Vector Search, GraphQL Builder, Aggregation)

### 📁 `analyses/`
Análises técnicas e arquiteturais:
- Análises de componentes ETL
- Análises de otimização
- Arquiteturas e schemas
- Análises de features e componentes

### 📁 `diagnostics/`
Documentação de diagnósticos:
- Diagnósticos de problemas
- Relatórios de fragmentação
- Análises de erros

### 📁 `troubleshooting/`
Soluções para problemas comuns:
- Problemas identificados
- Soluções implementadas
- Troubleshooting guides

### 📁 `changelogs/`
Histórico de mudanças:
- Changelogs
- Resumos de implementação
- Logs de mudanças
- Correções aplicadas

### 📁 `comparisons/`
Comparações e avaliações:
- Comparações entre versões
- Avaliações de features
- Comparações com outras soluções

### 📁 `integrations/`
Documentação de integrações:
- Integrações com componentes RAG2
- Integrações com GraphQL Builder
- Integrações com Tika
- Integrações com Haystack

### 📁 `assets/`
Recursos estáticos:
- PDFs de documentação
- Imagens e outros recursos

## Documentos Principais na Raiz de `docs/`

- `COMECE_AQUI.md` - Ponto de partida para novos usuários
- `INDICE_DOCUMENTACAO.md` - Índice completo da documentação
- `README_*.md` - READMEs específicos de componentes
- `TECHNICAL.md` - Documentação técnica
- `CONTRIBUTING.md` - Guia de contribuição

## Como Navegar

1. **Começando?** Leia `COMECE_AQUI.md`
2. **Quer entender a arquitetura?** Veja `analyses/`
3. **Precisa resolver um problema?** Veja `troubleshooting/` e `diagnostics/`
4. **Quer implementar algo?** Veja `guides/`
5. **Quer ver o que mudou?** Veja `changelogs/`

## 🚀 Configurações Atuais

### ETL Entity-Aware Chunking (OTIMIZADO)
- **Status**: ✅ Habilitado e otimizado
- **Performance**: 10-15x mais rápido (30s → 2-3s)
- **Entidades**: Apenas ORG + PERSON/PER (exclui LOC/GPE)
- **Otimizações**: Binary search, deduplicação, normalização PT/EN
- **Documentação**: `guides/CONFIGURACAO_ETL_FINAL.md`

### Features Avançadas Weaviate ⭐ NOVO
- **Status**: ✅ Implementado e disponível
- **Named Vectors**: 3 vetores especializados (concept_vec, sector_vec, company_vec)
- **Multi-Vector Search**: Busca paralela com RRF para melhor recall
- **GraphQL Builder**: Queries dinâmicas com HTTP fallback
- **Aggregation**: Analytics com HTTP fallback quando gRPC falha
- **Framework Detection**: Detecção automática de frameworks/empresas/setores
- **Documentação**: `guides/ADVANCED_WEAVIATE_FEATURES.md`


