# Configuração Hierárquica do EntityAwareRetriever

## Visão Geral

As 21 flags de configuração do EntityAwareRetriever foram reorganizadas em **4 blocos hierárquicos** com validação automática e auto-desabilitação de flags conflitantes.

## Estrutura dos Blocos

### Bloco 1: Busca Fundamental

Configurações básicas que sempre estão disponíveis:

- **Search Mode**: Modo de busca (apenas "Hybrid Search" disponível)
- **Limit Mode**: Método de limitação (Autocut/Fixed)
- **Limit/Sensitivity**: Valor de limite ou sensibilidade
- **Alpha**: Balance entre BM25 (0.0) e Vector (1.0)
- **Reranker Top K**: Número de chunks após reranking

**Características:**
- Sempre visível
- Sem dependências
- Pode ser ajustado livremente

---

### Bloco 2: Filtros

Filtros independentes que podem ser combinados:

- **Enable Entity Filter**: Filtro por entidades
- **Entity Filter Mode**: Estratégia (strict/boost/adaptive/hybrid)
- **Enable Semantic Search**: Busca semântica
- **Enable Language Filter**: Filtro por idioma
- **Enable Temporal Filter**: Filtro por data
- **Date Field Name**: Nome do campo de data
- **Enable Framework Filter**: Filtro por frameworks/setores/empresas

**Características:**
- Independentes entre si
- Podem ser combinados
- Alguns podem ser desabilitados automaticamente por outros blocos

---

### Bloco 3: Modo de Busca (Hierárquico)

Escolha **UM** modo de busca (mutuamente exclusivos):

#### Modo Padrão (Entity Filter + Semantic)
- Usa Entity Filter e Semantic Search
- Padrão quando nenhum outro modo está ativo

#### Modo Dois-Fases (Two-Phase Search)
- **Two-Phase Search Mode**: auto/enabled/disabled
- **Enable Multi-Vector Search**: Busca em named vectors
- **Enable Relative Score Fusion**: Fusão de scores melhorada

**Regras:**
- Desabilita automaticamente: Entity Filter (redundante)
- Requer: Enable Named Vectors (global) para Multi-Vector Search

#### Modo Análise (Aggregation)
- **Enable Aggregation**: Queries de agregação/analytics

**Regras:**
- Desabilita automaticamente: Entity Filter, Two-Phase Search, Multi-Vector Search
- Modo alternativo: retorna análise, não chunks

---

### Bloco 4: Otimizações

Melhorias opcionais de performance e qualidade:

- **Enable Query Expansion**: Expansão de queries (3-5 variações)
- **Enable Dynamic Alpha**: Alpha dinâmico baseado em tipo de query
- **Enable Relative Score Fusion**: Fusão de scores melhorada
- **Enable Query Rewriting**: Query Rewriter (fallback)
- **Query Rewriter Cache TTL**: Cache TTL em segundos
- **Chunk Window**: Chunks vizinhos a retornar

**Características:**
- Opcionais
- Sem conflitos
- Melhoram resultados sem riscos

---

## Regras de Hierarquia

### Regra 1: Two-Phase Search desabilita Entity Filter

**Quando:** `Two-Phase Search Mode` ≠ "disabled"

**Ação automática:**
- `Enable Entity Filter` → `False`
- `Entity Filter Mode` → desabilitado visualmente

**Motivo:** Two-Phase Search já faz filtro de entidades na Fase 1, Entity Filter seria redundante.

**Aviso:** "Entity Filter desabilitado automaticamente (redundante com Two-Phase Search)"

---

### Regra 2: Aggregation desabilita todos os filtros

**Quando:** `Enable Aggregation` = `True`

**Ação automática:**
- `Enable Entity Filter` → `False`
- `Two-Phase Search Mode` → "disabled"
- `Enable Multi-Vector Search` → `False`

**Motivo:** Modo Agregação é alternativo, retorna análise ao invés de chunks.

**Aviso:** "Modo Agregação: filtros e outros modos desabilitados automaticamente"

---

### Regra 3: Multi-Vector Search requer Named Vectors

**Quando:** `Enable Multi-Vector Search` = `True`

**Verificação:**
- Se `Enable Named Vectors` (global) = `False` → desabilita Multi-Vector Search

**Motivo:** Multi-Vector Search precisa de named vectors no schema.

**Aviso:** "Multi-Vector Search requer Enable Named Vectors (global) - desabilitado automaticamente"

**Solução:** Habilitar em Settings → Advanced → Enable Named Vectors

---

### Regra 4: Dynamic Alpha ajusta Alpha automaticamente

**Quando:** `Enable Dynamic Alpha` = `True`

**Ação:**
- `Alpha` é usado apenas como base
- Valor final é calculado dinamicamente baseado em tipo de query

**Aviso:** "Se ativado, Alpha acima é apenas base (será ajustado automaticamente)"

---

## Como Funciona

### Backend (Validação Automática)

1. **No início de `retrieve()`:**
   ```python
   validated_config, warnings = self._apply_config_validation(config)
   ```

2. **Validação aplica regras:**
   - Detecta conflitos
   - Auto-desabilita flags conflitantes
   - Gera avisos para o usuário

3. **Config validado é usado:**
   - Resto do método usa `validated_config`
   - Avisos são logados via `msg.warn()`

### Frontend (Validação no Cliente)

1. **Componente `RetrieverConfigBlocks`:**
   - Agrupa flags por blocos
   - Mostra avisos inline
   - Desabilita campos visualmente quando conflito detectado

2. **Validação em tempo real:**
   - `useEffect` valida quando config muda
   - Auto-ajusta flags conflitantes
   - Mostra avisos contextuais

---

## Exemplos de Configuração

### Configuração Padrão (Busca Normal)

```python
{
    # Bloco 1: Fundamental
    "Search Mode": "Hybrid Search",
    "Limit Mode": "Autocut",
    "Limit/Sensitivity": 1,
    "Alpha": "0.6",
    "Reranker Top K": 5,
    
    # Bloco 2: Filtros
    "Enable Entity Filter": True,
    "Entity Filter Mode": "adaptive",
    "Enable Semantic Search": True,
    "Enable Language Filter": True,
    "Enable Temporal Filter": True,
    "Enable Framework Filter": True,
    
    # Bloco 3: Modo de Busca
    "Two-Phase Search Mode": "disabled",  # Modo padrão
    "Enable Aggregation": False,
    
    # Bloco 4: Otimizações
    "Enable Query Expansion": True,
    "Enable Dynamic Alpha": True,
    "Enable Relative Score Fusion": True,
}
```

**Resultado:** Busca híbrida com filtros, sem conflitos.

---

### Configuração Two-Phase (Consultoria)

```python
{
    # Bloco 3: Modo de Busca
    "Two-Phase Search Mode": "auto",  # ← Ativado
    "Enable Multi-Vector Search": True,
    "Enable Relative Score Fusion": True,
    
    # Bloco 2: Filtros
    "Enable Entity Filter": False,  # ← Desabilitado automaticamente
    # ... outros filtros podem ficar ligados
}
```

**Resultado:**
- Two-Phase Search ativo
- Entity Filter desabilitado automaticamente
- Multi-Vector Search ativo (se Named Vectors habilitado)

**Avisos:**
- "Entity Filter desabilitado automaticamente (redundante com Two-Phase Search)"

---

### Configuração Agregação (Análise)

```python
{
    # Bloco 3: Modo de Busca
    "Enable Aggregation": True,  # ← Ativado
    
    # Bloco 2: Filtros
    "Enable Entity Filter": False,  # ← Desabilitado automaticamente
    "Two-Phase Search Mode": "disabled",  # ← Desabilitado automaticamente
    "Enable Multi-Vector Search": False,  # ← Desabilitado automaticamente
}
```

**Resultado:**
- Modo Agregação ativo
- Todos os filtros desabilitados automaticamente
- Retorna análise, não chunks

**Avisos:**
- "Modo Agregação: filtros e outros modos desabilitados automaticamente"

---

## Troubleshooting

### Problema: "Multi-Vector Search requer Enable Named Vectors"

**Causa:** Named Vectors não está habilitado globalmente.

**Solução:**
1. Vá para Settings → Advanced
2. Ative "Enable Named Vectors"
3. **Importante:** Collections existentes precisam ser recriadas

---

### Problema: Entity Filter não funciona com Two-Phase

**Causa:** Two-Phase Search desabilita Entity Filter automaticamente (redundante).

**Solução:**
- Se quer usar Entity Filter → desabilite Two-Phase Search
- Se quer usar Two-Phase Search → Entity Filter será desabilitado automaticamente (OK)

---

### Problema: Aggregation não retorna chunks

**Causa:** Modo Agregação retorna análise, não chunks (comportamento esperado).

**Solução:**
- Desabilite "Enable Aggregation" para busca normal
- Use Aggregation apenas para queries de agregação ("quantos", "group by", etc.)

---

## Compatibilidade

### Backward Compatibility

- ✅ Configs existentes continuam funcionando
- ✅ Novos campos são opcionais
- ✅ Validação não quebra comportamento antigo

### Migração

Não é necessária migração. Sistema detecta automaticamente:
- Se flags têm metadados → aplica validação
- Se flags não têm metadados → funciona normalmente

---

## Arquivos Modificados

### Backend

1. `goldenverba/components/types.py`
   - Estendido `InputConfig` com campos opcionais

2. `verba_extensions/plugins/entity_aware_retriever.py`
   - Adicionado `_validate_config_hierarchy()`
   - Adicionado `_apply_config_validation()`
   - Atualizado `__init__()` com metadados
   - Integrado validação em `retrieve()`

### Frontend

1. `frontend/app/components/Chat/RetrieverConfigBlocks.tsx` (NOVO)
   - Componente de blocos hierárquicos
   - Validação no cliente

2. `frontend/app/components/Ingestion/ComponentView.tsx`
   - Integrado RetrieverConfigBlocks para Retriever

### Testes

1. `verba_extensions/tests/test_config_hierarchy.py` (NOVO)
   - Testes de validação de hierarquia

---

## Benefícios

### Para Usuários

✅ **Clarity** - Entende logo como funciona
✅ **Safety** - Impossível fazer combinações inválidas
✅ **Guidance** - Sistema sugere próximos passos
✅ **Fewer Mistakes** - Conflitos são auto-resolvidos

### Para Desenvolvedores

✅ **Maintainability** - Lógica clara e testável
✅ **Scalability** - Fácil adicionar novos modos
✅ **Debugging** - Estado é determinístico

---

## Próximos Passos

1. **Testar** configurações em diferentes cenários
2. **Ajustar** avisos e mensagens conforme feedback
3. **Expandir** para outros componentes (se necessário)
4. **Monitorar** uso e ajustar regras conforme necessário

---

## Referências

- [Análise de Flags de Configuração](./ANALISE_FLAGS_CONFIGURACAO.md)
- [Reorganização Hierárquica Proposta](./REORGANIZACAO_HIERARQUICA_FLAGS.md)
- [Explicação Detalhada de Funcionalidades](./EXPLICACAO_DETALHADA_FUNCIONALIDADES.md)

