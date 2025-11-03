"""
Script para criar schema Weaviate Article/Passage
Execute uma vez antes de usar o ingestor
"""

import os
import sys
import weaviate
from weaviate.classes.config import Configure
from weaviate.classes.init import AdditionalConfig, Timeout

def _num(name): 
    return {"name": name, "dataType": ["number"], "indexFilterable": True}

def _txt(name, filterable=False): 
    return {"name": name, "dataType": ["text"], "indexFilterable": filterable}

def _arr(name, filterable=True): 
    return {"name": name, "dataType": ["text[]"], "indexFilterable": filterable}

def main():
    # Conecta ao Weaviate
    url = os.getenv("WEAVIATE_URL", "http://localhost:8080")
    api_key = os.getenv("WEAVIATE_API_KEY")
    
    try:
        if api_key:
            client = weaviate.connect_to_custom(
                http_host=url.replace("http://", "").replace("https://", "").split(":")[0],
                http_port=int(url.split(":")[-1]) if ":" in url else 8080,
                http_secure=url.startswith("https"),
                auth_credentials=weaviate.auth.AuthApiKey(api_key),
                additional_config=AdditionalConfig(
                    timeout=Timeout(init=60, query=30, insert=30)
                )
            )
        else:
            client = weaviate.connect_to_local(
                host=url.replace("http://", "").replace("https://", "").split(":")[0],
                port=int(url.split(":")[-1]) if ":" in url else 8080,
                skip_init_checks=True,
                additional_config=AdditionalConfig(
                    timeout=Timeout(init=60, query=30, insert=30)
                )
            )
        
        print("✅ Conectado ao Weaviate")
    except Exception as e:
        print(f"❌ Erro ao conectar: {str(e)}")
        sys.exit(1)
    
    # Deleta coleções existentes (opcional, comente se não quiser)
    try:
        client.collections.delete("Article", ignore_missing=True)
        client.collections.delete("Passage", ignore_missing=True)
        print("🗑️  Coleções antigas removidas (se existiam)")
    except:
        pass
    
    # Cria Article
    try:
        client.collections.create(
            name="Article",
            vectorizer_config=Configure.Vectorizer.none(),
            properties=[
                _txt("article_id", True),
                _txt("url_final", True),
                _txt("source_domain", True),
                _txt("title"),
                {"name": "published_at", "dataType": ["date"], "indexFilterable": True},
                _txt("language", True),
                _arr("entities_all_ids", True),
                _txt("batch_tag", True),
            ],
        )
        print("✅ Collection 'Article' criada")
    except Exception as e:
        print(f"⚠️ Erro ao criar Article: {str(e)}")
    
    # Cria Passage
    try:
        client.collections.create(
            name="Passage",
            vectorizer_config=Configure.Vectorizer.none(),
            vector_index_config=Configure.VectorIndex.hnsw(),
            properties=[
                _txt("text"),
                _txt("language", True),
                _txt("meta_tenant", True),
                _txt("etl_version"),
                _txt("text_hash", True),
                _txt("section_title"),
                _txt("section_first_para"),
                _arr("parent_entities", True),
                _arr("entities_local_ids"),
                _arr("section_entity_ids"),
                _num("section_scope_confidence"),
                _txt("primary_entity_id", True),
                _num("entity_focus_score"),
                _arr("topics_normalized", True),
                _txt("batch_tag", True),
                {"name": "article_ref", "dataType": ["Article"], "indexFilterable": True}
            ],
        )
        print("✅ Collection 'Passage' criada")
    except Exception as e:
        print(f"⚠️ Erro ao criar Passage: {str(e)}")
    
    client.close()
    print("✅ Schema criado com sucesso!")

if __name__ == "__main__":
    main()

