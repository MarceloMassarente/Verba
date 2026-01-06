import time
import subprocess
import json
from wasabi import msg

def run_test(profile, query):
    msg.info(f"Testando perfil: {profile} com query: '{query}'")
    cmd = [
        "python", "api_client_example.py",
        "--profile", profile,
        "--query", query,
        "--limit", "3"
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        msg.good(f"Perfil {profile}: SUCESSO")
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        msg.fail(f"Perfil {profile}: FALHOU")
        msg.fail(e.stderr)
        return False, e.stderr

def main():
    wait_time = 300
    msg.warn(f"Aguardando {wait_time} segundos para propagação do deploy...")
    # time.sleep(wait_time) 
    # REMOVIDO para execução via agente - o agente pode controlar o tempo se necessário, 
    # mas para economizar tempo do usuário, vamos assumir que o agente pode rodar isso em background.
    
    profiles = ["speed", "balanced", "max_quality", "consulting_frameworks", "company_research", "sector_analysis"]
    test_query = "agronegocio e sustentabilidade"
    
    overall_success = True
    results = []
    
    for profile in profiles:
        success, output = run_test(profile, test_query)
        results.append({
            "profile": profile,
            "success": success,
            "output_snippet": output[-500:] if output else ""
        })
        if not success:
            overall_success = False
            
    if overall_success:
        msg.good("TODOS OS TESTES PASSARAM!")
    else:
        msg.fail("ALVUNS TESTES FALHARAM.")
        
    with open("comprehensive_test_results.json", "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    main()
