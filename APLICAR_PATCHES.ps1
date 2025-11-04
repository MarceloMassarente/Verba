# Script para aplicar patches do Weaviate v4 após update do Verba (Windows PowerShell)
# Uso: .\APLICAR_PATCHES.ps1

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "APLICANDO PATCHES WEAVIATE V4 + RAG2" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Verificar se estamos no diretório correto
if (-not (Test-Path "goldenverba\components\managers.py")) {
    Write-Host "ERRO: Execute este script no diretório raiz do Verba" -ForegroundColor Red
    exit 1
}

# Backup
Write-Host "1. Criando backup..." -ForegroundColor Yellow
$backupFile = "goldenverba\components\managers.py.backup.$(Get-Date -Format 'yyyyMMdd_HHmmss')"
Copy-Item "goldenverba\components\managers.py" $backupFile
Write-Host "   Backup criado: $backupFile" -ForegroundColor Green

# Verificar versão weaviate-client
Write-Host ""
Write-Host "2. Verificando versão do weaviate-client..." -ForegroundColor Yellow
try {
    $weaviateInfo = pip show weaviate-client 2>&1 | Select-String "Version"
    if ($weaviateInfo) {
        $version = ($weaviateInfo -split ":\s+")[1]
        Write-Host "   Versão encontrada: $version" -ForegroundColor Green
        $majorVersion = [int]($version -split "\.")[0]
        if ($majorVersion -lt 4) {
            Write-Host "   AVISO: Versão < 4.0.0 encontrada. Recomendado: >= 4.0.0" -ForegroundColor Yellow
        }
    } else {
        Write-Host "   AVISO: weaviate-client não encontrado" -ForegroundColor Yellow
    }
} catch {
    Write-Host "   AVISO: Não foi possível verificar versão do weaviate-client" -ForegroundColor Yellow
}

# Verificar imports necessários
Write-Host ""
Write-Host "3. Verificando imports necessários..." -ForegroundColor Yellow
$managersContent = Get-Content "goldenverba\components\managers.py" -Raw

if ($managersContent -match "from weaviate\.auth import AuthApiKey") {
    Write-Host "   [OK] AuthApiKey import encontrado" -ForegroundColor Green
} else {
    Write-Host "   [AVISO] AuthApiKey import não encontrado - será necessário adicionar manualmente" -ForegroundColor Yellow
}

if ($managersContent -match "from weaviate\.classes\.init import AdditionalConfig, Timeout") {
    Write-Host "   [OK] AdditionalConfig, Timeout imports encontrados" -ForegroundColor Green
} else {
    Write-Host "   [AVISO] AdditionalConfig, Timeout imports não encontrados - será necessário adicionar manualmente" -ForegroundColor Yellow
}

# Verificar patches aplicados
Write-Host ""
Write-Host "4. Verificando patches já aplicados..." -ForegroundColor Yellow

if ($managersContent -match "WEAVIATE_HTTP_HOST") {
    Write-Host "   [OK] PATCH 1 (PaaS config) - APLICADO" -ForegroundColor Green
} else {
    Write-Host "   [FALTA] PATCH 1 (PaaS config) - NÃO APLICADO" -ForegroundColor Red
}

if ($managersContent -match "connect_to_custom" -and $managersContent -match "http_secure=True") {
    Write-Host "   [OK] PATCH 2 (HTTPS connect_to_custom) - PARCIALMENTE APLICADO" -ForegroundColor Green
} else {
    Write-Host "   [FALTA] PATCH 2 (HTTPS connect_to_custom) - NÃO APLICADO" -ForegroundColor Red
}

if ($managersContent -match "WeaviateV3HTTPAdapter") {
    Write-Host "   [ATENÇÃO] PATCH 3 (Remover adapter v3) - AINDA PRESENTE (precisa remover)" -ForegroundColor Yellow
} else {
    Write-Host "   [OK] PATCH 3 (Remover adapter v3) - APLICADO" -ForegroundColor Green
}

if ($managersContent -match "hasattr\(client, 'connect'\)") {
    Write-Host "   [OK] PATCH 4 (Verificação connect) - APLICADO" -ForegroundColor Green
} else {
    Write-Host "   [FALTA] PATCH 4 (Verificação connect) - NÃO APLICADO" -ForegroundColor Red
}

# Verificar mudanças no Chunk
Write-Host ""
Write-Host "5. Verificando mudanças no Chunk..." -ForegroundColor Yellow
$chunkContent = Get-Content "goldenverba\components\chunk.py" -Raw

if ($chunkContent -match "chunk_lang") {
    Write-Host "   [OK] chunk_lang - APLICADO" -ForegroundColor Green
} else {
    Write-Host "   [FALTA] chunk_lang - NÃO APLICADO" -ForegroundColor Red
}

if ($chunkContent -match "chunk_date") {
    Write-Host "   [OK] chunk_date - APLICADO" -ForegroundColor Green
} else {
    Write-Host "   [FALTA] chunk_date - NÃO APLICADO" -ForegroundColor Red
}

# Verificar plugins RAG2
Write-Host ""
Write-Host "6. Verificando plugins RAG2..." -ForegroundColor Yellow

if (Test-Path "verba_extensions\plugins\bilingual_filter.py") {
    Write-Host "   [OK] bilingual_filter.py - EXISTE" -ForegroundColor Green
} else {
    Write-Host "   [FALTA] bilingual_filter.py - NÃO ENCONTRADO" -ForegroundColor Red
}

if (Test-Path "verba_extensions\plugins\query_rewriter.py") {
    Write-Host "   [OK] query_rewriter.py - EXISTE" -ForegroundColor Green
} else {
    Write-Host "   [FALTA] query_rewriter.py - NÃO ENCONTRADO" -ForegroundColor Red
}

if (Test-Path "verba_extensions\plugins\temporal_filter.py") {
    Write-Host "   [OK] temporal_filter.py - EXISTE" -ForegroundColor Green
} else {
    Write-Host "   [FALTA] temporal_filter.py - NÃO ENCONTRADO" -ForegroundColor Red
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "VERIFICAÇÃO CONCLUÍDA" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Próximos passos:" -ForegroundColor Yellow
Write-Host "1. Revise TODAS_MUDANCAS_VERBA.md para instruções detalhadas" -ForegroundColor White
Write-Host "2. Revise PATCHES_VERBA_WEAVIATE_V4.md para patches específicos do Weaviate" -ForegroundColor White
Write-Host "3. Aplique os patches manualmente conforme necessário" -ForegroundColor White
Write-Host "4. Teste a conexão com Weaviate após aplicar patches" -ForegroundColor White
Write-Host ""
Write-Host "Para testar:" -ForegroundColor Yellow
Write-Host "  python test_weaviate_access.py" -ForegroundColor White
Write-Host "  pytest verba_extensions\tests\" -ForegroundColor White
Write-Host ""

