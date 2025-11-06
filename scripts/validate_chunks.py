"""
Script para validar chunks no Weaviate
Analisa duplicações, qualidade e fragmentação
"""

import asyncio
import os
import sys
from pathlib import Path
from collections import Counter
from typing import List, Dict, Set
import hashlib

# Adicionar path do projeto
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from wasabi import msg
import weaviate
from weaviate.classes.config import Configure
from weaviate.auth import AuthApiKey

load_dotenv()


def get_content_hash(content: str) -> str:
    """Gera hash do conteúdo para detectar duplicações exatas"""
    return hashlib.md5(content.strip().lower().encode()).hexdigest()


def detect_repetitive_phrases(content: str, min_words: int = 3) -> List[Dict]:
    """Detecta frases repetitivas no conteúdo"""
    words = content.split()
    if len(words) < min_words * 2:
        return []
    
    repetitive_phrases = []
    
    # Verificar sequências de 3, 4, 5 palavras
    for seq_length in [3, 4, 5]:
        if len(words) < seq_length * 2:
            continue
        
        phrase_counts = {}
        for i in range(len(words) - seq_length + 1):
            phrase = " ".join(words[i:i+seq_length])
            phrase_counts[phrase] = phrase_counts.get(phrase, 0) + 1
        
        # Encontrar frases que aparecem mais de 2 vezes
        for phrase, count in phrase_counts.items():
            if count >= 2:
                percentage = (count * seq_length) / len(words) * 100
                if percentage > 20:  # Mais de 20% do chunk
                    repetitive_phrases.append({
                        "phrase": phrase,
                        "count": count,
                        "percentage": round(percentage, 1),
                        "length": seq_length
                    })
    
    return repetitive_phrases


def analyze_chunk_quality(chunk: Dict) -> Dict:
    """Analisa qualidade de um chunk"""
    content = chunk.get("content", "")
    content_clean = content.strip()
    
    analysis = {
        "uuid": chunk.get("uuid", "unknown"),
        "chunk_id": chunk.get("chunk_id", "unknown"),
        "doc_uuid": chunk.get("doc_uuid", "unknown"),
        "length": len(content_clean),
        "word_count": len(content_clean.split()),
        "is_empty": len(content_clean) == 0,
        "is_short": len(content_clean) < 50,
        "repetitive_phrases": [],
        "starts_with_fragment": False,
        "ends_with_fragment": False,
        "quality_score": 100
    }
    
    if analysis["is_empty"]:
        analysis["quality_score"] = 0
        return analysis
    
    if analysis["is_short"]:
        analysis["quality_score"] -= 30
    
    # Detectar fragmentação (palavras muito curtas no início/fim)
    words = content_clean.split()
    if len(words) > 0:
        first_word = words[0]
        last_word = words[-1]
        if len(first_word) < 3 and len(words) > 1:
            analysis["starts_with_fragment"] = True
            analysis["quality_score"] -= 10
        if len(last_word) < 3 and len(words) > 1:
            analysis["ends_with_fragment"] = True
            analysis["quality_score"] -= 10
    
    # Detectar frases repetitivas
    repetitive = detect_repetitive_phrases(content_clean)
    if repetitive:
        analysis["repetitive_phrases"] = repetitive
        # Penalizar baseado na porcentagem de repetição
        max_percentage = max([p["percentage"] for p in repetitive])
        if max_percentage > 40:
            analysis["quality_score"] -= 50
        elif max_percentage > 20:
            analysis["quality_score"] -= 30
    
    analysis["quality_score"] = max(0, analysis["quality_score"])
    return analysis


async def validate_chunks(
    client,
    collection_name: str,
    limit: int = 100,
    sample_size: int = None
):
    """Valida chunks de uma collection"""
    
    msg.info(f"🔍 Validando chunks da collection: {collection_name}")
    
    try:
        collection = client.collections.get(collection_name)
    except Exception as e:
        msg.fail(f"❌ Erro ao acessar collection: {str(e)}")
        return
    
    # Buscar chunks
    msg.info(f"📥 Buscando até {limit} chunks...")
    chunks = []
    try:
        async for chunk in collection.iterator(limit=limit):
            chunk_data = {
                "uuid": str(chunk.uuid),
                "content": chunk.properties.get("content", ""),
                "chunk_id": chunk.properties.get("chunk_id", 0),
                "doc_uuid": chunk.properties.get("doc_uuid", ""),
                "chunk_lang": chunk.properties.get("chunk_lang", ""),
                "title": chunk.properties.get("title", ""),
            }
            chunks.append(chunk_data)
    except Exception as e:
        msg.fail(f"❌ Erro ao buscar chunks: {str(e)}")
        return
    
    if not chunks:
        msg.warn("⚠️ Nenhum chunk encontrado")
        return
    
    msg.good(f"✅ {len(chunks)} chunks recuperados")
    
    # Amostragem se especificado
    if sample_size and sample_size < len(chunks):
        import random
        chunks = random.sample(chunks, sample_size)
        msg.info(f"📊 Analisando amostra de {len(chunks)} chunks")
    
    # Análise
    msg.info("🔬 Analisando qualidade dos chunks...")
    
    analyses = []
    content_hashes = {}
    duplicates = []
    
    for chunk in chunks:
        analysis = analyze_chunk_quality(chunk)
        analyses.append(analysis)
        
        # Detectar duplicações exatas
        content_hash = get_content_hash(chunk["content"])
        if content_hash in content_hashes:
            duplicates.append({
                "uuid": chunk["uuid"],
                "chunk_id": chunk["chunk_id"],
                "duplicate_of": content_hashes[content_hash]["uuid"],
                "content_preview": chunk["content"][:100]
            })
        else:
            content_hashes[content_hash] = {
                "uuid": chunk["uuid"],
                "chunk_id": chunk["chunk_id"]
            }
    
    # Estatísticas
    total_chunks = len(analyses)
    empty_chunks = sum(1 for a in analyses if a["is_empty"])
    short_chunks = sum(1 for a in analyses if a["is_short"])
    fragmented_chunks = sum(1 for a in analyses if a["starts_with_fragment"] or a["ends_with_fragment"])
    repetitive_chunks = sum(1 for a in analyses if a["repetitive_phrases"])
    low_quality = sum(1 for a in analyses if a["quality_score"] < 50)
    
    avg_quality = sum(a["quality_score"] for a in analyses) / total_chunks if total_chunks > 0 else 0
    avg_length = sum(a["length"] for a in analyses) / total_chunks if total_chunks > 0 else 0
    avg_words = sum(a["word_count"] for a in analyses) / total_chunks if total_chunks > 0 else 0
    
    # Relatório
    msg.info("\n" + "="*80)
    msg.info("📊 RELATÓRIO DE VALIDAÇÃO DE CHUNKS")
    msg.info("="*80)
    msg.info(f"\nCollection: {collection_name}")
    msg.info(f"Total de chunks analisados: {total_chunks}")
    
    msg.info("\n📈 ESTATÍSTICAS GERAIS:")
    msg.info(f"  Média de qualidade: {avg_quality:.1f}/100")
    msg.info(f"  Média de tamanho: {avg_length:.0f} caracteres")
    msg.info(f"  Média de palavras: {avg_words:.1f} palavras")
    
    msg.info("\n⚠️ PROBLEMAS DETECTADOS:")
    if empty_chunks > 0:
        msg.warn(f"  Chunks vazios: {empty_chunks} ({empty_chunks/total_chunks*100:.1f}%)")
    if short_chunks > 0:
        msg.warn(f"  Chunks muito curtos (<50 chars): {short_chunks} ({short_chunks/total_chunks*100:.1f}%)")
    if fragmented_chunks > 0:
        msg.warn(f"  Chunks fragmentados: {fragmented_chunks} ({fragmented_chunks/total_chunks*100:.1f}%)")
    if repetitive_chunks > 0:
        msg.warn(f"  Chunks repetitivos: {repetitive_chunks} ({repetitive_chunks/total_chunks*100:.1f}%)")
    if len(duplicates) > 0:
        msg.warn(f"  Chunks duplicados (exatos): {len(duplicates)} ({len(duplicates)/total_chunks*100:.1f}%)")
    if low_quality > 0:
        msg.warn(f"  Chunks de baixa qualidade (<50): {low_quality} ({low_quality/total_chunks*100:.1f}%)")
    
    # Exemplos de problemas
    if repetitive_chunks > 0:
        msg.info("\n🔄 EXEMPLOS DE CHUNKS REPETITIVOS:")
        count = 0
        for analysis in analyses:
            if analysis["repetitive_phrases"]:
                count += 1
                if count <= 3:  # Mostrar apenas 3 exemplos
                    msg.warn(f"\n  Chunk {analysis['chunk_id']} (UUID: {analysis['uuid'][:8]}...):")
                    for phrase_info in analysis["repetitive_phrases"][:2]:  # Top 2 frases
                        msg.warn(f"    - '{phrase_info['phrase'][:60]}...' aparece {phrase_info['count']}x ({phrase_info['percentage']}% do chunk)")
    
    if duplicates:
        msg.info("\n🔁 EXEMPLOS DE CHUNKS DUPLICADOS:")
        for dup in duplicates[:5]:  # Mostrar apenas 5 exemplos
            msg.warn(f"  Chunk {dup['chunk_id']} (UUID: {dup['uuid'][:8]}...) é duplicado de {dup['duplicate_of'][:8]}...")
            msg.warn(f"    Preview: {dup['content_preview']}...")
    
    if low_quality > 0:
        msg.info("\n📉 CHUNKS DE BAIXA QUALIDADE (top 5 piores):")
        sorted_analyses = sorted(analyses, key=lambda x: x["quality_score"])[:5]
        for analysis in sorted_analyses:
            msg.warn(f"\n  Chunk {analysis['chunk_id']} (Score: {analysis['quality_score']}/100):")
            msg.warn(f"    Tamanho: {analysis['length']} chars, {analysis['word_count']} palavras")
            if analysis["repetitive_phrases"]:
                msg.warn(f"    Frases repetitivas: {len(analysis['repetitive_phrases'])}")
            if analysis["starts_with_fragment"]:
                msg.warn(f"    Começa com fragmento")
            if analysis["ends_with_fragment"]:
                msg.warn(f"    Termina com fragmento")
            preview = chunks[analyses.index(analysis)]["content"][:150]
            msg.warn(f"    Preview: {preview}...")
    
    msg.info("\n" + "="*80)
    
    # Retornar dados para uso programático
    return {
        "total_chunks": total_chunks,
        "avg_quality": avg_quality,
        "empty_chunks": empty_chunks,
        "short_chunks": short_chunks,
        "fragmented_chunks": fragmented_chunks,
        "repetitive_chunks": repetitive_chunks,
        "duplicates": len(duplicates),
        "low_quality": low_quality,
        "analyses": analyses,
        "duplicate_list": duplicates
    }


async def main():
    """Função principal"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Valida chunks no Weaviate")
    parser.add_argument("--collection", type=str, help="Nome da collection (ex: VERBA_Embedding_openai)")
    parser.add_argument("--limit", type=int, default=100, help="Número máximo de chunks a analisar (default: 100)")
    parser.add_argument("--sample", type=int, help="Tamanho da amostra aleatória (opcional)")
    parser.add_argument("--url", type=str, help="URL do Weaviate (ou usar WEAVIATE_URL_VERBA do .env)")
    parser.add_argument("--key", type=str, help="API Key do Weaviate (ou usar WEAVIATE_API_KEY_VERBA do .env)")
    
    args = parser.parse_args()
    
    # Conectar ao Weaviate
    w_url = args.url or os.getenv("WEAVIATE_URL_VERBA")
    w_key = args.key or os.getenv("WEAVIATE_API_KEY_VERBA")
    
    if not w_url:
        msg.fail("❌ WEAVIATE_URL_VERBA não encontrado. Use --url ou defina no .env")
        return
    
    msg.info(f"🔌 Conectando ao Weaviate: {w_url}")
    
    try:
        auth = AuthApiKey(w_key) if w_key else None
        client = weaviate.connect_to_weaviate_cloud(
            cluster_url=w_url,
            auth_credentials=auth
        ) if "weaviate.cloud" in w_url else weaviate.connect_to_local(
            host=w_url.replace("http://", "").replace("https://", "").split(":")[0],
            port=int(w_url.split(":")[-1]) if ":" in w_url else 8080
        )
        
        msg.good("✅ Conectado ao Weaviate")
    except Exception as e:
        msg.fail(f"❌ Erro ao conectar: {str(e)}")
        return
    
    # Se collection não especificada, listar collections disponíveis
    if not args.collection:
        msg.info("📋 Collections disponíveis:")
        try:
            collections = client.collections.list_all()
            for coll_name in collections:
                if "VERBA" in coll_name or "Embedding" in coll_name:
                    msg.info(f"  - {coll_name}")
        except Exception as e:
            msg.warn(f"⚠️ Não foi possível listar collections: {str(e)}")
        msg.info("\n💡 Use --collection para especificar uma collection")
        return
    
    # Validar chunks
    try:
        result = await validate_chunks(
            client,
            args.collection,
            limit=args.limit,
            sample_size=args.sample
        )
    except Exception as e:
        msg.fail(f"❌ Erro durante validação: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(main())

