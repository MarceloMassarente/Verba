#!/bin/bash
# Script para aplicar patches do Weaviate v4 após update do Verba
# Uso: ./APLICAR_PATCHES.sh

set -e

echo "=========================================="
echo "APLICANDO PATCHES WEAVIATE V4"
echo "=========================================="

# Verificar se estamos no diretório correto
if [ ! -f "goldenverba/components/managers.py" ]; then
    echo "ERRO: Execute este script no diretório raiz do Verba"
    exit 1
fi

# Backup
echo "1. Criando backup..."
cp goldenverba/components/managers.py goldenverba/components/managers.py.backup.$(date +%Y%m%d_%H%M%S)
echo "   Backup criado: goldenverba/components/managers.py.backup.*"

# Verificar versão weaviate-client
echo ""
echo "2. Verificando versão do weaviate-client..."
WEAVIATE_VERSION=$(pip show weaviate-client 2>/dev/null | grep Version | awk '{print $2}' || echo "não instalado")
echo "   Versão encontrada: $WEAVIATE_VERSION"

if [[ "$WEAVIATE_VERSION" == "não instalado" ]]; then
    echo "   AVISO: weaviate-client não encontrado"
elif [[ $(echo "$WEAVIATE_VERSION" | cut -d. -f1) -lt 4 ]]; then
    echo "   AVISO: Versão < 4.0.0 encontrada. Recomendado: >= 4.0.0"
fi

# Verificar imports necessários
echo ""
echo "3. Verificando imports necessários..."
if grep -q "from weaviate.auth import AuthApiKey" goldenverba/components/managers.py; then
    echo "   ✓ AuthApiKey import encontrado"
else
    echo "   ⚠ AuthApiKey import não encontrado - será necessário adicionar manualmente"
fi

if grep -q "from weaviate.classes.init import AdditionalConfig, Timeout" goldenverba/components/managers.py; then
    echo "   ✓ AdditionalConfig, Timeout imports encontrados"
else
    echo "   ⚠ AdditionalConfig, Timeout imports não encontrados - será necessário adicionar manualmente"
fi

# Verificar patches aplicados
echo ""
echo "4. Verificando patches já aplicados..."

if grep -q "WEAVIATE_HTTP_HOST" goldenverba/components/managers.py; then
    echo "   ✓ PATCH 1 (PaaS config) - APLICADO"
else
    echo "   ✗ PATCH 1 (PaaS config) - NÃO APLICADO"
fi

if grep -q "connect_to_custom" goldenverba/components/managers.py && grep -q "http_secure=True" goldenverba/components/managers.py; then
    echo "   ✓ PATCH 2 (HTTPS connect_to_custom) - PARCIALMENTE APLICADO"
else
    echo "   ✗ PATCH 2 (HTTPS connect_to_custom) - NÃO APLICADO"
fi

if grep -q "WeaviateV3HTTPAdapter" goldenverba/components/managers.py; then
    echo "   ⚠ PATCH 3 (Remover adapter v3) - AINDA PRESENTE (precisa remover)"
else
    echo "   ✓ PATCH 3 (Remover adapter v3) - APLICADO"
fi

if grep -q "hasattr(client, 'connect')" goldenverba/components/managers.py; then
    echo "   ✓ PATCH 4 (Verificação connect) - APLICADO"
else
    echo "   ✗ PATCH 4 (Verificação connect) - NÃO APLICADO"
fi

echo ""
echo "=========================================="
echo "VERIFICAÇÃO CONCLUÍDA"
echo "=========================================="
echo ""
echo "Próximos passos:"
echo "1. Revise PATCHES_VERBA_WEAVIATE_V4.md para instruções detalhadas"
echo "2. Aplique os patches manualmente conforme necessário"
echo "3. Teste a conexão com Weaviate após aplicar patches"
echo ""
echo "Para testar:"
echo "  python test_weaviate_access.py"
echo ""

