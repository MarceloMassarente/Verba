"""
Validação das Correções de Compatibilidade Sistêmica
"""

import sys
import os

# Adiciona path
sys.path.insert(0, os.path.dirname(__file__))

def validar_query_builder():
    """Valida se QueryBuilder tem filtros hierárquicos"""
    print("=" * 60)
    print("1. VALIDACAO: QueryBuilder")
    print("=" * 60)
    
    file_path = "verba_extensions/plugins/query_builder.py"
    hierarchical_filters = ['section_level', 'parent_section', 'document_context', 'section_path']
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        found = []
        missing = []
        for filter_name in hierarchical_filters:
            if filter_name in content:
                found.append(filter_name)
                print(f"  [OK] {filter_name} encontrado")
            else:
                missing.append(filter_name)
                print(f"  [FAIL] {filter_name} NAO encontrado")
        
        # Verificar se está na lista de available_filters
        if '"available_filters"' in content or "'available_filters'" in content:
            # Procurar por ocorrências próximas
            import re
            available_filters_pattern = r'available_filters["\']?\s*:\s*\[(.*?)\]'
            matches = re.findall(available_filters_pattern, content, re.DOTALL)
            
            if matches:
                filters_str = matches[0]
                filters_in_list = []
                for f in hierarchical_filters:
                    if f in filters_str:
                        filters_in_list.append(f)
                        print(f"  [OK] {f} na lista available_filters")
                    else:
                        print(f"  [WARN] {f} nao esta na lista available_filters")
            else:
                print("  [WARN] Nao foi possivel encontrar lista available_filters")
        
        if len(found) == 4:
            print("\n  [OK] QueryBuilder: TODOS os filtros hierarquicos presentes")
            return True
        else:
            print(f"\n  [FAIL] QueryBuilder: Faltam {4 - len(found)} filtros")
            return False
            
    except Exception as e:
        print(f"  [ERROR] Erro ao verificar: {e}")
        return False


def validar_entity_aware_retriever():
    """Valida se EntityAwareRetriever tem configuração de hierarquia"""
    print("\n" + "=" * 60)
    print("2. VALIDACAO: EntityAwareRetriever")
    print("=" * 60)
    
    file_path = "verba_extensions/plugins/entity_aware_retriever.py"
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Verificar se tem a configuração
        if 'Use Section Hierarchy' in content:
            print("  [OK] Configuracao 'Use Section Hierarchy' encontrada")
            
            # Verificar se está corretamente formatada
            if 'InputConfig' in content and 'type="bool"' in content:
                print("  [OK] Configuracao tem formato correto (InputConfig, bool)")
            else:
                print("  [WARN] Configuracao pode ter formato incorreto")
            
            # Verificar se tem values=[]
            if 'values=[]' in content or "values=[]" in content:
                print("  [OK] Configuracao tem values=[] (correto para bool)")
            else:
                print("  [WARN] Configuracao pode nao ter values=[]")
            
            return True
        else:
            print("  [FAIL] Configuracao 'Use Section Hierarchy' NAO encontrada")
            return False
            
    except Exception as e:
        print(f"  [ERROR] Erro ao verificar: {e}")
        return False


def validar_schema():
    """Valida se Schema tem propriedades hierárquicas"""
    print("\n" + "=" * 60)
    print("3. VALIDACAO: Schema Weaviate")
    print("=" * 60)
    
    try:
        from verba_extensions.integration.schema_updater import get_etl_properties
        props = get_etl_properties()
        prop_names = [p.name for p in props]
        
        hierarchical_props = ['section_level', 'parent_section', 'document_context', 'section_path']
        found = []
        missing = []
        
        for prop in hierarchical_props:
            if prop in prop_names:
                found.append(prop)
                print(f"  [OK] {prop} no schema")
            else:
                missing.append(prop)
                print(f"  [FAIL] {prop} NAO no schema")
        
        if len(found) == 4:
            print("\n  [OK] Schema: TODAS as propriedades hierarquicas presentes")
            return True
        else:
            print(f"\n  [FAIL] Schema: Faltam {4 - len(found)} propriedades")
            return False
            
    except Exception as e:
        print(f"  [ERROR] Erro ao verificar: {e}")
        import traceback
        traceback.print_exc()
        return False


def validar_etl():
    """Valida se ETL preserva metadados hierárquicos"""
    print("\n" + "=" * 60)
    print("4. VALIDACAO: ETL Pos-Chunking")
    print("=" * 60)
    
    file_path = "verba_extensions/plugins/a2_etl_hook.py"
    hierarchical_fields = ['section_level', 'parent_section', 'document_context', 'section_path']
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        found = []
        missing = []
        for field in hierarchical_fields:
            if field in content:
                found.append(field)
                print(f"  [OK] {field} preservado no ETL")
            else:
                missing.append(field)
                print(f"  [FAIL] {field} NAO preservado no ETL")
        
        if len(found) == 4:
            print("\n  [OK] ETL: Preserva TODOS os metadados hierarquicos")
            return True
        else:
            print(f"\n  [FAIL] ETL: Nao preserva todos os metadados ({len(found)}/4)")
            return False
            
    except Exception as e:
        print(f"  [ERROR] Erro ao verificar: {e}")
        return False


def main():
    """Executa todas as validações"""
    print("\n" + "=" * 60)
    print("VALIDACAO COMPLETA DAS CORRECOES")
    print("=" * 60)
    print()
    
    results = {
        'QueryBuilder': validar_query_builder(),
        'EntityAwareRetriever': validar_entity_aware_retriever(),
        'Schema': validar_schema(),
        'ETL': validar_etl(),
    }
    
    print("\n" + "=" * 60)
    print("RESUMO")
    print("=" * 60)
    
    all_ok = True
    for component, result in results.items():
        status = "[OK]" if result else "[FAIL]"
        print(f"{status} {component}")
        if not result:
            all_ok = False
    
    print("=" * 60)
    if all_ok:
        print("[OK] TODAS AS CORRECOES VALIDADAS COM SUCESSO!")
        return True
    else:
        print("[FAIL] ALGUMAS CORRECOES FALTANDO")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

