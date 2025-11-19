# Onde Configurar Named Vectors?

## 🎯 Resposta Direta

**O flag de Named Vectors deveria estar em SETTINGS GERAIS** (configuração global do sistema), porque:

1. ✅ **Afeta criação de collections** (schema) - acontece durante primeiro import
2. ✅ **Afeta todos os imports** - preparação de textos especializados
3. ✅ **Afeta todas as buscas** - multi-vector search depende disso
4. ✅ **É uma configuração de infraestrutura** - não é específica de um documento ou query

---

## 📍 Onde Está Atualmente

### ❌ Atual: Apenas Variável de Ambiente

```bash
# .env ou variáveis de ambiente do sistema
ENABLE_NAMED_VECTORS=true
```

**Problemas:**
- ❌ Não aparece na interface do Verba
- ❌ Usuário precisa editar arquivo `.env` ou variáveis de ambiente
- ❌ Não é visível/descoberta
- ❌ Requer reiniciar aplicação para aplicar

---

## ✅ Onde Deveria Estar (Recomendação)

### Opção 1: Settings Gerais (RECOMENDADO) ⭐

**Localização:** Configurações → Settings → Advanced/Weaviate Settings

**Por quê:**
- ✅ Configuração global que afeta todo o sistema
- ✅ Visível na interface
- ✅ Fácil de encontrar e configurar
- ✅ Pode ser salva no Weaviate (collection `VERBA_CONFIGURATION`)

**Como apareceria:**
```
┌─────────────────────────────────────────┐
│ Settings → Advanced                     │
├─────────────────────────────────────────┤
│ Weaviate Advanced Features               │
│                                          │
│ ☑ Enable Named Vectors                  │
│   Creates collections with 3 specialized│
│   vectors: concept_vec, sector_vec,      │
│   company_vec                            │
│                                          │
│   ⚠️ Requires collection recreation      │
│   ⚠️ Increases memory usage (~3x)        │
│                                          │
│ [Save]                                  │
└─────────────────────────────────────────┘
```

### Opção 2: Settings de Import (ALTERNATIVA)

**Localização:** Configurações → Import → Advanced Options

**Por quê:**
- ✅ Afeta como collections são criadas durante import
- ✅ Contexto relevante (import é quando collections são criadas)

**Desvantagens:**
- ❌ Menos visível (usuário precisa ir em import)
- ❌ Pode ser confundido com configuração por documento

### Opção 3: Settings de Busca (NÃO RECOMENDADO)

**Localização:** Configurações → Retriever → EntityAware

**Por quê:**
- ❌ Multi-vector search já tem flag próprio ("Enable Multi-Vector Search")
- ❌ Named vectors são pré-requisito, não configuração de busca
- ❌ Confuso - named vectors afetam mais que busca

---

## 🔧 Como Implementar (Opção 1 - Settings Gerais)

### Passo 1: Adicionar ao VerbaManager

```python
# goldenverba/verba_manager.py

def create_config(self) -> dict:
    config = {
        # ... configurações existentes ...
        "Advanced": {
            "Enable Named Vectors": {
                "type": "bool",
                "value": os.getenv("ENABLE_NAMED_VECTORS", "false").lower() == "true",
                "description": "Enable named vectors (concept_vec, sector_vec, company_vec). Requires collection recreation.",
                "values": []
            }
        }
    }
    return config
```

### Passo 2: Modificar schema_updater.py

```python
# verba_extensions/integration/schema_updater.py

async def patched_verify_collection(...):
    # ... código existente ...
    
    # Verifica se named vectors estão habilitados
    # 1. Tenta pegar da configuração do Verba (se disponível)
    enable_named_vectors = False
    try:
        # Tenta obter configuração do VerbaManager
        from goldenverba.verba_manager import VerbaManager
        vm = VerbaManager()
        config = vm.create_config()
        if "Advanced" in config and "Enable Named Vectors" in config["Advanced"]:
            enable_named_vectors = config["Advanced"]["Enable Named Vectors"]["value"]
    except:
        pass
    
    # 2. Fallback para variável de ambiente
    if not enable_named_vectors:
        enable_named_vectors = os.getenv("ENABLE_NAMED_VECTORS", "false").lower() == "true"
    
    # ... resto do código ...
```

### Passo 3: Adicionar na Interface (Frontend)

```typescript
// frontend/app/components/Settings/SettingsComponent.tsx

// Adicionar seção "Advanced" ou "Weaviate Settings"
// Com checkbox para "Enable Named Vectors"
```

---

## 📊 Comparação das Opções

| Localização | Prós | Contras | Recomendação |
|------------|------|---------|--------------|
| **Settings Gerais** | ✅ Visível<br>✅ Contexto correto<br>✅ Fácil de encontrar | ⚠️ Precisa implementar | ⭐ **RECOMENDADO** |
| **Settings de Import** | ✅ Contexto relevante<br>✅ Fácil de implementar | ❌ Menos visível<br>❌ Pode confundir | ⚠️ Alternativa |
| **Settings de Busca** | ✅ Já tem flags relacionados | ❌ Contexto errado<br>❌ Confuso | ❌ Não recomendado |
| **Variável de Ambiente** | ✅ Já funciona<br>✅ Não precisa mudar código | ❌ Não visível<br>❌ Requer reiniciar | ⚠️ Atual (temporário) |

---

## 🎯 Recomendação Final

### Implementação Imediata (Sem Mudanças no Código)

**Manter como variável de ambiente** mas documentar claramente:
- ✅ Funciona imediatamente
- ✅ Não quebra nada
- ⚠️ Documentar bem onde configurar

### Implementação Ideal (Com Mudanças)

**Adicionar em Settings Gerais:**
- ✅ Melhor UX
- ✅ Visível e descoberta
- ✅ Pode ser salvo no Weaviate
- ⚠️ Requer mudanças no frontend e backend

---

## 📝 Exemplo de Implementação Rápida

### Opção Simples: Adicionar Aviso na Interface

Se não quiser implementar agora, pode adicionar um aviso na interface de import:

```typescript
// frontend/app/components/Ingestion/ConfigurationView.tsx

// Adicionar banner informativo:
{!process.env.ENABLE_NAMED_VECTORS && (
  <div className="alert alert-info">
    💡 <strong>Tip:</strong> Enable named vectors for better search results.
    Set <code>ENABLE_NAMED_VECTORS=true</code> in environment variables.
  </div>
)}
```

---

## 🔍 Verificação Atual

**Como verificar se está habilitado:**
```python
import os
print(f"ENABLE_NAMED_VECTORS: {os.getenv('ENABLE_NAMED_VECTORS', 'NOT SET')}")
```

**Onde configurar atualmente:**
1. Arquivo `.env` na raiz do projeto
2. Variáveis de ambiente do sistema
3. Variáveis de ambiente do Docker/Railway

---

## ⚠️ Importante

### Named Vectors e Collections

- ⚠️ **Named vectors só podem ser adicionados na CRIAÇÃO da collection**
- ⚠️ **Se collection já existe sem named vectors, precisa DELETAR e RECRIAR**
- ⚠️ **Isso significa perder todos os dados da collection**

### Quando Mudar o Flag

1. **Antes de criar collections** (primeiro uso)
   - ✅ Pode mudar livremente
   - ✅ Collections serão criadas com named vectors

2. **Depois de criar collections** (já tem dados)
   - ⚠️ Precisa deletar collections existentes
   - ⚠️ Reimportar todos os documentos
   - ⚠️ Perde dados temporariamente

---

## 📚 Referências

- **Código atual:** `verba_extensions/integration/schema_updater.py` linha 402
- **Documentação:** `docs/guides/ADVANCED_WEAVIATE_FEATURES.md`
- **Configuração:** `docs/guides/ONDE_CONFIGURAR_FEATURES_AVANCADAS.md`

---

**Última atualização:** Janeiro 2025

