# Onde Configurar as Features Avançadas Weaviate

## 📍 Localização na Interface do Verba

### 1. EntityAware Retriever - Configurações

As novas features são configuráveis na interface do Verba, na seção de configurações do **EntityAware Retriever**.

**Como acessar:**
1. Abra o Verba
2. Vá para **Configurações** (Settings)
3. Selecione **Retriever**
4. Escolha **EntityAware** como retriever
5. Role até as opções de configuração

### 2. Configurações Disponíveis (Organizadas em Blocos)

As configurações agora estão organizadas em **4 blocos hierárquicos** com validação automática:

#### **Bloco 1: Busca Fundamental**
- **Search Mode**: Modo de busca (Hybrid Search)
- **Limit Mode**: Método de limitação (Autocut/Fixed)
- **Limit/Sensitivity**: Valor de limite ou sensibilidade
- **Alpha**: Balance entre BM25 (0.0) e Vector (1.0)
- **Reranker Top K**: Número de chunks após reranking

#### **Bloco 2: Filtros**
- **Enable Entity Filter**: Filtro por entidades
- **Entity Filter Mode**: Estratégia (strict/boost/adaptive/hybrid)
- **Enable Semantic Search**: Busca semântica
- **Enable Language Filter**: Filtro por idioma
- **Enable Temporal Filter**: Filtro por data
- **Date Field Name**: Nome do campo de data
- **Enable Framework Filter**: Filtro por frameworks/setores/empresas

#### **Bloco 3: Modo de Busca (Hierárquico - Escolha UM)**
- **Two-Phase Search Mode**: auto/enabled/disabled
  - ⚠️ **Auto-desabilita**: Entity Filter (redundante)
- **Enable Multi-Vector Search**: Busca em named vectors
  - ⚠️ **Requer**: Enable Named Vectors (global)
- **Enable Aggregation**: Queries de agregação/analytics
  - ⚠️ **Auto-desabilita**: Entity Filter, Two-Phase, Multi-Vector

#### **Bloco 4: Otimizações**
- **Enable Query Expansion**: Expansão de queries (3-5 variações)
- **Enable Dynamic Alpha**: Alpha dinâmico baseado em tipo de query
- **Enable Relative Score Fusion**: Fusão de scores melhorada
- **Enable Query Rewriting**: Query Rewriter (fallback)
- **Query Rewriter Cache TTL**: Cache TTL em segundos
- **Chunk Window**: Chunks vizinhos a retornar

> **📖 Para detalhes completos sobre blocos e validação, veja:** [Configuração Hierárquica](./CONFIGURACAO_HIERARQUICA.md)

---

## 🔧 Variáveis de Ambiente

### ENABLE_NAMED_VECTORS

**Onde configurar:**
- Arquivo `.env` na raiz do projeto
- Variáveis de ambiente do sistema
- Variáveis de ambiente do Docker/Railway

**Como configurar:**
```bash
# .env
ENABLE_NAMED_VECTORS=true
```

**O que faz:**
- Cria collections com named vectors (concept_vec, sector_vec, company_vec)
- Habilita propriedades de texto especializadas (concept_text, sector_text, company_text)
- **IMPORTANTE**: Deve ser configurado ANTES de criar collections

**Quando usar:**
- Quando você quer usar multi-vector search
- Quando seus documentos têm múltiplos aspectos (conceitos, setores, empresas)

---

## 📤 O que Mudou no Import de Documentos

### Mudanças Visíveis

#### 1. **Preparação de Textos Especializados** (Automático)

Durante o import, o sistema agora:
- ✅ Extrai textos especializados de cada chunk:
  - `concept_text`: frameworks + termos semânticos + texto base
  - `sector_text`: setores + texto base
  - `company_text`: empresas + texto base
- ✅ Armazena em `chunk.meta` antes de enviar para Weaviate
- ✅ Mapeia para propriedades Weaviate se collection suporta named vectors

**Onde ver:**
- Logs durante import: `[Named-Vectors] Extraindo textos especializados...`
- Propriedades do chunk em `chunk.meta` (se habilitado debug)

#### 2. **Mapeamento de Frameworks** (Automático)

Durante o import, o sistema agora:
- ✅ Detecta frameworks, empresas e setores durante chunking
- ✅ Armazena em `chunk.meta`: `frameworks`, `companies`, `sectors`, `framework_confidence`
- ✅ Mapeia para propriedades Weaviate se collection suporta

**Onde ver:**
- Logs durante import: `[Framework-Mapping] Mapeando frameworks...`
- Propriedades do chunk em `chunk.meta` (se habilitado debug)

### Mudanças NÃO Visíveis (Internas)

#### 1. **Patch de DataObject**

O sistema aplica um patch temporário em `DataObject.__init__` durante o import:
- Mapeia frameworks de `chunk.meta` para propriedades Weaviate
- Mapeia textos especializados de `chunk.meta` para propriedades Weaviate
- **Não afeta o usuário** - é transparente

#### 2. **Verificação de Collection**

Antes de importar, o sistema verifica:
- Se collection tem propriedades de framework
- Se collection tem named vectors
- **Não afeta o usuário** - é automático

---

## 🎯 Fluxo Completo

### 1. Configuração Inicial

```bash
# 1. Habilitar named vectors (opcional)
export ENABLE_NAMED_VECTORS="true"

# 2. Reiniciar Verba para aplicar
```

### 2. Import de Documento

**O que acontece:**
1. Usuário importa documento (PDF, DOCX, etc.)
2. Chunker detecta frameworks/empresas/setores
3. Sistema extrai textos especializados (se named vectors habilitados)
4. Sistema mapeia para propriedades Weaviate (se collection suporta)
5. Documento é importado normalmente

**O usuário vê:**
- ✅ Import normal (sem mudanças visíveis)
- ✅ Logs opcionais (se debug habilitado)

### 3. Configuração do Retriever

**Na interface do Verba:**
1. Vá para Configurações → Retriever → EntityAware
2. Ative "Enable Multi-Vector Search" (se quiser usar)
3. Ative "Enable Aggregation" (se quiser usar)
4. Salve configuração

### 4. Uso no Chat

**O que acontece:**
1. Usuário faz query no chat
2. Sistema detecta se query combina múltiplos aspectos
3. Se multi-vector habilitado E query apropriada:
   - Usa multi-vector search
4. Se aggregation habilitado E query é analítica:
   - Executa aggregation
5. Retorna resultados

**O usuário vê:**
- ✅ Resultados melhores (se features habilitadas)
- ✅ Logs opcionais (se debug habilitado)

---

## 📊 Comparação: Antes vs Depois

### Antes (Sem Features Avançadas)

**Import:**
- Chunks importados normalmente
- Apenas propriedades padrão do Verba

**Busca:**
- Busca simples (vetor único)
- Sem multi-vector search
- Sem aggregation

**Configuração:**
- Apenas configurações padrão do EntityAware Retriever

### Depois (Com Features Avançadas)

**Import:**
- ✅ Chunks com textos especializados (se named vectors habilitados)
- ✅ Chunks com frameworks/empresas/setores detectados
- ✅ Propriedades adicionais no Weaviate (se collection suporta)

**Busca:**
- ✅ Multi-vector search quando apropriado (se habilitado)
- ✅ Aggregation para queries analíticas (se habilitado)
- ✅ Filtros automáticos baseados em frameworks

**Configuração:**
- ✅ "Enable Multi-Vector Search" (novo)
- ✅ "Enable Aggregation" (novo)
- ✅ "Enable Framework Filter" (melhorado)

---

## 🔍 Como Verificar se Está Funcionando

### 1. Verificar Named Vectors

```python
# No Python console do Verba
from verba_extensions.integration.schema_updater import get_vector_config
vector_config = get_vector_config(enable_named_vectors=True)
if vector_config:
    print("✅ Named vectors configurados")
    print(f"Vetores: {list(vector_config.keys())}")
```

### 2. Verificar Collection

```python
# Verificar se collection tem named vectors
collection = client.collections.get("VERBA_Embedding_...")
config = await collection.config.get()
if hasattr(config, 'vector_config') and config.vector_config:
    print("✅ Collection tem named vectors")
```

### 3. Verificar Configurações do Retriever

Na interface do Verba:
1. Vá para Configurações → Retriever → EntityAware
2. Verifique se "Enable Multi-Vector Search" aparece
3. Verifique se "Enable Aggregation" aparece
4. Verifique se estão habilitados (se quiser usar)

### 4. Verificar Logs

Durante import:
```
[Named-Vectors] Extraindo textos especializados...
[Framework-Mapping] Mapeando frameworks...
```

Durante busca:
```
🎯 Multi-vector search habilitado
✅ Aggregation executada
```

---

## ⚠️ Importante

### Named Vectors

- **Deve ser configurado ANTES de criar collections**
- Se collection já existe sem named vectors, precisa recriar
- Overhead de memória: ~3x (3 vetores vs 1)

### Multi-Vector Search

- **Só funciona se named vectors estão habilitados**
- **Só é usado quando query combina múltiplos aspectos**
- Overhead de latência: ~2x (busca paralela)

### Aggregation

- **Funciona independente de named vectors**
- **Só é usado quando query é analítica**
- Fallback automático para HTTP se gRPC falhar

---

## 📝 Resumo

### Onde Configurar

1. **Variáveis de Ambiente**: `.env` ou sistema
   - `ENABLE_NAMED_VECTORS=true` (opcional)

2. **Interface do Verba**: Configurações → Retriever → EntityAware
   - "Enable Multi-Vector Search" (checkbox)
   - "Enable Aggregation" (checkbox)
   - "Enable Framework Filter" (checkbox)

### O que Mudou no Import

1. **Automático**: Preparação de textos especializados
2. **Automático**: Mapeamento de frameworks
3. **Transparente**: Não afeta o fluxo normal do usuário
4. **Opcional**: Só acontece se features estão habilitadas

### O que Mudou na Busca

1. **Configurável**: Multi-vector search e aggregation são opcionais
2. **Automático**: Detecção de quando usar
3. **Transparente**: Usuário vê apenas resultados melhores

---

**Última atualização:** Janeiro 2025

