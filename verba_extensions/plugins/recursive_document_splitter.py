"""
RecursiveDocumentSplitter Plugin for Verba

Chunking hierárquico inteligente que preserva estrutura semântica.
Implementa estratégia de fallback: parágrafos → sentenças → palavras → hard split.
"""

import re
import logging
from typing import List, Dict, Any, Optional
from goldenverba.components.chunk import Chunk

logger = logging.getLogger(__name__)


class RecursiveDocumentSplitterPlugin:
    """
    Plugin para recursive document splitting hierárquico.
    
    Melhora qualidade semântica dos chunks usando estratégia de fallback:
    1. Tenta split por parágrafos (\n\n)
    2. Se muito grande, tenta por sentenças (.\n)
    3. Se ainda grande, tenta por palavras
    4. Fallback: hard split por caracteres
    """
    
    def __init__(self):
        self.name = "RecursiveDocumentSplitter"
        self.description = "Chunking hierárquico que preserva estrutura semântica"
        self.installed = True
        
        # Configuração padrão
        self.default_chunk_size = 1000  # caracteres
        self.default_overlap = 200  # caracteres
        self.max_chunk_size = 1500  # tamanho máximo antes de forçar split
        
    async def process_chunk(
        self,
        chunk: Chunk,
        config: Optional[Dict[str, Any]] = None
    ) -> Chunk:
        """
        Processa um chunk individual e otimiza sua estrutura semântica.
        
        Args:
            chunk: Chunk a processar
            config: Configuração opcional
        
        Returns:
            Chunk otimizado (ou original se já está bem formatado)
        """
        # Se chunk já está pequeno e bem formatado, não precisa processar
        if len(chunk.content) <= self.default_chunk_size:
            return chunk
        
        config = config or {}
        chunk_size = config.get("chunk_size", self.default_chunk_size)
        overlap = config.get("overlap", self.default_overlap)
        
        # Se chunk está dentro do tamanho ideal, retorna
        if len(chunk.content) <= chunk_size:
            return chunk
        
        # Caso contrário, aplica recursive splitting
        optimized_content = self._recursive_split(
            chunk.content,
            chunk_size,
            overlap
        )
        
        # Atualiza conteúdo se houve melhoria
        if optimized_content != chunk.content:
            chunk.content = optimized_content
            chunk.meta["recursive_split_applied"] = True
        
        return chunk
    
    async def process_batch(
        self,
        chunks: List[Chunk],
        config: Optional[Dict[str, Any]] = None
    ) -> List[Chunk]:
        """
        Processa lote de chunks otimizando estrutura semântica.
        
        Args:
            chunks: Lista de chunks a processar
            config: Configuração opcional
        
        Returns:
            Chunks processados
        """
        if not chunks:
            return chunks
        
        config = config or {}
        chunk_size = config.get("chunk_size", self.default_chunk_size)
        
        # Agrupa chunks grandes que precisam ser re-chunked
        chunks_to_split = []
        optimized_chunks = []
        
        for chunk in chunks:
            if len(chunk.content) > chunk_size:
                chunks_to_split.append(chunk)
            else:
                optimized_chunks.append(chunk)
        
        if not chunks_to_split:
            return chunks
        
        # Processa chunks grandes com recursive splitting
        split_chunks = []
        for chunk in chunks_to_split:
            splits = self._split_large_chunk(chunk, chunk_size, config)
            split_chunks.extend(splits)
        
        # Combina chunks otimizados + splits
        result = optimized_chunks + split_chunks
        
        logger.info(f"RecursiveDocumentSplitter: {len(chunks)} chunks → {len(result)} chunks optimized")
        
        return result
    
    def _recursive_split(
        self,
        text: str,
        chunk_size: int,
        overlap: int
    ) -> str:
        """
        Aplica recursive splitting para otimizar estrutura do texto.
        
        Estratégia:
        1. Tenta manter parágrafos inteiros
        2. Se não cabe, tenta manter sentenças inteiras
        3. Se não cabe, tenta manter palavras inteiras
        4. Fallback: hard split
        
        Args:
            text: Texto a otimizar
            chunk_size: Tamanho ideal do chunk
            overlap: Overlap entre chunks
        
        Returns:
            Texto otimizado (ou original se já está bom)
        """
        if len(text) <= chunk_size:
            return text
        
        # Estratégia 1: Split por parágrafos duplos
        paragraphs = re.split(r'\n\n+', text)
        if len(paragraphs) > 1:
            optimized = self._merge_by_size(paragraphs, chunk_size, overlap)
            if optimized:
                return optimized
        
        # Estratégia 2: Split por sentenças (.\n ou .\s)
        sentences = re.split(r'(?<=[.!?])\s+', text)
        if len(sentences) > 1:
            optimized = self._merge_by_size(sentences, chunk_size, overlap)
            if optimized:
                return optimized
        
        # Estratégia 3: Split por palavras
        words = text.split()
        if len(words) > 1:
            optimized = self._merge_by_size(words, chunk_size, overlap, separator=' ')
            if optimized:
                return optimized
        
        # Estratégia 4: Hard split (caracteres)
        return self._hard_split(text, chunk_size, overlap)
    
    def _merge_by_size(
        self,
        parts: List[str],
        chunk_size: int,
        overlap: int,
        separator: str = ''
    ) -> Optional[str]:
        """
        Junta partes tentando manter dentro do chunk_size ideal.
        
        Args:
            parts: Lista de partes (parágrafos, sentenças, palavras)
            chunk_size: Tamanho ideal
            overlap: Overlap necessário
            separator: Separador a usar entre partes
        
        Returns:
            Texto otimizado ou None se não conseguir melhorar
        """
        if not parts:
            return None
        
        current_chunk = []
        current_size = 0
        optimized_parts = []
        
        for part in parts:
            part_size = len(part)
            
            # Se parte sozinha já é maior que chunk_size, precisa split interno
            if part_size > chunk_size:
                # Não pode otimizar esta parte
                if current_chunk:
                    optimized_parts.append(separator.join(current_chunk))
                    current_chunk = []
                    current_size = 0
                optimized_parts.append(part)  # Mantém como está
                continue
            
            # Se adicionar parte mantém dentro do limite
            if current_size + part_size + len(separator) <= chunk_size:
                current_chunk.append(part)
                current_size += part_size + len(separator)
            else:
                # Chunk atual está completo, cria novo
                if current_chunk:
                    optimized_parts.append(separator.join(current_chunk))
                current_chunk = [part]
                current_size = part_size
        
        # Adiciona último chunk
        if current_chunk:
            optimized_parts.append(separator.join(current_chunk))
        
        # Se conseguiu otimizar (reduziu número de chunks ou melhorou estrutura)
        if len(optimized_parts) < len(parts) or self._is_better_structure(parts, optimized_parts):
            return separator.join(optimized_parts)
        
        return None
    
    def _is_better_structure(
        self,
        original: List[str],
        optimized: List[str]
    ) -> bool:
        """
        Verifica se estrutura otimizada é melhor que original.
        
        Critérios:
        - Chunks mais balanceados em tamanho
        - Menos chunks muito pequenos ou muito grandes
        """
        if len(optimized) != len(original):
            return len(optimized) < len(original)
        
        # Calcula variância dos tamanhos
        orig_sizes = [len(p) for p in original]
        opt_sizes = [len(p) for p in optimized]
        
        orig_var = self._variance(orig_sizes)
        opt_var = self._variance(opt_sizes)
        
        # Menor variância = mais balanceado = melhor
        return opt_var < orig_var
    
    def _variance(self, values: List[float]) -> float:
        """Calcula variância de uma lista."""
        if not values:
            return 0.0
        mean = sum(values) / len(values)
        return sum((x - mean) ** 2 for x in values) / len(values)
    
    def _hard_split(
        self,
        text: str,
        chunk_size: int,
        overlap: int
    ) -> str:
        """
        Hard split por caracteres quando outras estratégias falharam.
        
        Args:
            text: Texto a splitar
            chunk_size: Tamanho do chunk
            overlap: Overlap entre chunks
        
        Returns:
            Texto splitado (mantém formato original se possível)
        """
        # Tenta manter ao menos palavras inteiras
        if len(text) <= chunk_size:
            return text
        
        # Split em palavras e reconstrói respeitando chunk_size
        words = text.split()
        chunks = []
        current_chunk = []
        current_size = 0
        
        for word in words:
            word_size = len(word) + 1  # +1 para espaço
            
            if current_size + word_size > chunk_size:
                if current_chunk:
                    chunks.append(' '.join(current_chunk))
                current_chunk = [word]
                current_size = len(word)
            else:
                current_chunk.append(word)
                current_size += word_size
        
        if current_chunk:
            chunks.append(' '.join(current_chunk))
        
        # Se conseguiu dividir em chunks melhores, retorna
        if len(chunks) > 1:
            # Retorna primeiro chunk (para process_chunk que não deve criar múltiplos)
            return chunks[0] if chunks else text
        
        return text
    
    def _split_large_chunk(
        self,
        chunk: Chunk,
        chunk_size: int,
        config: Dict[str, Any]
    ) -> List[Chunk]:
        """
        Split um chunk grande em múltiplos chunks menores.
        
        Args:
            chunk: Chunk grande a splitar
            chunk_size: Tamanho ideal dos novos chunks
            config: Configuração
        
        Returns:
            Lista de chunks menores
        """
        overlap = config.get("overlap", self.default_overlap)
        text = chunk.content
        
        # Aplica recursive splitting para dividir
        splits = self._recursive_split_text(text, chunk_size, overlap)
        
        # Cria novos chunks
        new_chunks = []
        for i, split_text in enumerate(splits):
            new_chunk = Chunk(
                content=split_text,
                chunk_id=f"{chunk.chunk_id}_{i}" if chunk.chunk_id else str(i),
                start_i=chunk.start_i + (i * chunk_size) if chunk.start_i else None,
                end_i=chunk.end_i if i == len(splits) - 1 else None,
                content_without_overlap=split_text
            )
            # Copia metadata original
            new_chunk.meta = chunk.meta.copy()
            new_chunk.meta["recursive_split"] = True
            new_chunk.meta["original_chunk_id"] = chunk.chunk_id
            new_chunks.append(new_chunk)
        
        return new_chunks
    
    def _recursive_split_text(
        self,
        text: str,
        chunk_size: int,
        overlap: int
    ) -> List[str]:
        """
        Divide texto em múltiplos chunks usando recursive splitting.
        
        Args:
            text: Texto a dividir
            chunk_size: Tamanho ideal dos chunks
            overlap: Overlap entre chunks
        
        Returns:
            Lista de chunks
        """
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            
            if end >= len(text):
                chunks.append(text[start:])
                break
            
            # Tenta encontrar ponto de corte natural
            # 1. Parágrafo
            para_break = text.rfind('\n\n', start, end)
            if para_break > start:
                end = para_break + 2
            else:
                # 2. Sentença
                sent_break = max(
                    text.rfind('. ', start, end),
                    text.rfind('.\n', start, end),
                    text.rfind('! ', start, end),
                    text.rfind('? ', start, end)
                )
                if sent_break > start:
                    end = sent_break + 2
                else:
                    # 3. Palavra
                    word_break = text.rfind(' ', start, end)
                    if word_break > start:
                        end = word_break + 1
            
            chunks.append(text[start:end])
            
            # Próximo chunk com overlap
            start = max(end - overlap, start + 1)
        
        return chunks
    
    def get_config(self) -> Dict[str, Any]:
        """Retorna configuração do plugin."""
        return {
            "name": self.name,
            "description": self.description,
            "default_chunk_size": self.default_chunk_size,
            "default_overlap": self.default_overlap,
            "max_chunk_size": self.max_chunk_size
        }
    
    def install(self) -> bool:
        """Instala o plugin."""
        self.installed = True
        logger.info("RecursiveDocumentSplitter instalado")
        return True
    
    def uninstall(self) -> bool:
        """Desinstala o plugin."""
        self.installed = False
        logger.info("RecursiveDocumentSplitter desinstalado")
        return True


def create_recursive_document_splitter() -> RecursiveDocumentSplitterPlugin:
    """Factory para criar instância do plugin."""
    return RecursiveDocumentSplitterPlugin()

