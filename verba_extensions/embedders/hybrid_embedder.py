
import os
from typing import List, Dict, Any, Optional
from wasabi import msg

from goldenverba.components.interfaces import Embedding
from goldenverba.components.types import InputConfig
from goldenverba.components.chunk import Chunk
from goldenverba.components.document import Document

# Limites de contexto para Voyage Context-3
# O modelo processa o documento inteiro (até 32k tokens) para gerar embeddings contextuais
MAX_VOYAGE_DOC_TOKENS = 32_000       # Limite por documento (32k tokens)
MAX_VOYAGE_BATCH_TOKENS = 120_000    # Total para batch
MAX_VOYAGE_BATCH_CHUNKS = 16_000     # Máximo de chunks por batch
MAX_VOYAGE_BATCH_DOCS = 1_000        # Máximo de documentos por batch
MAX_MINILM_TOKENS = 512              # MiniLM limit (automático)

# Estimativa: 1 token ≈ 4 caracteres
CHARS_PER_TOKEN = 4


class HybridConsultingEmbedder(Embedding):
    """
    Embedder híbrido otimizado para consultoria.
    
    Arquitetura:
    - DEFAULT VECTOR: Voyage Context-3 (contextual embeddings)
      - Usa contextualized_embed() para embeddings com contexto do documento
      - Chunks do mesmo documento são processados juntos
      - Dimensões: 1024 (configurável: 256, 512, 2048)
    
    - NAMED VECTORS: MiniLM (local, leve)
      - concept_vec: frameworks/metodologias (384 dims)
      - company_vec: empresas/stakeholders (384 dims)
      - sector_vec: setores/indústrias (384 dims)
    
    Economia: ~75% vs usar Voyage para todos os vetores
    """
    
    def __init__(self):
        super().__init__()
        self.name = "HybridConsultingEmbedder"
        self.description = (
            "Embedder híbrido para consultoria. "
            "Voyage Context-3 (contextual, premium) para vetor principal, "
            "MiniLM (local, grátis) para named vectors. Economia de 75%."
        )
        
        # Configuração
        self.config = {
            "Voyage Model": InputConfig(
                type="dropdown",
                value="voyage-context-3",
                description="Modelo Voyage. 'voyage-context-3' usa API contextual otimizada para RAG.",
                values=[
                    "voyage-context-3",      # Contextual API (recomendado para RAG)
                    "voyage-3.5",            # Embed API - Alta qualidade geral
                    "voyage-3.5-lite",       # Embed API - Mais rápido
                    "voyage-multilingual-2"  # Embed API - Para docs multilíngue
                ]
            ),
            "Output Dimension": InputConfig(
                type="dropdown",
                value="1024",
                description="Dimensões do embedding Voyage (menor = mais rápido, maior = mais preciso)",
                values=["256", "512", "1024", "2048"]
            ),
            "Enable Named Vectors": InputConfig(
                type="bool",
                value=True,
                description="Habilitar named vectors especializados (concept, company, sector)",
                values=[]
            ),
            "Voyage API Key": InputConfig(
                type="password",
                value=os.getenv("VOYAGE_API_KEY", ""),
                description="API Key Voyage (para default vector)",
                values=[]
            ),
            "Use GPU": InputConfig(
                type="bool",
                value=False,
                description="Usar GPU para embeddings locais (se disponível)",
                values=[]
            ),
            "Named Vector Model": InputConfig(
                type="dropdown",
                value="intfloat/multilingual-e5-small",
                description="Modelo para named vectors (concept/company/sector). e5-small: +129% em business jargon vs paraphrase-multilingual",
                values=[
                    "intfloat/multilingual-e5-small",  # Recomendado (MTEB 63.8%, melhor multilíngue)
                    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",  # Legacy
                ]
            )
        }
        
        # Inicializa embedders
        self.voyage_client = None
        self.minilm = None
        
        self._initialize_embedders()

    def vectorize_named_query(self, query: str) -> List[float]:
        """
        Gera embedding para named vector (MiniLM) para uma query.
        Usado pelo Retriever para buscar em concept_vec, company_vec, etc.
        """
        if not self.minilm:
            return []
        
        try:
            # Normalização é importante para cosine similarity
            embedding = self.minilm.encode(query, normalize_embeddings=True)
            return embedding.tolist()
        except Exception as e:
            msg.warn(f"Erro ao gerar named query vector: {e}")
            return []
    
    def vectorize_query(self, query: str, config: dict = None) -> List[float]:
        """
        Gera embedding para query usando Voyage Context-3.
        Para queries, usamos input_type="query".
        """
        if not self.voyage_client:
            msg.warn("Voyage client não disponível para query")
            return self.vectorize_named_query(query)  # Fallback para MiniLM
        
        # Merge config: argumento tem prioridade sobre self.config
        effective_config = self.config.copy()
        if config:
            effective_config.update(config)

        try:
            model = self._get_config_value(effective_config, "Voyage Model", "voyage-context-3")
            output_dim = int(self._get_config_value(effective_config, "Output Dimension", "1024"))
            
            if model == "voyage-context-3":
                # Contextual API para queries
                # input_type="query" é CRUCIAL para queries
                result = self.voyage_client.contextualized_embed(
                    inputs=[[query]],  # [[query]] (lista de listas obrigatória)
                    model="voyage-context-3",
                    input_type="query",
                    output_dimension=output_dim
                )
                
                # Parse robusto unificado
                extracted = self._extract_embeddings(result)
                if extracted and extracted[0] and extracted[0][0]:
                     return extracted[0][0]
                else:
                     raise ValueError(f"Retorno vazio do Voyage para query: {result}")

            else:
                # Embed API padrão para outros modelos
                result = self.voyage_client.embed(
                    texts=[query],
                    model=model,
                    input_type="query",
                    output_dimension=output_dim if model in ["voyage-3.5", "voyage-3.5-lite"] else None,
                    truncation=True
                )
                return result.embeddings[0]
                
        except Exception as e:
            msg.fail(f"Erro CRÍTICO ao gerar query embedding Voyage: {e}")
            # Strict mode: Não fazer fallback silencioso para MiniLM se Voyage foi explicitamente solicitado
            # Retorna vetor vazio ou propaga erro
            return []
    
    def _initialize_embedders(self):
        """Inicializa embedders (lazy loading)"""
        # Voyage Context-3 (premium, contextual para default vector)
        try:
            import voyageai
            api_key = os.getenv("VOYAGE_API_KEY", "")
            if api_key:
                self.voyage_client = voyageai.Client(api_key=api_key)
                msg.good("✅ Voyage Context-3 inicializado (default vector - contextual)")
            else:
                msg.warn("⚠️ VOYAGE_API_KEY não configurada - default vector não disponível")
        except ImportError:
            msg.warn("⚠️ voyageai não instalado - pip install voyageai")
        
        # Named Vectors Model (local, para concept/company/sector)
        try:
            from sentence_transformers import SentenceTransformer
            use_gpu = self._get_config_value(self.config, "Use GPU", False)
            device = 'cuda' if use_gpu else 'cpu'
            
            # Usar modelo configurável (default: e5-small para melhor performance multilíngue)
            model_name = self._get_config_value(
                self.config, 
                "Named Vector Model", 
                "intfloat/multilingual-e5-small"
            )
            
            self.minilm = SentenceTransformer(model_name, device=device)
            
            # Display info baseado no modelo
            model_display = "E5-Small" if "e5-small" in model_name else "Paraphrase-Multilingual"
            msg.good(f"✅ {model_display} inicializado em {device} (named vectors)")
            msg.info(f"   Modelo: {model_name}")
            msg.info("   RAM: ~300 MB | Dimensões: 384 | Uso: concept/company/sector vectors")
        except ImportError:
            msg.warn("⚠️ sentence-transformers não instalado - pip install sentence-transformers")
        except Exception as e:
            msg.warn(f"⚠️ Erro ao carregar named vector model: {str(e)}")
    
    async def vectorize(self, config: dict, content: List[str]) -> List[List[float]]:
        """
        Vectorize usando Voyage (contextual ou embed API dependendo do modelo).
        
        Para voyage-context-3: Usa contextualized_embed() com formato [[chunk1, chunk2, ...]]
        Para outros modelos: Usa embed() padrão
        """
        if not self.voyage_client:
            msg.fail("[Hybrid-Embedder] Voyage client não inicializado")
            return []
        
        model = self._get_config_value(config, "Voyage Model", "voyage-context-3")
        output_dim = int(self._get_config_value(config, "Output Dimension", "1024"))
        
        if model == "voyage-context-3":
            # ============================================
            # CONTEXTUAL API - voyage-context-3
            # ============================================
            # Formato: inputs = [[chunk1, chunk2, ...]] onde cada inner list é um documento
            # Para vectorize() simples, tratamos como um único documento
            return await self._embed_voyage_contextual(content, output_dim)
        else:
            # ============================================
            # EMBED API PADRÃO - outros modelos
            # ============================================
            return await self._embed_voyage_standard(content, model, output_dim)
    
    async def _embed_voyage_contextual(
        self, 
        chunks: List[str], 
        output_dim: int = 1024
    ) -> List[List[float]]:
        """
        Embedding contextual usando voyage-context-3.
        
        Formato de input: [[chunk1, chunk2, chunk3, ...]]
        - Cada inner list representa chunks de UM documento
        - O modelo entende o contexto entre chunks do mesmo doc
        """
        if not chunks:
            return []
        
        msg.info(f"[Hybrid-Embedder] 🧠 Contextual embedding: {len(chunks)} chunks")
        
        try:
            # Para vectorize() simples, todos os chunks são do mesmo documento
            # Então enviamos como uma única inner list
            result = self.voyage_client.contextualized_embed(
                inputs=[chunks],  # [[chunk1, chunk2, ...]]
                model="voyage-context-3",
                input_type="document",
                output_dimension=output_dim
            )
            
            # Resultado: embeddings[0] = lista de embeddings para o primeiro documento
            embeddings = result.embeddings[0]
            
            msg.good(f"[Hybrid-Embedder] ✅ Contextual: {len(embeddings)} embeddings ({output_dim}d)")
            return embeddings
            
        except Exception as e:
            msg.fail(f"[Hybrid-Embedder] Erro no Voyage Contextual: {str(e)}")
            return []
    
    async def _embed_voyage_standard(
        self, 
        texts: List[str], 
        model: str,
        output_dim: int = 1024
    ) -> List[List[float]]:
        """
        Embedding padrão usando embed() API (voyage-3.5, voyage-3.5-lite, etc).
        """
        if not texts:
            return []
        
        msg.info(f"[Hybrid-Embedder] 📄 Standard embedding ({model}): {len(texts)} texts")
        
        try:
            # Suporte a output_dimension apenas para modelos 3.5
            supports_dim = model in ["voyage-3.5", "voyage-3.5-lite"]
            
            result = self.voyage_client.embed(
                texts=texts,
                model=model,
                input_type="document",
                output_dimension=output_dim if supports_dim else None,
                truncation=True
            )
            
            msg.good(f"[Hybrid-Embedder] ✅ Standard: {len(result.embeddings)} embeddings")
            return result.embeddings
            
        except Exception as e:
            msg.fail(f"[Hybrid-Embedder] Erro no Voyage Standard: {str(e)}")
            return []
    
    async def vectorize_named(
        self,
        config: Dict[str, Any],
        content: List[str],
        vector_name: str = "default"
    ) -> List[List[float]]:
        """
        Embeddings para um named vector específico.
        
        - default: Voyage Context-3 (1024 dims)
        - concept/company/sector: MiniLM (384 dims)
        """
        if vector_name == "default":
            if self.voyage_client:
                return await self.vectorize(config, content)
            else:
                msg.warn("⚠️ Voyage não disponível, usando MiniLM como fallback")
                return self._embed_minilm(content)
        
        elif vector_name in ["concept_vec", "company_vec", "sector_vec"]:
            if self.minilm:
                return self._embed_minilm(content)
            else:
                msg.warn(f"⚠️ MiniLM não disponível para {vector_name}")
                return [[0.0] * 384 for _ in content]
        
        else:
            msg.warn(f"⚠️ Vector name desconhecido: {vector_name}")
            return await self.vectorize_named(config, content, "default")
    
    async def vectorize_with_named_vectors(
        self,
        chunks: List[Chunk],
        documents: List[Document]
    ) -> Dict[str, List[List[float]]]:
        """
        Gera embeddings para todos os named vectors.
        
        Arquitetura:
        - default: Voyage Context-3 (contextual, por documento)
        - concept/company/sector: MiniLM (local, leve)
        
        Returns:
            {
                "default": [[1024 floats], ...],      # Voyage Context-3
                "concept_vec": [[384 floats], ...],   # MiniLM
                "company_vec": [[384 floats], ...],   # MiniLM
                "sector_vec": [[384 floats], ...]     # MiniLM
            }
        """
        enable_named = self._get_config_value(self.config, "Enable Named Vectors", True)
        output_dim = int(self._get_config_value(self.config, "Output Dimension", "1024"))
        model = self._get_config_value(self.config, "Voyage Model", "voyage-context-3")
        
        if not enable_named:
            # Apenas default vector
            default_texts = [chunk.content for chunk in chunks]
            default_embeddings = await self.vectorize(self.config, default_texts)
            return {"default": default_embeddings}
        
        msg.info("[Hybrid-Embedder] 🎯 Gerando embeddings híbridos...")
        
        # Agrupa chunks por documento para contexto
        chunks_by_doc = self._group_by_document(chunks, documents)
        
        # Inicializa resultados com List Comprehension para evitar referência duplicada
        results_default = [None for _ in range(len(chunks))]
        results_concept = [None for _ in range(len(chunks))]
        results_company = [None for _ in range(len(chunks))]
        results_sector = [None for _ in range(len(chunks))]
        
        # Map chunk -> índice original
        chunk_indices = {id(chunk): i for i, chunk in enumerate(chunks)}
        
        for doc_uuid, doc_chunks in chunks_by_doc.items():
            # ORDENAÇÃO É IMPORTANTE para contexto!
            # Ordena por chunk_id (float) ou start_i
            doc_chunks.sort(key=lambda c: (getattr(c, 'chunk_id', 0) or 0)) 

            document = self._get_document(doc_uuid, documents)
            if not document:
                document = Document(text="", name="Unknown", type="text")
            
            # Índices dos chunks deste documento
            current_indices = [chunk_indices[id(c)] for c in doc_chunks]
            
            # ============================================
            # 1. DEFAULT VECTOR: Voyage Context-3 (Contextual Batching)
            # ============================================
            # Apenas prepara os dados aqui - o processamento real em batch acontece depois
            if self.voyage_client and model == "voyage-context-3":
                 # Acumula para batch processing global
                 # Precisamos de uma lista global de documentos para enviar em batches eficientes
                 pass 
            elif self.voyage_client:
                # Outros modelos Voyage (standard)
                doc_texts = [c.content for c in doc_chunks]
                emb_default = await self._embed_voyage_standard(doc_texts, model, output_dim)
            else:
                # Fallback: MiniLM
                doc_texts = [c.content for c in doc_chunks]
                emb_default = self._embed_minilm(doc_texts)
            
            # ============================================
            # 2-4. NAMED VECTORS: MiniLM (Local, Leve)
            # ============================================
            global_context = self._build_global_context(document, doc_chunks)
            
            texts_concept = []
            texts_company = []
            texts_sector = []
            
            for chunk in doc_chunks:
                texts_concept.append(self._build_concept_text(global_context, chunk))
                texts_company.append(self._build_company_text(global_context, chunk))
                texts_sector.append(self._build_sector_text(global_context, chunk))
            
            if self.minilm:
                emb_concept = self._embed_minilm(texts_concept)
                emb_company = self._embed_minilm(texts_company)
                emb_sector = self._embed_minilm(texts_sector)
            else:
                # Inicialização correta sem referências compartilhadas
                emb_concept = [[0.0] * 384 for _ in range(len(texts_concept))]
                emb_company = [[0.0] * 384 for _ in range(len(texts_company))]
                emb_sector = [[0.0] * 384 for _ in range(len(texts_sector))]
            
            # Coloca resultados nas posições corretas (exceto default contextual, que faremos em batch)
            original_indices = [chunk_indices[id(c)] for c in doc_chunks]
            
            for i, idx in enumerate(original_indices):
                if not (self.voyage_client and model == "voyage-context-3"):
                     results_default[idx] = emb_default[i] if i < len(emb_default) else [0.0] * output_dim
                
                results_concept[idx] = emb_concept[i]
                results_company[idx] = emb_company[i]
                results_sector[idx] = emb_sector[i]
                
        # ============================================
        # PROCESSAMENTO EM BATCH (Voyage Contextual)
        # ============================================
        if self.voyage_client and model == "voyage-context-3":
             msg.info("[Hybrid-Embedder] 🚀 Iniciando processamento em batch contextual...")
             
             # Prepara documentos para batching
             # Lista de (doc_chunks, original_indices_for_these_chunks)
             docs_to_process = []
             
             for doc_uuid, doc_chunks in chunks_by_doc.items():
                 # Já foram ordenados acima
                 original_indices = [chunk_indices[id(c)] for c in doc_chunks]
                 docs_to_process.append((doc_chunks, original_indices))
             
             # Processa com batching inteligente
             batch_results = await self._embed_voyage_contextual_batch(docs_to_process, output_dim)
             
             # Desempacota resultados
             for i, embedding in batch_results.items():
                 # i key is the original index
                 results_default[i] = embedding
        
        # Robustez final: Preencher Nones restantes com zeros
        # (Isso garante que nunca retornamos None para o banco vetorial)
        none_indices = [i for i, x in enumerate(results_default) if x is None]
        if none_indices:
             msg.warn(f"[Hybrid-Embedder] ⚠️ Preenchendo {len(none_indices)} chunks com vetores vazios (falha upstream).")
             zero_vec = [0.0] * output_dim
             for i in none_indices:
                 results_default[i] = zero_vec
                  
        msg.good("✅ Embedding híbrido completo:")
        msg.info(f"   Default (Voyage): {len([r for r in results_default if r])} chunks ({output_dim}d)")
        msg.info(f"   Named (MiniLM): {len([r for r in results_concept if r])} chunks x3 (384d)")
        
        return {
            "default": results_default,
            "concept_vec": results_concept,
            "company_vec": results_company,
            "sector_vec": results_sector
        }
    
    async def _embed_voyage_contextual_batch(
        self,
        docs_with_indices: List[tuple],
        output_dim: int
    ) -> Dict[int, List[float]]:
        """
        Processa múltiplos documentos em batches respeitando limites da API.
        
        Retorna: Dict {original_index: embedding}
        """
        final_results = {}
        
        # Buffer para o batch atual
        current_batch_inputs = []      # List[List[str]]
        current_batch_indices = []     # List[List[int]] (indices originais correspondentes)
        
        current_tokens = 0
        current_chunks = 0
        
        for doc_chunks, original_indices in docs_with_indices:
            # 1. NÍVEL 1: Validação e Split de Documento (Limite 32k)
            # Garante que nenhum documento individual exceda o limite de contexto
            sub_docs = self._ensure_document_limits(doc_chunks, original_indices)
            
            for sub_doc_texts, sub_doc_indices in sub_docs:
                doc_tokens = sum(len(t)//CHARS_PER_TOKEN for t in sub_doc_texts)
                doc_n_chunks = len(sub_doc_texts)
                
                # 2. NÍVEL 2: Verificação de Limite do Batch (Limite 120k / 16k chunks / 1k docs)
                # Se adicionar este doc estourar o batch, despacha o atual e começa novo
                if (current_tokens + doc_tokens > MAX_VOYAGE_BATCH_TOKENS or
                    current_chunks + doc_n_chunks > MAX_VOYAGE_BATCH_CHUNKS or
                    len(current_batch_inputs) >= MAX_VOYAGE_BATCH_DOCS):
                    
                    # Despacha batch atual
                    await self._dispatch_batch(current_batch_inputs, current_batch_indices, output_dim, final_results)
                    
                    # Reset batch
                    current_batch_inputs = []
                    current_batch_indices = []
                    current_tokens = 0
                    current_chunks = 0
                
                # Adiciona ao batch atual
                current_batch_inputs.append(sub_doc_texts)
                current_batch_indices.append(sub_doc_indices)
                current_tokens += doc_tokens
                current_chunks += doc_n_chunks
        
        # Despacha o último batch remanescente
        if current_batch_inputs:
            await self._dispatch_batch(current_batch_inputs, current_batch_indices, output_dim, final_results)
            
        return final_results

    def _ensure_document_limits(self, chunks: List[Chunk], indices: List[int]) -> List[tuple]:
        """
        NÍVEL 1: Garante que um documento respeite o limite de 32k tokens de contexto.
        Se exceder, divide em sub-documentos lógicos.
        """
        texts = [c.content for c in chunks]
        total_tokens = sum(len(t)//CHARS_PER_TOKEN for t in texts)
        
        if total_tokens <= MAX_VOYAGE_DOC_TOKENS:
            return [(texts, indices)]
        
        # Documento excede 32k tokens - Strategy: Split Simples (mantém ordem)
        msg.warn(f"[Hybrid-Embedder] ⚠️ Documento excede limite de contexto ({total_tokens} > {MAX_VOYAGE_DOC_TOKENS}). Dividindo em sub-contextos.")
        
        sub_docs = []
        current_sub_texts = []
        current_sub_indices = []
        current_sub_tokens = 0
        
        for i, text in enumerate(texts):
            chunk_tokens = len(text)//CHARS_PER_TOKEN
            
            # Se um único chunk for maior que o limite (caso extremo), trunca ou falha
            if chunk_tokens > MAX_VOYAGE_DOC_TOKENS:
                # Falha explícita para forçar chunking correto upstream
                msg.fail(f"[Hybrid-Embedder] ❌ Chunk {i} excede limite de contexto ({chunk_tokens} > {MAX_VOYAGE_DOC_TOKENS}).")
                # Se for crítico para operação, poderiamos tentar truncar aqui, mas better fail loud
                raise ValueError(f"Chunk excede limite de tokens do Voyage ({chunk_tokens} > {MAX_VOYAGE_DOC_TOKENS}). Reduza tamanho dos chunks na ingestão.") 
            
            # Check de limite de CHUNKS no documento (além de tokens)
            # Se acumulamos chunks demais num único sub-doc, Voyage pode rejeitar
            # MAX_VOYAGE_BATCH_CHUNKS divide entre docs, mas um único doc também não pode exceder
            if len(current_sub_texts) >= MAX_VOYAGE_BATCH_CHUNKS: # Limite seguro
                 # Fecha sub-doc atual
                 sub_docs.append((current_sub_texts, current_sub_indices))
                 current_sub_texts = []
                 current_sub_indices = []
                 current_sub_tokens = 0
            
            if current_sub_tokens + chunk_tokens > MAX_VOYAGE_DOC_TOKENS:
                # Fecha sub-documento atual
                if current_sub_texts:
                    sub_docs.append((current_sub_texts, current_sub_indices))
                
                # Começa novo
                current_sub_texts = []
                current_sub_indices = []
                current_sub_tokens = 0
            
            current_sub_texts.append(text)
            current_sub_indices.append(indices[i])
            current_sub_tokens += chunk_tokens
            
        if current_sub_texts:
             sub_docs.append((current_sub_texts, current_sub_indices))
             
        return sub_docs

    async def _dispatch_batch(
        self, 
        inputs: List[List[str]], 
        indices_list: List[List[int]], 
        output_dim: int,
        results_map: Dict
    ):
        """Helper para enviar batch e mapear resultados"""
        if not inputs:
            return

        msg.info(f"[Hybrid-Embedder] 📡 Despachando batch: {len(inputs)} docs, {sum(len(x) for x in inputs)} chunks")
        
        try:
            result = self.voyage_client.contextualized_embed(
                inputs=inputs,
                model="voyage-context-3",
                input_type="document",
                output_dimension=output_dim
            )
            
            # Parse robusto usando helper
            all_embeddings = self._extract_embeddings(result)
            
            if len(all_embeddings) != len(inputs):
                 msg.warn(f"[Hybrid-Embedder] ⚠️ Mismatch Docs: Enviei {len(inputs)}, recebi {len(all_embeddings)}. Tentando alinhar...")
                 # Se houver mismatch de docs, é catastrófico. Mas tentamos zipar.

            for doc_idx, doc_embeddings in enumerate(all_embeddings):
                if doc_idx >= len(indices_list):
                    break # Recebemos mais docs do que enviamos??
                    
                original_indices = indices_list[doc_idx]
                
                if len(doc_embeddings) != len(original_indices):
                    msg.warn(f"Mismatch Chunks (Doc {doc_idx}): enviei {len(original_indices)}, recebi {len(doc_embeddings)}. Preenchendo zeros.")
                    # Preenche o que der, completa o resto com zeros
                    for i, idx in enumerate(original_indices):
                        if i < len(doc_embeddings):
                            results_map[idx] = doc_embeddings[i]
                        else:
                            results_map[idx] = [0.0] * output_dim
                else:
                    for chuck_idx, embedding in enumerate(doc_embeddings):
                        final_idx = original_indices[chuck_idx]
                        results_map[final_idx] = embedding
                    
        except Exception as e:
            msg.fail(f"[Hybrid-Embedder] ❌ Erro no batch Voyage: {str(e)}")
            # Fallback seguro: preencher com zeros
            for doc_idx, indices in enumerate(indices_list):
                 for idx in indices:
                     results_map[idx] = [0.0] * output_dim
    
    def _embed_minilm(self, texts: List[str]) -> List[List[float]]:
        """Embedding com MiniLM (local, 384 dims)."""
        if not self.minilm:
            return [[0.0] * 384 for _ in texts]
        
        embeddings = self.minilm.encode(
            texts,
            batch_size=64,
            show_progress_bar=False,
            normalize_embeddings=True
        )
        return embeddings.tolist()
    
    # ========================================================================
    # CONSTRUÇÃO DE CONTEXTOS PARA NAMED VECTORS
    # ========================================================================
    
    def _build_global_context(self, document: Document, chunks: List[Chunk]) -> Dict:
        """Contexto global do documento"""
        frameworks_all = set()
        companies_all = set()
        sectors_all = set()
        
        for chunk in chunks:
            if hasattr(chunk, 'meta') and chunk.meta:
                meta = chunk.meta
                if isinstance(meta.get("frameworks"), list):
                    frameworks_all.update(meta.get("frameworks"))
                if isinstance(meta.get("companies"), list):
                    companies_all.update(meta.get("companies"))
                if isinstance(meta.get("sectors"), list):
                    sectors_all.update(meta.get("sectors"))
        
        return {
            "title": getattr(document, 'name', None) or getattr(document, 'title', None) or "Documento",
            "frameworks": list(frameworks_all),
            "companies": list(companies_all),
            "sectors": list(sectors_all)
        }
    
    def _build_concept_text(self, global_context: Dict, chunk: Chunk) -> str:
        """Texto para concept_vec (foco em frameworks)"""
        chunk_frameworks = chunk.meta.get("frameworks", []) if hasattr(chunk, 'meta') and chunk.meta else []
        
        if chunk_frameworks:
            prefix = f"Frameworks: {', '.join(chunk_frameworks)}\n"
        elif global_context.get("frameworks"):
            prefix = f"Frameworks: {', '.join(global_context['frameworks'][:5])}\n"
        else:
            prefix = "Análise de negócios\n"
        
        return prefix + chunk.content
    
    def _build_company_text(self, global_context: Dict, chunk: Chunk) -> str:
        """Texto para company_vec (foco em empresas)"""
        chunk_companies = chunk.meta.get("companies", []) if hasattr(chunk, 'meta') and chunk.meta else []
        
        if chunk_companies:
            prefix = f"Empresas: {', '.join(chunk_companies)}\n"
        elif global_context.get("companies"):
            prefix = f"Empresas: {', '.join(global_context['companies'][:5])}\n"
        else:
            prefix = "Stakeholders corporativos\n"
        
        return prefix + chunk.content
    
    def _build_sector_text(self, global_context: Dict, chunk: Chunk) -> str:
        """Texto para sector_vec (foco em setores)"""
        chunk_sectors = chunk.meta.get("sectors", []) if hasattr(chunk, 'meta') and chunk.meta else []
        
        if chunk_sectors:
            prefix = f"Setores: {', '.join(chunk_sectors)}\n"
        elif global_context.get("sectors"):
            prefix = f"Setores: {', '.join(global_context['sectors'][:5])}\n"
        else:
            prefix = "Contexto industrial\n"
        
        return prefix + chunk.content
    
    # ========================================================================
    # HELPERS
    # ========================================================================
    
    def _group_by_document(self, chunks: List[Chunk], documents: List[Document]) -> Dict:
        """Agrupa chunks por documento UUID"""
        grouped = {}
        for chunk in chunks:
            doc_uuid = getattr(chunk, 'doc_uuid', None)
            if doc_uuid:
                if doc_uuid not in grouped:
                    grouped[doc_uuid] = []
                grouped[doc_uuid].append(chunk)
            else:
                if "unknown" not in grouped:
                    grouped["unknown"] = []
                grouped["unknown"].append(chunk)
        return grouped
    
    def _get_document(self, doc_uuid: str, documents: List[Document]) -> Optional[Document]:
        """Encontra documento por UUID"""
        for doc in documents:
            if hasattr(doc, 'uuid') and doc.uuid == doc_uuid:
                return doc
        return None

    def _get_config_value(self, config: dict, key: str, default):
        """Extrai valor do config de forma robusta"""
        config_item = config.get(key, {})
        if isinstance(config_item, dict):
            return config_item.get("value", default)
        elif hasattr(config_item, 'value'):
            return config_item.value
        elif isinstance(config_item, (str, int, float, bool)):
             return config_item
        else:
            return default

    def _extract_embeddings(self, result) -> List[List[List[float]]]:
        """
        Helper unificado para extrair embeddings da resposta da API Voyage.
        Normaliza para List[List[List[float]]] (Batch -> Doc -> Vectors).
        """
        # Padrão Voyage Contextual: result.results[i].embeddings
        if hasattr(result, 'results'):
            return [r.embeddings for r in result.results]
        
        # Padrão Legacy/Flat ou Embed Standard: result.embeddings
        if hasattr(result, 'embeddings'):
            # Se for flat list of floats (1 doc, 1 vector? Não, input é chunks)
            # Se input=flat list, output=list of list (vectors)
            # Se input=nested list, output=?
            # Assumindo que result.embeddings pode ser a lista direta
            embeds = result.embeddings
            if not embeds:
                return []
            
            # Heurística: se primeiro elem é float, é um único vetor -> wrap
            if isinstance(embeds[0], float):
                return [[embeds]] # Batch=1, Doc=1, Vec=embedding
            
            # Se primeiro elem é lista de floats (vetor) -> é lista de vetores (1 doc)
            if isinstance(embeds[0], list) and isinstance(embeds[0][0], float):
                return [embeds] # Batch=1, Doc=inputs, Vecs=embeddings
            
            # Se já é lista de lista de vetores
            return embeds
            
        return []
