"""
Utilitários para telemetria e métricas de cobertura ESCO/regex.

Gera relatórios de melhoria contínua para identificar gaps em normalização
e mapeamentos. Adaptado do RAG2 para Verba.

Features:
- Rastreia métodos de normalização (títulos, skills, companies)
- Identifica termos não mapeados (gaps)
- Gera relatórios JSON
- Estatísticas de qualidade de chunks

Uso:
    from verba_extensions.utils.telemetry import get_telemetry
    
    telemetry = get_telemetry()
    
    # Registrar normalização de título
    telemetry.record_title_normalization(
        method="regex",  # ou "llm", "none", etc.
        original_title="CEO"
    )
    
    # Registrar skill não mapeada
    telemetry.record_skill_normalization(
        was_mapped=False,
        original_skill="Python"
    )
    
    # Registrar chunk filtrado por qualidade
    telemetry.record_chunk_filtered_by_quality(
        parent_type="section",
        score=0.25,
        reason="LEN_V_SHORT:DENSITY_LOW"
    )
    
    # Gerar relatório
    report = telemetry.generate_report()
    telemetry.save_report("telemetry_report.json")

Relatório inclui:
- Cobertura de normalização de títulos por método
- Top 20 termos não mapeados
- Distribuição de proveniência de company_id
- Estatísticas de chunks filtrados por qualidade

Documentação completa: verba_extensions/utils/README.md
"""
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional
import json
from datetime import datetime, timezone


class TelemetryCollector:
    """
    Coletor de telemetria para métricas de normalização e cobertura.
    """
    
    def __init__(self):
        self.title_norm_methods = Counter()
        self.unmapped_titles = Counter()
        self.unmapped_skills = Counter()
        self.company_id_sources = Counter()
        self.date_granularities = Counter()
        self.side_gigs_filtered = 0
        # Telemetria de skills 2-stage
        self.skills_collisions = 0
        self.skills_unknown_rate_sum = 0.0
        self.skills_normalization_batches = 0
        # Telemetria de chunks filtrados por qualidade
        self.chunks_filtered_by_type = Counter()
        self.chunks_filtered_by_reason = Counter()
        self.chunks_filtered_scores = defaultdict(list)
    
    def record_title_normalization(self, method: str, original_title: Optional[str] = None):
        """Registra método usado para normalizar título."""
        self.title_norm_methods[method] += 1
        if method == "none" and original_title:
            self.unmapped_titles[original_title.lower()[:100]] += 1
    
    def record_skill_normalization(self, was_mapped: bool, original_skill: Optional[str] = None):
        """Registra se skill foi mapeada."""
        if not was_mapped and original_skill:
            self.unmapped_skills[original_skill.lower()[:100]] += 1
    
    def record_company_id_source(self, source: str):
        """Registra proveniência de company_id."""
        self.company_id_sources[source] += 1
    
    def record_date_granularity(self, granularity: Optional[str]):
        """Registra granularidade de data."""
        if granularity:
            self.date_granularities[granularity] += 1
    
    def record_side_gig_filtered(self, count: int = 1):
        """Registra quantos side gigs foram filtrados."""
        self.side_gigs_filtered += count
    
    def record_skills_collisions(self, count: int):
        """Registra contagem de colisões em skills 2-stage."""
        self.skills_collisions += count
        self.skills_normalization_batches += 1
    
    def record_skills_unknown_rate(self, rate: float):
        """Registra taxa de unknown skills em lote."""
        self.skills_unknown_rate_sum += rate
    
    def record_chunk_filtered_by_quality(self, parent_type: str, score: float, reason: str):
        """Registra chunk filtrado por qualidade."""
        self.chunks_filtered_by_type[parent_type] += 1
        self.chunks_filtered_by_reason[reason] += 1
        self.chunks_filtered_scores[parent_type].append(score)
    
    def generate_report(self) -> Dict[str, Any]:
        """
        Gera relatório de telemetria.
        
        Returns:
            Dict com métricas agregadas
        """
        total_titles = sum(self.title_norm_methods.values())
        total_skills = sum(self.unmapped_skills.values())
        total_companies = sum(self.company_id_sources.values())
        
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "title_normalization": {
                "total": total_titles,
                "by_method": dict(self.title_norm_methods),
                "coverage_pct": {
                    method: (count / total_titles * 100) if total_titles > 0 else 0
                    for method, count in self.title_norm_methods.items()
                },
                "top_unmapped": [
                    {"title": title, "count": count}
                    for title, count in self.unmapped_titles.most_common(20)
                ]
            },
            "skill_normalization": {
                "total_unmapped": total_skills,
                "top_unmapped": [
                    {"skill": skill, "count": count}
                    for skill, count in self.unmapped_skills.most_common(20)
                ]
            },
            "company_id_sources": {
                "total": total_companies,
                "by_source": dict(self.company_id_sources),
                "distribution_pct": {
                    source: (count / total_companies * 100) if total_companies > 0 else 0
                    for source, count in self.company_id_sources.items()
                }
            },
            "date_granularities": {
                "by_granularity": dict(self.date_granularities)
            },
            "side_gigs": {
                "filtered_count": self.side_gigs_filtered
            },
            "skills_2stage": {
                "collisions_total": self.skills_collisions,
                "unknown_rate_avg": (
                    self.skills_unknown_rate_sum / self.skills_normalization_batches 
                    if self.skills_normalization_batches > 0 else 0.0
                ),
                "batches_processed": self.skills_normalization_batches
            },
            "chunks_quality_filtered": {
                "by_type": dict(self.chunks_filtered_by_type),
                "by_reason": dict(self.chunks_filtered_by_reason),
                "avg_score_by_type": {
                    parent_type: sum(scores) / len(scores) if scores else 0.0
                    for parent_type, scores in self.chunks_filtered_scores.items()
                },
                "total_filtered": sum(self.chunks_filtered_by_type.values())
            }
        }
        
        return report
    
    def save_report(self, output_path: str):
        """Salva relatório em JSON."""
        report = self.generate_report()
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
    
    def reset(self):
        """Limpa coletor (útil para períodos semanais)."""
        self.title_norm_methods.clear()
        self.unmapped_titles.clear()
        self.unmapped_skills.clear()
        self.company_id_sources.clear()
        self.date_granularities.clear()
        self.side_gigs_filtered = 0
        self.skills_collisions = 0
        self.skills_unknown_rate_sum = 0.0
        self.skills_normalization_batches = 0
        self.chunks_filtered_by_type.clear()
        self.chunks_filtered_by_reason.clear()
        self.chunks_filtered_scores.clear()


# Instância global (pode ser substituída por singleton se necessário)
_telemetry_collector = TelemetryCollector()


def get_telemetry() -> TelemetryCollector:
    """Retorna instância global do coletor de telemetria."""
    return _telemetry_collector

