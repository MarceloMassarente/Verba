"""
Test for BatchManager.check_batch() with Advanced section in rag_config.

This test validates that the fix for the Advanced section validation error works correctly.
The Advanced section is not a proper RAGComponentClass structure, so it needs to be
removed before FileConfig validation.
"""

import pytest
import json
from goldenverba.server.helpers import BatchManager
from goldenverba.server.types import FileConfig, FileStatus, DataBatchPayload, Credentials


def create_test_fileconfig_json_with_advanced():
    """Create a FileConfig JSON with Advanced section (the problematic structure)"""
    return {
        "fileID": "test_file_123",
        "filename": "test.pdf",
        "isURL": False,
        "overwrite": False,
        "extension": ".pdf",
        "source": "local",
        "content": "Test content",
        "labels": ["test"],
        "rag_config": {
            "Reader": {
                "selected": "BasicReader",
                "components": {
                    "BasicReader": {
                        "name": "BasicReader",
                        "variables": [],
                        "library": [],
                        "description": "Basic reader",
                        "config": {},
                        "type": "Reader",
                        "available": True
                    }
                }
            },
            "Chunker": {
                "selected": "TokenChunker",
                "components": {
                    "TokenChunker": {
                        "name": "TokenChunker",
                        "variables": [],
                        "library": [],
                        "description": "Token chunker",
                        "config": {},
                        "type": "Chunker",
                        "available": True
                    }
                }
            },
            "Embedder": {
                "selected": "OllamaEmbedder",
                "components": {
                    "OllamaEmbedder": {
                        "name": "OllamaEmbedder",
                        "variables": [],
                        "library": [],
                        "description": "Ollama embedder",
                        "config": {},
                        "type": "Embedder",
                        "available": True
                    }
                }
            },
            "Advanced": {
                "Enable Named Vectors": {
                    "type": "bool",
                    "value": True,
                    "description": "Enable named vectors",
                    "values": []
                }
            }
        },
        "file_size": 1000,
        "status": "READY",
        "metadata": "",
        "status_report": {}
    }


def test_batch_manager_handles_advanced_section():
    """Test that BatchManager correctly handles Advanced section in rag_config"""
    batch_manager = BatchManager()
    
    # Create test credentials
    credentials = Credentials(
        deployment="Local",
        url="http://localhost:8080",
        key="test-key"
    )
    
    # Create FileConfig JSON with Advanced section
    fileconfig_json = create_test_fileconfig_json_with_advanced()
    json_str = json.dumps(fileconfig_json)
    
    # Simulate batch chunks - split into smaller pieces
    chunk_size = 100
    chunks = []
    for i in range(0, len(json_str), chunk_size):
        chunk = json_str[i:i + chunk_size]
        chunks.append(chunk)
    
    total_chunks = len(chunks)
    fileID = fileconfig_json["fileID"]
    
    # Add all chunks to batch manager
    for order, chunk in enumerate(chunks):
        payload = DataBatchPayload(
            fileID=fileID,
            chunk=chunk,
            order=order,
            total=total_chunks,
            isLastChunk=(order == total_chunks - 1),
            credentials=credentials
        )
        result = batch_manager.add_batch(payload)
        
        # On last chunk, should return FileConfig
        if order == total_chunks - 1:
            assert result is not None, "FileConfig should be returned on last chunk"
            assert isinstance(result, FileConfig), "Result should be FileConfig instance"
            assert result.fileID == fileID, "FileConfig should have correct fileID"
            assert result.filename == fileconfig_json["filename"], "FileConfig should have correct filename"
            # Advanced section should NOT be in rag_config anymore
            assert "Advanced" not in result.rag_config, "Advanced section should be removed from rag_config"
            # But normal components should still be there
            assert "Reader" in result.rag_config, "Reader should still be in rag_config"
            assert "Chunker" in result.rag_config, "Chunker should still be in rag_config"
            assert "Embedder" in result.rag_config, "Embedder should still be in rag_config"


def test_batch_manager_without_advanced_section():
    """Test that BatchManager still works correctly without Advanced section"""
    batch_manager = BatchManager()
    
    # Create test credentials
    credentials = Credentials(
        deployment="Local",
        url="http://localhost:8080",
        key="test-key"
    )
    
    # Create FileConfig JSON WITHOUT Advanced section
    fileconfig_json = create_test_fileconfig_json_with_advanced()
    # Remove Advanced section
    del fileconfig_json["rag_config"]["Advanced"]
    
    json_str = json.dumps(fileconfig_json)
    
    # Simulate batch chunks
    chunk_size = 100
    chunks = []
    for i in range(0, len(json_str), chunk_size):
        chunk = json_str[i:i + chunk_size]
        chunks.append(chunk)
    
    total_chunks = len(chunks)
    fileID = fileconfig_json["fileID"]
    
    # Add all chunks to batch manager
    for order, chunk in enumerate(chunks):
        payload = DataBatchPayload(
            fileID=fileID,
            chunk=chunk,
            order=order,
            total=total_chunks,
            isLastChunk=(order == total_chunks - 1),
            credentials=credentials
        )
        result = batch_manager.add_batch(payload)
        
        # On last chunk, should return FileConfig
        if order == total_chunks - 1:
            assert result is not None, "FileConfig should be returned on last chunk"
            assert isinstance(result, FileConfig), "Result should be FileConfig instance"
            assert result.fileID == fileID, "FileConfig should have correct fileID"
            assert "Advanced" not in result.rag_config, "Advanced section should not be present"


def test_fileconfig_validation_fails_with_advanced():
    """Test that FileConfig validation fails when Advanced section is present (before fix)"""
    fileconfig_json = create_test_fileconfig_json_with_advanced()
    
    # Direct validation should fail (this is what we're fixing)
    with pytest.raises(Exception):  # Should raise ValidationError
        FileConfig.model_validate(fileconfig_json)


def test_fileconfig_validation_succeeds_without_advanced():
    """Test that FileConfig validation succeeds when Advanced section is removed"""
    fileconfig_json = create_test_fileconfig_json_with_advanced()
    # Remove Advanced section
    del fileconfig_json["rag_config"]["Advanced"]
    
    # Direct validation should succeed
    file_config = FileConfig.model_validate(fileconfig_json)
    assert file_config is not None
    assert file_config.fileID == "test_file_123"
    assert "Advanced" not in file_config.rag_config

