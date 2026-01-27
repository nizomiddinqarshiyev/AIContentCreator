from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
from typing import List, Literal, Optional
import httpx
import feedparser
from datetime import datetime

# Import our modules
from config import settings, get_prompt_template, get_system_prompt, COUNTRY_CONFIG
from utils import validator as content_validator, trend_analyzer, image_helper, rate_limiter, logger

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI-powered social media content generator from trending topics"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================
# DATA MODELS
# ============================================

class TrendRequest(BaseModel):
    country: str = Field(default="US", description="Country code (US, GB, UZ, RU, TR)")
    
    @validator('country')
    def validate_country(cls, v):
        if v not in settings.supported_countries:
            raise ValueError(f"Country must be one of: {settings.supported_countries}")
        return v.upper()

class ContentRequest(BaseModel):
    topic: str = Field(..., min_length=3, max_length=200, description="Topic to generate content about")
    platform: Literal["instagram", "telegram", "twitter"] = Field(..., description="Social media platform")
    language: Literal["en", "uz", "ru"] = Field(default="en", description="Content language")
    style: Optional[Literal["creative", "professional", "viral", "educational"]] = Field(
        default="creative", 
        description="Content style"
    )

class TrendResponse(BaseModel):
    trends: List[str]
    country: str
    country_info: dict
    timestamp: str

class ContentResponse(BaseModel):
    topic: str
    platform: str
    language: str
    style: str
    content: str
    image_url: str
    metadata: dict
    timestamp: str

class HealthResponse(BaseModel):
    status: str
    version: str
    uptime: str
    endpoints: List[str]

# ============================================
# STARTUP & SHUTDOWN
# ============================================

startup_time = datetime.now()

@app.on_event("startup")
async def startup_event():
    """Initialize application"""
    logger.log_request("STARTUP", "system", {"version": settings.app_version})
    print(f"🚀 {settings.app_name} v{settings.app_version} started")
    print(f"📡 Server running on {settings.host}:{settings.port}")
    print(f"🔧 Debug mode: {settings.debug}")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.log_request("SHUTDOWN", "system", {})
    print("👋 Application shutting down...")

# ============================================
# MIDDLEWARE
# ============================================

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests"""
    start_time = datetime.now()
    
    # Process request
    response = await call_next(request)
    
    # Calculate processing time
    process_time = (datetime.now() - start_time).total_seconds()
    response.headers["X-Process-Time"] = str(process_time)
    
    return response

# ============================================
# FRONTEND
# ============================================

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the frontend page"""
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Frontend not found. Please add index.html</h1>", status_code=404)

# ============================================
# API ENDPOINTS
# ============================================

@app.post("/api/trends", response_model=TrendResponse)
async def get_trending_topics(request: TrendRequest, client_request: Request):
    """
    Fetch top trending topics for a given country
    
    - **country**: Country code (US, GB, UZ, RU, TR)
    
    Returns list of trending topics with metadata
    """
    client_ip = client_request.client.host
    logger.log_request("/api/trends", client_ip, {"country": request.country})
    
    # Rate limiting
    if settings.rate_limit_enabled:
        if not rate_limiter.is_allowed(client_ip, settings.requests_per_minute):
            raise HTTPException(status_code=429, detail="Rate limit exceeded. Please try again later.")
    
    try:
        # Get country configuration
        country_info = COUNTRY_CONFIG.get(request.country, {})
        locale = country_info.get("locale", "en-US")
        
        # Fetch from Google News RSS
        rss_url = f"https://news.google.com/rss?hl={locale}&gl={request.country}&ceid={request.country}:{locale.split('-')[0]}"
        feed = feedparser.parse(rss_url)
        
        # Extract and process trends
        raw_trends = []
        for entry in feed.entries[:20]:
            topic = entry.title.split(' - ')[0].strip()
            if len(topic) > 10 and topic not in raw_trends:
                raw_trends.append(topic)
        
        # Deduplicate and sort by relevance
        trends = trend_analyzer.deduplicate_trends(raw_trends)
        trends = trend_analyzer.sort_by_relevance(trends)
        trends = trends[:settings.max_trends]
        
        # Fallback if no trends found
        if not trends:
            trends = [
                "Artificial Intelligence Revolution",
                "Climate Change Solutions",
                "Space Exploration Advances",
                "Electric Vehicle Innovation",
                "Quantum Computing Breakthrough"
            ]
        
        return TrendResponse(
            trends=trends,
            country=request.country,
            country_info=country_info,
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        logger.log_error(e, "get_trending_topics")
        raise HTTPException(status_code=500, detail=f"Failed to fetch trends: {str(e)}")


@app.post("/api/generate", response_model=ContentResponse)
async def generate_content(request: ContentRequest, client_request: Request):
    """
    Generate social media content for a given topic
    
    - **topic**: Topic to create content about
    - **platform**: instagram, telegram, or twitter
    - **language**: en, uz, or ru
    - **style**: creative, professional, viral, or educational
    
    Returns generated content with image URL and metadata
    """
    client_ip = client_request.client.host
    logger.log_request("/api/generate", client_ip, request.dict())
    
    # Rate limiting
    if settings.rate_limit_enabled:
        if not rate_limiter.is_allowed(client_ip, settings.requests_per_minute):
            raise HTTPException(status_code=429, detail="Rate limit exceeded. Please try again later.")
    
    # Sanitize input
    topic = content_validator.sanitize_text(request.topic)
    
    # Check for forbidden content
    if content_validator.contains_forbidden_words(topic):
        raise HTTPException(status_code=400, detail="Topic contains forbidden words")
    
    # Build prompt
    prompt = get_prompt_template(request.platform, request.language, topic)
    system_prompt = get_system_prompt(request.style)
    
    try:
        # Generate text content using GROQ API
        async with httpx.AsyncClient(timeout=settings.timeout) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.groq_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": settings.ai_model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": settings.max_tokens,
                    "temperature": settings.temperature
                }
            )
            
            if response.status_code != 200:
                logger.log_error(Exception("AI API error"), "generate_content")
                raise HTTPException(status_code=500, detail="AI API error")
            
            data = response.json()
            content = data["choices"][0]["message"]["content"].strip()
            
            # Validate generated content
            content = content_validator.sanitize_text(content)
        
        # Generate image URL
        image_prompt = f"professional photo of {topic}, high quality, trending"
        image_url = image_helper.generate_pollinations_url(image_prompt)
        
        # Collect metadata
        metadata = {
            "character_count": content_validator.count_characters(content),
            "hashtag_count": content_validator.count_hashtags(content),
            "hashtags": content_validator.extract_hashtags(content),
            "ai_model": settings.ai_model,
            "generation_time": datetime.now().isoformat()
        }
        
        # Log successful generation
        logger.log_generation(topic, request.platform, True)
        
        return ContentResponse(
            topic=topic,
            platform=request.platform,
            language=request.language,
            style=request.style,
            content=content,
            image_url=image_url,
            header=f"Authorization: Bearer {settings.polly_api_key}",
            metadata=metadata,
            timestamp=datetime.now().isoformat()
        )
        
    except httpx.TimeoutException:
        logger.log_error(Exception("Timeout"), "generate_content")
        raise HTTPException(status_code=504, detail="AI API timeout")
    except Exception as e:
        logger.log_error(e, "generate_content")
        logger.log_generation(topic, request.platform, False)
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")


@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint
    
    Returns application status and metadata
    """
    uptime = (datetime.now() - startup_time).total_seconds()
    
    return HealthResponse(
        status="healthy",
        version=settings.app_version,
        uptime=f"{int(uptime)}s",
        endpoints=["/api/trends", "/api/generate", "/api/health", "/api/stats"]
    )


@app.get("/api/stats")
async def get_statistics():
    """
    Get application statistics
    
    Returns usage statistics and configuration
    """
    return {
        "supported_platforms": settings.supported_platforms,
        "supported_languages": settings.supported_languages,
        "supported_countries": settings.supported_countries,
        "max_trends": settings.max_trends,
        "character_limits": {
            "instagram": settings.instagram_max_chars,
            "telegram": settings.telegram_max_chars,
            "twitter": settings.twitter_max_chars
        },
        "ai_model": settings.ai_model,
        "rate_limiting": {
            "enabled": settings.rate_limit_enabled,
            "requests_per_minute": settings.requests_per_minute
        }
    }


# ============================================
# ERROR HANDLERS
# ============================================

@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Handle 404 errors"""
    return JSONResponse(
        status_code=404,
        content={"detail": "Endpoint not found", "path": str(request.url)}
    )

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    """Handle 500 errors"""
    logger.log_error(exc, "internal_server_error")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "message": str(exc)}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host=settings.host, 
        port=settings.port,
        log_level="info" if settings.debug else "warning"
    )