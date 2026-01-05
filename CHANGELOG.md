# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.5] - 2026-01-04
> Commits: (Current Release)

### Fixed
- **PDF Ingestion**: Fixed crash when ingesting PDF files locally (without Docling/Visual API)
  - Added `pypdf` support in `UnifiedConsultingIngestor` for local PDF extraction
  - Fixed `Document` class instantiation using invalid arguments (`text=`, `type=`)
  - Fixed `msg.debug` call that was failing (method doesn't exist)
- **PPTX Grouped Shapes**: Fixed text extraction from grouped shapes and tables in PPTX files
  - Implemented recursive `_get_shape_text` function to handle nested shapes
  - Added table text extraction logic

### Changed
- `UnifiedConsultingIngestor` now properly falls back to `pypdf` for PDF files when Docling is not available

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
