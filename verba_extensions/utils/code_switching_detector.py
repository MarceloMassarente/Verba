"""
Code-Switching Detector
Detecta textos bilíngues (PT+EN) comuns em documentos corporativos brasileiros

Exemplo: "O cash flow da empresa foi impactado pelo EBITDA ajustado"
         → Detectado como 'pt-en' (português com jargão técnico em inglês)
"""

from typing import List, Tuple
import re


class CodeSwitchingDetector:
    """
    Detecta code-switching PT+EN em textos corporativos
    
    Estratégia:
    1. Identifica termos técnicos/jargão em inglês (lista pré-definida)
    2. Conta proporção de termos EN vs total de palavras
    3. Classifica como:
       - "pt" (português puro)
       - "en" (inglês puro)
       - "pt-en" (português com jargão EN significativo)
       - "en-pt" (inglês com termos PT significativos)
    """
    
    def __init__(self):
        # Stopwords portuguesas (palavras estruturais)
        self.pt_stopwords = [
            "de", "da", "do", "dos", "das", "em", "na", "no", "nas", "nos",
            "para", "com", "sem", "sobre", "entre", "por", "pelo", "pela",
            "como", "onde", "quando", "quem", "porque", "que", "qual",
            "este", "esta", "esse", "essa", "aquele", "aquela",
            "está", "estão", "são", "foi", "foram", "fez", "fazem",
            "tem", "têm", "tinha", "tinham", "ser", "estar", "ter", "fazer",
            "mais", "menos", "muito", "pouco", "grande", "pequeno",
            "empresa", "empresas", "trabalho", "trabalhando", "trabalhou"
        ]
        
        # Stopwords inglesas (palavras estruturais)
        self.en_stopwords = [
            "the", "a", "an", "of", "in", "on", "at", "to", "for", "with",
            "from", "by", "about", "as", "is", "are", "was", "were", "been",
            "have", "has", "had", "do", "does", "did", "will", "would", "can",
            "could", "should", "may", "might", "must",
            "this", "that", "these", "those", "who", "what", "where", "when",
            "company", "companies", "work", "working", "worked"
        ]
        
        # Jargão técnico corporativo/financeiro em inglês
        # (comum em documentos brasileiros)
        self.technical_terms_en = [
            # Financeiro
            "cash", "flow", "cashflow", "revenue", "profit", "margin",
            "ebitda", "ebit", "roi", "kpi", "kpis", "opex", "capex",
            "p&l", "balance", "sheet", "statement", "assets", "liabilities",
            "equity", "debt", "valuation", "irr", "npv", "payback",
            
            # Negócios
            "business", "model", "strategy", "plan", "planning",
            "stakeholder", "stakeholders", "shareholder", "shareholders",
            "management", "governance", "compliance", "audit",
            "merger", "acquisition", "m&a", "ipo", "exit",
            "partnership", "joint", "venture", "jv",
            
            # Marketing/Vendas
            "market", "share", "target", "segment", "customer",
            "lead", "leads", "pipeline", "forecast", "churn",
            "retention", "acquisition", "conversion", "funnel",
            "branding", "positioning", "pricing",
            
            # Operações
            "supply", "chain", "logistics", "inventory", "stock",
            "quality", "assurance", "qa", "process", "workflow",
            "efficiency", "productivity", "throughput", "bottleneck",
            
            # Tech/Digital
            "software", "hardware", "platform", "cloud", "saas",
            "dashboard", "analytics", "data", "driven", "insights",
            "digital", "transformation", "innovation", "disruptive",
            "startup", "scale", "scalability", "growth", "hacking",
            
            # RH
            "human", "resources", "hr", "talent", "hiring",
            "onboarding", "offboarding", "performance", "review",
            "feedback", "engagement", "turnover", "headcount",
            
            # Geral
            "framework", "roadmap", "milestone", "deliverable",
            "deadline", "timeline", "scope", "budget", "risk",
            "issue", "stakeholder", "feedback", "meeting", "call",
            "email", "report", "presentation", "slide", "deck"
        ]
    
    def _normalize_text(self, text: str) -> str:
        """Normaliza texto para análise"""
        # Lowercase
        text = text.lower()
        # Remove pontuação mas mantém espaços
        text = re.sub(r'[^\w\s]', ' ', text)
        # Remove múltiplos espaços
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def detect_language_mix(self, text: str) -> Tuple[str, dict]:
        """
        Detecta mistura de idiomas no texto
        
        Returns:
            (language_code, stats)
            
            language_code:
                - "pt" (português puro ou dominante)
                - "en" (inglês puro ou dominante)
                - "pt-en" (português com jargão EN significativo ≥20%)
                - "en-pt" (inglês com termos PT significativos ≥20%)
            
            stats: {
                "total_words": int,
                "pt_words": int,
                "en_words": int,
                "technical_en": int,
                "pt_ratio": float,
                "en_ratio": float,
                "technical_ratio": float
            }
        """
        if not text or len(text.strip()) < 10:
            return "pt", {}  # Default para português
        
        normalized = self._normalize_text(text)
        words = normalized.split()
        total_words = len(words)
        
        if total_words == 0:
            return "pt", {}
        
        # Contar stopwords PT e EN
        pt_count = sum(1 for word in words if word in self.pt_stopwords)
        en_count = sum(1 for word in words if word in self.en_stopwords)
        
        # Contar termos técnicos EN (jargão corporativo)
        technical_count = 0
        for word in words:
            # Verificar termo exato
            if word in self.technical_terms_en:
                technical_count += 1
                continue
            # Verificar se palavra contém termo técnico (ex: "cashflow" contém "cash")
            for term in self.technical_terms_en:
                if len(term) >= 4 and term in word:
                    technical_count += 1
                    break
        
        # Calcular proporções
        pt_ratio = pt_count / total_words
        en_ratio = en_count / total_words
        technical_ratio = technical_count / total_words
        
        stats = {
            "total_words": total_words,
            "pt_words": pt_count,
            "en_words": en_count,
            "technical_en": technical_count,
            "pt_ratio": round(pt_ratio, 3),
            "en_ratio": round(en_ratio, 3),
            "technical_ratio": round(technical_ratio, 3)
        }
        
        # Decisão de classificação
        # Se tem ≥12% de termos técnicos EN, considerar bilíngue
        # (Threshold reduzido para capturar documentos corporativos com jargão moderado)
        if technical_ratio >= 0.12:
            # Se tem mais stopwords PT, é PT com jargão EN
            if pt_ratio > en_ratio:
                return "pt-en", stats
            # Se tem mais stopwords EN, é EN com termos PT
            elif en_ratio > pt_ratio:
                return "en-pt", stats
            # Empate: se tem termos técnicos, provavelmente é PT com jargão
            else:
                return "pt-en", stats
        
        # Se não tem jargão EN significativo, decidir pelo stopwords
        if pt_ratio > en_ratio * 1.5:  # PT dominante (1.5x mais stopwords)
            return "pt", stats
        elif en_ratio > pt_ratio * 1.5:  # EN dominante
            return "en", stats
        elif pt_ratio > en_ratio:  # PT leve vantagem
            return "pt", stats
        elif en_ratio > pt_ratio:  # EN leve vantagem
            return "en", stats
        else:
            # Empate: default PT (contexto brasileiro)
            return "pt", stats
    
    def is_bilingual(self, language_code: str) -> bool:
        """Verifica se language_code indica texto bilíngue"""
        return "-" in language_code  # "pt-en" ou "en-pt"
    
    def get_primary_language(self, language_code: str) -> str:
        """Extrai idioma primário de code-switching
        
        Exemplos:
            "pt-en" → "pt"
            "en-pt" → "en"
            "pt" → "pt"
        """
        return language_code.split("-")[0]
    
    def get_language_list(self, language_code: str) -> List[str]:
        """Retorna lista de idiomas presentes
        
        Exemplos:
            "pt-en" → ["pt", "en"]
            "pt" → ["pt"]
        """
        if "-" in language_code:
            return language_code.split("-")
        return [language_code]


# Singleton global para reusar instância
_detector = None

def get_detector() -> CodeSwitchingDetector:
    """Retorna singleton do detector"""
    global _detector
    if _detector is None:
        _detector = CodeSwitchingDetector()
    return _detector

