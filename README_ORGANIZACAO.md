# 📁 Guia de Organização do Projeto

Este documento explica a organização do projeto Verba customizado e como navegar na estrutura de arquivos.

## 🗂️ Estrutura de Diretórios

```
Verba/
├── 📋 Documentação Principal
│   ├── INDICE_DOCUMENTACAO.md          ⭐ Índice centralizado
│   ├── README_ORGANIZACAO.md            ⭐ Este arquivo
│   ├── ANALISE_COMPARATIVA_VERBA_OFFICIAL_VS_CUSTOM.md
│   ├── RESUMO_COMPARACAO_VERBA.md
│   └── LOG_COMPLETO_MUDANCAS.md
│
├── 🔧 Patches e Updates
│   ├── patches/                         ⭐ Sistema de versionamento
│   │   ├── README.md
│   │   └── v2.1.3/
│   │       └── README.md
│   ├── PATCHES_VERBA_WEAVIATE_V4.md
│   ├── GUIA_APLICAR_PATCHES_UPDATE.md
│   └── PATCH_CONNECT_TO_CUSTOM.md
│
├── 🚀 Extensões e Plugins
│   ├── verba_extensions/
│   │   ├── README.md                    (via README_EXTENSOES.md)
│   │   ├── plugins/
│   │   ├── compatibility/
│   │   └── integration/
│   ├── README_EXTENSOES.md
│   └── GUIA_UPGRADE_AUTOMATICO.md
│
├── 🛠️ Scripts
│   ├── scripts/
│   │   ├── apply_patches.py
│   │   ├── verify_patches.py
│   │   ├── create_schema.py
│   │   └── ...
│   └── SCRIPTS_README.md                ⭐ Documentação de scripts
│
├── 📚 Guias e Tutoriais
│   ├── GUIA_*.md                        (múltiplos guias)
│   ├── EXPLICACAO_*.md
│   └── COMO_*.md
│
├── 🔍 Análises e Comparações
│   ├── ANALISE_*.md
│   ├── COMPARACAO_*.md
│   └── RESUMO_*.md
│
├── 🗄️ Core do Verba (modificado)
│   └── goldenverba/
│       ├── server/api.py                (modificado)
│       └── components/managers.py       (modificado)
│
└── 📦 Outros
    ├── ingestor/                        (minisserviço separado)
    ├── frontend/                        (sem modificações)
    └── requirements-extensions.txt
```

## 📋 Categorização de Documentos

### ⭐ **Essencial para Updates**
Estes documentos são **ESSENCIAIS** ao atualizar o Verba:

1. **`INDICE_DOCUMENTACAO.md`** - Índice centralizado de toda documentação
2. **`LOG_COMPLETO_MUDANCAS.md`** - Lista completa de mudanças
3. **`PATCHES_VERBA_WEAVIATE_V4.md`** - Detalhes técnicos dos patches
4. **`GUIA_APLICAR_PATCHES_UPDATE.md`** - Guia passo a passo
5. **`patches/v2.1.3/README.md`** - Patches específicos por versão

### 🔧 **Sistema de Extensões**
Documentos sobre o sistema de plugins e extensões:

1. **`README_EXTENSOES.md`** - Guia completo do sistema
2. **`GUIA_UPGRADE_AUTOMATICO.md`** - Upgrade automático
3. **`GUIA_ENTITY_AWARE_RETRIEVER.md`** - Plugin específico

### 🛠️ **Scripts e Automação**
Documentação de scripts:

1. **`SCRIPTS_README.md`** - Documentação de todos os scripts
2. Scripts individuais em `scripts/`

### 📚 **Guias por Tópico**
Guias organizados por área:

- **Deploy:** `GUIA_DEPLOY_RAILWAY.md`, `GUIA_DOCKER.md`
- **Weaviate:** `GUIA_WEAVIATE_V3.md`, `REFATORACAO_WEAVIATE_V4.md`
- **ETL:** `GUIA_INGESTOR_UNIVERSAL.md`, `EXPLICACAO_FLUXO_COMPLETO_ETL.md`
- **Uso:** `GUIA_USO_ENTITY_AWARE_RETRIEVER.md`, `GUIA_USO_LABELS_CHAT.md`

## 🎯 Como Navegar

### Para Desenvolvedores

1. **Comece com:** `INDICE_DOCUMENTACAO.md`
2. **Entenda mudanças:** `ANALISE_COMPARATIVA_VERBA_OFFICIAL_VS_CUSTOM.md`
3. **Veja detalhes:** `LOG_COMPLETO_MUDANCAS.md`
4. **Aplique patches:** `GUIA_APLICAR_PATCHES_UPDATE.md`

### Para Aplicar Updates

1. **Resumo rápido:** `RESUMO_COMPARACAO_VERBA.md`
2. **Guia completo:** `GUIA_APLICAR_PATCHES_UPDATE.md`
3. **Patches específicos:** `patches/v2.1.3/README.md`
4. **Verificar:** `scripts/verify_patches.py`

### Para Usar Extensões

1. **Visão geral:** `README_EXTENSOES.md`
2. **Criar plugins:** `GUIA_UPGRADE_AUTOMATICO.md`
3. **Plugins específicos:** `GUIA_ENTITY_AWARE_RETRIEVER.md`

## 🔍 Busca Rápida

### Por Funcionalidade

**Patches:**
- `LOG_COMPLETO_MUDANCAS.md`
- `PATCHES_VERBA_WEAVIATE_V4.md`
- `patches/v2.1.3/README.md`

**Extensões:**
- `README_EXTENSOES.md`
- `GUIA_UPGRADE_AUTOMATICO.md`

**Scripts:**
- `SCRIPTS_README.md`
- `scripts/apply_patches.py`
- `scripts/verify_patches.py`

**Deploy:**
- `GUIA_DEPLOY_RAILWAY.md`
- `GUIA_DOCKER.md`

**Weaviate:**
- `PATCHES_VERBA_WEAVIATE_V4.md`
- `GUIA_WEAVIATE_V3.md`

### Por Tipo de Documento

**Análises:**
- `ANALISE_*.md`
- `COMPARACAO_*.md`

**Guias:**
- `GUIA_*.md`
- `EXPLICACAO_*.md`

**Resumos:**
- `RESUMO_*.md`
- `TODAS_MUDANCAS_VERBA.md`

## 📊 Sistema de Versionamento

### Patches Organizados por Versão

```
patches/
├── README.md              # Como usar sistema de patches
├── v2.1.3/               # Patches para Verba 2.1.3
│   └── README.md
└── v2.2.0/                # Patches para Verba 2.2.0 (quando disponível)
    └── README.md
```

**Vantagens:**
- ✅ Histórico de patches por versão
- ✅ Fácil de aplicar em versões específicas
- ✅ Documentação específica por versão

## 🚀 Fluxo de Trabalho Recomendado

### 1. Atualizar Verba

```bash
# 1. Verificar versão atual
pip show goldenverba | grep Version

# 2. Atualizar
pip install --upgrade goldenverba

# 3. Verificar nova versão
pip show goldenverba | grep Version
```

### 2. Aplicar Patches

```bash
# 1. Verificar patches disponíveis
cat patches/v2.1.3/README.md

# 2. Aplicar patches automáticos
python scripts/apply_patches.py --version 2.1.3

# 3. Verificar patches aplicados
python scripts/verify_patches.py --version 2.1.3

# 4. Aplicar patches manuais
# Seguir: GUIA_APLICAR_PATCHES_UPDATE.md
```

### 3. Verificar Sistema

```bash
# 1. Verificar conexão Weaviate
python test_weaviate_access.py

# 2. Verificar plugins
python -c "from verba_extensions.startup import initialize_extensions; ..."

# 3. Testar sistema completo
python run_all_tests.py
```

## 📝 Convenções de Nomenclatura

### Documentos

- **`GUIA_*.md`** - Guias passo a passo
- **`EXPLICACAO_*.md`** - Explicações detalhadas
- **`ANALISE_*.md`** - Análises técnicas
- **`COMPARACAO_*.md`** - Comparações
- **`RESUMO_*.md`** - Resumos executivos
- **`README_*.md`** - Documentação principal de área

### Scripts

- **`apply_*.py`** - Scripts que aplicam mudanças
- **`verify_*.py`** - Scripts que verificam estado
- **`create_*.py`** - Scripts que criam recursos
- **`test_*.py`** - Scripts de teste
- **`check_*.py`** - Scripts de verificação

## 🔄 Manutenção

### Quando Adicionar Nova Documentação

1. **Atualizar `INDICE_DOCUMENTACAO.md`**
2. **Adicionar ao README relevante** (se aplicável)
3. **Atualizar este documento** (se mudar estrutura)

### Quando Criar Nova Versão de Patches

1. **Criar diretório:** `patches/v2.2.0/`
2. **Copiar patches anteriores:** `cp -r patches/v2.1.3/* patches/v2.2.0/`
3. **Ajustar conforme necessário**
4. **Atualizar `patches/README.md`**

### Quando Atualizar Scripts

1. **Atualizar `SCRIPTS_README.md`**
2. **Documentar no cabeçalho do script**
3. **Adicionar exemplos de uso**

## ✅ Checklist de Organização

- [x] Índice centralizado de documentação
- [x] Sistema de versionamento de patches
- [x] Documentação de scripts
- [x] Guias organizados por categoria
- [x] Estrutura de diretórios clara
- [x] Convenções de nomenclatura
- [x] Fluxo de trabalho documentado

---

**Última atualização:** 2025-11-04  
**Versão:** 1.0

