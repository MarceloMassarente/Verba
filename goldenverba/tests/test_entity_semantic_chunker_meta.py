import pytest

from verba_extensions.plugins.entity_semantic_chunker import (
    _extract_companies_from_spans,
)


def test_extract_companies_from_spans_basic():
    spans = [
        {"text": "CBA", "label": "ORG"},
        {"text": "Vale", "label": "ORG"},
        {"text": "John", "label": "PERSON"},
    ]
    companies = _extract_companies_from_spans(spans)
    # Deve conter apenas ORG, normalizados (lower)
    assert "cba" in companies
    assert "vale" in companies
    assert all(name.islower() for name in companies)


def test_extract_companies_from_spans_empty():
    spans = [
        {"text": "Maria", "label": "PERSON"},
    ]
    companies = _extract_companies_from_spans(spans)
    assert companies == []


