"""
Manual E2E test script for entity extraction

This script tests the entity extraction functionality by:
1. Uploading a sample document
2. Listing extracted entities
3. Getting entity details
4. Querying chunks mentioning an entity
"""
import requests
import json
import sys
from pathlib import Path

# Configuration
BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api"


def print_section(title):
    """Print a section header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def test_health():
    """Test that API is running"""
    print_section("Testing API Health")

    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        response.raise_for_status()
        print("✅ API is healthy")
        return True
    except Exception as e:
        print(f"❌ API health check failed: {e}")
        print("\nPlease start the API server:")
        print("  python local/recall.py run")
        return False


def upload_sample_document():
    """Upload a sample document for testing"""
    print_section("Uploading Sample Document")

    # Create sample content with known entities
    sample_content = """
    Artificial Intelligence in Modern Technology

    Introduction

    Apple Inc., Google, and Microsoft are leading technology companies investing
    heavily in artificial intelligence and machine learning. These companies are
    based in the United States, with headquarters in California and Washington.

    Key Companies

    Apple Inc. is known for its consumer electronics and Siri voice assistant.
    Google, a subsidiary of Alphabet Inc., has developed TensorFlow and BERT.
    Microsoft has created Azure AI services and invested in OpenAI.

    Research Leaders

    Geoffrey Hinton, often called the "Godfather of AI", worked at Google.
    Yann LeCun is the Chief AI Scientist at Meta (formerly Facebook).
    Andrew Ng founded Google Brain and later Coursera.

    Technologies

    Popular frameworks include TensorFlow, PyTorch, and scikit-learn.
    Natural Language Processing has been revolutionized by BERT, GPT, and DALL-E.
    Computer vision applications use YOLO and Mask R-CNN.

    Applications

    AI is used in healthcare, finance, autonomous vehicles, and robotics.
    Companies like Amazon, IBM, and Tesla are developing AI solutions.
    Research institutions like MIT, Stanford, and Carnegie Mellon lead in AI education.

    Conclusion

    The field continues to grow with contributions from Silicon Valley and beyond.
    """

    # Save to temporary file
    temp_dir = Path("./data/uploads")
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_file = temp_dir / "test_ai_document.txt"

    with open(temp_file, "w") as f:
        f.write(sample_content)

    # Upload via API
    try:
        with open(temp_file, "rb") as f:
            files = {"file": ("ai_document.txt", f, "text/plain")}
            response = requests.post(f"{API_BASE}/ingest/upload", files=files)
            response.raise_for_status()

        data = response.json()
        print(f"✅ Document uploaded successfully")
        print(f"   Document ID: {data['document_id']}")
        print(f"   Title: {data['title']}")
        print(f"   Chunks: {data['num_chunks']}")

        if "num_entities" in data:
            print(f"   Entities: {data['num_entities']}")
            print(f"   Entity Mentions: {data['num_entity_mentions']}")
        else:
            print("   ⚠️  Entity extraction may not be enabled")

        return data["document_id"]

    except Exception as e:
        print(f"❌ Upload failed: {e}")
        if hasattr(e, 'response'):
            print(f"   Response: {e.response.text}")
        return None


def list_entities():
    """List all extracted entities"""
    print_section("Listing Extracted Entities")

    try:
        response = requests.get(f"{API_BASE}/entities?limit=20")
        response.raise_for_status()
        data = response.json()

        print(f"Total entities found: {data['total']}")

        if data["entities"]:
            print("\nTop entities (by mention count):\n")
            print(f"{'Name':<30} {'Type':<15} {'Mentions':<10}")
            print("-" * 60)

            for entity in data["entities"][:15]:
                name = entity["name"][:28]
                entity_type = entity["entity_type"]
                mentions = entity["mention_count"]
                print(f"{name:<30} {entity_type:<15} {mentions:<10}")

            return data["entities"]
        else:
            print("⚠️  No entities found")
            return []

    except Exception as e:
        print(f"❌ Failed to list entities: {e}")
        return []


def test_entity_filtering():
    """Test entity filtering by type"""
    print_section("Testing Entity Filters")

    # Test filtering by organization
    try:
        response = requests.get(f"{API_BASE}/entities?entity_type=ORG&limit=10")
        response.raise_for_status()
        data = response.json()

        print(f"Organizations found: {data['total']}")
        if data["entities"]:
            print("\nOrganizations:")
            for entity in data["entities"][:5]:
                print(f"  - {entity['name']} (mentioned {entity['mention_count']} times)")

    except Exception as e:
        print(f"❌ ORG filter failed: {e}")

    # Test filtering by person
    try:
        response = requests.get(f"{API_BASE}/entities?entity_type=PERSON&limit=10")
        response.raise_for_status()
        data = response.json()

        print(f"\nPersons found: {data['total']}")
        if data["entities"]:
            print("\nPersons:")
            for entity in data["entities"][:5]:
                print(f"  - {entity['name']} (mentioned {entity['mention_count']} times)")

    except Exception as e:
        print(f"❌ PERSON filter failed: {e}")

    # Test filtering by location
    try:
        response = requests.get(f"{API_BASE}/entities?entity_type=GPE&limit=10")
        response.raise_for_status()
        data = response.json()

        print(f"\nLocations found: {data['total']}")
        if data["entities"]:
            print("\nLocations:")
            for entity in data["entities"][:5]:
                print(f"  - {entity['name']} (mentioned {entity['mention_count']} times)")

    except Exception as e:
        print(f"❌ GPE filter failed: {e}")


def test_entity_details(entities):
    """Test getting entity details"""
    print_section("Testing Entity Details")

    if not entities:
        print("⚠️  No entities to test")
        return

    # Get details for first entity
    entity = entities[0]
    entity_id = entity["id"]

    try:
        response = requests.get(f"{API_BASE}/entities/{entity_id}")
        response.raise_for_status()
        data = response.json()

        print(f"Entity: {data['name']}")
        print(f"Type: {data['entity_type']}")
        print(f"Mention count: {data['mention_count']}")

        if data.get('variants'):
            print(f"Variants: {', '.join(data['variants'][:5])}")

        print(f"\nMentions: {len(data['mentions'])}")
        if data["mentions"]:
            print("\nFirst few mentions:")
            for mention in data["mentions"][:3]:
                doc_title = mention['document_title']
                chunk_idx = mention['chunk_index']
                context = mention['context'][:100]
                print(f"  - {doc_title} (chunk {chunk_idx})")
                print(f"    Context: {context}...")

    except Exception as e:
        print(f"❌ Failed to get entity details: {e}")


def test_entity_chunks(entities):
    """Test getting chunks for an entity"""
    print_section("Testing Entity Chunks")

    if not entities:
        print("⚠️  No entities to test")
        return

    # Get chunks for first entity
    entity = entities[0]
    entity_id = entity["id"]

    try:
        response = requests.get(f"{API_BASE}/entities/{entity_id}/chunks?limit=5")
        response.raise_for_status()
        data = response.json()

        print(f"Entity: {data['entity']['name']} ({data['entity']['type']})")
        print(f"Total chunks: {data['total']}")

        if data["chunks"]:
            print("\nChunks mentioning this entity:\n")
            for i, chunk in enumerate(data["chunks"], 1):
                print(f"Chunk {i}:")
                print(f"  Document: {chunk['document_title']}")
                print(f"  Content: {chunk['content'][:150]}...")
                if chunk.get('context'):
                    print(f"  Context: {chunk['context'][:100]}...")
                print()

    except Exception as e:
        print(f"❌ Failed to get entity chunks: {e}")


def test_types_summary():
    """Test entity types summary"""
    print_section("Testing Entity Types Summary")

    try:
        response = requests.get(f"{API_BASE}/entities/types/summary")
        response.raise_for_status()
        data = response.json()

        print("Entity types distribution:\n")
        print(f"{'Type':<15} {'Count':<10} {'Total Mentions':<15}")
        print("-" * 45)

        for type_info in data["types"]:
            entity_type = type_info["entity_type"]
            count = type_info["count"]
            mentions = type_info["total_mentions"]
            print(f"{entity_type:<15} {count:<10} {mentions:<15}")

    except Exception as e:
        print(f"❌ Failed to get types summary: {e}")


def main():
    """Run all tests"""
    print("\n" + "=" * 80)
    print("  Entity Extraction E2E Test")
    print("=" * 80)

    # Check API health
    if not test_health():
        sys.exit(1)

    # Upload document
    doc_id = upload_sample_document()
    if not doc_id:
        print("\n⚠️  Upload failed, cannot continue tests")
        sys.exit(1)

    # List entities
    entities = list_entities()

    # Test filtering
    test_entity_filtering()

    # Test entity details
    if entities:
        test_entity_details(entities)

    # Test entity chunks
    if entities:
        test_entity_chunks(entities)

    # Test types summary
    test_types_summary()

    # Summary
    print_section("Test Summary")
    if entities:
        print("✅ All tests completed successfully!")
        print(f"   Found {len(entities)} entities in the uploaded document")
    else:
        print("⚠️  Tests completed but no entities were extracted")
        print("   This might indicate:")
        print("   1. Entity extraction is disabled in config")
        print("   2. spaCy model is not installed")
        print("   3. The document has no recognizable entities")

    print("\nNext steps:")
    print("  - Run unit tests: pytest tests/test_entity_extraction.py -v")
    print("  - Run integration tests: pytest tests/test_entities_api.py -v")
    print("  - Check entities in database: sqlite3 data/recall.db 'SELECT * FROM entities LIMIT 10;'")
    print()


if __name__ == "__main__":
    main()
