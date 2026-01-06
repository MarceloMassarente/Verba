
import sys
import os
from pydantic import BaseModel
from typing import Dict, Any, Union

# Mock classes to mimic Verba's internal classes
class ConfigSetting(BaseModel):
    name: str
    value: Any
    type: str

class RAGComponentConfig(BaseModel):
    name: str # e.g. "EntityAware"
    config: Dict[str, ConfigSetting]

class RAGComponentClass(BaseModel):
    selected: str
    components: Dict[str, RAGComponentConfig]

# Logic to test (Copy-pasted adapted logic from api.py)
def apply_preset(rag_config: Dict[str, Any], preset_config: Dict[str, Any]):
    print("--- Starting Apply Preset ---")
    preset_applied = None
    
    if "Retriever" in rag_config:
        retriever = rag_config["Retriever"]
        
        # Adapt to Pydantic object
        if hasattr(retriever, "components"):
            components = retriever.components
        else:
            components = retriever.get("components", {})
        
        print(f"Components type: {type(components)}")
        
        # Detecta nome correto do componente (com ou sem hífen)
        entity_aware_key = None
        if "EntityAware" in components:
            entity_aware_key = "EntityAware"
        elif "Entity-Aware" in components:
            entity_aware_key = "Entity-Aware"
            
        if entity_aware_key:
            print(f"EntityAware key found: {entity_aware_key}")
            # Muda retriever selecionado para EntityAware
            if hasattr(retriever, "selected"):
                retriever.selected = entity_aware_key
            else:
                retriever["selected"] = entity_aware_key
            
            entity_aware = components[entity_aware_key]
            
            # Handle Component config
            ea_config = getattr(entity_aware, "config", None) if hasattr(entity_aware, "config") else entity_aware.get("config", {})
            print(f"EA Config found: {ea_config is not None}")
            
            if ea_config:
                # Aplica cada campo do preset
                for key, value in preset_config.items():
                    if key in ["name", "display_name", "description", 
                               "latency_estimate", "quality_estimate", "requirements"]:
                        continue
                    
                    print(f"Processing {key} -> {value}")
                    if key in ea_config:
                        config_item = ea_config[key]
                        
                        # Debug what config_item is
                        print(f"  Config Item type: {type(config_item)}")
                        
                        if hasattr(config_item, "value"):
                            config_item.value = value
                            print(f"  Updated via .value")
                        elif isinstance(config_item, dict):
                            config_item["value"] = value
                            print(f"  Updated via ['value']")
                        else:
                            # Se for valor direto (int/str) ou outro tipo
                            if hasattr(ea_config, "__setitem__"):
                                ea_config[key] = value
                                print("  Updated via config[key] = value")
                            else:
                                setattr(ea_config, key, value)
                                print("  Updated via setattr")
                    else:
                        print(f"  Key {key} not in ea_config keys: {list(ea_config.keys()) if isinstance(ea_config, dict) else 'Not a dict keys'}")
                
                preset_applied = "speed"
                print(f"✅ Preset applied: {preset_applied}")
        else:
             print("EntityAware not in components")
             print(f"Available components: {list(components.keys())}")
    else:
        print("Retriever not in rag_config")
    
    return preset_applied

# Setup Mock Data
print("Creating mock data...")

# Case 1: Pydantic Objects (Simulating clean internal objects)
config_setting = ConfigSetting(name="Chunk Window", value=1, type="int")
ea_config_pydantic = RAGComponentConfig(name="EntityAware", config={"Chunk Window": config_setting})
retriever_pydantic = RAGComponentClass(selected="Standard", components={"EntityAware": ea_config_pydantic})
rag_config_pydantic = {"Retriever": retriever_pydantic}

# Case 2: Dicts (Simulating JSON payload or dict-converted objects)
rag_config_dict = {
    "Retriever": {
        "selected": "Standard",
        "components": {
            "EntityAware": {
                "name": "EntityAware",
                "config": {
                    "Chunk Window": {"name": "Chunk Window", "value": 1, "type": "int"}
                }
            }
        }
    }
}

preset_config = {
    "name": "speed",
    "Chunk Window": 5
}

print("\n=== TEST 1: Pydantic Objects ===")
res1 = apply_preset(rag_config_pydantic, preset_config)
print(f"Result 1: {res1}")
print(f"New Value 1: {rag_config_pydantic['Retriever'].components['EntityAware'].config['Chunk Window'].value}")

print("\n=== TEST 2: Dictionaries ===")
res2 = apply_preset(rag_config_dict, preset_config)
print(f"Result 2: {res2}")
print(f"New Value 2: {rag_config_dict['Retriever']['components']['EntityAware']['config']['Chunk Window']['value']}")
