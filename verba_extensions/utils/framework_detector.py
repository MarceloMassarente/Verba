"""
Framework Detector
Detecta frameworks, empresas e setores em texto usando Gliner (NER local) com fallback para keywords
"""

import re
import json
import os
from typing import List, Dict, Optional, Set
from wasabi import msg


class ConsultoriaLabels:
    """Labels específicas para documentos de consultoria"""
    
    # Labels genéricas (fallback)
    GENERIC = [
        "framework",
        "business model",
        "strategic framework"
    ]
    
    # Labels específicas e contextualizadas
    ESPECIFICAS = [
        "framework de estratégia mencionado",
        "framework operacional citado",
        "metodologia de negócio referenciada",
        "modelo de análise estratégica mencionado",
        "ferramenta de consultoria citada"
    ]
    
    @classmethod
    def get_labels_for_context(cls, tipo_doc: Optional[str] = None) -> List[str]:
        """
        Retorna labels apropriadas baseadas no contexto.
        
        Args:
            tipo_doc: Tipo de documento ("estrategia", "operacoes", "organizacao", "financeiro")
        
        Returns:
            Lista de labels para usar no GLiNER
        """
        # Se tipo_doc especificado, usa labels específicas
        if tipo_doc:
            return cls.ESPECIFICAS
        # Caso contrário, usa labels específicas por padrão (melhor recall)
        return cls.ESPECIFICAS


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
    
    async def detect_frameworks(
        self, 
        text: str, 
        tipo_doc: Optional[str] = None,
        threshold: float = 0.55,
        extract_concepts: bool = True,
        extract_metrics: bool = True,
        classify_content: bool = True
    ) -> Dict[str, any]:
        """
        Detecta frameworks, empresas, pessoas, conceitos de negócio, métricas, tipo de conteúdo e setores em texto.
        
        Args:
            text: Texto a analisar
            tipo_doc: Tipo de documento para selecionar labels apropriadas
            threshold: Threshold de confiança para GLiNER frameworks (default: 0.55)
            extract_concepts: Se True, extrai conceitos de negócio (default: True)
            extract_metrics: Se True, extrai métricas e KPIs (default: True)
            classify_content: Se True, classifica tipo de conteúdo (default: True)
        
        Returns:
            Dict com:
            - frameworks: List[str] - Frameworks detectados
            - companies: List[str] - Empresas detectadas
            - persons: List[str] - Pessoas detectadas (executivos, consultores, autores)
            - conceitos_negocio: List[str] - Conceitos de negócio detectados
            - metricas: Dict - Métricas qualitativas e quantitativas
            - tipo_conteudo: str - Tipo de conteúdo ("analise", "recomendacao", "acao", "contexto")
            - sectors: List[str] - Setores detectados
            - confidence: float - Confiança geral (0.0-1.0)
        """
        result = {
            "frameworks": [],
            "companies": [],
            "persons": [],
            "conceitos_negocio": [],
            "metricas": {},
            "tipo_conteudo": "contexto",
            "sectors": [],
            "confidence": 0.0
        }
        
        if not text or len(text.strip()) < 10:
            return result
        
        # Detecta frameworks
        frameworks = self._detect_frameworks_in_text(text, tipo_doc=tipo_doc, threshold=threshold)
        result["frameworks"] = frameworks
        
        # Detecta empresas
        companies = await self._detect_companies_in_text(text)
        result["companies"] = companies
        
        # Detecta pessoas (executivos, consultores, autores)
        persons = self._extract_persons(text)
        result["persons"] = persons
        
        # Detecta conceitos de negócio (se habilitado)
        if extract_concepts:
            conceitos = self._extract_business_concepts(text, threshold=0.5)
            result["conceitos_negocio"] = conceitos
        
        # Detecta métricas (se habilitado)
        if extract_metrics:
            metricas = self._extract_metrics(text, threshold=0.6)
            result["metricas"] = metricas
        
        # Classifica tipo de conteúdo (se habilitado)
        if classify_content:
            tipo_conteudo = self._classify_content_type(text)
            result["tipo_conteudo"] = tipo_conteudo
        
        # Detecta setores
        sectors = self._detect_sectors_in_text(text)
        result["sectors"] = sectors
        
        # Calcula confiança
        confidence = self._calculate_confidence(frameworks, companies, sectors, text, persons)
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
    
    def _detect_frameworks_in_text(
        self, 
        text: str, 
        tipo_doc: Optional[str] = None,
        threshold: float = 0.55
    ) -> List[str]:
        """
        Detecta frameworks usando Gliner ou keyword matching com aliases
        
        Args:
            text: Texto a analisar
            tipo_doc: Tipo de documento para selecionar labels apropriadas
            threshold: Threshold de confiança para GLiNER (default: 0.55)
        """
        detected_names = set()  # Nomes canônicos dos frameworks
        text_lower = text.lower()

        # Tenta usar Gliner primeiro (mais preciso)
        if self.gliner_model:
            try:
                # Define labels para frameworks usando ConsultoriaLabels
                labels = ConsultoriaLabels.get_labels_for_context(tipo_doc)
                
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
                            chunk_entities = self.gliner_model.predict_entities(chunk, labels, threshold=threshold)
                            all_entities.extend(chunk_entities)
                            # Log apenas se muito verbose (comentado para não poluir logs)
                            # msg.info(f"[GLiNER] Chunk {i+1}/{len(text_chunks)}: {len(chunk_entities)} entidades encontradas")
                        except Exception as e:
                            msg.warn(f"[GLiNER] Erro ao processar chunk {i+1}: {str(e)}")
                    
                    entities = all_entities
                else:
                    # Texto cabe no limite, processa normalmente
                    entities = self.gliner_model.predict_entities(text, labels, threshold=threshold)

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
                    if ent.label_ == "ORG":
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
    
    def _extract_persons(self, text: str) -> List[str]:
        """
        Extrai pessoas mencionadas em contexto de negócio (executivos, consultores, autores).
        Filtra rigorosamente para evitar explosão de entidades.
        
        Args:
            text: Texto a analisar
        
        Returns:
            Lista de pessoas detectadas (máximo 10)
        """
        persons = []
        
        if not self.spacy_nlp:
            return persons
        
        try:
            doc = self.spacy_nlp(text)
            text_lower = text.lower()
            
            # Palavras-chave que indicam contexto de negócio
            business_context_keywords = [
                "ceo", "presidente", "diretor", "executivo", "consultor", "autor",
                "fundador", "cofundador", "lider", "gestor", "gerente",
                "mckinsey", "bain", "bcg", "deloitte", "pwc", "kpmg"
            ]
            
            # Nomes muito comuns que devem ser filtrados
            common_names = [
                "joão", "maria", "josé", "ana", "carlos", "paulo", "pedro",
                "john", "mary", "james", "robert", "michael", "david"
            ]
            
            for ent in doc.ents:
                if ent.label_ in ["PERSON", "PER"]:
                    person_text = ent.text.strip()
                    
                    # Filtros básicos
                    if len(person_text) < 3:
                        continue
                    if not person_text[0].isupper():
                        continue
                    
                    # Filtra nomes muito comuns (provavelmente não são relevantes)
                    person_lower = person_text.lower()
                    if any(common in person_lower for common in common_names):
                        # Só aceita se estiver em contexto de negócio
                        sent = ent.sent.text.lower() if ent.sent else ""
                        if not any(keyword in sent for keyword in business_context_keywords):
                            continue
                    
                    # Verifica contexto: pessoa deve estar em sentença com palavras-chave de negócio
                    sent = ent.sent.text.lower() if ent.sent else text_lower
                    if any(keyword in sent for keyword in business_context_keywords):
                        if person_text not in persons:
                            persons.append(person_text)
                    
                    # Limite de segurança: máximo 10 pessoas por chunk
                    if len(persons) >= 10:
                        break
        
        except Exception as e:
            msg.warn(f"Erro ao extrair pessoas: {str(e)}")
        
        return sorted(list(set(persons)))[:10]  # Remove duplicatas e limita a 10
    
    def _extract_business_concepts(self, text: str, threshold: float = 0.5) -> List[str]:
        """
        Extrai conceitos de negócio usando GLiNER.
        
        Args:
            text: Texto a analisar
            threshold: Threshold de confiança para GLiNER (default: 0.5)
        
        Returns:
            Lista de conceitos de negócio detectados (máximo 15)
        """
        concepts = []
        
        if not self.gliner_model:
            return concepts
        
        try:
            labels_conceitos = [
                "vantagem competitiva mencionada",
                "proposta de valor citada",
                "modelo de negócio descrito",
                "cadeia de valor mencionada",
                "diferenciação competitiva citada",
                "core competence citada",
                "cadeia de suprimentos mencionada",
                "canais de distribuição citados",
                "segmento de clientes mencionado",
                "estrutura de custos citada",
                "fonte de receita mencionada"
            ]
            
            # Verifica se texto precisa ser dividido
            estimated_tokens = self._estimate_token_count(text)
            
            if estimated_tokens > 350:
                text_chunks = self._split_text_for_gliner(text, max_tokens=350)
                all_entities = []
                for chunk in text_chunks:
                    try:
                        chunk_entities = self.gliner_model.predict_entities(
                            chunk, 
                            labels_conceitos, 
                            threshold=threshold
                        )
                        all_entities.extend(chunk_entities)
                    except Exception as e:
                        msg.warn(f"[GLiNER] Erro ao processar chunk para conceitos: {str(e)}")
                entities = all_entities
            else:
                entities = self.gliner_model.predict_entities(
                    text, 
                    labels_conceitos, 
                    threshold=threshold
                )
            
            # Extrai textos dos conceitos detectados
            for entity in entities:
                concept_text = entity.get("text", "").strip()
                if concept_text and concept_text not in concepts:
                    concepts.append(concept_text)
                    # Limite de segurança: máximo 15 conceitos por chunk
                    if len(concepts) >= 15:
                        break
        
        except Exception as e:
            msg.warn(f"Erro ao extrair conceitos de negócio: {str(e)}")
        
        return sorted(list(set(concepts)))[:15]  # Remove duplicatas e limita a 15
    
    def _classify_content_type(self, text: str) -> str:
        """
        Classifica tipo de conteúdo usando análise sintática do Spacy.
        
        Args:
            text: Texto a classificar
        
        Returns:
            Tipo de conteúdo: "analise", "recomendacao", "acao", "contexto"
        """
        if not self.spacy_nlp:
            return "contexto"
        
        try:
            doc = self.spacy_nlp(text)
            
            # Verbos por categoria
            verbos_analise = ['analisar', 'avaliar', 'examinar', 'investigar', 'estudar', 
                            'review', 'analyze', 'evaluate', 'examine', 'investigate']
            verbos_recomendacao = ['recomendar', 'sugerir', 'propor', 'indicar', 'aconselhar',
                                  'recommend', 'suggest', 'propose', 'advise']
            verbos_acao = ['implementar', 'executar', 'realizar', 'desenvolver', 'aplicar',
                          'implement', 'execute', 'develop', 'apply']
            
            contagem = {
                'verbos_analise': 0,
                'verbos_recomendacao': 0,
                'verbos_acao': 0
            }
            
            for token in doc:
                if token.pos_ == 'VERB':
                    lemma = token.lemma_.lower()
                    if lemma in verbos_analise:
                        contagem['verbos_analise'] += 1
                    elif lemma in verbos_recomendacao:
                        contagem['verbos_recomendacao'] += 1
                    elif lemma in verbos_acao:
                        contagem['verbos_acao'] += 1
            
            # Classifica baseado na contagem
            max_verbos = max(contagem.values())
            if max_verbos == 0:
                return "contexto"
            
            if contagem['verbos_recomendacao'] == max_verbos:
                return "recomendacao"
            elif contagem['verbos_acao'] == max_verbos:
                return "acao"
            elif contagem['verbos_analise'] == max_verbos:
                return "analise"
            else:
                return "contexto"
        
        except Exception as e:
            msg.warn(f"Erro ao classificar tipo de conteúdo: {str(e)}")
            return "contexto"
    
    def _extract_metrics(self, text: str, threshold: float = 0.6) -> Dict[str, any]:
        """
        Extrai métricas e KPIs mencionados no texto.
        
        Args:
            text: Texto a analisar
            threshold: Threshold de confiança para GLiNER (default: 0.6)
        
        Returns:
            Dict com:
            - metricas_qualitativas: List[Dict] - Menções qualitativas de métricas
            - metricas_quantitativas: List[Dict] - Valores numéricos com contexto
        """
        result = {
            "metricas_qualitativas": [],
            "metricas_quantitativas": []
        }
        
        # GLiNER para menções qualitativas
        if self.gliner_model:
            try:
                labels_metricas = [
                    "indicador de desempenho mencionado",
                    "métrica financeira citada",
                    "KPI operacional mencionado",
                    "métrica de mercado citada",
                    "indicador de qualidade mencionado"
                ]
                
                estimated_tokens = self._estimate_token_count(text)
                
                if estimated_tokens > 350:
                    text_chunks = self._split_text_for_gliner(text, max_tokens=350)
                    all_entities = []
                    for chunk in text_chunks:
                        try:
                            chunk_entities = self.gliner_model.predict_entities(
                                chunk, 
                                labels_metricas, 
                                threshold=threshold
                            )
                            all_entities.extend(chunk_entities)
                        except Exception as e:
                            msg.warn(f"[GLiNER] Erro ao processar chunk para métricas: {str(e)}")
                    entities = all_entities
                else:
                    entities = self.gliner_model.predict_entities(
                        text, 
                        labels_metricas, 
                        threshold=threshold
                    )
                
                for entity in entities:
                    if len(result["metricas_qualitativas"]) >= 20:  # Limite de 20
                        break
                    result["metricas_qualitativas"].append({
                        "texto": entity.get("text", "").strip(),
                        "label": entity.get("label", ""),
                        "score": entity.get("score", 0.0)
                    })
            except Exception as e:
                msg.warn(f"Erro ao extrair métricas qualitativas: {str(e)}")
        
        # Regex + Spacy para valores numéricos com contexto
        if self.spacy_nlp:
            try:
                doc = self.spacy_nlp(text)
                
                # Padrões para detectar métricas numéricas
                metric_patterns = [
                    (r'ROI\s+(?:de|of)?\s*([\d.,]+%)', 'ROI'),
                    (r'crescimento\s+(?:de|of)?\s*([\d.,]+%)', 'crescimento'),
                    (r'market\s+share\s+(?:de|of)?\s*([\d.,]+%)', 'market_share'),
                    (r'margem\s+(?:de|of)?\s*([\d.,]+%)', 'margem'),
                    (r'EBITDA\s+(?:de|of)?\s*([\d.,]+)', 'EBITDA'),
                    (r'receita\s+(?:de|of)?\s*([\d.,]+)', 'receita'),
                ]
                
                for pattern, metric_name in metric_patterns:
                    matches = re.finditer(pattern, text, re.IGNORECASE)
                    for match in matches:
                        if len(result["metricas_quantitativas"]) >= 20:  # Limite de 20
                            break
                        valor = match.group(1)
                        start_pos = match.start()
                        end_pos = match.end()
                        
                        # Encontra sentença que contém a métrica
                        sentenca = ""
                        for sent in doc.sents:
                            if start_pos >= sent.start_char and end_pos <= sent.end_char:
                                sentenca = sent.text
                                break
                        
                        result["metricas_quantitativas"].append({
                            "valor": valor,
                            "metrica": metric_name,
                            "sentenca": sentenca.strip()
                        })
            except Exception as e:
                msg.warn(f"Erro ao extrair métricas quantitativas: {str(e)}")
        
        return result
    
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
        text: str,
        persons: Optional[List[str]] = None
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
        persons_count = len(persons) if persons else 0
        total_detections = len(frameworks) + len(companies) + len(sectors) + persons_count
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

