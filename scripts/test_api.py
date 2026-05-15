"""
Quick script to test the Recall API
"""
import requests
import sys
from pathlib import Path

API_BASE = "http://localhost:8000"


def test_health():
    """Test if API is running"""
    print("Testing health endpoint...")
    response = requests.get(f"{API_BASE}/health")
    if response.status_code == 200:
        print("✅ API is healthy")
        return True
    else:
        print("❌ API is not responding")
        return False


def upload_test_document():
    """Upload a test document"""
    print("\nUploading test document...")

    # Create a simple test file
    test_content = """
    This is a test document about machine learning and artificial intelligence.

    Machine learning is a subset of artificial intelligence that focuses on
    teaching computers to learn from data. Neural networks are a key technology
    in modern machine learning, inspired by the human brain.

    Deep learning uses multiple layers of neural networks to process information
    in increasingly abstract ways. This has led to breakthroughs in areas like
    computer vision and natural language processing.
    """

    test_file = Path("/tmp/test_document.txt")
    test_file.write_text(test_content)

    with open(test_file, "rb") as f:
        response = requests.post(
            f"{API_BASE}/api/ingest/upload",
            files={"file": ("test_document.txt", f, "text/plain")}
        )

    if response.status_code == 200:
        data = response.json()
        print(f"✅ Document uploaded: {data['document_id']}")
        print(f"   Chunks created: {data['num_chunks']}")
        return data['document_id']
    else:
        print(f"❌ Upload failed: {response.text}")
        return None


def test_search():
    """Test semantic search"""
    print("\nTesting search...")
    response = requests.get(
        f"{API_BASE}/api/search",
        params={"query": "neural networks", "limit": 3}
    )

    if response.status_code == 200:
        data = response.json()
        print(f"✅ Search returned {data['count']} results")
        for idx, result in enumerate(data['results'], 1):
            print(f"\n   Result {idx}:")
            print(f"   Score: {result['score']:.3f}")
            print(f"   Content: {result['content'][:100]}...")
        return True
    else:
        print(f"❌ Search failed: {response.text}")
        return False


def test_chat():
    """Test RAG chat"""
    print("\nTesting chat...")
    response = requests.post(
        f"{API_BASE}/api/chat",
        json={
            "message": "What is deep learning?",
            "num_context_chunks": 3
        }
    )

    if response.status_code == 200:
        data = response.json()
        print("✅ Chat response received")
        print(f"\n{data['response']}")
        return True
    else:
        print(f"❌ Chat failed: {response.text}")
        return False


def list_documents():
    """List all documents"""
    print("\nListing documents...")
    response = requests.get(f"{API_BASE}/api/ingest/documents")

    if response.status_code == 200:
        docs = response.json()
        print(f"✅ Found {len(docs)} documents")
        for doc in docs:
            print(f"   - {doc['title']} ({doc['num_chunks']} chunks)")
        return True
    else:
        print(f"❌ Failed to list documents: {response.text}")
        return False


def main():
    print("=" * 60)
    print("Recall API Test Suite")
    print("=" * 60)

    # Test health
    if not test_health():
        print("\n❌ API is not running. Start it with: docker-compose up")
        sys.exit(1)

    # Upload test document
    doc_id = upload_test_document()
    if not doc_id:
        print("\n❌ Failed to upload document")
        sys.exit(1)

    # Wait a moment for indexing
    import time
    time.sleep(2)

    # Test search
    test_search()

    # Test chat
    test_chat()

    # List all documents
    list_documents()

    print("\n" + "=" * 60)
    print("✅ All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
