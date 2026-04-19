from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
from typing import List, Literal, Optional
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Request, Depends, status
import feedparser
import httpx
import os
from fastapi.staticfiles import StaticFiles

# Import our modules
# Import our modules
from config import settings, get_prompt_template, get_system_prompt, COUNTRY_CONFIG
from utils import validator as content_validator, trend_analyzer, image_helper, rate_limiter, logger
from database import init_db, get_db
from models import User, GeneratedPost
from auth import (
    hash_password, verify_password, create_access_token, 
    get_current_user, ACCESS_TOKEN_EXPIRE_MINUTES
)
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from fastapi import Depends, status

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

app.mount("/static", StaticFiles(directory="static"), name="static")

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
    platform: Literal["instagram", "telegram", "twitter", "linkedin"] = Field(..., description="Social media platform")
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
    meta_data: dict
    timestamp: str

class HealthResponse(BaseModel):
    status: str
    version: str
    uptime: str
    endpoints: List[str]

class UserCreate(BaseModel):
    email: str
    username: str
    password: str
    full_name: Optional[str] = None

class UserResponse(BaseModel):
    id: str
    email: str
    username: str
    full_name: Optional[str] = None
    subscription_tier: str
    credits: int
    
    class Config:
        orm_mode = True

class Token(BaseModel):
    access_token: str
    token_type: str

class UpgradeRequest(BaseModel):
    plan_type: Literal["pro_monthly", "pro_yearly"] = "pro_monthly"


# ============================================
# STARTUP & SHUTDOWN
# ============================================

startup_time = datetime.now()

@app.on_event("startup")
async def startup_event():
    """Initialize application"""
    init_db()  # Initialize database tables
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

@app.get("/static/hero.png")
async def get_hero_image():
    if os.path.exists("static/hero.png"):
        return FileResponse("static/hero.png")
    raise HTTPException(status_code=404)

# ============================================
# API ENDPOINTS
# ============================================

@app.post("/auth/register", response_model=UserResponse)
async def register(user: UserCreate, db: Session = Depends(get_db)):
    """Register new user"""
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    db_user = db.query(User).filter(User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already taken")
    
    hashed_password = hash_password(user.password)
    new_user = User(
        email=user.email,
        username=user.username,
        password_hash=hashed_password,
        full_name=user.full_name
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.post("/auth/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Login and get token"""
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.id}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/auth/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """Get current user profile"""
    return current_user

@app.post("/api/upgrade", response_model=UserResponse)
async def upgrade_to_pro(request: UpgradeRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Upgrade user to Pro tier
    """
    import asyncio
    
    # Simulate payment processing
    await asyncio.sleep(2)
    
    current_user.subscription_tier = "pro"
    current_user.credits = 999999  # Unlimited
    
    db.commit()
    db.refresh(current_user)
    
    logger.log_request("/api/upgrade", "system", {"user_id": current_user.id, "plan": request.plan_type})
    
    return current_user

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
async def generate_content(request: ContentRequest, client_request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
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
            
    # Check credits
    if current_user.credits < 1:
        raise HTTPException(
            status_code=403, 
            detail="Insufficient credits. Please upgrade your plan."
        )
    
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
        

        # Create and save GeneratedPost instance
        new_post = GeneratedPost(
            user_id=current_user.id,
            topic=topic,
            content=content,
            platform=request.platform,
            language=request.language,
            style=request.style,
            image_url=image_url,
            meta_data=metadata,
            character_count=metadata.get("character_count"),
            hashtag_count=metadata.get("hashtag_count")
        )
        db.add(new_post)
        
        # Deduct credits
        current_user.credits -= 1
        current_user.credits_used += 1
        db.commit()
        db.refresh(new_post)
        
        # Log successful generation
        logger.log_generation(topic, request.platform, True)
        
        return ContentResponse(
            topic=topic,
            platform=request.platform,
            language=request.language,
            style=request.style,
            content=content,
            image_url=image_url,
            meta_data=metadata,
            timestamp=new_post.created_at.isoformat()
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


@app.get("/api/history", response_model=List[ContentResponse])
async def get_post_history(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Get user's generated post history
    """
    posts = db.query(GeneratedPost).filter(
        GeneratedPost.user_id == current_user.id
    ).order_by(GeneratedPost.created_at.desc()).limit(50).all()
    
    return [
        ContentResponse(
            topic=p.topic,
            platform=p.platform,
            language=p.language,
            style=p.style,
            content=p.content,
            image_url=p.image_url,
            meta_data=p.meta_data,
            timestamp=p.created_at.isoformat()
        ) for p in posts
    ]


@app.post("/api/platforms/connect")
async def connect_platform(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Simulated endpoint to connect social media platforms"""
    data = await request.json()
    platform = data.get("platform")
    
    # In a real app, this would involve OAuth flows
    logger.log_request("/api/platforms/connect", "system", {"user_id": current_user.id, "platform": platform})
    
    return {"status": "connected", "platform": platform}


@app.post("/api/platforms/publish")
async def publish_to_platform(request: Request, current_user: User = Depends(get_current_user)):
    """Simulated endpoint to publish content to social media"""
    data = await request.json()
    content = data.get("content")
    platform = data.get("platform")
    
    if not content or not platform:
        raise HTTPException(status_code=400, detail="Missing content or platform")
        
    # Simulate API interaction
    import asyncio
    await asyncio.sleep(1.5)
    
    logger.log_request("/api/platforms/publish", "system", {"user_id": current_user.id, "platform": platform})
    
    return {"status": "success", "message": f"Published to {platform}"}


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