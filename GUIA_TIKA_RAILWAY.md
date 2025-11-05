# 🚂 Configurar Tika no Railway

## ✅ Sim, Tika Pode Ser Configurado via Variável de Ambiente

O Tika já está configurado para usar variável de ambiente `TIKA_SERVER_URL` em todos os componentes.

---

## 🔧 Como Configurar no Railway

### **Passo 1: No Projeto Verba no Railway**

1. Vá em **Settings** (ícone de engrenagem)
2. Clique em **Variables**
3. Adicione a variável:

```bash
TIKA_SERVER_URL=http://192.168.1.197:9998
```

**OU** se o Tika estiver em outro serviço Railway:

```bash
# Se Tika estiver em outro projeto Railway
TIKA_SERVER_URL=https://tika-production-xxxx.up.railway.app

# OU se estiver no mesmo projeto (acesso interno)
TIKA_SERVER_URL=http://tika.railway.internal:9998
```

4. Salve (Railway faz redeploy automaticamente)

---

## 📋 Opções de Configuração

### **Opção 1: Tika em Servidor Separado (Seu Caso Atual)**

```bash
TIKA_SERVER_URL=http://192.168.1.197:9998
```

**Vantagens:**
- ✅ Tika rodando em servidor dedicado
- ✅ Pode ser acessado de qualquer lugar
- ✅ Mais controle sobre recursos

**Desvantagens:**
- ⚠️ Precisa de acesso de rede externa
- ⚠️ Pode ter latência maior

---

### **Opção 2: Tika como Serviço no Railway**

Se você quiser deployar Tika no Railway também:

1. Crie novo serviço no Railway
2. Use imagem Docker do Tika:
   ```dockerfile
   FROM apache/tika:latest
   ```
3. Configure variável no Verba:
   ```bash
   # Se no mesmo projeto Railway
   TIKA_SERVER_URL=http://tika.railway.internal:9998
   
   # Se em projeto separado
   TIKA_SERVER_URL=https://tika-production-xxxx.up.railway.app
   ```

---

### **Opção 3: Tika Local (Desenvolvimento)**

Para desenvolvimento local:

```bash
# No .env local
TIKA_SERVER_URL=http://localhost:9998
```

Ou deixe sem configurar (usa padrão `http://localhost:9998`)

---

## 🔍 Verificação

### **Após Configurar no Railway:**

1. **Verifique os logs do Verba:**
   ```
   [INFO] Tika fallback habilitado - formatos não suportados usarão Tika automaticamente
   ```

2. **Teste importando um PPTX:**
   - Use "Universal A2 (ETL Automático)" reader
   - Faça upload de um PPTX
   - Deve ver nos logs: `[UNIVERSAL-READER] Usando Tika para 'arquivo.pptx'`

3. **Se Tika não estiver disponível:**
   - Sistema continua funcionando normalmente
   - Usa métodos nativos (BasicReader)
   - Apenas formatos não suportados (PPTX, etc.) não funcionarão

---

## ⚙️ Comportamento por Componente

### **1. Tika Reader Plugin**
- Lê `TIKA_SERVER_URL` do config da UI **OU** variável de ambiente
- Se configurado na UI, usa o valor da UI
- Se não configurado na UI, usa `TIKA_SERVER_URL` do ambiente
- Padrão: `http://localhost:9998`

### **2. Tika Fallback Patch**
- **Sempre** usa `TIKA_SERVER_URL` do ambiente
- Padrão: `http://localhost:9998`
- Não tem configuração via UI

### **3. Universal Reader**
- **Sempre** usa `TIKA_SERVER_URL` do ambiente
- Padrão: `http://localhost:9998`
- Configuração "Use Tika When Available" na UI apenas habilita/desabilita uso

---

## 🎯 Prioridade de Configuração

```
1. UI Config (Tika Reader Plugin) → Se configurado na UI
2. TIKA_SERVER_URL (variável de ambiente) → Se não configurado na UI
3. http://localhost:9998 → Padrão se nada configurado
```

---

## 📊 Exemplo de Configuração Completa no Railway

### **Variáveis de Ambiente no Verba:**

```bash
# Weaviate
WEAVIATE_URL_VERBA=https://weaviate-production-0d0e.up.railway.app
WEAVIATE_API_KEY_VERBA=
DEFAULT_DEPLOYMENT=Custom

# Tika (NOVO!)
TIKA_SERVER_URL=http://192.168.1.197:9998

# Outras
ALLOWED_ORIGINS=https://verba-production-c347.up.railway.app
ENABLE_EXTENSIONS=true
ENABLE_ETL_A2=true
```

---

## 🔍 Troubleshooting

### **Tika não está sendo usado:**

1. **Verifique variável de ambiente:**
   ```bash
   # Nos logs do Railway, procure por:
   [INFO] Tika fallback habilitado
   ```

2. **Teste conectividade:**
   ```bash
   # No container do Verba (se tiver acesso shell)
   curl http://192.168.1.197:9998/tika
   ```

3. **Verifique logs:**
   - Se aparecer `[TIKA-FALLBACK]` → Tika está sendo usado
   - Se não aparecer → Tika não está disponível ou não está sendo necessário

### **Erro "Tika não disponível":**

- Verifique se servidor Tika está rodando
- Verifique se URL está correta em `TIKA_SERVER_URL`
- Verifique se há firewall bloqueando acesso
- Verifique se porta está correta (9998)

### **Sistema funciona sem Tika:**

- ✅ Normal! Tika é opcional
- ✅ Métodos nativos continuam funcionando
- ✅ Apenas formatos não suportados (PPTX, DOC, etc.) não funcionarão sem Tika

---

## 💡 Dicas

1. **Para produção:** Use variável de ambiente (não config na UI)
   - Mais fácil de gerenciar
   - Não precisa reconfigurar a cada deploy

2. **Para desenvolvimento:** Pode usar localhost ou servidor de dev

3. **Para testes:** Desabilite Tika temporariamente removendo a variável
   - Sistema continua funcionando normalmente
   - Apenas formatos que precisam Tika não funcionarão

---

## 📋 Checklist

- [ ] Variável `TIKA_SERVER_URL` configurada no Railway
- [ ] Servidor Tika está acessível da rede do Railway
- [ ] Logs mostram "Tika fallback habilitado"
- [ ] Teste com PPTX funciona (se Tika disponível)
- [ ] Sistema funciona normalmente mesmo sem Tika

---

**Última atualização:** 2025-11-05


