"""
Framework Detector
Detecta frameworks, empresas e setores em texto usando Gliner (NER local) com fallback para keywords
"""

import re
import json
import os
from typing import List, Dict, Optional, Set
from wasabi import msg


class FrameworkDetector:
    """
    Detecta frameworks, empresas e setores em texto.
    
    Usa Gliner para NER quando disponível, com fallback para keyword matching.
    Carrega frameworks de arquivo JSON com aliases PT/EN.
    """
    
    def __init__(self):
        # Lista hardcoded como fallback (compatibilidade)
        self.frameworks_list_fallback = [
            "SWOT", "Porter", "BCG Matrix", "BCG", "EBITDA", "CAGR",
            "PEST", "PESTEL", "5 Forces", "Five Forces", "Value Chain",
            "Ansoff Matrix", "McKinsey 7S", "Balanced Scorecard",
            "Blue Ocean", "Red Ocean", "Business Model Canvas",
            "Lean Startup", "Agile", "Scrum", "Kanban"
        ]
        
        # Estrutura de frameworks carregada do JSON
        self.frameworks_data = {}  # {alias: framework_name}
        self.frameworks_by_name = {}  # {framework_name: {aliases, category, description}}
        self._load_frameworks_from_json()
        
        self.sector_keywords = [
            "varejo", "retail", "bancos", "banking", "financeiro", "financial",
            "óleo e gás", "oil and gas", "energia", "energy", "telecomunicações",
            "telecom", "tecnologia", "technology", "saúde", "healthcare",
            "educação", "education", "consultoria", "consulting", "indústria",
            "industry", "manufatura", "manufacturing", "serviços", "services"
        ]
        
        self.gliner_model = None
        self.spacy_nlp = None
        self._load_models()
    
    def _load_frameworks_from_json(self):
        """Carrega frameworks do arquivo JSON com aliases"""
        frameworks_json_paths = [
            "verba_extensions/resources/frameworks.json",
            os.path.join(os.path.dirname(__file__), "../resources/frameworks.json"),
            "frameworks.json"
        ]
        
        frameworks_json = None
        for path in frameworks_json_paths:
            if os.path.exists(path):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        frameworks_json = json.load(f)
                    msg.info(f"Carregados frameworks de: {path}")
                    break
                except Exception as e:
                    msg.warn(f"Erro ao carregar {path}: {str(e)}")
                    continue
        
        if not frameworks_json:
            msg.warn("Arquivo frameworks.json nao encontrado - usando lista hardcoded")
            # Usa lista hardcoded como fallback
            for framework in self.frameworks_list_fallback:
                self.frameworks_data[framework.lower()] = framework
                self.frameworks_by_name[framework] = {
                    "aliases": [framework],
                    "category": "Ferramentas Clássicas",
                    "description": ""
                }
            return
        
        # Processa frameworks do JSON
        frameworks = frameworks_json.get("frameworks", [])
        for framework in frameworks:
            name = framework.get("name", "")
            aliases = framework.get("aliases", [])
            category = framework.get("category", "")
            description = framework.get("description", "")
            
            if not name:
                continue
            
            # Armazena por nome canônico
            self.frameworks_by_name[name] = {
                "aliases": aliases,
                "category": category,
                "description": description
            }
            
            # Mapeia cada alias para o nome canônico
            for alias in aliases:
                alias_lower = alias.lower().strip()
                if alias_lower:
                    # Se já existe, mantém o primeiro (prioridade)
                    if alias_lower not in self.frameworks_data:
                        self.frameworks_data[alias_lower] = name
        
        msg.info(f"Carregados {len(self.frameworks_by_name)} frameworks com {len(self.frameworks_data)} aliases")
    
    def _load_models(self):
        """Carrega modelos de NER se disponíveis"""
        # Tenta carregar Gliner
        try:
            from gliner import GLiNER
            self.gliner_model = GLiNER.from_pretrained("urchade/gliner_small-v2.1")
            msg.info("Gliner carregado para deteccao de frameworks")
        except ImportError:
            msg.info("Gliner nao disponivel - usando fallback para keywords")
        except Exception as e:
            msg.warn(f"Erro ao carregar Gliner: {str(e)} - usando fallback")
        
        # Tenta carregar spaCy para detecção de empresas
        try:
            import spacy
            # Tenta carregar modelo português primeiro
            try:
                self.spacy_nlp = spacy.load("pt_core_news_sm")
            except OSError:
                # Fallback para inglês
                try:
                    self.spacy_nlp = spacy.load("en_core_web_sm")
                except OSError:
                    msg.info("spaCy nao disponivel - empresas serao detectadas via keywords")
        except ImportError:
            msg.info("spaCy nao disponivel - empresas serao detectadas via keywords")
        except Exception as e:
            msg.warn(f"Erro ao carregar spaCy: {str(e)}")
    
    async def detect_frameworks(self, text: str) -> Dict[str, any]:
        """
        Detecta frameworks, empresas e setores em texto.
        
        Args:
            text: Texto a analisar
        
        Returns:
            Dict com:
            - frameworks: List[str] - Frameworks detectados
            - companies: List[str] - Empresas detectadas
            - sectors: List[str] - Setores detectados
            - confidence: float - Confiança geral (0.0-1.0)
        """
        result = {
            "frameworks": [],
            "companies": [],
            "sectors": [],
            "confidence": 0.0
        }
        
        if not text or len(text.strip()) < 10:
            return result
        
        # Detecta frameworks
        frameworks = self._detect_frameworks_in_text(text)
        result["frameworks"] = frameworks
        
        # Detecta empresas
        companies = await self._detect_companies_in_text(text)
        result["companies"] = companies
        
        # Detecta setores
        sectors = self._detect_sectors_in_text(text)
        result["sectors"] = sectors
        
        # Calcula confiança
        confidence = self._calculate_confidence(frameworks, companies, sectors, text)
        result["confidence"] = confidence
        
        return result
    
    def _estimate_token_count(self, text: str) -> int:
        """
        Estima número de tokens em um texto.
        
        Aproximação: 
        - Português: ~2.5 caracteres por token
        - Inglês: ~4 caracteres por token
        - Usa média conservadora de 3 caracteres por token
        """
        # Conta caracteres (espaços também contam como tokens)
        char_count = len(text)
        # Aproximação conservadora: 3 chars por token (português tende a ter mais tokens por char)
        estimated_tokens = char_count // 3
        return estimated_tokens
    
    def _split_text_for_gliner(self, text: str, max_tokens: int = 350) -> List[str]:
        """
        Divide texto em chunks menores respeitando limite de tokens do GLiNER (384 tokens).
        
        Usa max_tokens=350 para deixar margem de segurança (384 - 10%).
        Tenta dividir em delimitadores naturais (sentenças, parágrafos).
        
        Args:
            text: Texto a dividir
            max_tokens: Limite máximo de tokens por chunk (padrão: 350)
        
        Returns:
            Lista de chunks de texto
        """
        # Se texto é pequeno, retorna como está
        if self._estimate_token_count(text) <= max_tokens:
            return [text]
        
        chunks = []
        # Aproximação: max_chars = max_tokens * 3 (caracteres por token)
        max_chars_per_chunk = max_tokens * 3
        
        # Divide o texto
        current_pos = 0
        text_length = len(text)
        
        while current_pos < text_length:
            # Define fim do chunk
            end_pos = min(current_pos + max_chars_per_chunk, text_length)
            
            # Se é o último chunk, pega o restante
            if end_pos >= text_length:
                chunk = text[current_pos:]
                if chunk.strip():
                    chunks.append(chunk)
                break
            
            # Tenta encontrar delimitador natural antes do limite
            # Prioridade: parágrafo > sentença > vírgula > espaço
            
            # 1. Tenta parágrafo (2 quebras de linha)
            para_break = text.rfind('\n\n', current_pos, end_pos)
            if para_break > current_pos + (max_chars_per_chunk * 0.5):  # Pelo menos 50% do chunk
                end_pos = para_break + 2
            else:
                # 2. Tenta sentença (ponto seguido de espaço/quebra)
                sent_break = max(
                    text.rfind('. ', current_pos, end_pos),
                    text.rfind('.\n', current_pos, end_pos),
                    text.rfind('! ', current_pos, end_pos),
                    text.rfind('? ', current_pos, end_pos)
                )
                if sent_break > current_pos + (max_chars_per_chunk * 0.6):  # Pelo menos 60% do chunk
                    end_pos = sent_break + 2
                else:
                    # 3. Tenta vírgula
                    comma_break = text.rfind(', ', current_pos, end_pos)
                    if comma_break > current_pos + (max_chars_per_chunk * 0.7):  # Pelo menos 70% do chunk
                        end_pos = comma_break + 2
                    else:
                        # 4. Fallback: espaço
                        space_break = text.rfind(' ', current_pos, end_pos)
                        if space_break > current_pos:
                            end_pos = space_break + 1
            
            # Extrai chunk
            chunk = text[current_pos:end_pos].strip()
            if chunk:
                chunks.append(chunk)
            
            # Move para próximo chunk
            current_pos = end_pos
        
        return chunks if chunks else [text]
    
    def _detect_frameworks_in_text(self, text: str) -> List[str]:
        """Detecta frameworks usando Gliner ou keyword matching com aliases"""
        detected_names = set()  # Nomes canônicos dos frameworks
        text_lower = text.lower()

        # Tenta usar Gliner primeiro (mais preciso)
        if self.gliner_model:
            try:
                # Define labels para frameworks
                labels = ["framework", "business model", "strategic framework"]
                
                # Verifica se texto precisa ser dividido (limite GLiNER: 384 tokens)
                estimated_tokens = self._estimate_token_count(text)
                
                if estimated_tokens > 350:  # Margem de segurança (350 < 384)
                    # Divide texto em chunks menores
                    text_chunks = self._split_text_for_gliner(text, max_tokens=350)
                    # Log apenas se muito verbose (comentado para não poluir logs)
                    # msg.info(f"[GLiNER] Texto longo ({estimated_tokens} tokens estimados) dividido em {len(text_chunks)} chunks")
                    
                    # Processa cada chunk separadamente
                    all_entities = []
                    for i, chunk in enumerate(text_chunks):
                        try:
                            chunk_entities = self.gliner_model.predict_entities(chunk, labels, threshold=0.5)
                            all_entities.extend(chunk_entities)
                            # Log apenas se muito verbose (comentado para não poluir logs)
                            # msg.info(f"[GLiNER] Chunk {i+1}/{len(text_chunks)}: {len(chunk_entities)} entidades encontradas")
                        except Exception as e:
                            msg.warn(f"[GLiNER] Erro ao processar chunk {i+1}: {str(e)}")
                    
                    entities = all_entities
                else:
                    # Texto cabe no limite, processa normalmente
                    entities = self.gliner_model.predict_entities(text, labels, threshold=0.5)

                # Processa entidades encontradas (de todos os chunks ou único)
                for entity in entities:
                    entity_text = entity.get("text", "").strip()
                    if entity_text:
                        entity_lower = entity_text.lower()
                        # Verifica se corresponde a algum alias conhecido
                        for alias, framework_name in self.frameworks_data.items():
                            # Match parcial ou completo
                            if alias in entity_lower or entity_lower in alias:
                                detected_names.add(framework_name)
                                break
            except Exception as e:
                msg.warn(f"Erro ao usar Gliner para frameworks: {str(e)}")

        # Keyword matching como fallback ou complemento
        # Prioriza aliases curtos sobre longos para evitar que palavras curtas sejam "mascaradas"
        sorted_aliases = sorted(self.frameworks_data.items(),
                              key=lambda x: (len(x[0].split()), len(x[0])))  # Ordem normal (curtos primeiro)

        for alias, framework_name in sorted_aliases:
            # Ignora aliases muito genéricos que podem causar falsos positivos
            if alias in ["analysis", "framework", "model", "system", "method", "matrix", "index"]:
                continue

            # Para aliases curtos (1 palavra), busca exata com word boundary
            if len(alias.split()) == 1:
                pattern = r'\b' + re.escape(alias) + r'\b'
                if re.search(pattern, text_lower):
                    detected_names.add(framework_name)
            # Para aliases curtos (2 palavras), busca exata
            elif len(alias.split()) == 2:
                pattern = r'\b' + re.escape(alias) + r'\b'
                if re.search(pattern, text_lower):
                    detected_names.add(framework_name)
            # Para aliases médios (3 palavras), permite match mais flexível
            elif len(alias.split()) == 3:
                # Verifica se todas as palavras estão presentes (não necessariamente na ordem)
                words_in_alias = alias.split()
                words_found = sum(1 for word in words_in_alias if word in text_lower)
                if words_found == len(words_in_alias):
                    detected_names.add(framework_name)
            # Para aliases longos, permite match parcial mas requer mais palavras
            else:
                words_in_alias = alias.split()
                if len(words_in_alias) >= 4:
                    # Pelo menos 3 palavras do alias devem estar no texto
                    words_found = sum(1 for word in words_in_alias if word in text_lower)
                    if words_found >= 3:
                        detected_names.add(framework_name)

        # Retorna nomes canônicos ordenados
        return sorted(list(detected_names))
    
    async def _detect_companies_in_text(self, text: str) -> List[str]:
        """Detecta empresas usando spaCy NER ou keywords"""
        detected = set()
        
        # Tenta usar spaCy primeiro
        if self.spacy_nlp:
            try:
                doc = self.spacy_nlp(text)
                # Extrai entidades do tipo ORG (organizações)
                for ent in doc.ents:
                    if ent.label_ in ["ORG", "PERSON"]:  # Pessoas podem ser empresas também
                        entity_text = ent.text.strip()
                        if len(entity_text) > 2 and entity_text[0].isupper():
                            detected.add(entity_text)
            except Exception as e:
                msg.warn(f"Erro ao usar spaCy para empresas: {str(e)}")
        
        # Fallback: detecta palavras capitalizadas que podem ser empresas
        # Padrão: palavras com inicial maiúscula seguidas de outras palavras capitalizadas
        words = text.split()
        potential_companies = []
        
        for i, word in enumerate(words):
            # Palavra capitalizada com pelo menos 3 caracteres
            if word and word[0].isupper() and len(word) > 2:
                # Se próxima palavra também é capitalizada, pode ser nome de empresa
                if i + 1 < len(words) and words[i + 1] and words[i + 1][0].isupper():
                    company_name = f"{word} {words[i + 1]}"
                    if len(company_name) > 5:  # Filtra nomes muito curtos
                        potential_companies.append(company_name)
        
        # Adiciona empresas conhecidas (exemplos comuns)
        known_companies = [
            "Apple", "Google", "Microsoft", "Amazon", "Meta", "Facebook",
            "Tesla", "Netflix", "Uber", "Airbnb", "Spotify", "LinkedIn",
            "Shell", "Petrobras", "Vale", "Itaú", "Bradesco", "Banco do Brasil"
        ]
        
        text_lower = text.lower()
        for company in known_companies:
            if company.lower() in text_lower:
                detected.add(company)
        
        # Adiciona potenciais empresas encontradas
        for company in potential_companies[:10]:  # Limita a 10 para evitar ruído
            detected.add(company)
        
        return sorted(list(detected))[:20]  # Limita a 20 empresas
    
    def _detect_sectors_in_text(self, text: str) -> List[str]:
        """Detecta setores usando keyword matching"""
        detected = set()
        text_lower = text.lower()
        
        for sector in self.sector_keywords:
            if sector.lower() in text_lower:
                detected.add(sector)
        
        return sorted(list(detected))
    
    def _calculate_confidence(
        self,
        frameworks: List[str],
        companies: List[str],
        sectors: List[str],
        text: str
    ) -> float:
        """
        Calcula confiança na detecção baseado em:
        - Número de entidades detectadas
        - Tamanho do texto
        - Uso de modelos avançados (Gliner/spaCy)
        """
        confidence = 0.0
        
        # Base: se detectou algo, confiança mínima
        if frameworks or companies or sectors:
            confidence = 0.3
        
        # Bonus por usar modelos avançados
        if self.gliner_model:
            confidence += 0.2
        if self.spacy_nlp:
            confidence += 0.1
        
        # Bonus por múltiplas detecções
        total_detections = len(frameworks) + len(companies) + len(sectors)
        if total_detections >= 3:
            confidence += 0.2
        elif total_detections >= 2:
            confidence += 0.1
        
        # Bonus se texto é longo (mais contexto)
        if len(text) > 500:
            confidence += 0.1
        elif len(text) > 200:
            confidence += 0.05
        
        # Cap em 1.0
        return min(confidence, 1.0)


# Singleton instance
_framework_detector_instance = None


def get_framework_detector() -> FrameworkDetector:
    """Retorna instância singleton do FrameworkDetector"""
    global _framework_detector_instance
    if _framework_detector_instance is None:
        _framework_detector_instance = FrameworkDetector()
    return _framework_detector_instance

