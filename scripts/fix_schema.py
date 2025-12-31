
import os
import sys
import asyncio
import weaviate
from weaviate.classes.init import Auth
from weaviate.classes.config import Property, DataType

# Tenta carregar variáveis de ambiente
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Mesma lógica de conexão do verify
WEAVIATE_URL = os.getenv("VERBA_URL", "http://localhost:8080")
WEAVIATE_API_KEY = os.getenv("WEAVIATE_API_KEY", "")

def get_missing_properties():
    """Defines the properties to add if missing"""
    return [
        Property(name="frameworks", data_type=DataType.TEXT_ARRAY, description="Frameworks detectados"),
        Property(name="companies", data_type=DataType.TEXT_ARRAY, description="Empresas mencionadas"),
        Property(name="sectors", data_type=DataType.TEXT_ARRAY, description="Setores mencionados"),
        Property(name="persons", data_type=DataType.TEXT_ARRAY, description="Pessoas mencionadas"),
        Property(name="conceitos_negocio", data_type=DataType.TEXT_ARRAY, description="Conceitos de negócio"),
        Property(name="metricas_mencionadas", data_type=DataType.TEXT_ARRAY, description="Métricas mencionadas"),
        Property(name="tipo_conteudo", data_type=DataType.TEXT, description="Tipo de conteúdo"),
        Property(name="framework_confidence", data_type=DataType.NUMBER, description="Confiança na detecção"),
        # ETL fields
        Property(name="entities_local_ids", data_type=DataType.TEXT_ARRAY),
        Property(name="section_entity_ids", data_type=DataType.TEXT_ARRAY),
        Property(name="section_scope_confidence", data_type=DataType.NUMBER),
        Property(name="primary_entity_id", data_type=DataType.TEXT),
        Property(name="entity_focus_score", data_type=DataType.NUMBER),
        Property(name="etl_version", data_type=DataType.TEXT),
    ]

async def main():
    print(f"--- Fixing Schema for {WEAVIATE_URL} ---")
    
    headers = {}
    
    try:
        if WEAVIATE_API_KEY:
             client = weaviate.connect_to_custom(
                http_host=WEAVIATE_URL.replace("http://", "").replace("https://", "").split(":")[0],
                http_port=8080 if ":" not in WEAVIATE_URL.replace("http://", "").replace("https://", "") else int(WEAVIATE_URL.split(":")[-1]),
                http_secure=WEAVIATE_URL.startswith("https"),
                headers=headers,
                auth_credentials=Auth.api_key(WEAVIATE_API_KEY)
            )
        else:
            client = weaviate.connect_to_local()
    except Exception as e:
        print(f"Error connecting: {e}")
        return

    try:
        collections_to_fix = ["Passage"]
        # Check for Embedding collections too
        all_cols = client.collections.list_all()
        for c in all_cols:
            if "VERBA_Embedding" in c:
                collections_to_fix.append(c)
        
        props_to_add = get_missing_properties()
        
        for col_name in collections_to_fix:
            print(f"\nProcessing Collection: {col_name}")
            if col_name not in all_cols:
                print("Skipping (not found)")
                continue

            col = client.collections.get(col_name)
            config = col.config.get()
            existing_props = {p.name for p in config.properties}
            
            for prop in props_to_add:
                if prop.name not in existing_props:
                    print(f"  + Adding missing property: {prop.name}")
                    try:
                        col.config.add_property(prop)
                        print("    Success!")
                    except Exception as e:
                        print(f"    Failed: {e}")
                else:
                    # print(f"  . Property {prop.name} exists.")
                    pass

    except Exception as e:
        print(f"Error during schema fix: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
