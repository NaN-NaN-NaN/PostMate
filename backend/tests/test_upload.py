"""
Test upload endpoints
"""

import pytest
import io
from PIL import Image


def create_test_image():
    """Create a simple test image in memory"""
    img = Image.new('RGB', (100, 100), color='white')
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='JPEG')
    img_bytes.seek(0)
    return img_bytes


def test_health_check(client):
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data


def test_root_endpoint(client):
    """Test root endpoint"""
    response = client.get("/")
    assert response.status_code == 200

    data = response.json()
    assert data["service"] == "PostMate API"
    assert data["docs"] == "/docs"


def test_upload_single_image(client):
    """Test uploading a single image"""
    # Create test image
    test_image = create_test_image()

    # Upload
    response = client.post(
        "/api/v1/upload",
        files={"files": ("test.jpg", test_image, "image/jpeg")}
    )

    assert response.status_code == 201

    data = response.json()
    assert "document_id" in data
    assert data["status"] == "uploaded"
    assert data["uploaded_files"] == 1
    assert data["document_id"].startswith("doc_")


def test_upload_multiple_images(client):
    """Test uploading multiple images"""
    # Create test images
    test_images = [
        ("test1.jpg", create_test_image(), "image/jpeg"),
        ("test2.jpg", create_test_image(), "image/jpeg"),
    ]

    # Upload
    response = client.post(
        "/api/v1/upload",
        files=[("files", img) for img in test_images]
    )

    assert response.status_code == 201

    data = response.json()
    assert data["uploaded_files"] == 2


def test_upload_no_files(client):
    """Test upload with no files"""
    response = client.post("/api/v1/upload", files={})

    assert response.status_code == 422  # Validation error


def test_upload_invalid_format(client):
    """Test upload with invalid file format"""
    # Create a text file
    text_file = io.BytesIO(b"Not an image")

    response = client.post(
        "/api/v1/upload",
        files={"files": ("test.txt", text_file, "text/plain")}
    )

    # Should fail validation
    assert response.status_code == 400


def test_get_document_status_not_found(client):
    """Test getting status for non-existent document"""
    response = client.get("/api/v1/documents/invalid_id/status")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
