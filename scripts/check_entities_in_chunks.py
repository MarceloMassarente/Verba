"""
Script para verificar se chunks têm entidades detectadas (entity_mentions)
Acessa o banco diretamente via HTTP REST API do Weaviate
"""

import asyncio
import httpx
import json
from urllib.parse import urlparse
from wasabi import msg
import argparse

async def fetch_chunks_http(url: str, collection: str, limit: int = 100) -> list:
    """Busca chunks via HTTP REST do Weaviate"""
    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    
    headers = {"Content-Type": "application/json"}
    
    # Endpoint v1 (Weaviate v4)
    endpoint_v1 = f"{base_url}/v1/objects"
    params = {
        "class": collection,
        "limit": limit
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.get(endpoint_v1, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            
            chunks = []
            for obj in data.get("objects", []):
                props = obj.get("properties", {})
                chunks.append({
                    "uuid": obj.get("id", ""),
                    "content": props.get("content", "")[:100],  # Preview
                    "entity_mentions": props.get("entity_mentions", ""),
                    "entities_local_ids": props.get("entities_local_ids", []),
                    "section_entity_ids": props.get("section_entity_ids", []),
                    "etl_version": props.get("etl_version", ""),
                })
            
            return chunks
        except Exception as e:
            msg.fail(f"Erro ao buscar chunks: {str(e)}")
            return []

async def check_entities(url: str, collection: str, limit: int = 100):
    """Verifica presença de entidades nos chunks"""
    msg.info(f"Conectando ao Weaviate: {url}")
    msg.info(f"Collection: {collection}")
    msg.info(f"Analisando {limit} chunks...\n")
    
    chunks = await fetch_chunks_http(url, collection, limit)
    
    if not chunks:
        msg.fail("Nenhum chunk encontrado")
        return
    
    msg.info(f"✅ {len(chunks)} chunks recuperados\n")
    
    # Análise
    total = len(chunks)
    with_entity_mentions = 0
    with_entity_ids = 0
    empty_chunks = 0
    etl_versions = {}
    
    for chunk in chunks:
        # Verificar entity_mentions (novo campo)
        entity_mentions_str = chunk.get("entity_mentions", "").strip()
        if entity_mentions_str and entity_mentions_str != "[]":
            with_entity_mentions += 1
            try:
                mentions = json.loads(entity_mentions_str)
                msg.good(f"  ✅ Chunk {chunk['uuid'][:8]}... tem {len(mentions)} entidades: {[m['text'] for m in mentions]}")
            except:
                pass
        
        # Verificar campos legados
        if chunk.get("entities_local_ids") or chunk.get("section_entity_ids"):
            with_entity_ids += 1
        
        # Verificar versão do ETL
        etl_version = chunk.get("etl_version", "none")
        etl_versions[etl_version] = etl_versions.get(etl_version, 0) + 1
        
        # Mostrar preview se estiver vazio
        if not entity_mentions_str and not chunk.get("entities_local_ids"):
            if empty_chunks < 3:  # Mostrar apenas 3 exemplos
                try:
                    preview = chunk['content'].encode('utf-8', errors='ignore').decode('utf-8')
                    msg.warn(f"  Chunk {chunk['uuid'][:8]}... VAZIO (preview: '{preview}')")
                except:
                    msg.warn(f"  Chunk {chunk['uuid'][:8]}... VAZIO")
            empty_chunks += 1
    
    # Relatório
    msg.info(f"\n{'='*80}")
    msg.info("RELATORIO DE ENTIDADES NOS CHUNKS")
    msg.info(f"{'='*80}")
    msg.info(f"\nESTATISTICAS:")
    msg.info(f"  Total de chunks analisados: {total}")
    msg.info(f"  Chunks com entity_mentions (novo): {with_entity_mentions} ({with_entity_mentions/total*100:.1f}%)")
    msg.info(f"  Chunks com entity_ids legados: {with_entity_ids} ({with_entity_ids/total*100:.1f}%)")
    msg.info(f"  Chunks SEM nenhuma entidade: {empty_chunks} ({empty_chunks/total*100:.1f}%)")
    
    msg.info(f"\nVERSOES DO ETL DETECTADAS:")
    for version, count in sorted(etl_versions.items()):
        msg.info(f"  {version}: {count} chunks")
    
    msg.info(f"\n{'='*80}")
    
    # Diagnóstico
    msg.info("\nDIAGNOSTICO:")
    if with_entity_mentions == 0 and with_entity_ids == 0:
        msg.fail("  NENHUMA ENTIDADE DETECTADA")
        msg.warn("  Motivo: ETL inteligente ainda nao foi executado")
        msg.info("  Solucao: Re-importe os documentos para executar o novo ETL")
    elif with_entity_mentions > 0:
        msg.good(f"  ETL INTELIGENTE FUNCIONANDO ({with_entity_mentions} chunks com entidades)")
    elif with_entity_ids > 0:
        msg.good(f"  ETL LEGADO (com gazetteer) ({with_entity_ids} chunks com entity_ids)")
    else:
        msg.warn("  SITUACAO MISTA - alguns chunks tem entidades, outros nao")

async def main():
    parser = argparse.ArgumentParser(description="Verificar entidades nos chunks do Weaviate")
    parser.add_argument("--url", required=True, help="URL do Weaviate (ex: https://weaviate.example.com)")
    parser.add_argument("--collection", default="VERBA_Embedding_all_MiniLM_L6_v2", help="Nome da collection")
    parser.add_argument("--limit", type=int, default=100, help="Número de chunks a analisar")
    
    args = parser.parse_args()
    
    await check_entities(args.url, args.collection, args.limit)

if __name__ == "__main__":
    asyncio.run(main())

