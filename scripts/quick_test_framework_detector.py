"""
Teste rápido do Framework Detector
"""

import asyncio
import sys
import os

# Adicionar o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from verba_extensions.utils.framework_detector import get_framework_detector


async def quick_test():
    detector = get_framework_detector()

    # Teste rápido com alguns casos
    tests = [
        ('SWOT analysis', ['SWOT Analysis']),
        ('Porter Five Forces', ['Porter\'s Five Forces']),
        ('Análise SWOT completa', ['SWOT Analysis']),
        ('5 Forças de Porter', ['Porter\'s Five Forces']),
        ('PESTEL e Cadeia de Valor', ['PESTEL Analysis', 'Value Chain Analysis']),
        ('NPS melhorou', ['Net Promoter System - NPS']),
        ('BCG Matrix', ['BCG Matrix']),
        ('Balanced Scorecard', ['Balanced Scorecard']),
        ('Ansoff Matrix', ['Ansoff Matrix']),
        ('7-S Framework', ['7-S Framework']),
    ]

    print('TESTE RAPIDO DE DETECCAO:')
    print('=' * 40)

    all_passed = True
    for i, (text, expected) in enumerate(tests, 1):
        result = await detector.detect_frameworks(text)
        detected = result.get('frameworks', [])
        expected_set = set(expected)
        detected_set = set(detected)

        if expected_set.issubset(detected_set):
            print(f'{i}. [OK] \"{text}\" -> {detected}')
        else:
            print(f'{i}. [FALHOU] \"{text}\" -> {detected} (esperado: {expected})')
            missing = expected_set - detected_set
            if missing:
                print(f'     Faltando: {missing}')
            all_passed = False

    print('=' * 40)
    print(f'Resultado: {"APROVADO" if all_passed else "REPROVADO"}')

    # Estatísticas
    print(f'Frameworks carregados: {len(detector.frameworks_by_name)}')
    print(f'Aliases disponíveis: {len(detector.frameworks_data)}')
    print(f'Média aliases/framework: {len(detector.frameworks_data) / len(detector.frameworks_by_name):.1f}')

    # Teste de aliases
    print('\nTESTE DE ALIASES:')
    print('-' * 30)

    # Verificar se aliases estão funcionando
    aliases_to_test = ['SWOT', 'Análise SWOT', 'Porter', 'Five Forces', '5 Forças', 'Cadeia de Valor']
    for alias in aliases_to_test:
        result = await detector.detect_frameworks(alias)
        detected = result.get('frameworks', [])
        if detected:
            print(f'"{alias}" -> {detected[0]}')
        else:
            print(f'"{alias}" -> NADA DETECTADO')

    # Debug: verificar se aliases estão no dicionário
    print('\nDEBUG - ALIASES NO DICIONARIO:')
    print('-' * 40)

    test_aliases = ['SWOT', 'Porter', 'Five Forces']
    for alias in test_aliases:
        if alias.lower() in detector.frameworks_data:
            framework = detector.frameworks_data[alias.lower()]
            print(f'"{alias}" -> "{framework}"')
        else:
            print(f'"{alias}" -> NAO ENCONTRADO no frameworks_data')
            # Verificar se está em algum outro alias
            found = False
            for k, v in detector.frameworks_data.items():
                if alias.lower() in k:
                    print(f'  Mas encontrado como parte de: "{k}" -> "{v}"')
                    found = True
                    break
            if not found:
                print(f'  NAO encontrado em nenhum alias')

    # Debug da ordenação
    print('\nDEBUG - ORDENACAO DE ALIASES:')
    print('-' * 40)

    # Mostrar os primeiros 10 aliases ordenados
    sorted_aliases = sorted(detector.frameworks_data.items(),
                          key=lambda x: (len(x[0].split()), len(x[0])))

    print('Primeiros 10 aliases ordenados (curtos primeiro):')
    for i, (alias, framework_name) in enumerate(sorted_aliases[:10]):
        word_count = len(alias.split())
        print(f'  #{i+1}: "{alias}" ({word_count} palavras) -> {framework_name}')

    print('\nAliases com 1 palavra:')
    one_word_aliases = [(alias, fw) for alias, fw in sorted_aliases if len(alias.split()) == 1]
    for alias, fw in one_word_aliases[:5]:  # Apenas primeiros 5
        print(f'  "{alias}" -> {fw}')

    # Debug da detecção passo a passo
    print('\nDEBUG - DETECCAO PASSO A PASSO:')
    print('-' * 40)

    test_text = "SWOT"
    print(f'Testando texto: "{test_text}"')
    print(f'Texto lowercase: "{test_text.lower()}"')

    # Simular a lógica de detecção com aliases de 1 palavra primeiro
    text_lower = test_text.lower()

    found_any = False
    for i, (alias, framework_name) in enumerate(sorted_aliases):
        if alias in ["analysis", "framework", "model", "system", "method", "matrix", "index"]:
            continue

        if len(alias.split()) == 1:
            print(f'  Testando alias de 1 palavra #{i+1}: "{alias}"')

            import re
            pattern = r'\b' + re.escape(alias) + r'\b'
            match = re.search(pattern, text_lower)
            if match:
                print(f'    MATCH! Pattern: {pattern}, Match: {match.group()}')
                print(f'    Framework: {framework_name}')
                found_any = True
                break
            else:
                print(f'    No match. Pattern: {pattern}')
        elif i > 20:  # Parar depois de 20 aliases para não poluir
            break

    if not found_any:
        print('  NENHUM alias encontrado!')

    return all_passed


if __name__ == "__main__":
    success = asyncio.run(quick_test())
    exit(0 if success else 1)
