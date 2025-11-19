"""
Framework Detector
Detecta frameworks, empresas e setores em texto usando Gliner (NER local) com fallback para keywords
"""

import re
from typing import List, Dict, Optional, Set
from wasabi import msg


class FrameworkDetector:
    """
    Detecta frameworks, empresas e setores em texto.
    
    Usa Gliner para NER quando disponível, com fallback para keyword matching.
    """
    
    def __init__(self):
        self.frameworks_list = [
            "SWOT", "Porter", "BCG Matrix", "BCG", "EBITDA", "CAGR",
            "PEST", "PESTEL", "5 Forces", "Five Forces", "Value Chain",
            "Ansoff Matrix", "McKinsey 7S", "Balanced Scorecard",
            "Blue Ocean", "Red Ocean", "Business Model Canvas",
            "Lean Startup", "Agile", "Scrum", "Kanban"
        ]
        
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
    
    def _load_models(self):
        """Carrega modelos de NER se disponíveis"""
        # Tenta carregar Gliner
        try:
            from gliner import GLiNER
            self.gliner_model = GLiNER.from_pretrained("urchade/gliner_small-v2.1")
            msg.info("✅ Gliner carregado para detecção de frameworks")
        except ImportError:
            msg.info("ℹ️  Gliner não disponível - usando fallback para keywords")
        except Exception as e:
            msg.warn(f"⚠️  Erro ao carregar Gliner: {str(e)} - usando fallback")
        
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
                    msg.info("ℹ️  spaCy não disponível - empresas serão detectadas via keywords")
        except ImportError:
            msg.info("ℹ️  spaCy não disponível - empresas serão detectadas via keywords")
        except Exception as e:
            msg.warn(f"⚠️  Erro ao carregar spaCy: {str(e)}")
    
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
    
    def _detect_frameworks_in_text(self, text: str) -> List[str]:
        """Detecta frameworks usando Gliner ou keyword matching"""
        detected = set()
        text_lower = text.lower()
        
        # Tenta usar Gliner primeiro
        if self.gliner_model:
            try:
                # Define labels para frameworks
                labels = ["framework", "business model", "strategic framework"]
                entities = self.gliner_model.predict_entities(text, labels, threshold=0.5)
                
                for entity in entities:
                    entity_text = entity.get("text", "").strip()
                    if entity_text:
                        # Verifica se corresponde a algum framework conhecido
                        for framework in self.frameworks_list:
                            if framework.lower() in entity_text.lower() or entity_text.lower() in framework.lower():
                                detected.add(framework)
                                break
            except Exception as e:
                msg.debug(f"Erro ao usar Gliner para frameworks: {str(e)}")
        
        # Fallback: keyword matching
        for framework in self.frameworks_list:
            # Busca framework no texto (case-insensitive)
            pattern = r'\b' + re.escape(framework) + r'\b'
            if re.search(pattern, text, re.IGNORECASE):
                detected.add(framework)
        
        return sorted(list(detected))
    
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
                msg.debug(f"Erro ao usar spaCy para empresas: {str(e)}")
        
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

