"""
Configuration management for AI Trend Content Creator
Supports environment variables and .env files
"""
import os
from typing import Dict, List
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Application settings with environment variable support"""
    
    # API Keys
    groq_api_key: str = "YOUR_GROQ_API_KEY"
    unsplash_access_key: str = ""
    pexels_api_key: str = ""
    polly_api_key: str = ""
    
    # Application Settings
    app_name: str = "AI Trend Content Creator"
    app_version: str = "1.0.0"
    debug: bool = True
    
    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    
    # AI Model Settings
    ai_model: str = "llama-3.1-8b-instant"
    max_tokens: int = 300
    temperature: float = 0.8
    timeout: int = 30
    
    # Content Generation Limits
    max_trends: int = 5
    instagram_max_chars: int = 150
    telegram_max_chars: int = 200
    twitter_max_chars: int = 280
    
    # Rate Limiting
    rate_limit_enabled: bool = False
    requests_per_minute: int = 10
    
    # Supported Platforms and Languages
    supported_platforms: List[str] = ["instagram", "telegram", "twitter"]
    supported_languages: List[str] = ["en", "uz", "ru"]
    supported_countries: List[str] = ["US", "GB", "UZ", "RU", "TR"]
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

# Platform-specific configurations
PLATFORM_CONFIG: Dict[str, Dict] = {
    "instagram": {
        "max_chars": 150,
        "hashtag_count": "3-5",
        "emojis": True,
        "format": "casual"
    },
    "telegram": {
        "max_chars": 200,
        "hashtag_count": "0-2",
        "emojis": True,
        "format": "informative"
    },
    "twitter": {
        "max_chars": 280,
        "hashtag_count": "2-3",
        "emojis": False,
        "format": "punchy"
    }
}

# Country configurations
COUNTRY_CONFIG: Dict[str, Dict] = {
    "US": {
        "name": "United States",
        "flag": "🇺🇸",
        "locale": "en-US",
        "timezone": "America/New_York"
    },
    "GB": {
        "name": "United Kingdom",
        "flag": "🇬🇧",
        "locale": "en-GB",
        "timezone": "Europe/London"
    },
    "UZ": {
        "name": "Uzbekistan",
        "flag": "🇺🇿",
        "locale": "ru-UZ",
        "timezone": "Asia/Tashkent"
    },
    "RU": {
        "name": "Russia",
        "flag": "🇷🇺",
        "locale": "ru-RU",
        "timezone": "Europe/Moscow"
    },
    "TR": {
        "name": "Turkey",
        "flag": "🇹🇷",
        "locale": "tr-TR",
        "timezone": "Europe/Istanbul"
    }
}

# AI Prompt templates
PROMPT_TEMPLATES: Dict[str, Dict[str, str]] = {
    "instagram": {
        "en": "Create an engaging Instagram post about '{topic}'. Include emojis and {hashtag_count} relevant hashtags. Maximum {max_chars} characters. Be creative and catchy!",
        "uz": "'{topic}' haqida qiziqarli Instagram post yozing. Emojilar va {hashtag_count} ta hashtag qo'shing. Maksimum {max_chars} belgi. Ijodiy yozing!",
        "ru": "Создайте интересный пост для Instagram о '{topic}'. Добавьте эмодзи и {hashtag_count} хэштегов. Максимум {max_chars} символов. Будьте креативны!"
    },
    "telegram": {
        "en": "Write a concise Telegram message about '{topic}'. Maximum {max_chars} characters. Clear and informative. {hashtag_count} hashtags if relevant.",
        "uz": "'{topic}' haqida qisqa Telegram xabari yozing. Maksimum {max_chars} belgi. Aniq va ma'lumotli bo'lsin.",
        "ru": "Напишите краткое сообщение для Telegram о '{topic}'. Максимум {max_chars} символов. Четко и информативно."
    },
    "twitter": {
        "en": "Create a viral tweet about '{topic}'. Maximum {max_chars} characters. Include {hashtag_count} hashtags. Be punchy and engaging!",
        "uz": "'{topic}' haqida viral tweet yozing. Maksimum {max_chars} belgi. {hashtag_count} ta hashtag qo'shing. Qisqa va ta'sirchan!",
        "ru": "Создайте вирусный твит о '{topic}'. Максимум {max_chars} символов. Добавьте {hashtag_count} хэштега. Кратко и эффектно!"
    }
}

# System prompts for different content types
SYSTEM_PROMPTS: Dict[str, str] = {
    "creative": "You are a creative social media content creator. Output only the final post text, no explanations. Be engaging and authentic.",
    "professional": "You are a professional content strategist. Create polished, brand-safe content. Output only the final text.",
    "viral": "You are a viral content specialist. Create attention-grabbing posts that encourage engagement. Output only the final text.",
    "educational": "You are an educational content creator. Make complex topics accessible and interesting. Output only the final text."
}

# Initialize settings
settings = Settings()

def get_prompt_template(platform: str, language: str, topic: str) -> str:
    """Generate formatted prompt for content generation"""
    template = PROMPT_TEMPLATES[platform][language]
    config = PLATFORM_CONFIG[platform]
    
    return template.format(
        topic=topic,
        max_chars=config["max_chars"],
        hashtag_count=config["hashtag_count"]
    )

def get_system_prompt(content_type: str = "creative") -> str:
    """Get system prompt for AI model"""
    return SYSTEM_PROMPTS.get(content_type, SYSTEM_PROMPTS["creative"])