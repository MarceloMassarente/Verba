"""
Script auxiliar para autenticação OAuth 2.0 com Google Drive

Uso:
    python verba_extensions/plugins/google_drive_auth.py

Este script:
1. Abre o navegador para autenticação
2. Salva o token em token.json
3. Use token.json como GOOGLE_DRIVE_CREDENTIALS
"""

import os
import json
from pathlib import Path

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.oauth2.credentials import Credentials
except ImportError:
    print("❌ Dependências não instaladas. Execute:")
    print("   pip install google-auth-oauthlib")
    exit(1)

# Scopes necessários para ler arquivos do Google Drive
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

def authenticate():
    """Autentica com Google Drive via OAuth 2.0"""
    
    # Procura credentials.json no diretório atual ou parent
    script_dir = Path(__file__).parent
    credentials_file = script_dir / 'credentials.json'
    
    if not credentials_file.exists():
        # Tenta no diretório atual
        credentials_file = Path('credentials.json')
    
    if not credentials_file.exists():
        print("❌ Arquivo credentials.json não encontrado!")
        print("\n📝 Como obter credentials.json:")
        print("1. Acesse https://console.cloud.google.com/")
        print("2. Crie um projeto ou selecione um existente")
        print("3. Ative a Google Drive API")
        print("4. Vá em 'APIs & Services' > 'Credentials'")
        print("5. Clique em 'Create Credentials' > 'OAuth client ID'")
        print("6. Selecione 'Desktop app'")
        print("7. Baixe o JSON e salve como 'credentials.json'")
        print(f"8. Coloque o arquivo em: {script_dir} ou no diretório atual")
        return None
    
    print(f"✅ Encontrado credentials.json em: {credentials_file}")
    print("🌐 Abrindo navegador para autenticação...")
    
    try:
        flow = InstalledAppFlow.from_client_secrets_file(
            str(credentials_file),
            SCOPES
        )
        creds = flow.run_local_server(port=0)
        
        # Salva token
        token_file = script_dir / 'token.json'
        with open(token_file, 'w') as token:
            token.write(creds.to_json())
        
        print(f"✅ Autenticação concluída!")
        print(f"✅ Token salvo em: {token_file}")
        print(f"\n📝 Configure a variável de ambiente:")
        print(f"   export GOOGLE_DRIVE_CREDENTIALS=\"{token_file}\"")
        print(f"\n   Ou no .env:")
        print(f"   GOOGLE_DRIVE_CREDENTIALS={token_file}")
        
        return creds
        
    except Exception as e:
        print(f"❌ Erro na autenticação: {str(e)}")
        return None

if __name__ == "__main__":
    authenticate()

