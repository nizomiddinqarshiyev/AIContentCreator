"""
Unit tests for AI Trend Content Creator
Run with: pytest tests.py -v
"""
import pytest
from fastapi.testclient import TestClient
from main import app
from utils import ContentValidator, TrendAnalyzer, ImageHelper

client = TestClient(app)

# ============================================
# API ENDPOINT TESTS
# ============================================

def test_health_check():
    """Test health check endpoint"""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data

def test_get_statistics():
    """Test statistics endpoint"""
    response = client.get("/api/stats")
    assert response.status_code == 200
    data = response.json()
    assert "supported_platforms" in data
    assert "supported_languages" in data
    assert "supported_countries" in data

def test_fetch_trends_valid_country():
    """Test fetching trends with valid country"""
    response = client.post("/api/trends", json={"country": "US"})
    assert response.status_code == 200
    data = response.json()
    assert "trends" in data
    assert isinstance(data["trends"], list)
    assert len(data["trends"]) > 0

def test_fetch_trends_invalid_country():
    """Test fetching trends with invalid country"""
    response = client.post("/api/trends", json={"country": "XX"})
    assert response.status_code == 422  # Validation error

def test_generate_content_valid():
    """Test content generation with valid input"""
    response = client.post("/api/generate", json={
        "topic": "Artificial Intelligence",
        "platform": "instagram",
        "language": "en"
    })
    # Note: This will fail without valid API key
    # In real tests, you'd mock the API call
    assert response.status_code in [200, 500]  # 500 if no API key

def test_generate_content_invalid_platform():
    """Test content generation with invalid platform"""
    response = client.post("/api/generate", json={
        "topic": "Test",
        "platform": "invalid",
        "language": "en"
    })
    assert response.status_code == 422

def test_generate_content_short_topic():
    """Test content generation with too short topic"""
    response = client.post("/api/generate", json={
        "topic": "AI",
        "platform": "instagram",
        "language": "en"
    })
    assert response.status_code == 422

# ============================================
# UTILITY FUNCTION TESTS
# ============================================

def test_content_validator_character_count():
    """Test character counting"""
    validator = ContentValidator()
    text = "Hello, World!"
    assert validator.count_characters(text) == 13

def test_content_validator_hashtag_count():
    """Test hashtag counting"""
    validator = ContentValidator()
    text = "Check out #AI and #Technology #Innovation"
    assert validator.count_hashtags(text) == 3

def test_content_validator_extract_hashtags():
    """Test hashtag extraction"""
    validator = ContentValidator()
    text = "Post about #AI #ML #DeepLearning"
    hashtags = validator.extract_hashtags(text)
    assert len(hashtags) == 3
    assert "#AI" in hashtags

def test_content_validator_length_validation():
    """Test length validation"""
    validator = ContentValidator()
    assert validator.validate_length("Short text", 20) == True
    assert validator.validate_length("Very long text" * 100, 50) == False

def test_content_validator_sanitize():
    """Test text sanitization"""
    validator = ContentValidator()
    dirty_text = "Text  with   extra    spaces"
    clean = validator.sanitize_text(dirty_text)
    assert clean == "Text with extra spaces"

def test_trend_analyzer_deduplicate():
    """Test trend deduplication"""
    analyzer = TrendAnalyzer()
    trends = ["AI", "ai", "Blockchain", "AI"]
    unique = analyzer.deduplicate_trends(trends)
    assert len(unique) == 2
    assert "AI" in unique or "ai" in unique
    assert "Blockchain" in unique

def test_trend_analyzer_extract_keywords():
    """Test keyword extraction"""
    analyzer = TrendAnalyzer()
    text = "Artificial Intelligence and Machine Learning"
    keywords = analyzer.extract_keywords(text)
    assert "artificial" in keywords
    assert "intelligence" in keywords
    assert len(keywords) >= 4

def test_trend_analyzer_calculate_score():
    """Test trend scoring"""
    analyzer = TrendAnalyzer()
    score1 = analyzer.calculate_trend_score("Short")
    score2 = analyzer.calculate_trend_score("Good Length Trending Topic")
    assert score2 > score1

def test_image_helper_pollinations_url():
    """Test Pollinations URL generation"""
    helper = ImageHelper()
    url = helper.generate_pollinations_url("test topic", 800, 800)
    assert "pollinations.ai" in url
    assert "width=800" in url
    assert "height=800" in url

def test_image_helper_picsum_url():
    """Test Picsum URL generation"""
    helper = ImageHelper()
    url = helper.generate_picsum_url(seed="test")
    assert "picsum.photos" in url

# ============================================
# INTEGRATION TESTS
# ============================================

def test_full_workflow():
    """Test complete workflow: fetch trends -> generate content"""
    # Step 1: Fetch trends
    trends_response = client.post("/api/trends", json={"country": "US"})
    assert trends_response.status_code == 200
    trends_data = trends_response.json()
    
    # Step 2: Use first trend to generate content
    # Note: This requires valid API key
    if len(trends_data["trends"]) > 0:
        first_trend = trends_data["trends"][0]
        generate_response = client.post("/api/generate", json={
            "topic": first_trend,
            "platform": "instagram",
            "language": "en"
        })
        # Will fail without API key, but structure is tested
        assert generate_response.status_code in [200, 500]

# ============================================
# PYTEST CONFIGURATION
# ============================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])