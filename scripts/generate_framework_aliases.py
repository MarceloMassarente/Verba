"""
Script para gerar aliases PT/EN para frameworks a partir do CSV
"""

import csv
import json
import re
import os
from typing import List, Dict

# Mapeamento de traduções comuns
TRANSLATIONS = {
    "Analysis": "Análise",
    "Matrix": "Matriz",
    "Framework": "Framework",
    "Model": "Modelo",
    "System": "Sistema",
    "Method": "Método",
    "Principle": "Princípio",
    "Index": "Índice",
    "Tree": "Árvore",
    "Curve": "Curva",
    "Map": "Mapa",
    "Journey": "Jornada",
    "Decision": "Decisão",
    "Problem Solving": "Resolução de Problemas",
    "Growth": "Crescimento",
    "Value": "Valor",
    "Customer": "Cliente",
    "Consumer": "Consumidor",
    "Leadership": "Liderança",
    "Organizational": "Organizacional",
    "Transformation": "Transformação",
    "Digital": "Digital",
    "Innovation": "Inovação",
    "Strategy": "Estratégia",
    "Strategic": "Estratégico",
    "Performance": "Desempenho",
    "Operations": "Operações",
    "Marketing": "Marketing",
    "People": "Pessoas",
    "Technology": "Tecnologia",
}

# Abreviações comuns
ABBREVIATIONS = {
    "NPS": ["NPS", "Net Promoter Score", "Net Promoter System", "NPS System"],
    "OHI": ["OHI", "Organizational Health Index", "Índice de Saúde Organizacional"],
    "RAPID": ["RAPID", "RAPID Decision Making"],
    "ZBR": ["ZBR", "Zero-Based Redesign", "Redesenho Zero-Base"],
    "ZBB": ["ZBB", "Zero-Based Budgeting", "Orçamento Zero-Base"],
    "DQ": ["DQ", "Digital Quotient", "Quociente Digital"],
    "EP": ["EP", "Economic Profit", "Lucro Econômico"],
    "TSR": ["TSR", "Total Shareholder Return", "Retorno Total ao Acionista"],
    "ROIC": ["ROIC", "Return on Invested Capital", "Retorno sobre Capital Investido"],
    "MECE": ["MECE", "Mutually Exclusive, Collectively Exhaustive", "Mutualmente Exclusivo, Coletivamente Exaustivo"],
    "SCQA": ["SCQA", "Situation, Complication, Question, Answer"],
    "VoC": ["VoC", "Voice of the Customer", "Voz do Cliente"],
    "BCG": ["BCG", "BCG Matrix", "Matriz BCG"],
    "SWOT": ["SWOT", "SWOT Analysis", "Análise SWOT"],
    "PESTEL": ["PESTEL", "PESTEL Analysis", "Análise PESTEL", "PEST"],
    "PEST": ["PEST", "PEST Analysis", "Análise PEST"],
    "EBITDA": ["EBITDA"],
    "CAGR": ["CAGR", "Compound Annual Growth Rate", "Taxa de Crescimento Anual Composta"],
}

def clean_framework_name(name: str) -> str:
    """Remove parênteses e informações extras do nome"""
    # Remove (McK), (Bain), etc.
    name = re.sub(r'\s*\([^)]*\)', '', name)
    # Remove traços e espaços extras
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def extract_abbreviation(name: str) -> List[str]:
    """Extrai possíveis abreviações do nome"""
    abbrevs = []
    # Busca padrões como "NPS", "OHI", etc.
    matches = re.findall(r'\b[A-Z]{2,}\b', name)
    for match in matches:
        if match in ABBREVIATIONS:
            abbrevs.extend(ABBREVIATIONS[match])
    return abbrevs

def generate_aliases(name: str, category: str) -> List[str]:
    """Gera lista de aliases para um framework (PT/EN)"""
    aliases = set()
    
    # Nome original limpo
    clean_name = clean_framework_name(name)
    aliases.add(clean_name)
    
    # Nome em minúsculas
    aliases.add(clean_name.lower())
    
    # Extrair palavras-chave principais
    words = re.findall(r'\b\w+\b', clean_name)
    
    # Adicionar variações com palavras principais
    if len(words) > 1:
        # Primeira palavra + última palavra (ex: "Porter Forces")
        if len(words) >= 2:
            aliases.add(f"{words[0]} {words[-1]}")
        # Apenas última palavra (ex: "Forces")
        aliases.add(words[-1])
        # Apenas primeira palavra (ex: "Porter")
        aliases.add(words[0])
    
    # Abreviações conhecidas
    abbrevs = extract_abbreviation(name)
    aliases.update(abbrevs)
    
    # Variações com números (ex: "5 Forces" vs "Five Forces")
    if "Five" in clean_name:
        aliases.add(clean_name.replace("Five", "5"))
        aliases.add(clean_name.replace("Five", "five"))
    if "5" in clean_name:
        aliases.add(clean_name.replace("5", "Five"))
        aliases.add(clean_name.replace("5", "five"))
    
    # Variações com "vs" e "&"
    if " vs " in clean_name.lower():
        aliases.add(clean_name.replace(" vs ", " vs. "))
        aliases.add(clean_name.replace(" vs ", " & "))
    if " & " in clean_name.lower():
        aliases.add(clean_name.replace(" & ", " and "))
    
    # Remover "Analysis", "Framework", etc. para criar versões curtas
    for suffix in [" Analysis", " Framework", " Model", " System", " Method", " Matrix", " Index"]:
        if clean_name.endswith(suffix):
            short = clean_name[:-len(suffix)]
            aliases.add(short)
            aliases.add(short.lower())
    
    # Traduções PT/EN comuns
    pt_en_aliases = generate_pt_en_aliases(clean_name)
    aliases.update(pt_en_aliases)
    
    # Remover duplicatas e vazios
    aliases = {a.strip() for a in aliases if a.strip() and len(a.strip()) > 1}
    
    return sorted(list(aliases))

def generate_pt_en_aliases(name: str) -> List[str]:
    """Gera aliases em português e inglês"""
    aliases = []
    
    # Traduções diretas comuns
    translations = {
        "Analysis": "Análise",
        "Matrix": "Matriz",
        "Framework": "Framework",
        "Model": "Modelo",
        "System": "Sistema",
        "Index": "Índice",
        "Tree": "Árvore",
        "Curve": "Curva",
        "Map": "Mapa",
        "Journey": "Jornada",
        "Decision": "Decisão",
        "Problem Solving": "Resolução de Problemas",
        "Growth": "Crescimento",
        "Value": "Valor",
        "Customer": "Cliente",
        "Consumer": "Consumidor",
        "Leadership": "Liderança",
        "Organizational": "Organizacional",
        "Transformation": "Transformação",
        "Digital": "Digital",
        "Innovation": "Inovação",
        "Strategy": "Estratégia",
        "Strategic": "Estratégico",
        "Performance": "Desempenho",
        "Operations": "Operações",
        "Marketing": "Marketing",
        "People": "Pessoas",
        "Technology": "Tecnologia",
        "Health": "Saúde",
        "Profit": "Lucro",
        "Economic": "Econômico",
        "Budgeting": "Orçamento",
        "Redesign": "Redesenho",
        "Based": "Base",
        "Zero": "Zero",
    }
    
    # Tenta traduzir termos comuns
    translated = name
    for en, pt in translations.items():
        if en in name:
            translated_pt = name.replace(en, pt)
            if translated_pt != name:
                aliases.append(translated_pt)
                aliases.append(translated_pt.lower())
        if pt in name:
            translated_en = name.replace(pt, en)
            if translated_en != name:
                aliases.append(translated_en)
                aliases.append(translated_en.lower())
    
    # Casos especiais conhecidos
    special_cases = {
        "SWOT Analysis": ["Análise SWOT"],
        "Porter's Five Forces": ["5 Forças de Porter", "Cinco Forças de Porter", "Forças de Porter", "Porter 5 Forças"],
        "Porter's 5 Forces": ["5 Forças de Porter", "Cinco Forças de Porter", "Forças de Porter"],
        "Five Forces": ["5 Forças", "Cinco Forças"],
        "5 Forces": ["Five Forces", "Cinco Forças", "5 Forças"],
        "PESTEL Analysis": ["Análise PESTEL"],
        "PEST Analysis": ["Análise PEST"],
        "Ansoff Matrix": ["Matriz de Ansoff"],
        "Value Chain": ["Cadeia de Valor"],
        "Value Chain Analysis": ["Análise da Cadeia de Valor", "Cadeia de Valor"],
        "Balanced Scorecard": ["BSC", "Indicadores Balanceados", "Balanced Scorecard"],
        "Business Model Canvas": ["Canvas", "Canvas de Modelo de Negócio", "Modelo de Negócio Canvas"],
        "Net Promoter Score": ["NPS", "Net Promoter System"],
        "Net Promoter System": ["NPS", "Sistema NPS"],
        "Organizational Health Index": ["OHI", "Índice de Saúde Organizacional"],
        "Economic Profit": ["Lucro Econômico", "EP"],
        "Zero-Based Budgeting": ["ZBB", "Orçamento Zero-Base"],
        "Zero-Based Redesign": ["ZBR", "Redesenho Zero-Base"],
        "7-S Framework": ["7-S", "McKinsey 7S", "Framework 7-S", "Framework 7S"],
        "McKinsey 7S": ["7-S", "7-S Framework", "Framework 7-S"],
        "BCG Matrix": ["Matriz BCG", "BCG"],
        "Blue Ocean": ["Oceano Azul"],
        "Red Ocean": ["Oceano Vermelho"],
        "Lean Startup": ["Startup Enxuta"],
        "Agile": ["Ágil", "Metodologia Ágil"],
        "Scrum": ["Scrum"],
        "Kanban": ["Kanban"],
    }
    
    for key, values in special_cases.items():
        if key.lower() in name.lower() or name.lower() in key.lower():
            aliases.extend(values)
    
    return aliases

def process_csv_to_json(csv_path: str, output_path: str):
    """Processa CSV e gera JSON com aliases"""
    frameworks = []
    
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f, delimiter=';')
        
        for row in reader:
            # Pega o nome do framework (segunda coluna)
            framework_name = list(row.values())[1].strip() if len(row) > 1 else ''
            # Pega a categoria (primeira coluna)
            category = list(row.values())[0].strip() if len(row) > 0 else ''
            # Pega a descrição (terceira coluna)
            description = list(row.values())[2].strip() if len(row) > 2 else ''
            
            if not framework_name:
                continue
            
            # Gera aliases
            aliases = generate_aliases(framework_name, category)
            
            framework = {
                "name": clean_framework_name(framework_name),
                "aliases": aliases,
                "category": category,
                "description": description
            }
            
            frameworks.append(framework)
    
    # Salva JSON
    output = {
        "frameworks": frameworks,
        "total": len(frameworks),
        "version": "1.0"
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"OK: Gerado {len(frameworks)} frameworks com aliases")
    print(f"Salvo em: {output_path}")
    
    # Estatísticas
    total_aliases = sum(len(f['aliases']) for f in frameworks)
    print(f"Total de aliases: {total_aliases}")
    print(f"Media de aliases por framework: {total_aliases / len(frameworks):.1f}")

if __name__ == "__main__":
    csv_path = "frameworks.csv"
    output_path = "verba_extensions/resources/frameworks.json"
    
    if not os.path.exists(csv_path):
        print(f"ERRO: Arquivo nao encontrado: {csv_path}")
        exit(1)
    
    # Garantir que diretório existe
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    process_csv_to_json(csv_path, output_path)

