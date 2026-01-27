"""
Utility functions for AI Trend Content Creator
"""
from random import random
import re
import hashlib
from typing import List, Optional
from datetime import datetime
import httpx

class ContentValidator:
    """Validate and sanitize generated content"""
    
    @staticmethod
    def count_characters(text: str) -> int:
        """Count characters in text"""
        return len(text)
    
    @staticmethod
    def count_hashtags(text: str) -> int:
        """Count hashtags in text"""
        return len(re.findall(r'#\w+', text))
    
    @staticmethod
    def extract_hashtags(text: str) -> List[str]:
        """Extract all hashtags from text"""
        return re.findall(r'#\w+', text)
    
    @staticmethod
    def validate_length(text: str, max_length: int) -> bool:
        """Check if text is within character limit"""
        return len(text) <= max_length
    
    @staticmethod
    def sanitize_text(text: str) -> str:
        """Remove potentially problematic characters"""
        # Remove control characters
        text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    @staticmethod
    def contains_forbidden_words(text: str, forbidden_list: List[str] = None) -> bool:
        """Check for forbidden words (spam detection)"""
        if not forbidden_list:
            forbidden_list = ["spam", "click here", "buy now", "limited time"]
        
        text_lower = text.lower()
        return any(word in text_lower for word in forbidden_list)


class TrendAnalyzer:
    """Analyze and process trending topics"""
    
    @staticmethod
    def deduplicate_trends(trends: List[str]) -> List[str]:
        """Remove duplicate trends while preserving order"""
        seen = set()
        unique = []
        for trend in trends:
            trend_lower = trend.lower()
            if trend_lower not in seen:
                seen.add(trend_lower)
                unique.append(trend)
        return unique
    
    @staticmethod
    def extract_keywords(text: str, min_length: int = 3) -> List[str]:
        """Extract keywords from text"""
        # Remove special characters and split
        words = re.findall(r'\b\w+\b', text.lower())
        # Filter by length
        keywords = [w for w in words if len(w) >= min_length]
        return list(set(keywords))
    
    @staticmethod
    def calculate_trend_score(trend: str) -> float:
        """Calculate relevance score for a trend"""
        # Simple scoring based on length and keyword diversity
        score = 0.0
        
        # Length score (prefer 10-50 chars)
        length = len(trend)
        if 10 <= length <= 50:
            score += 1.0
        elif length < 10:
            score += 0.5
        
        # Keyword diversity score
        keywords = TrendAnalyzer.extract_keywords(trend)
        score += min(len(keywords) * 0.2, 1.0)
        
        return score
    
    @staticmethod
    def sort_by_relevance(trends: List[str]) -> List[str]:
        """Sort trends by relevance score"""
        scored = [(trend, TrendAnalyzer.calculate_trend_score(trend)) for trend in trends]
        sorted_trends = sorted(scored, key=lambda x: x[1], reverse=True)
        return [trend for trend, _ in sorted_trends]


class ImageHelper:
    """Helper functions for image generation and processing"""
    
    @staticmethod
    def generate_pollinations_url(prompt: str, width: int = 800, height: int = 800) -> str:
        """Generate Pollinations AI image URL"""
        from urllib.parse import quote
        import random
        from config import settings
        seed = random.randint(0, 2147483647)
        encoded_prompt = quote(prompt)
        api_key = settings.polly_api_key or "demo_key"
        return f"https://gen.pollinations.ai/image/{encoded_prompt}?width={width}&height={height}&model=flux&nologo=true&key={api_key}&seed={seed}"
    
    @staticmethod
    def generate_picsum_url(seed: str = None, width: int = 800, height: int = 800) -> str:
        """Generate Lorem Picsum random image URL"""
        if seed:
            # Use hash of seed for consistent images
            hash_value = int(hashlib.md5(seed.encode()).hexdigest(), 16) % 1000
            return f"https://picsum.photos/seed/{hash_value}/{width}/{height}"
        return f"https://picsum.photos/{width}/{height}"
    
    @staticmethod
    async def verify_image_url(url: str, timeout: int = 5) -> bool:
        """Verify if image URL is accessible"""
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.head(url)
                return response.status_code == 200
        except:
            return False


class RateLimiter:
    """Simple in-memory rate limiter"""
    
    def __init__(self):
        self.requests = {}
    
    def is_allowed(self, client_id: str, limit: int = 10, window: int = 60) -> bool:
        """Check if request is allowed within rate limit"""
        now = datetime.now().timestamp()
        
        if client_id not in self.requests:
            self.requests[client_id] = []
        
        # Remove old requests outside the time window
        self.requests[client_id] = [
            req_time for req_time in self.requests[client_id]
            if now - req_time < window
        ]
        
        # Check if limit exceeded
        if len(self.requests[client_id]) >= limit:
            return False
        
        # Add current request
        self.requests[client_id].append(now)
        return True
    
    def get_remaining(self, client_id: str, limit: int = 10) -> int:
        """Get remaining requests for client"""
        if client_id not in self.requests:
            return limit
        return max(0, limit - len(self.requests[client_id]))


class Logger:
    """Simple logging utility"""
    
    @staticmethod
    def log_request(endpoint: str, client_ip: str, params: dict):
        """Log API request"""
        timestamp = datetime.now().isoformat()
        print(f"[{timestamp}] {endpoint} - {client_ip} - {params}")
    
    @staticmethod
    def log_error(error: Exception, context: str = ""):
        """Log error"""
        timestamp = datetime.now().isoformat()
        print(f"[{timestamp}] ERROR - {context}: {str(error)}")
    
    @staticmethod
    def log_generation(topic: str, platform: str, success: bool):
        """Log content generation"""
        timestamp = datetime.now().isoformat()
        status = "SUCCESS" if success else "FAILED"
        print(f"[{timestamp}] GENERATION - {topic} ({platform}) - {status}")


# Global instances
validator = ContentValidator()
trend_analyzer = TrendAnalyzer()
image_helper = ImageHelper()
rate_limiter = RateLimiter()
logger = Logger()