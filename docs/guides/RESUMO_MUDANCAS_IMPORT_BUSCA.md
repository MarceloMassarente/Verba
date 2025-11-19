# Resumo das Mudanças: Import e Busca

## 🎯 Resumo Executivo

### O que mudou?
- ✅ **Import**: Preparação automática de textos especializados e mapeamento de frameworks
- ✅ **Busca**: Novas opções configuráveis no EntityAware Retriever
- ✅ **Configuração**: Variável de ambiente `ENABLE_NAMED_VECTORS` e checkboxes na interface

### Onde ver?
- **Interface**: Configurações → Retriever → EntityAware
- **Variáveis**: `.env` ou variáveis de ambiente do sistema
- **Logs**: Durante import e busca (se debug habilitado)

---

## 📤 Import de Documentos - O que Mudou

### Antes (Sem Features Avançadas)

```
Usuário importa PDF
  ↓
Chunker quebra em chunks
  ↓
Chunks enviados para Weaviate
  ↓
Fim
```

**Propriedades do chunk:**
- Apenas propriedades padrão do Verba (chunk_id, content, doc_uuid, etc.)

### Depois (Com Features Avançadas)

```
Usuário importa PDF
  ↓
Chunker quebra em chunks
  ↓
[NOVO] Detecção de frameworks/empresas/setores
  ↓
[NOVO] Extração de textos especializados (se named vectors habilitados)
  ↓
[NOVO] Mapeamento para propriedades Weaviate (se collection suporta)
  ↓
Chunks enviados para Weaviate
  ↓
Fim
```

**Propriedades do chunk:**
- ✅ Propriedades padrão do Verba
- ✅ `frameworks`, `companies`, `sectors`, `framework_confidence` (se collection suporta)
- ✅ `concept_text`, `sector_text`, `company_text` (se named vectors habilitados)

### Mudanças Visíveis vs Invisíveis

#### ✅ Visível (mas opcional)
- Logs durante import (se debug habilitado):
  ```
  [Framework-Mapping] Mapeando frameworks...
  [Named-Vectors] Extraindo textos especializados...
  ```

#### 🔒 Invisível (automático)
- Patch temporário de `DataObject.__init__`
- Verificação de collection (tem named vectors? tem framework props?)
- Mapeamento de `chunk.meta` para propriedades Weaviate

---

## 🔍 Busca - O que Mudou

### Antes (Sem Features Avançadas)

```
Usuário faz query
  ↓
EntityAware Retriever busca
  ↓
Retorna chunks
```

**Configurações disponíveis:**
- Search Mode
- Limit Mode
- Alpha
- Enable Entity Filter
- Enable Semantic Search
- etc.

### Depois (Com Features Avançadas)

```
Usuário faz query
  ↓
[NOVO] Detecta se é query de agregação?
  ├─ Sim → Executa aggregation (se habilitado)
  └─ Não → Continua
  ↓
[NOVO] Detecta se query combina múltiplos aspectos?
  ├─ Sim → Usa multi-vector search (se habilitado)
  └─ Não → Busca normal
  ↓
Retorna chunks
```

**Configurações disponíveis (NOVAS):**
- ✅ **Enable Multi-Vector Search** (checkbox, default: false)
- ✅ **Enable Aggregation** (checkbox, default: false)
- ✅ **Enable Framework Filter** (checkbox, default: true) - melhorado

---

## 🎛️ Onde Configurar - Guia Visual

### 1. Variáveis de Ambiente

**Arquivo:** `.env` (na raiz do projeto)

```bash
# Habilitar named vectors (opcional)
ENABLE_NAMED_VECTORS=true
```

**Quando configurar:**
- ✅ ANTES de criar collections
- ✅ Se quiser usar multi-vector search

**O que faz:**
- Cria collections com named vectors
- Habilita propriedades de texto especializadas

---

### 2. Interface do Verba

**Caminho:** Configurações → Retriever → EntityAware

**Tela de configurações:**

```
┌─────────────────────────────────────────────────┐
│ EntityAware Retriever - Configurações           │
├─────────────────────────────────────────────────┤
│ Search Mode: [Hybrid Search ▼]                   │
│ Limit Mode: [Autocut ▼]                         │
│ Limit/Sensitivity: [1]                          │
│ Alpha: [0.6]                                    │
│ Enable Entity Filter: [✓]                       │
│ Entity Filter Mode: [adaptive ▼]                │
│ Enable Semantic Search: [✓]                     │
│ Enable Language Filter: [✓]                     │
│ Enable Query Rewriting: [ ]                     │
│ Enable Temporal Filter: [✓]                     │
│ Enable Framework Filter: [✓]                     │
│                                                  │
│ ⭐ Enable Multi-Vector Search: [ ] ← NOVO       │
│ ⭐ Enable Aggregation: [ ] ← NOVO               │
│                                                  │
│ [Salvar]                                        │
└─────────────────────────────────────────────────┘
```

**Onde encontrar:**
1. Abra o Verba
2. Clique em **Configurações** (ícone de engrenagem)
3. Selecione **Retriever** no menu lateral
4. Escolha **EntityAware** na lista
5. Role até ver as novas opções

---

## 📊 Fluxo Completo - Exemplo Prático

### Cenário 1: Import com Named Vectors

**Configuração:**
```bash
ENABLE_NAMED_VECTORS=true
```

**Ação:**
1. Usuário importa PDF "Relatório Varejo 2024.pdf"

**O que acontece (automático):**
1. Chunker detecta: frameworks=["SWOT"], companies=["Amazon"], sectors=["Varejo"]
2. Sistema extrai textos especializados:
   - `concept_text`: "SWOT análise estratégica..."
   - `sector_text`: "Varejo setor retail..."
   - `company_text`: "Amazon empresa..."
3. Sistema mapeia para propriedades Weaviate
4. Chunks são importados com todas as propriedades

**O usuário vê:**
- ✅ Import normal (sem mudanças visíveis)
- ✅ Logs opcionais (se debug habilitado)

---

### Cenário 2: Busca com Multi-Vector Search

**Configuração:**
- Interface: "Enable Multi-Vector Search" = ✓

**Ação:**
1. Usuário faz query: "Estratégia digital para bancos"

**O que acontece (automático):**
1. Sistema detecta:
   - Conceito: "Estratégia digital" → `concept_vec`
   - Setor: "bancos" → `sector_vec`
2. Sistema usa multi-vector search:
   - Busca paralela em `concept_vec` e `sector_vec`
   - Combina resultados com RRF
3. Retorna chunks relevantes

**O usuário vê:**
- ✅ Resultados melhores (chunks que combinam ambos aspectos)
- ✅ Logs opcionais: "🎯 Multi-vector search habilitado"

---

### Cenário 3: Busca com Aggregation

**Configuração:**
- Interface: "Enable Aggregation" = ✓

**Ação:**
1. Usuário faz query: "Quantos documentos sobre SWOT?"

**O que acontece (automático):**
1. Sistema detecta: query de agregação
2. Sistema executa aggregation:
   - Conta chunks com `frameworks` contendo "SWOT"
3. Retorna resultado analítico

**O usuário vê:**
- ✅ Resposta: "Resultados de agregação: {total_count: 42}"
- ✅ Logs opcionais: "✅ Aggregation executada"

---

## 🔍 Como Verificar se Está Funcionando

### 1. Verificar Named Vectors

**No Python console:**
```python
from verba_extensions.integration.schema_updater import get_vector_config
vector_config = get_vector_config(enable_named_vectors=True)
if vector_config:
    print("✅ Named vectors configurados")
```

**Na interface:**
- Verifique se collection foi criada com named vectors
- Verifique logs durante criação de collection

### 2. Verificar Configurações do Retriever

**Na interface:**
1. Vá para Configurações → Retriever → EntityAware
2. Verifique se aparecem:
   - ✅ "Enable Multi-Vector Search"
   - ✅ "Enable Aggregation"
3. Ative se quiser usar

### 3. Verificar Logs

**Durante import:**
```
[Named-Vectors] Extraindo textos especializados...
[Framework-Mapping] Mapeando frameworks...
```

**Durante busca:**
```
🎯 Multi-vector search habilitado
✅ Aggregation executada
```

---

## ⚠️ Importante

### Named Vectors
- ⚠️ **Deve ser configurado ANTES de criar collections**
- ⚠️ Se collection já existe sem named vectors, precisa recriar
- ⚠️ Overhead de memória: ~3x (3 vetores vs 1)

### Multi-Vector Search
- ⚠️ **Só funciona se named vectors estão habilitados**
- ⚠️ **Só é usado quando query combina múltiplos aspectos**
- ⚠️ Overhead de latência: ~2x (busca paralela)

### Aggregation
- ✅ Funciona independente de named vectors
- ✅ **Só é usado quando query é analítica**
- ✅ Fallback automático para HTTP se gRPC falhar

---

## 📝 Checklist Rápido

### Para Usar Named Vectors + Multi-Vector Search

- [ ] Configurar `ENABLE_NAMED_VECTORS=true` (antes de criar collections)
- [ ] Recriar collections (se já existem)
- [ ] Ativar "Enable Multi-Vector Search" na interface
- [ ] Importar documentos
- [ ] Fazer queries que combinam múltiplos aspectos

### Para Usar Aggregation

- [ ] Ativar "Enable Aggregation" na interface
- [ ] Fazer queries analíticas ("quantos", "count", etc.)

### Para Usar Framework Filter

- [ ] Ativar "Enable Framework Filter" na interface (já vem ativado)
- [ ] Importar documentos (frameworks são detectados automaticamente)
- [ ] Fazer queries mencionando frameworks/empresas/setores

---

**Última atualização:** Janeiro 2025

