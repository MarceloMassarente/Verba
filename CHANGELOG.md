# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.5] - 2026-01-04
> Commits: (Current Release)

## [2.1.6] - 2026-01-04

### Added
- **E5 Robustness**: Implemented automatic prefix enforcement for E5 models (`query:`/`passage:`).
    - **Configuration**: New boolean flag `Enforce E5 Prefixes` in `HybridConsultingEmbedder` (default: True).
    - **Automation**: Automatically prepends `query:` to queries and `passage:` to document chunks when using E5 models.
    - **Rationale**: Aligns with model training objectives to prevent performance degradation in "messy" scenarios.
    - **Audit**: Verified via ranking classification audit (improved hard-negative separation by +0.0011).
- **Safety**: Added explicit compatibility tests to ensure legacy models (e.g., `paraphrase-multilingual`) are unaffected by these changes.

### Fixed
- **PDF Ingestion**: Fixed crash when ingesting PDF files locally (without Docling/Visual API)
  - Added `pypdf` support in `UnifiedConsultingIngestor` for local PDF extraction
  - Fixed `Document` class instantiation using invalid arguments (`text=`, `type=`)
  - Fixed `msg.debug` call that was failing (method doesn't exist)
- **PPTX Grouped Shapes**: Fixed text extraction from grouped shapes and tables in PPTX files
  - Implemented recursive `_get_shape_text` function to handle nested shapes
  - Added table text extraction logic
- **PPTX Chunking**: Fixed critical issue where files resulted in 0 chunks
  - **Fixed Regex**: Relaxed anchors in `UnifiedConsultingIngestor` to handle Windows EOL (`\r\n`) and dash variations (`-`, `–`, `—`)
  - **Fixed Config Bug**: Corrected `SlidesSemanticaVisualChunker` causing `AttributeError` by properly propagating user config instead of static defaults
  - **Robustness**: Added fallback parser strategy using `---` separator to guarantee chunk generation if regex fails

### Added
- **New Embedding Model**: `intfloat/multilingual-e5-small` now available as embedding option
  - Added to `SentenceTransformersEmbedder` dropdown for general use
  - **New Default** for named vectors in `HybridConsultingEmbedder`
  - Performance in Micro-Benchmark (15 chunks/14 queries):
    - **Quality**: Statistical tie in Recall@3 (92.9%) and MRR (0.875)
    - **Ranking**: Nonsignificant advantage in nDCG@3 (+0.022)
    - **Qualitative**: Better semantic handling of indirect concepts
  - 100 language support (vs 50 in previous model)
  - Configuration option to switch between e5-small and legacy paraphrase-multilingual
- **Benchmark Tool**: Added `test_retrieval_benchmark.py` for comparative analysis (removed after use)

### Changed
- `HybridConsultingEmbedder` now uses configurable model for named vectors (concept_vec, company_vec, sector_vec)
  - Default changed from `paraphrase-multilingual-MiniLM-L12-v2` to `intfloat/multilingual-e5-small`
  - Backward compatible: can revert to legacy model via configuration
- `UnifiedConsultingIngestor` now properly falls back to `pypdf` for PDF files when Docling is not available

### Performance Improvements
- **Multilingual Semantics**: E5-Small selected for superior global MTEB performance (63.8% vs 53%)
- **Multilingual Coverage**: 100 languages vs 50 previously supported

### Trade-offs
- Initial model load time increased: 22.92s vs 3.83s (one-time startup cost)
- Latency: E5-Small is ~10% slower per query (5.8ms vs 5.3ms) in rigorous testing

## [2.1.4] - 2025-12-XX
> Commits: a9aa67b, 7773d42, 09b5631, afc34da

### Added
- Initial release of Consulting RAG extensions
- Entity-Aware Retriever with semantic search
- Unified Consulting Ingestor with Visual API support
- Slides Semantica Visual Chunker
- Framework detection (GLiNER/Regex)
- Stakeholder detection via spaCy NER

## [2.1.0] - 2025-XX-XX

### Added
- Base Verba functionality
- Weaviate integration
- Multiple reader/chunker/embedder support
