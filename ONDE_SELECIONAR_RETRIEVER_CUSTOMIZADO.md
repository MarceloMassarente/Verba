# 📍 Onde Selecionar Retriever Customizado (EntityAware)

## 🎯 Localização na Interface

Na tela de **Config** que você está vendo:

1. **Role até a seção "Retriever"** (está abaixo de Generator)
2. **Clique no dropdown** que mostra atualmente "Advanced"
3. **Você deve ver:**
   - ✅ **Window** (padrão do Verba - também chamado "Advanced")
   - ✅ **EntityAware** ← Este é o customizado!

---

## 🔍 Se EntityAware Não Aparece

### **Possíveis Causas:**

1. **Plugins não foram carregados ainda**
   - Verifique logs do Railway
   - Deve aparecer: `✅ Retriever adicionado: EntityAware`

2. **Redeploy ainda não terminou**
   - Aguarde mais alguns minutos

3. **Cache do navegador**
   - Pressione **Ctrl+F5** (hard refresh)
   - Ou limpe cache

4. **Hook não foi aplicado**
   - Verifique se há erros nos logs

---

## ✅ Como Verificar se Está Funcionando

### **Nos Logs do Railway:**

Procure por:
```
✅ Extensoes carregadas: 4 plugins
✅ Plugin carregado: entity_aware_retriever
✅ Retriever adicionado: EntityAware
```

### **Na UI:**

1. Vá em **Settings** → **Config**
2. Role até **"Retriever"**
3. Abra o dropdown
4. Deve aparecer **"EntityAware"** na lista

---

## 🎯 Passos para Selecionar

### **Quando EntityAware Aparecer:**

1. **Na seção Retriever**, clique no dropdown
2. **Selecione "EntityAware"**
3. **Configure:**
   - ✅ **Enable Entity Filter**: Ative (checkbox)
   - **Limit/Sensitivity**: 32 (ajuste se necessário)
   - **Chunk Window**: 1
   - **Alpha**: 0.6
4. **Clique em "Save"** (botão ao lado de "Retriever Settings")
5. **Clique em "Save Config"** (botão no topo)

---

## ⚠️ Se Ainda Não Aparecer

### **Verificação Manual:**

1. **Verifique logs do Railway:**
   ```bash
   # Deve aparecer:
   ✅ Plugin carregado: entity_aware_retriever
   ✅ Retriever adicionado: EntityAware
   ```

2. **Teste via API:**
   ```python
   # Chame /api/get_rag_config
   # Verifique se "EntityAware" está em rag_config.Retriever.components
   ```

3. **Se não aparecer:**
   - O plugin pode não estar sendo carregado
   - Verifique se há erros nos logs
   - Pode precisar de ajuste no plugin_manager

---

## 💡 Nota sobre "Advanced"

**"Advanced"** é o nome interno do `WindowRetriever` padrão do Verba.

O **EntityAware** é um retriever diferente, com filtros entity-aware.

Ambos devem aparecer no dropdown após o redeploy completo!

---

**Aguarde o redeploy e verifique novamente!** 🚀

