# 📦 Sistema de Versionamento de Patches

Este diretório contém patches organizados por versão do Verba oficial.

## 📁 Estrutura

```
patches/
├── README.md                          # Este arquivo
├── v2.1.3/                            # Patches para Verba 2.1.3
│   ├── README.md                      # Documentação dos patches desta versão
│   ├── api.py.patch                   # Patch para api.py
│   ├── managers.py.patch              # Patch para managers.py
│   └── connect_to_custom_backup.py    # Backup do método completo
├── v2.2.0/                            # Patches para Verba 2.2.0 (quando disponível)
│   └── ...
└── templates/                         # Templates de patches
    ├── patch_template.md
    └── merge_template.py
```

## 🎯 Como Usar

### 1. Identificar Versão do Verba

```bash
# Verificar versão instalada
pip show goldenverba | grep Version

# Ou verificar no código
python -c "import goldenverba; print(goldenverba.__version__)"
```

### 2. Aplicar Patches da Versão

```bash
# Aplicar patches para versão específica
python scripts/apply_patches.py --version 2.1.3

# Ou manualmente
cd patches/v2.1.3
# Seguir instruções no README.md da versão
```

### 3. Criar Novos Patches para Nova Versão

Quando o Verba for atualizado:

1. **Criar diretório da nova versão:**
   ```bash
   mkdir patches/v2.2.0
   ```

2. **Copiar patches da versão anterior:**
   ```bash
   cp -r patches/v2.1.3/* patches/v2.2.0/
   ```

3. **Ajustar patches conforme necessário:**
   - Verificar se mudanças no Verba afetam os patches
   - Atualizar código conforme necessário
   - Documentar mudanças no README.md

4. **Testar:**
   ```bash
   python scripts/test_patches.py --version 2.2.0
   ```

## 📋 Checklist de Patch

Cada patch deve ter:

- [ ] **README.md** - Documentação completa
- [ ] **Código antes/depois** - Comparação clara
- [ ] **Localização exata** - Linhas ou funções afetadas
- [ ] **Dependências** - Outros patches necessários
- [ ] **Testes** - Como verificar se funciona
- [ ] **Rollback** - Como reverter se necessário

## 🔄 Fluxo de Atualização

```
1. Verba atualizado → v2.2.0
   ↓
2. Criar patches/v2.2.0/
   ↓
3. Copiar patches/v2.1.3/ → patches/v2.2.0/
   ↓
4. Ajustar patches conforme mudanças no Verba
   ↓
5. Testar patches
   ↓
6. Documentar mudanças
   ↓
7. Commitar patches
```

## 📚 Documentação Relacionada

- `../LOG_COMPLETO_MUDANCAS.md` - Lista completa de mudanças
- `../GUIA_APLICAR_PATCHES_UPDATE.md` - Guia passo a passo
- `../PATCHES_VERBA_WEAVIATE_V4.md` - Detalhes técnicos Weaviate v4

## ⚠️ Notas Importantes

1. **Sempre faça backup** antes de aplicar patches
2. **Teste em ambiente de desenvolvimento** primeiro
3. **Documente mudanças** em cada atualização
4. **Mantenha histórico** de patches aplicados

---

**Última atualização:** 2025-11-04  
**Versão atual suportada:** 2.1.3

