# Reorganização Hierárquica de Flags de Configuração

## ✅ STATUS: IMPLEMENTADO E VALIDADO

**Data de Implementação:** Novembro 2025  
**Status:** ✅ Completo e testado (12 testes passando)

Esta proposta foi **implementada com sucesso** e está em produção. As flags foram reorganizadas em 4 blocos hierárquicos com validação automática.

> **📖 Para documentação completa da implementação, veja:** [Configuração Hierárquica](./CONFIGURACAO_HIERARQUICA.md)  
> **📊 Para relatório de validação, veja:** [Validation Report](../VALIDATION_REPORT.md)

---

## 🎯 Proposta Original: Estrutura em Blocos com Hierarquia

Ao invés de 21 flags independentes, organizar em **4 blocos principais** com **dependências automáticas**.

---

## 📐 Estrutura Proposta

```
┌─────────────────────────────────────────────────────────┐
│ BLOCO 1: BUSCA FUNDAMENTAL (sempre visível)             │
├─────────────────────────────────────────────────────────┤
│ ├─ Search Mode: [Hybrid Search]                         │
│ ├─ Limit Mode: [Autocut / Fixed]                        │
│ ├─ Limit/Sensitivity: [1]                               │
│ ├─ Alpha: [0.6]                                         │
│ └─ Reranker Top K: [5]                                  │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ BLOCO 2: FILTROS (independentes, ativar conforme        │
├─────────────────────────────────────────────────────────┤
│ ├─ ✓ Enable Entity Filter                               │
│ │  ├─ Entity Filter Mode: [adaptive▼]                   │
│ │  └─ ⚠️ AVISO: Desabilita Two-Phase (conflitante)     │
│ │                                                       │
│ ├─ ✓ Enable Semantic Search                             │
│ │                                                       │
│ ├─ ✓ Enable Language Filter                             │
│ │                                                       │
│ ├─ ✓ Enable Temporal Filter                             │
│ │  └─ Date Field Name: [chunk_date]                     │
│ │                                                       │
│ └─ ✓ Enable Framework Filter                            │
│                                                         │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ BLOCO 3: MODO DE BUSCA (escolher UM)                    │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ ⚫ MODO PADRÃO (Entity Filter + Semantic)                │
│  └─ [Entity Filter está ativado?] SIM → Usar este modo │
│                                                         │
│ ⚫ MODO DOIS-FASES (Consultoria)                         │
│  ├─ Two-Phase Search Mode: [auto▼]                      │
│  │  • auto: Ativa se detectar entidades                │
│  │  • enabled: Sempre ativo                            │
│  │  • disabled: Nunca ativo                            │
│  │                                                      │
│  ├─ ✓ Enable Multi-Vector Search                        │
│  │  └─ ⚠️ Requer: Enable Named Vectors (global)         │
│  │                                                      │
│  ├─ ✓ Enable Relative Score Fusion                      │
│  │  └─ (Melhor que RRF, preserva magnitude)             │
│  │                                                      │
│  └─ 🔴 AUTOMATICAMENTE DESABILITA:                      │
│     └─ Entity Filter (redundante)                       │
│                                                         │
│ ⚫ MODO ANÁLISE (Agregação)                              │
│  ├─ ✓ Enable Aggregation                                │
│  │                                                      │
│  └─ 🔴 AUTOMATICAMENTE DESABILITA:                      │
│     ├─ Entity Filter                                    │
│     ├─ Multi-Vector Search                              │
│     └─ Two-Phase Search                                 │
│                                                         │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ BLOCO 4: OTIMIZAÇÕES (opcional, melhoram resultados)    │
├─────────────────────────────────────────────────────────┤
│ ├─ ✓ Enable Query Expansion                             │
│ │  └─ (Gera variações, sem riscos)                      │
│ │                                                       │
│ ├─ ✓ Enable Dynamic Alpha                               │
│ │  └─ (Sobrescreve Alpha com base em query type)        │
│ │  └─ ⚠️ Se marcado: Alpha acima é apenas base         │
│ │                                                       │
│ ├─ ☐ Enable Query Rewriting (fallback)                  │
│ │  └─ Query Rewriter Cache TTL: [3600]                  │
│ │  └─ (Apenas se QueryBuilder falhar)                   │
│ │                                                       │
│ └─ Chunk Window: [1]                                    │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 🔄 Lógica de Hierarquia e Auto-Desabilitação

### Cenário 1: Usuário Ativa "Two-Phase Search Mode"

```python
# Código que executa na UI
if two_phase_mode != "disabled":
    # AUTOMATICAMENTE:
    entity_filter_enabled = False  # Desabilita (redundante)
    entity_filter_mode_disabled = True  # Desabilita campo
    multi_vector_search_enabled = True  # Sugere ligar (se named vectors disponível)
    relative_score_fusion_enabled = True  # Sugere ligar
    
    # AVISOS:
    show_warning("Two-Phase Search ativado")
    show_warning("Entity Filter automaticamente desabilitado (redundante)")
    show_info("Entity Filter Mode desabilitado (não aplicável)")
```

### Cenário 2: Usuário Ativa "Enable Aggregation"

```python
if aggregation_enabled:
    # AUTOMATICAMENTE DESABILITA:
    entity_filter_enabled = False
    semantic_search_enabled = False  # Faz menos sentido
    multi_vector_search_enabled = False
    two_phase_mode = "disabled"
    
    # MOSTRA AVISO:
    show_warning("Modo Agregação ativado - busca normal desabilitada")
    show_info("Configure filtros para agregação")
```

### Cenário 3: Usuário Ativa "Multi-Vector Search" SEM Named Vectors

```python
if multi_vector_search_enabled and not named_vectors_enabled_global:
    # AVISO CRÍTICO:
    show_error(
        "Multi-Vector Search requer Enable Named Vectors habilitado globalmente",
        "Vá para: Settings → Advanced → Enable Named Vectors",
        "Nota: Requer recriação de collections"
    )
    # DESABILITA:
    multi_vector_search_enabled = False
```

---

## 📋 Implementação em Python

### Estrutura de Configuração

```python
# Modelo de hierarquia
class RetrieverConfig:
    """Configuração com auto-desabilitação inteligente"""
    
    # BLOCO 1: Fundamental (sempre habilitado)
    search_mode = "Hybrid Search"  # Único valor disponível
    limit_mode = "Autocut"
    limit_sensitivity = 1
    alpha = 0.6
    reranker_top_k = 5
    
    # BLOCO 2: Filtros (independentes)
    enable_entity_filter = True
    entity_filter_mode = "adaptive"
    enable_semantic_search = True
    enable_language_filter = True
    enable_temporal_filter = True
    date_field_name = "chunk_date"
    enable_framework_filter = True
    
    # BLOCO 3: Modo de Busca (hierárquico)
    two_phase_search_mode = "disabled"  # "auto" | "enabled" | "disabled"
    enable_aggregation = False
    
    # BLOCO 4: Otimizações
    enable_query_expansion = True
    enable_dynamic_alpha = True
    enable_relative_score_fusion = True
    enable_query_rewriting = False  # Fallback
    query_rewriter_cache_ttl = 3600
    chunk_window = 1
    
    # Flags avançados
    enable_multi_vector_search = False
    
    def validate_and_auto_adjust(self):
        """Valida e auto-ajusta flags conflitantes"""
        
        # REGRA 1: Se Two-Phase ativado, desabilitar Entity Filter
        if self.two_phase_search_mode != "disabled":
            self.enable_entity_filter = False  # Auto-desabilita
            msg.warn("Entity Filter desabilitado (redundante com Two-Phase)")
        
        # REGRA 2: Se Aggregation ativado, desabilitar filtros
        if self.enable_aggregation:
            self.enable_entity_filter = False
            self.two_phase_search_mode = "disabled"
            self.enable_multi_vector_search = False
            msg.info("Modo Agregação: filtros desabilitados")
        
        # REGRA 3: Se Multi-Vector, verificar Named Vectors global
        if self.enable_multi_vector_search:
            if not GLOBAL_CONFIG.get("enable_named_vectors"):
                self.enable_multi_vector_search = False
                raise ConfigError(
                    "Multi-Vector requer Enable Named Vectors (global)",
                    "Configure em: Settings → Advanced → Enable Named Vectors"
                )
        
        # REGRA 4: Se Dynamic Alpha, avisar que Alpha é base
        if self.enable_dynamic_alpha:
            msg.info(f"Dynamic Alpha ativo: Alpha ({self.alpha}) é base apenas")
        
        return self
    
    def get_active_mode(self) -> str:
        """Detecta qual modo está ativo"""
        if self.enable_aggregation:
            return "aggregation"
        elif self.two_phase_search_mode != "disabled":
            return "two_phase"
        else:
            return "standard"
```

### Validação Automática

```python
# Integração no EntityAwareRetriever
class EntityAwareRetriever(Retriever):
    def __init__(self):
        super().__init__()
        self._setup_config()
        self._register_validation_hooks()
    
    def _register_validation_hooks(self):
        """Registra hooks para auto-ajustar quando flags mudam"""
        
        # Quando Two-Phase muda
        self.config["Two-Phase Search Mode"].on_change = self._handle_two_phase_change
        
        # Quando Aggregation muda
        self.config["Enable Aggregation"].on_change = self._handle_aggregation_change
        
        # Quando Multi-Vector muda
        self.config["Enable Multi-Vector Search"].on_change = self._handle_multi_vector_change
    
    def _handle_two_phase_change(self, new_value):
        """Executado quando Two-Phase muda"""
        if new_value != "disabled":
            # Auto-desabilitar Entity Filter
            self.config["Enable Entity Filter"].value = False
            self.config["Enable Entity Filter"].disabled = True
            msg.warn("✓ Entity Filter desabilitado automaticamente")
        else:
            # Re-habilitar Entity Filter
            self.config["Enable Entity Filter"].disabled = False
            msg.info("✓ Entity Filter re-habilitado")
    
    def _handle_aggregation_change(self, new_value):
        """Executado quando Aggregation muda"""
        if new_value:
            # Desabilitar tudo
            self.config["Enable Entity Filter"].value = False
            self.config["Enable Entity Filter"].disabled = True
            self.config["Two-Phase Search Mode"].disabled = True
            self.config["Enable Multi-Vector Search"].disabled = True
            msg.info("✓ Modo Agregação: filtros desabilitados")
        else:
            # Re-habilitar
            self.config["Enable Entity Filter"].disabled = False
            self.config["Two-Phase Search Mode"].disabled = False
            self.config["Enable Multi-Vector Search"].disabled = False
    
    def _handle_multi_vector_change(self, new_value):
        """Executado quando Multi-Vector muda"""
        if new_value:
            # Verificar Named Vectors global
            if not os.getenv("ENABLE_NAMED_VECTORS", "false").lower() == "true":
                self.config["Enable Multi-Vector Search"].value = False
                msg.error(
                    "Multi-Vector requer Enable Named Vectors (global)",
                    "Settings → Advanced → Enable Named Vectors"
                )
```

---

## 🎨 Mock de UI (Visão do Usuário)

### Estado 1: Busca Padrão (Padrão)

```
┌─ BUSCA FUNDAMENTAL ──────────────────────────────────┐
│ Search Mode: [Hybrid Search] (somente leitura)        │
│ Limit Mode: [Autocut ▼]                              │
│ Limit/Sensitivity: [1]                                │
│ Alpha: [0.6]                                          │
│ Reranker Top K: [5]                                   │
└──────────────────────────────────────────────────────┘

┌─ FILTROS DISPONÍVEIS ────────────────────────────────┐
│ ☑ Entity Filter Mode: [adaptive ▼]                   │
│ ☑ Semantic Search                                    │
│ ☑ Language Filter                                    │
│ ☑ Temporal Filter    Date Field: [chunk_date]        │
│ ☑ Framework Filter                                   │
└──────────────────────────────────────────────────────┘

┌─ MODO DE BUSCA ──────────────────────────────────────┐
│ ⭕ PADRÃO (Entity Filter + Semantic) ← Ativo          │
│ ⚪ DOIS-FASES (Multi-Vector)                          │
│ ⚪ ANÁLISE (Agregação)                                │
└──────────────────────────────────────────────────────┘

┌─ OTIMIZAÇÕES ────────────────────────────────────────┐
│ ☑ Query Expansion                                    │
│ ☑ Dynamic Alpha (Alpha é base: 0.6)                  │
│ ☐ Query Rewriting (Fallback)  Cache TTL: [3600]      │
│ Chunk Window: [1]                                    │
└──────────────────────────────────────────────────────┘
```

### Estado 2: Two-Phase Search Ativado

```
┌─ MODO DE BUSCA ──────────────────────────────────────┐
│ ⚪ PADRÃO                                             │
│ ⭕ DOIS-FASES (Multi-Vector) ← Ativo                 │
│    └─ Multi-Vector Search: [Habilitado]               │
│    └─ Relative Score Fusion: [Habilitado]             │
│    └─ ⚠️  Entity Filter foi desabilitado (redundante) │
│ ⚪ ANÁLISE                                            │
└──────────────────────────────────────────────────────┘
```

### Estado 3: Agregação Ativada

```
┌─ MODO DE BUSCA ──────────────────────────────────────┐
│ ⚪ PADRÃO                                             │
│ ⚪ DOIS-FASES (desabilitado)                          │
│ ⭕ ANÁLISE (Agregação) ← Ativo                        │
│    └─ 🔴 Filtros desabilitados: Entity Filter,        │
│       Multi-Vector, Two-Phase                        │
└──────────────────────────────────────────────────────┘

⚠️ AVISO: Modo Agregação ativado
Busca normal está desabilitada. Configure para queries de agregação.
```

---

## ✅ Benefícios da Reorganização

### Para o Usuário

1. **Clarity** - Entende logo como as coisas funcionam
2. **Safety** - Impossível fazer combinações inválidas
3. **Guidance** - Sistema sugere próximos passos
4. **Fewer Mistakes** - Conflitos são auto-resolvidos

### Para o Dev

1. **Maintainability** - Lógica clara e testável
2. **Scalability** - Fácil adicionar novos modos
3. **Debugging** - Estado é determinístico

---

## 🔧 Mudanças Necessárias no Código

### 1. InputConfig com Dependências

```python
class InputConfig:
    # Novo campo: dependências
    def __init__(self, ..., 
                 disabled_by: List[str] = None,
                 disables: List[str] = None):
        self.disabled_by = disabled_by  # Flags que desabilitam este
        self.disables = disables  # Flags que este desabilita
```

### 2. Validação Automática

```python
def apply_config(self, config_dict):
    """Aplica config e valida automaticamente"""
    self.config.update(config_dict)
    self._validate_hierarchy()
    self._auto_adjust_flags()
```

### 3. UI Component

```python
# Na UI, exibir blocos em abas/seções
# Com avisos inline quando conflito detectado
```

---

## 🎯 Conclusão

Ao reorganizar as flags em **4 blocos com hierarquia automática**:

✅ Reduz de 21 flags "independentes" para **4 modes inteligentes**
✅ Impossível fazer combinações inválidas
✅ UX muito mais clara
✅ Código mais testável e maintível

**Recomendação:** Implementar gradualmente:
1. Fase 1: Validação automática (sem UI changes)
2. Fase 2: UI com novos blocos
3. Fase 3: Auto-desabilitação

