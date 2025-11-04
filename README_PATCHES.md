# 🔧 Documentação de Patches - Guia Rápido

Este é um guia rápido para aplicar patches após atualizar o Verba. Para documentação completa, veja os documentos listados abaixo.

## 🚀 Quick Start

### 1. Identificar Versão do Verba

```bash
pip show goldenverba | grep Version
# Ou
python -c "import setup; print(setup.version)"
```

### 2. Aplicar Patches Automáticos

```bash
# Verificar o que será feito (dry-run)
python scripts/apply_patches.py --version 2.1.3 --dry-run

# Aplicar patches automáticos
python scripts/apply_patches.py --version 2.1.3

# Aplicar automaticamente sem perguntas
python scripts/apply_patches.py --version 2.1.3 --auto
```

### 3. Verificar Patches Aplicados

```bash
# Verificar todos os patches
python scripts/verify_patches.py --version 2.1.3

# Verificar um patch específico
python scripts/verify_patches.py --version 2.1.3 --patch managers_connect_to_custom

# Gerar relatório detalhado
python scripts/verify_patches.py --version 2.1.3 --report
```

### 4. Aplicar Patches Manuais

Patches complexos precisam ser aplicados manualmente:

1. **Ver documentação específica:**
   ```bash
   cat patches/v2.1.3/README.md
   ```

2. **Seguir guia completo:**
   ```bash
   cat GUIA_APLICAR_PATCHES_UPDATE.md
   ```

3. **Ver detalhes técnicos:**
   ```bash
   cat PATCHES_VERBA_WEAVIATE_V4.md
   ```

## 📋 Checklist Rápido

- [ ] Backup do código atual
- [ ] Verificar versão do Verba
- [ ] Aplicar patches automáticos (`scripts/apply_patches.py`)
- [ ] Verificar patches aplicados (`scripts/verify_patches.py`)
- [ ] Aplicar patches manuais (se necessário)
- [ ] Testar conexão Weaviate
- [ ] Testar plugins
- [ ] Testar ETL

## 📚 Documentação Completa

### Essencial
- **[INDICE_DOCUMENTACAO.md](INDICE_DOCUMENTACAO.md)** - Índice centralizado
- **[LOG_COMPLETO_MUDANCAS.md](LOG_COMPLETO_MUDANCAS.md)** - Lista completa de mudanças
- **[GUIA_APLICAR_PATCHES_UPDATE.md](GUIA_APLICAR_PATCHES_UPDATE.md)** - Guia passo a passo
- **[patches/v2.1.3/README.md](patches/v2.1.3/README.md)** - Patches específicos por versão

### Técnica
- **[PATCHES_VERBA_WEAVIATE_V4.md](PATCHES_VERBA_WEAVIATE_V4.md)** - Detalhes técnicos Weaviate
- **[ANALISE_COMPARATIVA_VERBA_OFFICIAL_VS_CUSTOM.md](ANALISE_COMPARATIVA_VERBA_OFFICIAL_VS_CUSTOM.md)** - Análise comparativa
- **[verba_extensions/patches/README_PATCHES.md](verba_extensions/patches/README_PATCHES.md)** - **Documentação completa de patches ETL e hooks** ⭐ NOVO
- **[ANALISE_ETL_ANTES_CHUNKING.md](ANALISE_ETL_ANTES_CHUNKING.md)** - Análise de viabilidade ETL pré-chunking

### Scripts
- **[SCRIPTS_README.md](SCRIPTS_README.md)** - Documentação de scripts
- `scripts/apply_patches.py` - Aplicador de patches
- `scripts/verify_patches.py` - Verificador de patches

## 🎯 Patches por Complexidade

### ⭐ Baixa (Automático)
- ✅ Carregamento de extensões (`api.py`)
- ✅ SentenceTransformersEmbedder (`managers.py`)

### ⭐⭐ Média (Manual Simples)
- ⚠️ CORS middleware (`api.py`)
- ⚠️ `connect_to_cluster()` (`managers.py`)
- ⚠️ `get_models()` (`OpenAIGenerator.py`, `AnthropicGenerator.py`)
- ⚠️ **ETL Pré-Chunking Hook** (`verba_manager.py`) - Novo!

### ⭐⭐⭐ Alta (Manual com Hooks)
- 🔧 **Import Hook (ETL Pós-Chunking)** (`import_hook.py`) - Monkey patch
- 🔧 **Section-Aware Chunker Entity-Aware** (`section_aware_chunker.py`) - Modificado

### ⭐⭐⭐⭐⭐ Muito Alta (Manual Complexo)
- 🚨 `connect_to_custom()` (`managers.py`) - ~200 linhas reescritas

## ⚠️ Troubleshooting

### Erro: Versão não encontrada

```bash
# Verificar versão manualmente
python -c "import setup; print(setup.version)"
# Ou editar setup.py e ver linha: version="..."
```

### Erro: Patch já aplicado

Isso é normal! O script detecta patches já aplicados e os pula.

### Erro: Conflitos em merge manual

1. Ver diferenças entre versão oficial e customizada
2. Aplicar mudanças incrementalmente
3. Testar após cada mudança
4. Ver `GUIA_APLICAR_PATCHES_UPDATE.md` seção "Conflitos Comuns"

## 💡 Dicas

1. **Sempre faça backup** antes de aplicar patches
2. **Use `--dry-run`** primeiro para ver o que será feito
3. **Teste incrementalmente** após cada patch
4. **Documente mudanças** se ajustar algo manualmente

---

**Última atualização:** 2025-11-04  
**Versão atual suportada:** 2.1.3
