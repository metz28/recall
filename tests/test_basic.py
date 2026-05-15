"""
Basic tests for the API
"""
import pytest
from fastapi.testclient import TestClient
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from main import app

client = TestClient(app)


def test_root():
    """Test root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "running"


def test_health():
    """Test health check"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_search_without_documents():
    """Test search with no documents"""
    response = client.get("/api/search?query=test")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 0


def test_list_documents_empty():
    """Test listing documents when none exist"""
    response = client.get("/api/ingest/documents")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
