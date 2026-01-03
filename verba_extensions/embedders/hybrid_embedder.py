
import os
from typing import List, Dict, Any, Optional
from wasabi import msg

from goldenverba.components.interfaces import Embedding
from goldenverba.components.types import InputConfig
from goldenverba.components.chunk import Chunk
from goldenverba.components.document import Document

# Limites de contexto
MAX_VOYAGE_TOKENS = 31_000  # Voyage 3.5 limit: 32k, margem de segurança
MAX_MINILM_TOKENS = 512     # MiniLM limit (automático)


class HybridConsultingEmbedder(Embedding):
    """
    Embedder híbrido otimizado para consultoria.
    
    Modo BYOV (Bring Your Own Vectors):
    - Verba gera todos os embeddings
    - Weaviate apenas armazena
    - Permite usar embedders diferentes por named vector
    """
    
    def __init__(self):
        super().__init__()
        self.name = "HybridConsultingEmbedder"
        self.description = (
            "Embedder híbrido lean para consultoria. "
            "Voyage 3.5 (premium API) para default, MiniLM (local) para 3 named vectors. "
            "Economia de 75% + apenas 300MB RAM."
        )
        
        # Configuração
        self.config = {
            "Enable Named Vectors": InputConfig(
                type="bool",
                value=True,
                description="Habilitar named vectors especializados",
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
                description="Usar GPU para MiniLM (se disponível)",
                values=[]
            )
        }
        
        # Inicializa embedders
        self.voyage_client = None
        self.minilm = None
        
        self._initialize_embedders()
    
    def _initialize_embedders(self):
        """Inicializa embedders (lazy loading)"""
        # Voyage 3.5 (premium, para default vector)
        try:
            import voyageai
            api_key = os.getenv("VOYAGE_API_KEY", "")
            if api_key:
                self.voyage_client = voyageai.Client(api_key=api_key)
                msg.good("✅ Voyage 3.5 inicializado (default vector)")
            else:
                msg.warn("⚠️ VOYAGE_API_KEY não configurada - default vector não disponível")
        except ImportError:
            msg.warn("⚠️ voyageai não instalado - pip install voyageai")
        
        # MiniLM-L12 (local, universal para concept/company/sector)
        try:
            from sentence_transformers import SentenceTransformer
            # Use helper to get config value safely
            use_gpu = self._get_config_value(self.config, "Use GPU", False)
            device = 'cuda' if use_gpu else 'cpu'
            self.minilm = SentenceTransformer(
                'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2',
                device=device
            )
            msg.good(f"✅ MiniLM-L12 inicializado em {device} (concept/company/sector)")
            msg.info("   RAM: ~300 MB | Dimensões: 384 | Uso: Universal (3 named vectors)")
        except ImportError:
            msg.warn("⚠️ sentence-transformers não instalado - pip install sentence-transformers")
        except Exception as e:
            msg.warn(f"⚠️ Erro ao carregar MiniLM: {str(e)}")
    
    async def vectorize(self, config: dict, content: List[str]) -> List[List[float]]:
        """
        Vectorize usando Voyage 3.5 com proteção contra overflow.
        
        Voyage 3.5 limite: 32,000 tokens
        Estratégia:
        - Se chunk < 31k tokens: processa normalmente
        - Se chunk > 31k tokens: trunca mantendo início + fim
        
        Alternativa: Use auto-chunking para zero perda (ver ANALISE_LIMITES_CONTEXTO.md)
        """
        if not self.voyage_client:
            msg.fail("[Hybrid-Embedder] Voyage client não inicializado")
            return []
        
        # Processa content com truncation protection
        processed_content = []
        truncated_count = 0
        
        for i, text in enumerate(content):
            # Estima tokens (aproximação: 1 token ≈ 4 chars)
            token_estimate = len(text) // 4
            
            if token_estimate > MAX_VOYAGE_TOKENS:
                truncated_count += 1
                msg.warn(
                    f"[Hybrid-Embedder] ⚠️ Chunk {i} tem ~{token_estimate:,} tokens "
                    f"(limite: {MAX_VOYAGE_TOKENS:,}). Truncando início+fim..."
                )
                
                # Truncate inteligente: mantém início + fim (perde meio)
                # Rationale: Início tem contexto, fim tem conclusões
                chars_limit = MAX_VOYAGE_TOKENS * 4
                half_limit = chars_limit // 2
                
                truncated = (
                    text[:half_limit] + 
                    "\n\n[... CONTEÚDO TRUNCADO ...]\n\n" + 
                    text[-half_limit:]
                )
                processed_content.append(truncated)
            else:
                processed_content.append(text)
        
        if truncated_count > 0:
            msg.info(
                f"[Hybrid-Embedder] 💡 {truncated_count} chunk(s) truncado(s). "
                f"Considere re-chunking para evitar perda de dados."
            )
        
        try:
            result = self.voyage_client.embed(
                texts=processed_content,
                model="voyage-3.5",
                input_type="document",
                truncation=True  # ✅ Fallback adicional (Voyage internal truncation)
            )
            return result.embeddings
        
        except Exception as e:
            msg.fail(f"[Hybrid-Embedder] Erro no Voyage: {str(e)}")
            return []
    
    async def vectorize_named(
        self,
        config: Dict[str, Any],
        content: List[str],
        vector_name: str = "default"
    ) -> List[List[float]]:
        """
        Embeddings para um named vector específico (Smart Import Hook).
        
        Interface para import_hook.py que sabe qual vetor está gerando.
        Implementa a spec do Hybrid Multi-Embedder Design.
        
        Args:
            config: Configuração do embedder
            content: Lista de textos para embedar
            vector_name: Nome do vetor ("default", "concept_vec", "company_vec", "sector_vec")
        
        Returns:
            Lista de embeddings (dimensões dependem do vector_name)
            - default: 1024 dims (Voyage)
            - concept/company/sector: 384 dims (MiniLM)
        
        Example:
            # Smart Import Hook chama:
            vec = await embedder.vectorize_named(config, ["text"], vector_name="company_vec")
        """
        if vector_name == "default":
            # Voyage 3.5 (premium, 1024 dims)
            if self.voyage_client:
                return await self.vectorize(config, content)
            else:
                msg.warn("⚠️ Voyage não disponível, usando MiniLM como fallback")
                return self._embed_minilm(content)
        
        elif vector_name in ["concept_vec", "company_vec", "sector_vec"]:
            # MiniLM (local, 384 dims) - universal para todos os 3
            if self.minilm:
                return self._embed_minilm(content)
            else:
                msg.warn(f"⚠️ MiniLM não disponível para {vector_name}, usando Voyage")
                # Fallback to vectorize (creates 1024 dims, which might fail insert if schema expects 384)
                # But it's better than nothing.
                try:
                    return await self.vectorize(config, content)
                except:
                    # Return empty vectors if dimension mismatch expected
                    return [[0.0] * 384 for _ in content]
        
        else:
            msg.warn(f"⚠️ Vector name desconhecido: {vector_name}, usando default")
            return await self.vectorize_named(config, content, "default")
    
    async def vectorize_with_named_vectors(
        self,
        chunks: List[Chunk],
        documents: List[Document]
    ) -> Dict[str, List[List[float]]]:
        """
        Gera embeddings para todos os named vectors.
        
        Returns:
            {
                "default": [[1024 floats], ...],      # Voyage 3.5
                "concept_vec": [[1024 floats], ...],  # BGE-M3/MiniLM
                "company_vec": [[384 floats], ...],   # MiniLM
                "sector_vec": [[384 floats], ...]     # MiniLM
            }
        """
        enable_named_config = self.config.get("Enable Named Vectors", {})
        enable_named = enable_named_config.get("value", True) if isinstance(enable_named_config, dict) else True
        
        if not enable_named:
            # Apenas default vector
            default_texts = [chunk.content for chunk in chunks]
            default_embeddings = await self.vectorize(self.config, default_texts)
            return {"default": default_embeddings}
        
        msg.info("[Hybrid-Embedder] 🎯 Gerando embeddings com named vectors...")
        
        # Agrupa chunks por documento para contexto hierárquico
        chunks_by_doc = self._group_by_document(chunks, documents)
        
        named_embeddings = {
            "default": [],
            "concept_vec": [],
            "company_vec": [],
            "sector_vec": []
        }
        
        # Maintain order of chunks for result alignment
        # We process by doc, but results need to match original chunks order?
        # Actually verify_import/ingest sends a list of chunks, usually from same doc or batch.
        # But to be safe, we should respect input order. 
        # The simplest way is to process by doc, then construct a map {chunk_id: embeddings} and reconstruct list.
        # But chunks are objects, not easily hashable.
        # Assuming chunks list is processed sequentially.
        # Let's verify input. Chunks are usually from one document in load().
        # But chunk() might batch.
        
        # However, for simplicity and performance we process by doc.
        # To handle ordering:
        
        # 1. Map chunks to their original index
        chunk_indices = {id(chunk): i for i, chunk in enumerate(chunks)}
        
        # Initialize results list with empty placeholders
        results_default = [None] * len(chunks)
        results_concept = [None] * len(chunks)
        results_company = [None] * len(chunks)
        results_sector = [None] * len(chunks)
        
        for doc_uuid, doc_chunks in chunks_by_doc.items():
            document = self._get_document(doc_uuid, documents)
            if not document:
                 # Fallback if doc not found (shouldn't happen)
                 document = Document(text="", title="Unknown", type="text")

            
            # Constrói contextos hierárquicos
            global_context = self._build_global_context(document, doc_chunks)
            concept_context = self._build_concept_context(global_context)
            company_context = self._build_company_context(global_context)
            sector_context = self._build_sector_context(global_context)
            
            # Prepara textos para cada named vector
            texts_default = []
            texts_concept = []
            texts_company = []
            texts_sector = []
            
            current_doc_indices = []
            
            for chunk in doc_chunks:
                # Store index to put result back in correct place
                current_doc_indices.append(chunk_indices[id(chunk)])
                
                # Default: contexto completo (Voyage contextual)
                texts_default.append(
                    self._build_default_text(global_context, chunk)
                )
                
                # Concept: foco em frameworks e metodologias
                texts_concept.append(
                    self._build_concept_text(concept_context, chunk)
                )
                
                # Company: foco em empresas mencionadas
                texts_company.append(
                    self._build_company_text(company_context, chunk)
                )
                
                # Sector: foco em setores/indústrias
                texts_sector.append(
                    self._build_sector_text(sector_context, chunk)
                )
            
            # === EMBEDDING COM MODELO UNIVERSAL ===
            
            msg.info(f"   Doc {str(doc_uuid)[:8]}: hybrid embedding ({len(doc_chunks)} chunks)...")
            
            # 1. DEFAULT: Voyage 3.5 (premium, contextual)
            if self.voyage_client:
                # msg.info(f"      [Voyage] default_vec ({len(texts_default)} chunks)...")
                emb_default = await self._embed_voyage_batch(texts_default)
            else:
                emb_default = self._embed_minilm(texts_default) # Fallback

            # 2-4. SECUNDÁRIOS: MiniLM (local, universal para todos)
            if self.minilm:
                # msg.info(f"      [MiniLM] concept_vec ({len(texts_concept)} chunks)...")
                emb_concept = self._embed_minilm(texts_concept)
                
                # msg.info(f"      [MiniLM] company_vec ({len(texts_company)} chunks)...")
                emb_company = self._embed_minilm(texts_company)
                
                # msg.info(f"      [MiniLM] sector_vec ({len(texts_sector)} chunks)...")
                emb_sector = self._embed_minilm(texts_sector)
            else:
                 # Fallback if local model fails (shouldn't happen if initialized)
                 emb_concept = [[0.0]*384] * len(texts_concept)
                 emb_company = [[0.0]*384] * len(texts_company)
                 emb_sector = [[0.0]*384] * len(texts_sector)

            
            # Place results in correct positions
            for i, idx in enumerate(current_doc_indices):
                results_default[idx] = emb_default[i]
                results_concept[idx] = emb_concept[i]
                results_company[idx] = emb_company[i]
                results_sector[idx] = emb_sector[i]
        
        # Verify complete
        named_embeddings["default"] = results_default
        named_embeddings["concept_vec"] = results_concept
        named_embeddings["company_vec"] = results_company
        named_embeddings["sector_vec"] = results_sector
        
        msg.good("✅ Hybrid embedding completo:")
        msg.info(f"   Voyage calls: {len(results_default)} chunks")
        msg.info(f"   Local embeddings: {len(results_company) * 3} chunks")
        
        return named_embeddings
    
    async def _embed_voyage_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Embedding com Voyage em batches com proteção contra overflow.
        
        Aplica mesma lógica de truncation do vectorize().
        """
        # Pre-processa textos com truncation
        processed_texts = []
        for text in texts:
            token_estimate = len(text) // 4
            
            if token_estimate > MAX_VOYAGE_TOKENS:
                # Trunca
                chars_limit = MAX_VOYAGE_TOKENS * 4
                half = chars_limit // 2
                truncated = (
                    text[:half] + 
                    "\n\n[...TRUNCATED...]\n\n" + 
                    text[-half:]
                )
                processed_texts.append(truncated)
            else:
                processed_texts.append(text)
        
        # Batch processing
        batch_size = 128
        all_embeddings = []
        
        for i in range(0, len(processed_texts), batch_size):
            batch = processed_texts[i:i+batch_size]
            
            result = self.voyage_client.embed(
                texts=batch,
                model="voyage-3.5",
                input_type="document",
                truncation=True  # ✅ Fallback
            )
            
            all_embeddings.extend(result.embeddings)
        
        return all_embeddings
    
    def _embed_minilm(self, texts: List[str]) -> List[List[float]]:
        """
        Embedding com MiniLM (local, universal).
        """
        embeddings = self.minilm.encode(
            texts,
            batch_size=64,
            show_progress_bar=False,
            normalize_embeddings=True
        )
        return embeddings.tolist()
    
    # ========================================================================
    # CONSTRUÇÃO DE CONTEXTOS HIERÁRQUICOS
    # ========================================================================
    
    def _build_global_context(self, document: Document, chunks: List[Chunk]) -> Dict:
        """Contexto global do documento"""
        frameworks_all = set()
        companies_all = set()
        sectors_all = set()
        
        for chunk in chunks:
            if hasattr(chunk, 'meta') and chunk.meta:
                meta = chunk.meta
                # Handle potential string vs list issues
                if isinstance(meta.get("frameworks"), list):
                    frameworks_all.update(meta.get("frameworks"))
                if isinstance(meta.get("companies"), list):
                    companies_all.update(meta.get("companies"))
                if isinstance(meta.get("sectors"), list):
                    sectors_all.update(meta.get("sectors"))
        
        return {
            "title": document.title or "Documento de Consultoria",
            "frameworks": list(frameworks_all),
            "companies": list(companies_all),
            "sectors": list(sectors_all)
        }
    
    def _build_concept_context(self, global_context: Dict) -> str:
        """Contexto para concept_vec (frameworks/metodologias)"""
        frameworks = global_context.get("frameworks", [])
        if frameworks:
            return f"Frameworks: {', '.join(frameworks)}"
        return "Análise de negócios"
    
    def _build_company_context(self, global_context: Dict) -> str:
        """Contexto para company_vec (empresas)"""
        companies = global_context.get("companies", [])
        if companies:
            return f"Empresas: {', '.join(companies[:5])}"
        return "Stakeholders corporativos"
    
    def _build_sector_context(self, global_context: Dict) -> str:
        """Contexto para sector_vec (setores)"""
        sectors = global_context.get("sectors", [])
        if sectors:
            return f"Setores: {', '.join(sectors)}"
        return "Contexto industrial"
    
    def _build_default_text(self, global_context: Dict, chunk: Chunk) -> str:
        """
        Texto completo para default vector (Voyage contextual) com contexto adaptativo.
        """
        # Estima tamanho do chunk
        chunk_tokens = len(chunk.content) // 4
        
        # Decide nível de contexto baseado em tamanho
        if chunk_tokens > 25_000:
            # CONTEXTO MÍNIMO (~50 tokens)
            context_prefix = f"Documento: {global_context.get('title', 'Unknown')}\n\n"
            
            msg.info(
                f"[Hybrid-Embedder] Chunk grande (~{chunk_tokens:,} tokens), "
                "usando contexto mínimo"
            )
        
        elif chunk_tokens > 20_000:
            # CONTEXTO REDUZIDO (~200-500 tokens)
            context_prefix = f"Documento: {global_context.get('title', 'Unknown')}\n"
            
            chunk_frameworks = chunk.meta.get("frameworks", [])[:5] if hasattr(chunk, 'meta') and chunk.meta else []
            if chunk_frameworks:
                context_prefix += f"Frameworks: {', '.join(chunk_frameworks)}\n"
            
            chunk_companies = chunk.meta.get("companies", [])[:5] if hasattr(chunk, 'meta') and chunk.meta else []
            if chunk_companies:
                context_prefix += f"Empresas: {', '.join(chunk_companies)}\n"
            
            context_prefix += "\n"
            
            msg.info(
                f"[Hybrid-Embedder] Chunk médio (~{chunk_tokens:,} tokens), "
                "usando contexto reduzido"
            )
        
        else:
            # CONTEXTO COMPLETO (~2k-5k tokens)
            context_prefix = f"Documento: {global_context['title']}\n"
            
            if global_context.get('frameworks'):
                context_prefix += f"Frameworks: {', '.join(global_context['frameworks'][:10])}\n"
            
            if global_context.get('companies'):
                context_prefix += f"Empresas: {', '.join(global_context['companies'][:10])}\n"
            
            if global_context.get('sectors'):
                context_prefix += f"Setores: {', '.join(global_context['sectors'][:5])}\n"
            
            context_prefix += "\n"
        
        return context_prefix + chunk.content
    
    def _build_concept_text(self, concept_context: str, chunk: Chunk) -> str:
        """Texto para concept_vec (foco em frameworks) - MiniLM"""
        chunk_frameworks = chunk.meta.get("frameworks", []) if hasattr(chunk, 'meta') and chunk.meta else []
        
        if chunk_frameworks:
            prefix = f"Frameworks: {', '.join(chunk_frameworks)}\n"
        else:
            prefix = f"{concept_context}\n"
        
        return prefix + chunk.content
    
    def _build_company_text(self, company_context: str, chunk: Chunk) -> str:
        """Texto para company_vec (foco em empresas)"""
        chunk_companies = chunk.meta.get("companies", []) if hasattr(chunk, 'meta') and chunk.meta else []
        
        if chunk_companies:
            prefix = f"Empresas: {', '.join(chunk_companies)}\n"
        else:
            prefix = f"{company_context}\n"
        
        return prefix + chunk.content
    
    def _build_sector_text(self, sector_context: str, chunk: Chunk) -> str:
        """Texto para sector_vec (foco em setores)"""
        chunk_sectors = chunk.meta.get("sectors", []) if hasattr(chunk, 'meta') and chunk.meta else []
        
        if chunk_sectors:
            prefix = f"Setores: {', '.join(chunk_sectors)}\n"
        else:
            prefix = f"{sector_context}\n"
        
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
                # Handle chunks without doc_uuid (rare)
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
        else:
            return default
