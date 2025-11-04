"""
Script que inicia servidor se necessário e executa teste completo
"""

import asyncio
import subprocess
import sys
import time
import os
from pathlib import Path

# Verifica se API está rodando
def check_api_running():
    """Verifica se API está respondendo"""
    try:
        import aiohttp
        import asyncio
        
        async def check():
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get('http://localhost:8000/api/health', timeout=2) as response:
                        return response.status == 200
            except:
                return False
        
        return asyncio.run(check())
    except:
        return False

# Inicia servidor em background
def start_server():
    """Inicia servidor Verba"""
    print("🚀 Iniciando servidor Verba...")
    
    # Verifica se já está rodando
    if check_api_running():
        print("✅ Servidor já está rodando")
        return None
    
    # Inicia servidor
    try:
        # Usa verba start se disponível
        process = subprocess.Popen(
            [sys.executable, "-m", "goldenverba.server.api"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=os.getcwd()
        )
        
        # Aguarda servidor iniciar
        print("⏳ Aguardando servidor iniciar...")
        for i in range(30):  # 30 tentativas de 1 segundo
            time.sleep(1)
            if check_api_running():
                print("✅ Servidor iniciado com sucesso")
                return process
            print(f"   Tentativa {i+1}/30...")
        
        print("❌ Servidor não iniciou a tempo")
        process.terminate()
        return None
        
    except Exception as e:
        print(f"❌ Erro ao iniciar servidor: {e}")
        return None

if __name__ == "__main__":
    print("=" * 60)
    print("🧪 TESTE COMPLETO DO PIPELINE VERBA")
    print("=" * 60)
    
    # Verifica se API está rodando
    if not check_api_running():
        print("\n⚠️  API não está rodando. Tentando iniciar...")
        server_process = start_server()
        
        if not server_process and not check_api_running():
            print("\n❌ Não foi possível iniciar o servidor automaticamente")
            print("\n💡 Opções:")
            print("   1. Inicie manualmente: verba start")
            print("   2. Configure VERBA_API_URL para ambiente remoto")
            print("   3. Execute: python test_pipeline_simples.py")
            sys.exit(1)
    else:
        print("\n✅ API está rodando")
        server_process = None
    
    # Executa teste
    print("\n" + "=" * 60)
    print("📋 Executando teste completo...")
    print("=" * 60 + "\n")
    
    try:
        # Importa e executa teste
        from test_pipeline_simples import main as test_main
        asyncio.run(test_main())
    except KeyboardInterrupt:
        print("\n⚠️  Teste interrompido pelo usuário")
    except Exception as e:
        print(f"\n❌ Erro ao executar teste: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Encerra servidor se iniciado por este script
        if server_process:
            print("\n🛑 Encerrando servidor...")
            server_process.terminate()
            try:
                server_process.wait(timeout=5)
            except:
                server_process.kill()

