
from typing import Optional, Dict, Any, List, Tuple
from wasabi import msg
from goldenverba.components.chunk import Chunk
from verba_extensions.compatibility.weaviate_imports import Filter, WEAVIATE_V4
import json
import re

def get_config_value(config, key, default=None):
    if key not in config: return default
    item = config[key]
    if item is None: return default
    if hasattr(item, 'value'): return item.value if item.value is not None else default
    if isinstance(item, dict): return item.get('value', default)
    return item


def _apply_proximity_boost(
    self,
    chunks: List[Any],
    entity_chunk_positions: Dict[str, List[int]],
    proximity_window: int = 2
) -> List[Any]:
    """
    Aplica boost de proximidade aos chunks: prioriza chunks que estão próximos
    aos chunks que mencionam entidades.
    
    Exemplo:
    - Chunk 1: Menciona "Apple" (chunk_id=0)
    - Chunk 2: Fala sobre "governança" (chunk_id=1, não menciona Apple)
    - Chunk 3: Fala sobre "inovação" (chunk_id=2)
    
    Com proximity_window=2:
    - Chunk 2 (id=1) está a ±1 de chunk 0 → BOOST ALTO
    - Chunk 3 (id=2) está a ±2 de chunk 0 → BOOST MÉDIO
    
    Args:
        chunks: Lista de chunks retornados da busca semântica
        entity_chunk_positions: {doc_uuid: [chunk_ids]} - Posições dos chunks com entidades
        proximity_window: Janela de proximidade (chunks ±N posições)
    
    Returns:
        Lista de chunks reordenada com boost de proximidade aplicado
    """
    if not chunks or not entity_chunk_positions:
        return chunks
    
    try:
        # Criar lista de (score_boosted, chunk) para reordenar
        boosted_chunks = []
        
        for chunk in chunks:
            if not hasattr(chunk, 'properties'):
                boosted_chunks.append((0.0, chunk))
                continue
            
            doc_uuid = str(chunk.properties.get("doc_uuid", ""))
            chunk_id_raw = chunk.properties.get("chunk_id")
            
            if not doc_uuid or chunk_id_raw is None:
                boosted_chunks.append((0.0, chunk))
                continue
            
            try:
                chunk_id = int(float(chunk_id_raw))
            except (ValueError, TypeError):
                boosted_chunks.append((0.0, chunk))
                continue
            
            # Calcular boost baseado em proximidade
            proximity_boost = 0.0
            
            if doc_uuid in entity_chunk_positions:
                entity_chunk_ids = entity_chunk_positions[doc_uuid]
                
                # Verificar proximidade a qualquer chunk com entidade
                for entity_chunk_id in entity_chunk_ids:
                    distance = abs(chunk_id - entity_chunk_id)
                    
                    if distance == 0:
                        # Chunk é o próprio chunk com entidade
                        proximity_boost = max(proximity_boost, 1.0)
                    elif distance <= proximity_window:
                        # Boost decresce com a distância
                        # Distância 1: boost 0.8, Distância 2: boost 0.5
                        boost_value = 1.0 - (distance * 0.3)
                        proximity_boost = max(proximity_boost, max(0.0, boost_value))
            
            # Score original do chunk (se disponível)
            original_score = 0.0
            if hasattr(chunk, 'metadata') and hasattr(chunk.metadata, 'score'):
                original_score = float(chunk.metadata.score) if chunk.metadata.score else 0.0
            
            # Score combinado: 70% original + 30% boost de proximidade
            # Isso garante que chunks semanticamente relevantes ainda sejam priorizados
            combined_score = (original_score * 0.7) + (proximity_boost * 0.3)
            
            boosted_chunks.append((combined_score, chunk))
        
        # Ordenar por score combinado (maior primeiro)
        boosted_chunks.sort(key=lambda x: x[0], reverse=True)
        
        # Retornar apenas os chunks (sem scores)
        return [chunk for _, chunk in boosted_chunks]
        
    except Exception as e:
        msg.debug(f"    Erro ao aplicar boost de proximidade: {str(e)}")
        # Em caso de erro, retornar chunks originais
        return chunks


def _format_document_list_result(self, documents_info: List[Dict], query: str) -> List[Chunk]:
    """
    Formata resultado de listagem de documentos como chunks para LLM.
    
    Args:
        documents_info: Lista de dicionários com informações dos documentos
        query: Query original do usuário
    
    Returns:
        Lista de chunks sintéticos com lista formatada
    """
    formatted_text = f"Documentos encontrados para a query '{query}':\n\n"
    for i, doc in enumerate(documents_info, 1):
        formatted_text += f"{i}. {doc['title']} ({doc['chunk_count']} chunks)\n"
    
    # Retornar como chunk para compatibilidade com pipeline
    synthetic_chunk = Chunk(
        content=formatted_text,
        chunk_id=0,
        start_i=0,
        end_i=len(formatted_text)
    )
    return [synthetic_chunk]


async def _process_chunks(
    self,
    client,
    chunks,
    weaviate_manager,
    embedder,
    config,
    detected_frameworks: List[str] = None,
    detected_concepts: List[str] = None,
    detected_companies: List[str] = None,
    detected_content_type: str = "",
):
    """Processa chunks aplicando window technique"""
    
    chunk_window_config = config.get("Chunk Window", {})
    if hasattr(chunk_window_config, 'value'):
        chunk_window = int(chunk_window_config.value)
    else:
        chunk_window = 1  # Default
    
    # Log removido para reduzir verbosidade (chunk window é aplicado silenciosamente)
    
    if chunk_window > 0 and chunks:
        # Agrupa chunks adjacentes com window, evitando repetição excessiva
        windowed_chunks = []
        for i, chunk in enumerate(chunks):
            context_chunks = chunks[max(0, i - chunk_window):min(len(chunks), i + chunk_window + 1)]
            
            # Coletar conteúdos únicos (evitar duplicação exata)
            contents = []
            seen_contents = set()
            for c in context_chunks:
                content = c.properties["content"] if hasattr(c, "properties") else c.get("content", "")
                content_normalized = content.strip().lower()
                # Evitar adicionar conteúdo exatamente igual
                if content_normalized and content_normalized not in seen_contents:
                    contents.append(content)
                    seen_contents.add(content_normalized)
            
            # Combinar com separador adequado
            combined_content = " ".join(contents)
            
            # Se o conteúdo combinado for muito repetitivo, usar apenas o chunk central
            # (evitar criar repetição massiva)
            if len(contents) > 1:
                # Verificar se há repetição excessiva na combinação
                words = combined_content.split()
                if len(words) > 10:
                    # Contar repetições de sequências curtas
                    seq_counts = {}
                    for seq_len in [3, 4]:
                        if len(words) >= seq_len * 2:
                            for j in range(len(words) - seq_len + 1):
                                seq = " ".join(words[j:j+seq_len])
                                seq_counts[seq] = seq_counts.get(seq, 0) + 1
                    
                    max_repetition = max(seq_counts.values()) if seq_counts else 0
                    # Se há muita repetição (mais de 5x), usar apenas o chunk central
                    if max_repetition > 5:
                        # Log removido para reduzir verbosidade (chunk window aplicado silenciosamente)
                        central_content = context_chunks[len(context_chunks)//2]
                        combined_content = central_content.properties["content"] if hasattr(central_content, "properties") else central_content.get("content", "")
            
            # Atualiza o content do chunk atual
            if hasattr(chunk, "properties"):
                chunk.properties["content"] = combined_content
            else:
                chunk["content"] = combined_content
            windowed_chunks.append(chunk)
        chunks = windowed_chunks
    
    # Aplicar reranking inteligente se temos dados enriquecidos da query
    if detected_frameworks or detected_concepts or detected_companies or detected_content_type:
        try:
            query_enriched = {
                "frameworks": detected_frameworks,
                "conceitos_negocio": detected_concepts,
                "companies": detected_companies,
                "tipo_conteudo": detected_content_type
            }
            
            # Converter chunks para formato de dict para reranking
            chunks_dict = []
            for chunk in chunks:
                # Acessa propriedades do chunk (Weaviate retorna objetos com .properties)
                if hasattr(chunk, 'properties'):
                    props = chunk.properties
                elif isinstance(chunk, dict):
                    props = chunk
                else:
                    props = {}
                
                chunk_dict = {
                    "frameworks": props.get("frameworks", []),
                    "companies": props.get("companies", []),
                    "conceitos_negocio": props.get("conceitos_negocio", []),
                    "tipo_conteudo": props.get("tipo_conteudo", "contexto"),
                    "_additional": getattr(chunk, '_additional', {}) if hasattr(chunk, '_additional') else {}
                }
                chunks_dict.append(chunk_dict)
            
            # Aplicar reranking
            reranked_dicts = self._rerank_with_semantic_filters(chunks_dict, query_enriched)
            
            # Reordenar chunks originais baseado no reranking
            # Criar mapa de score final
            score_map = {i: r['final_score'] for i, r in enumerate(reranked_dicts)}
            
            # Ordenar índices por score
            sorted_indices = sorted(range(len(chunks)), key=lambda i: score_map.get(i, 0.0), reverse=True)
            
            # Reordenar chunks
            chunks = [chunks[i] for i in sorted_indices]
            
            msg.info(f"  🎯 Reranking aplicado: {len(chunks)} chunks reordenados por score semântico")
        except Exception as e:
            msg.debug(f"  Erro ao aplicar reranking (não crítico): {str(e)}")
    
    return (chunks, "Chunks retrieved with entity-aware filtering")


def _is_chunk_quality_good(self, chunk_content: str, chunk_window: int = 0) -> bool:
    """Valida qualidade do chunk antes de incluir no contexto
    
    Detecta:
    - Chunks repetitivos (mesmo texto repetido múltiplas vezes)
    - Chunks fragmentados (começam/fim no meio de palavras)
    - Chunks muito curtos ou vazios
    
    NÃO filtra:
    - Tabelas/gráficos (muitos números, poucas palavras)
    - Chunks com dados estruturados legítimos
    - Chunks combinados via Chunk Window (espera-se alguma repetição)
    - Repetições de cabeçalhos/rodapés de documento (normal em PDFs)
    
    Args:
        chunk_content: Conteúdo do chunk a validar
        chunk_window: Tamanho do chunk window usado (0 = não usado)
    """
    if not chunk_content or len(chunk_content.strip()) < 10:
        return False
    
    content = chunk_content.strip()
    words = content.split()
    if len(words) < 3:
        return False
    
    # Detectar e remover cabeçalhos/rodapés comuns de documentos PDF
    # Cabeçalhos/rodapés geralmente aparecem no início ou fim e são repetidos em múltiplos chunks
    # Exemplo: "Documento de discussão São Paulo, 17 de setembro de 2025 1 AGENDA Sobre a..."
    import re
    
    # Padrões comuns de cabeçalhos/rodapés
    lines = content.split('\n')
    
    # Verificar primeiras 2-3 linhas (possível cabeçalho)
    header_lines = [line.strip() for line in lines[:3] if line.strip()]
    # Verificar últimas 2-3 linhas (possível rodapé)
    footer_lines = [line.strip() for line in lines[-3:] if line.strip()]
    
    # Padrões de palavras-chave de cabeçalhos/rodapés
    header_footer_keywords = ['documento', 'discussão', 'agenda', 'página', 'data', 'setembro', 
                              'outubro', 'novembro', 'dezembro', 'janeiro', 'fevereiro', 'março', 
                              'abril', 'maio', 'junho', 'julho', 'agosto']
    
    potential_headers_footers = []
    
    # 1. Verificar linhas individuais (cabeçalhos simples)
    for line in header_lines + footer_lines:
        if len(line) < 150 and any(keyword in line.lower() for keyword in header_footer_keywords):
            potential_headers_footers.append(line)
    
    # 2. Detectar padrão específico: "Documento de discussão [Local] [Data] [Número] AGENDA [Tópicos]"
    # Padrão flexível que captura o cabeçalho completo
    header_pattern = r'Documento de discussão[^.]*?\d+\s+de\s+\w+\s+de\s+\d+[^.]*?AGENDA[^.]*?(?:Modelo|Abordagem|Sobre|Sobre a|da|de|na|em)'
    content_start = content[:250]  # Primeiros 250 caracteres (onde cabeçalho geralmente está)
    header_match = re.search(header_pattern, content_start, re.IGNORECASE)
    if header_match:
        header_text = header_match.group(0).strip()
        if header_text not in potential_headers_footers:
            potential_headers_footers.append(header_text)
    
    # 3. Detectar sequências repetitivas no início que parecem cabeçalhos
    # Se os primeiros 80-150 caracteres aparecem múltiplas vezes, provavelmente é cabeçalho
    for check_len in [80, 120, 150]:
        first_chars = content[:check_len].strip()
        if len(first_chars) < 40:  # Muito curto, pular
            continue
        # Contar quantas vezes aparece (case-insensitive)
        occurrences = len(re.findall(re.escape(first_chars), content, re.IGNORECASE))
        # Se aparece 2+ vezes e contém palavras-chave de cabeçalho, é provável cabeçalho
        if occurrences >= 2 and any(keyword in first_chars.lower() for keyword in header_footer_keywords):
            if first_chars not in potential_headers_footers:
                potential_headers_footers.append(first_chars)
            break  # Encontrou um, não precisa verificar outros tamanhos
    
    # Remover cabeçalhos/rodapés do conteúdo para verificação de repetição
    content_for_repetition_check = content
    if potential_headers_footers:
        # Remover ocorrências de cabeçalhos/rodapés (podem aparecer múltiplas vezes)
        for header_footer in potential_headers_footers:
            # Remover todas as ocorrências (case-insensitive parcial)
            # Usar regex para remover variações
            escaped = re.escape(header_footer)
            # Permitir pequenas variações (espaços extras, etc.)
            pattern = escaped.replace(r'\ ', r'\s+')
            content_for_repetition_check = re.sub(pattern, ' ', content_for_repetition_check, flags=re.IGNORECASE)
        
        # Limpar espaços múltiplos
        content_for_repetition_check = re.sub(r'\s+', ' ', content_for_repetition_check).strip()
        # Log removido para reduzir verbosidade (cabeçalhos detectados silenciosamente)
    
    # Se após remover cabeçalhos/rodapés o conteúdo ficou muito pequeno, usar conteúdo original
    if len(content_for_repetition_check.split()) < 5:
        content_for_repetition_check = content
    
    # Verificar se é uma tabela/gráfico (muitos números, poucas palavras)
    # Chunks de tabelas/gráficos são legítimos mesmo que tenham padrões repetitivos
    numbers = re.findall(r'\d+', content)
    number_ratio = len(numbers) / len(words) if words else 0
    
    # Se mais de 30% do conteúdo são números, provavelmente é tabela/gráfico
    # Aceitar esses chunks mesmo com repetição
    is_likely_table_or_chart = number_ratio > 0.3
    
    if is_likely_table_or_chart:
        # Para tabelas/gráficos, ser mais permissivo com repetição
        # Apenas filtrar se for claramente um erro (sequência muito curta repetida muitas vezes)
        if len(words) > 20:  # Tabelas grandes são OK
            return True
    
    # Ajustar threshold baseado no chunk window
    # Quando chunks são combinados (chunk_window > 0), espera-se mais repetição
    # porque chunks adjacentes podem ter conteúdo similar
    base_threshold_short = 5  # Sequências curtas (3 palavras): aceita até 5 repetições
    base_threshold_medium = 4  # Sequências médias (4 palavras): aceita até 4 repetições
    base_threshold_long = 3   # Sequências longas (5 palavras): aceita até 3 repetições
    
    # Aumentar threshold se chunk window está ativo (chunks combinados)
    if chunk_window > 0:
        # Chunks combinados podem ter mais repetição natural
        window_multiplier = 1.5 + (chunk_window * 0.3)  # Ex: window=3 → multiplier=2.4
        base_threshold_short = int(base_threshold_short * window_multiplier)
        base_threshold_medium = int(base_threshold_medium * window_multiplier)
        base_threshold_long = int(base_threshold_long * window_multiplier)
    
    # Ajustar ainda mais para tabelas/gráficos
    if is_likely_table_or_chart:
        base_threshold_short = max(base_threshold_short, 8)
        base_threshold_medium = max(base_threshold_medium, 6)
        base_threshold_long = max(base_threshold_long, 5)
    
    # Usar conteúdo sem cabeçalhos/rodapés para verificação de repetição
    words_for_repetition = content_for_repetition_check.split()
    
    # Detectar repetição excessiva: verifica sequências de diferentes tamanhos
    # Verificar se há padrões repetitivos (mesma sequência de palavras repetida)
    # Exemplo: "mização da revisão tarifária" repetido múltiplas vezes
    # Verifica sequências de 3, 4 e 5 palavras para capturar diferentes padrões
    max_repetition = 0
    max_repetition_seq_length = 0
    
    for seq_length in [3, 4, 5]:
        if len(words_for_repetition) < seq_length:
            continue
        word_sequences = {}
        for i in range(len(words_for_repetition) - seq_length + 1):
            seq = " ".join(words_for_repetition[i:i+seq_length])
            word_sequences[seq] = word_sequences.get(seq, 0) + 1
        
        current_max = max(word_sequences.values()) if word_sequences else 0
        if current_max > max_repetition:
            max_repetition = current_max
            max_repetition_seq_length = seq_length
    
    # Aplicar threshold apropriado baseado no tamanho da sequência repetida
    if max_repetition_seq_length == 3:
        threshold = base_threshold_short
    elif max_repetition_seq_length == 4:
        threshold = base_threshold_medium
    elif max_repetition_seq_length == 5:
        threshold = base_threshold_long
    else:
        threshold = base_threshold_medium  # Default
    
    # Filtrar apenas se repetição for claramente excessiva
    # E também verificar se a repetição representa uma fração significativa do chunk
    # Usar words_for_repetition (sem cabeçalhos/rodapés) para cálculo de fração
    if max_repetition > threshold:
        # Calcular fração do chunk ocupada pela sequência repetida (usando conteúdo sem cabeçalhos/rodapés)
        repeated_fraction = (max_repetition * max_repetition_seq_length) / len(words_for_repetition) if len(words_for_repetition) > 0 else 0
        
        # Filtrar apenas se repetição é alta E ocupa mais de 40% do chunk (sem cabeçalhos/rodapés)
        # (permite repetição moderada em chunks longos)
        if repeated_fraction > 0.4:
            # Log removido para reduzir verbosidade (filtros são contabilizados ao final)
            return False
        else:
            # Repetição alta mas não ocupa tanto espaço - provavelmente OK
            return True
    
    # Verificação adicional: detectar repetição de frases completas (não apenas sequências curtas)
    # Útil para casos como "mização da revisão tarifária" ou frases completas repetidas
    # Para tabelas/gráficos, verificar apenas frases longas (não números)
    min_phrase_length = 6 if is_likely_table_or_chart else 4
    max_phrase_length = 15  # Frases muito longas podem ser parágrafos completos
    
    # Ajustar thresholds de repetição de frases baseado no chunk window
    # Quando chunks são combinados, frases podem se repetir mais naturalmente
    phrase_repetition_multiplier = 1.0
    if chunk_window > 0:
        phrase_repetition_multiplier = 1.5 + (chunk_window * 0.2)  # Ex: window=3 → multiplier=2.1
    
    if len(words_for_repetition) > 10:
        # Verificar sequências de diferentes tamanhos (4-15 palavras)
        # Usar words_for_repetition para ignorar repetições de cabeçalhos/rodapés
        for seq_length in range(min_phrase_length, min(max_phrase_length + 1, len(words_for_repetition) // 2 + 1)):
            if len(words_for_repetition) < seq_length * 2:  # Precisa ter pelo menos 2 repetições
                continue
            
            phrase_counts = {}
            for i in range(len(words_for_repetition) - seq_length + 1):
                phrase = " ".join(words_for_repetition[i:i+seq_length])
                # Para tabelas/gráficos, ignorar sequências que são principalmente números
                if is_likely_table_or_chart:
                    # Se a frase tem mais de 50% números, provavelmente é parte de uma tabela legítima
                    phrase_numbers = len(re.findall(r'\d+', phrase))
                    if phrase_numbers / seq_length > 0.5:
                        continue
                
                phrase_counts[phrase] = phrase_counts.get(phrase, 0) + 1
            
            if phrase_counts:
                most_common_phrase = max(phrase_counts.items(), key=lambda x: x[1])
                phrase_text, phrase_count = most_common_phrase
                
                # Para frases longas (8+ palavras), ser mais permissivo
                # Para frases médias (4-7 palavras), ser mais restritivo
                if seq_length >= 8:
                    # Frases longas: filtrar apenas se aparecer muitas vezes E representar >30% do chunk
                    threshold_ratio = 0.3
                    min_repetitions = int(2 * phrase_repetition_multiplier)
                else:
                    # Frases médias: filtrar se aparecer muitas vezes E representar >40% do chunk
                    threshold_ratio = 0.4
                    min_repetitions = int(2 * phrase_repetition_multiplier)
                
                # Aumentar threshold_ratio quando chunk window está ativo (mais tolerante)
                if chunk_window > 0:
                    threshold_ratio = threshold_ratio * (1.0 + chunk_window * 0.1)  # Ex: window=3 → +30%
                
                # Usar words_for_repetition para calcular fração (ignora cabeçalhos/rodapés)
                if phrase_count >= min_repetitions and (phrase_count * seq_length) / len(words_for_repetition) > threshold_ratio:
                    # Log removido para reduzir verbosidade (filtros são contabilizados ao final)
                    return False
    
    # Detectar fragmentação: chunk começa ou termina no meio de palavra
    # (palavras muito curtas no início/fim podem indicar fragmentação)
    if len(words) > 0:
        first_word = words[0]
        last_word = words[-1]
        # Palavras muito curtas no início/fim podem ser fragmentos
        if len(first_word) < 3 and len(words) > 1:
            # Log removido para reduzir verbosidade (filtros são contabilizados ao final)
            return False
    
    return True


def combine_context(self, documents: list[dict], chunk_window: int = 0) -> tuple[str, list[dict], dict]:
    """Combina contexto dos documentos, filtrando chunks de baixa qualidade
    
    Args:
        documents: Lista de documentos com chunks
        chunk_window: Tamanho do chunk window usado (para ajustar thresholds de qualidade)
    
    Returns:
        tuple: (context_string, filtered_documents, filter_info)
            filter_info: dict com informações sobre filtragem {'fallback_used': bool, 'filtered_count': int, 'total_count': int}
    """
    from goldenverba.components.retriever.WindowRetriever import WindowRetriever
    
    # Filtrar chunks de baixa qualidade antes de combinar
    filtered_documents = []
    total_chunks = 0
    filtered_chunks = 0
    fallback_used = False
    
    for document in documents:
        filtered_chunks_list = []
        for chunk in document["chunks"]:
            total_chunks += 1
            chunk_content = chunk.get("content", "")
            if self._is_chunk_quality_good(chunk_content, chunk_window=chunk_window):
                filtered_chunks_list.append(chunk)
            else:
                filtered_chunks += 1
        
        # Só adicionar documento se tiver pelo menos um chunk válido
        if filtered_chunks_list:
            filtered_document = document.copy()
            filtered_document["chunks"] = filtered_chunks_list
            filtered_documents.append(filtered_document)
    
    # FALLBACK 1: Se mais de 80% dos chunks foram filtrados, tentar novamente com thresholds mais relaxados
    if total_chunks > 0 and filtered_chunks / total_chunks > 0.8:
        # Log consolidado - apenas uma mensagem ao invés de múltiplas
        msg.warn(f"  ⚠️ {filtered_chunks}/{total_chunks} chunks filtrados - ativando modo emergência")
        
        # Segunda passada com modo emergência (thresholds mais relaxados)
        filtered_documents_emergency = []
        filtered_chunks_emergency = 0
        
        for document in documents:
            filtered_chunks_list = []
            for chunk in document["chunks"]:
                chunk_content = chunk.get("content", "")
                # Modo emergência: apenas filtrar chunks completamente vazios ou muito fragmentados
                if chunk_content and len(chunk_content.strip()) >= 10:
                    # Apenas verificar fragmentação extrema (palavras muito curtas no início/fim)
                    words = chunk_content.strip().split()
                    if len(words) >= 3:
                        first_word = words[0] if words else ""
                        # Apenas filtrar se começar com fragmento muito óbvio (1-2 caracteres)
                        if len(first_word) >= 2:
                            filtered_chunks_list.append(chunk)
                        else:
                            filtered_chunks_emergency += 1
                    else:
                        filtered_chunks_emergency += 1
                else:
                    filtered_chunks_emergency += 1
            
            if filtered_chunks_list:
                filtered_document = document.copy()
                filtered_document["chunks"] = filtered_chunks_list
                filtered_documents_emergency.append(filtered_document)
        
        # Se modo emergência conseguiu salvar alguns chunks, usar eles
        if len(filtered_documents_emergency) > 0:
            # Log reduzido
            msg.info(f"  ✅ Modo emergência: {total_chunks - filtered_chunks_emergency}/{total_chunks} chunks mantidos")
            filtered_documents = filtered_documents_emergency
            filtered_chunks = filtered_chunks_emergency
            fallback_used = True
        else:
            # Modo emergência também falhou, usar todos os chunks originais
            msg.warn(f"  ⚠️ Modo emergência falhou - usando todos os chunks originais")
            filtered_documents = documents
            filtered_chunks = 0
            fallback_used = True
    
    # FALLBACK 2: Se ainda não há documentos, usar todos os chunks originais
    if len(filtered_documents) == 0 and len(documents) > 0:
        # Log consolidado
        msg.warn(f"  ⚠️ Todos os {total_chunks} chunks filtrados - usando fallback final")
        filtered_documents = documents
        filtered_chunks = 0
        fallback_used = True
    
    # Mostrar mensagem de filtragem apenas se não foi usado fallback (log reduzido)
    if filtered_chunks > 0 and not fallback_used and filtered_chunks < total_chunks * 0.5:
        # Apenas logar se menos de 50% foram filtrados (casos normais)
        pass  # Log removido para reduzir verbosidade
    elif fallback_used:
        # Log já foi feito acima, não repetir
        pass
    
    # Usar método do WindowRetriever para combinar contexto
    window_retriever = WindowRetriever()
    context = window_retriever.combine_context(filtered_documents)
    
    # Informações sobre filtragem
    filter_info = {
        'fallback_used': fallback_used,
        'filtered_count': filtered_chunks,
        'total_count': total_chunks,
        'final_count': sum(len(doc['chunks']) for doc in filtered_documents)
    }
    
    return (context, filtered_documents, filter_info)


def _rerank_with_semantic_filters(
    self,
    results: List[Dict[str, Any]],
    query_enriched: Dict[str, Any],
    base_similarity_key: str = "_additional"
) -> List[Dict[str, Any]]:
    """
    Rerank resultados baseado em match com filtros semânticos.
    Combina similaridade vetorial + match semântico.
    
    Args:
        results: Lista de resultados do Weaviate
        query_enriched: Dados enriquecidos da query (frameworks, conceitos, etc.)
        base_similarity_key: Chave para acessar similaridade vetorial (default: "_additional")
    
    Returns:
        Lista de resultados rerankeados com score final
    """
    scored_results = []
    
    query_frameworks = query_enriched.get("frameworks", [])
    query_concepts = query_enriched.get("conceitos_negocio", [])
    query_companies = query_enriched.get("companies", [])
    query_content_type = query_enriched.get("tipo_conteudo")
    
    for result in results:
        # Score base: similaridade vetorial (distance do Weaviate)
        # Weaviate retorna distance (menor = mais similar), converter para score (maior = melhor)
        base_distance = 0.0
        if base_similarity_key in result:
            additional = result[base_similarity_key]
            if isinstance(additional, dict) and "distance" in additional:
                base_distance = additional["distance"]
        
        # Converter distance para score (distance 0 = score 1.0, distance maior = score menor)
        # Normalizar para 0-1 (assumindo distance máximo ~2.0 para cosine)
        base_score = max(0.0, 1.0 - (base_distance / 2.0))
        
        # Boosts por match semântico
        framework_boost = self._calculate_framework_boost(result, query_frameworks)
        concept_boost = self._calculate_concept_boost(result, query_concepts)
        company_boost = self._calculate_company_boost(result, query_companies)
        content_type_boost = self._calculate_content_type_boost(result, query_content_type)
        
        # Score final = weighted sum
        final_score = (
            base_score * 0.4 +           # Similaridade semântica (40%)
            framework_boost * 0.25 +     # Match de frameworks (25%)
            concept_boost * 0.20 +      # Match de conceitos (20%)
            company_boost * 0.10 +       # Match de empresas (10%)
            content_type_boost * 0.05    # Match de tipo (5%)
        )
        
        scored_results.append({
            **result,
            'final_score': final_score,
            'score_breakdown': {
                'base': base_score,
                'framework': framework_boost,
                'concept': concept_boost,
                'company': company_boost,
                'content_type': content_type_boost
            }
        })
    
    # Ordena por score final (maior primeiro)
    scored_results.sort(key=lambda x: x['final_score'], reverse=True)
    
    return scored_results

