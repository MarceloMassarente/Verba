"""
Script para validar chunks no Weaviate usando apenas HTTP/REST
Analisa duplicações, qualidade e fragmentação sem depender de gRPC
"""

import os
import sys
import json
import re
from pathlib import Path
from collections import Counter
from typing import List, Dict, Set
import hashlib
import httpx
from urllib.parse import urlparse

# Adicionar path do projeto
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from wasabi import msg

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
            if count >= 3:
                percentage = (count * seq_length) / len(words) * 100
                repetitive_phrases.append({
                    "phrase": phrase,
                    "count": count,
                    "length": seq_length,
                    "percentage": percentage
                })
    
    return sorted(repetitive_phrases, key=lambda x: x["count"], reverse=True)


def analyze_chunk_quality(chunk: dict) -> dict:
    """Analisa qualidade de um chunk"""
    content = chunk.get("content", "")
    
    analysis = {
        "uuid": chunk.get("uuid", ""),
        "chunk_id": chunk.get("chunk_id", 0),
        "length": len(content),
        "word_count": len(content.split()) if content else 0,
        "is_empty": not content or len(content.strip()) == 0,
        "is_short": len(content) < 50,
        "starts_with_fragment": False,
        "ends_with_fragment": False,
        "repetitive_phrases": [],
        "quality_score": 100
    }
    
    if analysis["is_empty"]:
        analysis["quality_score"] = 0
        return analysis
    
    if analysis["is_short"]:
        analysis["quality_score"] -= 20
    
    # Detectar fragmentação
    words = content.split()
    if words:
        first_word = words[0]
        last_word = words[-1]
        if len(first_word) < 3:
            analysis["starts_with_fragment"] = True
            analysis["quality_score"] -= 15
        if len(last_word) < 3:
            analysis["ends_with_fragment"] = True
            analysis["quality_score"] -= 15
    
    # Detectar repetição
    repetitive = detect_repetitive_phrases(content)
    if repetitive:
        analysis["repetitive_phrases"] = repetitive
        # Penalizar por repetição
        max_repetition = max(r["count"] for r in repetitive)
        if max_repetition >= 5:
            analysis["quality_score"] -= 40
        elif max_repetition >= 3:
            analysis["quality_score"] -= 20
    
    # Verificar se é tabela/gráfico (muitos números)
    numbers = re.findall(r'\d+', content)
    number_ratio = len(numbers) / analysis["word_count"] if analysis["word_count"] > 0 else 0
    if number_ratio > 0.3:
        # Tabelas/gráficos são OK mesmo com repetição
        analysis["is_table_or_chart"] = True
        if analysis["quality_score"] < 50:
            analysis["quality_score"] = min(70, analysis["quality_score"] + 20)
    
    analysis["quality_score"] = max(0, min(100, analysis["quality_score"]))
    
    return analysis


async def fetch_chunks_http(url: str, collection: str, limit: int = 100, api_key: str = None):
    """Busca chunks usando API REST HTTP do Weaviate"""
    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    
    headers = {
        "Content-Type": "application/json"
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    
    # Weaviate v4 usa endpoint diferente
    # Tentar v4 primeiro: /v1/collections/{collection}/objects
    endpoint_v4 = f"{base_url}/v1/collections/{collection}/objects"
    
    params = {
        "limit": limit,
        "include": "all"
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            # Tentar v4 primeiro
            response = await client.get(endpoint_v4, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            
            # Debug: ver estrutura da resposta
            msg.info(f"Debug: Status {response.status_code}, Resposta tipo: {type(data)}")
            if isinstance(data, dict):
                msg.info(f"Debug: Resposta tem {len(data)} chaves: {list(data.keys())[:5]}")
                if "objects" in data:
                    msg.info(f"Debug: objects tem {len(data['objects'])} itens")
                else:
                    msg.warn(f"Debug: Resposta nao tem 'objects'. Chaves: {list(data.keys())[:10]}")
            elif isinstance(data, list):
                msg.info(f"Debug: Resposta e uma lista com {len(data)} itens")
            else:
                msg.warn(f"Debug: Tipo inesperado: {type(data)}")
            
            chunks = []
            # Weaviate v4 pode retornar objetos diretamente ou em "objects"
            objects_list = data.get("objects", [])
            if not objects_list and isinstance(data, list):
                objects_list = data
            
            for obj in objects_list:
                # v4 pode ter estrutura diferente
                if isinstance(obj, dict):
                    props = obj.get("properties", {})
                    chunks.append({
                        "uuid": obj.get("id", str(obj.get("uuid", ""))),
                        "content": props.get("content", ""),
                        "chunk_id": props.get("chunk_id", 0),
                        "doc_uuid": props.get("doc_uuid", ""),
                        "chunk_lang": props.get("chunk_lang", ""),
                        "title": props.get("title", ""),
                    })
            
            msg.info(f"Debug: Processou {len(chunks)} chunks da resposta v4")
            return chunks
        except httpx.HTTPStatusError as e:
            msg.warn(f"Debug: HTTPStatusError {e.response.status_code}: {str(e)[:100]}")
            if e.response.status_code == 404:
                # Tentar v1 (formato antigo)
                endpoint_v1 = f"{base_url}/v1/objects"
                params_v1 = {
                    "class": collection,
                    "limit": limit
                }
                msg.info("Tentando endpoint v1...")
                response = await client.get(endpoint_v1, headers=headers, params=params_v1)
                response.raise_for_status()
                data = response.json()
                
                msg.info(f"Debug v1: Resposta tipo {type(data)}, chaves: {list(data.keys())[:5] if isinstance(data, dict) else 'N/A'}")
                if "objects" in data:
                    msg.info(f"Debug v1: objects tem {len(data['objects'])} itens")
                
                chunks = []
                for obj in data.get("objects", []):
                    props = obj.get("properties", {})
                    chunks.append({
                        "uuid": obj.get("id", ""),
                        "content": props.get("content", ""),
                        "chunk_id": props.get("chunk_id", 0),
                        "doc_uuid": props.get("doc_uuid", ""),
                        "chunk_lang": props.get("chunk_lang", ""),
                        "title": props.get("title", ""),
                    })
                
                msg.info(f"Debug v1: Processou {len(chunks)} chunks")
                return chunks
            else:
                raise


async def validate_chunks_http(
    url: str,
    collection_name: str,
    limit: int = 100,
    api_key: str = None
):
    """Valida chunks usando apenas HTTP"""
    
    msg.info(f"Validando chunks da collection: {collection_name}")
    msg.info(f"Buscando ate {limit} chunks via HTTP REST...")
    
    try:
        chunks = await fetch_chunks_http(url, collection_name, limit, api_key)
        msg.info(f"Debug: fetch_chunks_http retornou {len(chunks) if chunks else 0} chunks")
    except Exception as e:
        msg.fail(f"Erro ao buscar chunks: {str(e)}")
        import traceback
        traceback.print_exc()
        return
    
    if not chunks:
        msg.warn("Nenhum chunk encontrado")
        return
    
    msg.good(f"{len(chunks)} chunks recuperados")
    
    # Analisar qualidade
    msg.info("Analisando qualidade dos chunks...")
    
    analyses = []
    content_hashes = {}
    duplicates = []
    
    for chunk in chunks:
        analysis = analyze_chunk_quality(chunk)
        analyses.append(analysis)
        
        # Detectar duplicações
        content = chunk.get("content", "")
        if content:
            content_hash = get_content_hash(content)
            if content_hash in content_hashes:
                duplicates.append({
                    "uuid": chunk.get("uuid", ""),
                    "chunk_id": chunk.get("chunk_id", 0),
                    "duplicate_of": content_hashes[content_hash],
                    "content_preview": content[:100]
                })
            else:
                content_hashes[content_hash] = chunk.get("uuid", "")
    
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
    msg.info("RELATORIO DE VALIDACAO DE CHUNKS")
    msg.info("="*80)
    msg.info(f"\nCollection: {collection_name}")
    msg.info(f"Total de chunks analisados: {total_chunks}")
    
    msg.info("\nESTATISTICAS GERAIS:")
    msg.info(f"  Media de qualidade: {avg_quality:.1f}/100")
    msg.info(f"  Media de tamanho: {avg_length:.0f} caracteres")
    msg.info(f"  Media de palavras: {avg_words:.1f} palavras")
    
    msg.info("\nPROBLEMAS DETECTADOS:")
    if empty_chunks > 0:
        msg.warn(f"  Chunks vazios: {empty_chunks} ({empty_chunks/total_chunks*100:.1f}%)")
    if short_chunks > 0:
        msg.warn(f"  Chunks muito curtos (<50 chars): {short_chunks} ({short_chunks/total_chunks*100:.1f}%)")
    if fragmented_chunks > 0:
        msg.warn(f"  Chunks fragmentados: {fragmented_chunks} ({fragmented_chunks/total_chunks*100:.1f}%)")
    if repetitive_chunks > 0:
        msg.warn(f"  Chunks repetitivos: {repetitive_chunks} ({repetitive_chunks/total_chunks*100:.1f}%)")
    if duplicates:
        msg.warn(f"  Chunks duplicados (exatos): {len(duplicates)} ({len(duplicates)/total_chunks*100:.1f}%)")
    if low_quality > 0:
        msg.warn(f"  Chunks de baixa qualidade (<50): {low_quality} ({low_quality/total_chunks*100:.1f}%)")
    
    # Exemplos de problemas
    if repetitive_chunks > 0:
        msg.info("\nEXEMPLOS DE CHUNKS REPETITIVOS:")
        count = 0
        # Ordenar por maior repetição primeiro
        sorted_repetitive = sorted(
            [a for a in analyses if a["repetitive_phrases"]],
            key=lambda x: max(p["count"] for p in x["repetitive_phrases"]) if x["repetitive_phrases"] else 0,
            reverse=True
        )
        for analysis in sorted_repetitive:
            count += 1
            if count <= 10:  # Mostrar 10 exemplos
                max_repetition = max(p["count"] for p in analysis["repetitive_phrases"]) if analysis["repetitive_phrases"] else 0
                msg.warn(f"\n  Chunk {analysis['chunk_id']} (UUID: {analysis['uuid'][:8]}...), Score: {analysis['quality_score']}/100:")
                msg.warn(f"    Tamanho: {analysis['length']} chars, {analysis['word_count']} palavras")
                for phrase_info in analysis["repetitive_phrases"][:3]:  # Top 3 frases
                    msg.warn(f"    - '{phrase_info['phrase'][:80]}...' aparece {phrase_info['count']}x ({phrase_info['percentage']:.1f}% do chunk)")
                # Mostrar preview do conteúdo
                chunk_idx = analyses.index(analysis)
                if chunk_idx < len(chunks):
                    try:
                        preview = chunks[chunk_idx]["content"][:200].encode('utf-8', errors='ignore').decode('utf-8')
                        msg.warn(f"    Preview: {preview}...")
                    except:
                        msg.warn(f"    Preview: (erro ao exibir)")
    
    if duplicates:
        msg.info("\nEXEMPLOS DE CHUNKS DUPLICADOS:")
        for dup in duplicates[:5]:  # Mostrar apenas 5 exemplos
            try:
                preview = dup['content_preview'].encode('utf-8', errors='ignore').decode('utf-8')
                msg.warn(f"  Chunk {dup['chunk_id']} (UUID: {dup['uuid'][:8]}...) e duplicado de {dup['duplicate_of'][:8]}...")
                msg.warn(f"    Preview: {preview}...")
            except:
                msg.warn(f"  Chunk {dup['chunk_id']} (UUID: {dup['uuid'][:8]}...) e duplicado de {dup['duplicate_of'][:8]}...")
    
    if low_quality > 0:
        msg.info("\nCHUNKS DE BAIXA QUALIDADE (top 5 piores):")
        sorted_analyses = sorted(analyses, key=lambda x: x["quality_score"])[:5]
        for analysis in sorted_analyses:
            msg.warn(f"\n  Chunk {analysis['chunk_id']} (Score: {analysis['quality_score']}/100):")
            msg.warn(f"    Tamanho: {analysis['length']} chars, {analysis['word_count']} palavras")
            if analysis["repetitive_phrases"]:
                msg.warn(f"    Frases repetitivas: {len(analysis['repetitive_phrases'])}")
            if analysis["starts_with_fragment"]:
                msg.warn(f"    Comeca com fragmento")
            if analysis["ends_with_fragment"]:
                msg.warn(f"    Termina com fragmento")
            try:
                preview = chunks[analyses.index(analysis)]["content"][:150].encode('utf-8', errors='ignore').decode('utf-8')
                msg.warn(f"    Preview: {preview}...")
            except:
                msg.warn(f"    Preview: (erro ao exibir)")
    
    msg.info("\n" + "="*80)
    
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
    
    parser = argparse.ArgumentParser(description="Valida chunks no Weaviate usando HTTP REST")
    parser.add_argument("--collection", type=str, help="Nome da collection (ex: VERBA_Embedding_openai)")
    parser.add_argument("--limit", type=int, default=100, help="Numero maximo de chunks a analisar (default: 100)")
    parser.add_argument("--url", type=str, help="URL do Weaviate (ou usar WEAVIATE_URL_VERBA do .env)")
    parser.add_argument("--key", type=str, help="API Key do Weaviate (ou usar WEAVIATE_API_KEY_VERBA do .env)")
    
    args = parser.parse_args()
    
    # Conectar ao Weaviate
    w_url = args.url or os.getenv("WEAVIATE_URL_VERBA")
    w_key = args.key or os.getenv("WEAVIATE_API_KEY_VERBA")
    
    if not w_url:
        msg.fail("WEAVIATE_URL_VERBA nao encontrado. Use --url ou defina no .env")
        return
    
    if not args.collection:
        msg.fail("Collection nao especificada. Use --collection")
        return
    
    # Validar chunks
    try:
        import asyncio
        result = await validate_chunks_http(
            w_url,
            args.collection,
            limit=args.limit,
            api_key=w_key
        )
    except Exception as e:
        msg.fail(f"Erro durante validacao: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

