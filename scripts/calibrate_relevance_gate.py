"""
Script de Calibracao para Relevance Gate
=========================================
Mede scores de queries relevantes vs irrelevantes para determinar
bons defaults para Retrieval Threshold e Retrieval Margin.
"""

import asyncio
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

# Queries de teste
TEST_QUERIES = {
    # Irrelevantes / Fora de dominio
    "irrelevant": [
        "bolo de cenoura",
        "receita de pizza",
        "como fazer churrasco",
    ],
    # Provavelmente relevantes (consulting/business)
    "relevant": [
        "estrategia",
        "consultoria",
        "transformacao digital",
    ],
}


async def calibrate_scores():
    """Executa queries de teste e coleta scores."""
    
    try:
        from goldenverba.components.managers import WeaviateManager
        from goldenverba.components.embedding.VoyageAIEmbedder import VoyageAIEmbedder
        
        print("[INIT] Inicializando conexao com Weaviate...")
        
        # Configurar conexao via variaveis de ambiente
        wm = WeaviateManager()
        
        weaviate_url = os.getenv("WEAVIATE_URL_VERBA", "")
        weaviate_key = os.getenv("WEAVIATE_API_KEY_VERBA", "")
        
        if weaviate_url and weaviate_key:
            print(f"[INFO] Conectando a: {weaviate_url}")
            client = await wm.connect_to_cluster(weaviate_url, weaviate_key)
        else:
            print("[INFO] Conectando ao Weaviate Embedded/Docker...")
            client = await wm.connect_to_embedded()
        
        if not client:
            print("[ERROR] Falha ao conectar ao Weaviate")
            return
            
        print("[OK] Conectado ao Weaviate!")
        
        # Inicializar embedder
        embedder = VoyageAIEmbedder()
        embedder_name = "VoyageEmbedder"
        
        results = {
            "irrelevant": [],
            "relevant": [],
        }
        
        for category, queries in TEST_QUERIES.items():
            print(f"\n{'='*50}")
            print(f"[TEST] Testando queries {category.upper()}")
            print(f"{'='*50}")
            
            for query in queries:
                try:
                    # Fazer embedding da query
                    vector = await embedder.vectorize({}, [query])
                    vector = vector[0] if vector else None
                    
                    if not vector:
                        print(f"  [WARN] Falha ao vetorizar: {query}")
                        continue
                    
                    # Fazer busca hibrida
                    chunks = await wm.hybrid_chunks(
                        client=client,
                        embedder=embedder_name,
                        query=query,
                        vector=vector,
                        limit_mode="Fixed",
                        limit=10,
                        labels=[],
                        document_uuids=[],
                        alpha=0.6
                    )
                    
                    if not chunks:
                        print(f"  [WARN] Nenhum resultado: {query}")
                        results[category].append({
                            "query": query,
                            "top_1_score": 0.0,
                            "top_2_score": 0.0,
                            "margin": 0.0,
                            "num_results": 0
                        })
                        continue
                    
                    # Extrair scores
                    scores = []
                    for c in chunks:
                        score = 0.0
                        if hasattr(c, "metadata") and hasattr(c.metadata, "score"):
                            score = c.metadata.score or 0.0
                        scores.append(score)
                    
                    scores.sort(reverse=True)
                    top_1 = scores[0] if scores else 0.0
                    top_2 = scores[1] if len(scores) > 1 else 0.0
                    margin = top_1 - top_2
                    
                    results[category].append({
                        "query": query,
                        "top_1_score": top_1,
                        "top_2_score": top_2,
                        "margin": margin,
                        "num_results": len(chunks)
                    })
                    
                    print(f"  [SCORE] '{query}': top1={top_1:.4f}, top2={top_2:.4f}, margin={margin:.4f}")
                    
                except Exception as e:
                    print(f"  [ERROR] Erro em '{query}': {str(e)}")
                    import traceback
                    traceback.print_exc()
        
        # Analise e recomendacoes
        print("\n" + "="*60)
        print("[ANALYSIS] ANALISE DE SCORES")
        print("="*60)
        
        for category, data in results.items():
            if data:
                scores_list = [d["top_1_score"] for d in data if d["top_1_score"] > 0]
                if scores_list:
                    avg_top1 = sum(scores_list) / len(scores_list)
                    min_top1 = min(scores_list)
                    max_top1 = max(scores_list)
                    
                    print(f"\n{category.upper()}:")
                    print(f"  Media Top1: {avg_top1:.4f}")
                    print(f"  Min/Max Top1: {min_top1:.4f} / {max_top1:.4f}")
                else:
                    print(f"\n{category.upper()}: Sem dados")
        
        # Recomendacao
        irrelevant_scores = [d["top_1_score"] for d in results["irrelevant"] if d["top_1_score"] > 0]
        relevant_scores = [d["top_1_score"] for d in results["relevant"] if d["top_1_score"] > 0]
        
        if irrelevant_scores and relevant_scores:
            max_irrelevant = max(irrelevant_scores)
            min_relevant = min(relevant_scores)
            
            # Threshold ideal: entre o maximo irrelevante e minimo relevante
            # Com margem de seguranca para nao filtrar demais
            suggested_threshold = max_irrelevant * 0.9  # 10% abaixo do max irrelevante
            
            print("\n" + "="*60)
            print("[RECOMMEND] RECOMENDACAO DE DEFAULTS")
            print("="*60)
            print(f"  Max score irrelevante: {max_irrelevant:.4f}")
            print(f"  Min score relevante: {min_relevant:.4f}")
            print(f"  Gap: {min_relevant - max_irrelevant:.4f}")
            print(f"\n  [THRESHOLD] Threshold (T) recomendado: {suggested_threshold:.2f}")
            print(f"  [MARGIN] Margin (M) recomendado: 0.0 (deixar reranker decidir)")
        elif irrelevant_scores:
            max_irrelevant = max(irrelevant_scores)
            suggested_threshold = max_irrelevant * 0.9
            print("\n" + "="*60)
            print("[RECOMMEND] RECOMENDACAO DE DEFAULTS (apenas irrelevantes)")
            print("="*60)
            print(f"  Max score irrelevante: {max_irrelevant:.4f}")
            print(f"\n  [THRESHOLD] Threshold (T) recomendado: {suggested_threshold:.2f}")
        else:
            print("\n[WARN] Dados insuficientes para recomendacao")
        
        await wm.disconnect(client)
        return results
        
    except Exception as e:
        print(f"[ERROR] Erro: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    asyncio.run(calibrate_scores())
