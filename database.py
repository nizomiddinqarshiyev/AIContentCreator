"""
Database configuration and session management
PostgreSQL + SQLAlchemy
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
import os

# Database URL from settings
from config import settings
DATABASE_URL = settings.database_url

# Create engine
connect_args = {}
engine_args = {
    "pool_pre_ping": True,
    "echo": settings.debug
}

if "sqlite" in DATABASE_URL:
    connect_args["check_same_thread"] = False
    from sqlalchemy.pool import StaticPool
    engine_args["poolclass"] = StaticPool
else:
    engine_args["pool_size"] = 10
    engine_args["max_overflow"] = 20

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    **engine_args
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ============================================
# DATABASE DEPENDENCIES
# ============================================

def get_db() -> Session:
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ============================================
# DATABASE INITIALIZATION
# ============================================

def init_db():
    """Initialize database tables"""
    from models import Base
    Base.metadata.create_all(bind=engine)
    print("[OK] Database tables created")

def drop_db():
    """Drop all database tables"""
    from models import Base
    Base.metadata.drop_all(bind=engine)
    print("[DELETE] Database tables dropped")

# ============================================
# REDIS CACHE
# ============================================

import redis
from typing import Optional, Any
import json

class RedisCache:
    """Redis cache manager"""
    
    def __init__(self):
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        try:
            self.client = redis.from_url(redis_url, decode_responses=True)
            self.client.ping()
            self.enabled = True
            print("[OK] Redis connected")
        except:
            self.enabled = False
            print("[WARNING] Redis not available, using database cache")
    
    def get(self, key: str) -> Optional[str]:
        """Get value from cache"""
        if not self.enabled:
            return None
        try:
            return self.client.get(key)
        except:
            return None
    
    def set(self, key: str, value: Any, expire: int = 3600):
        """Set value in cache with expiration"""
        if not self.enabled:
            return False
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            self.client.setex(key, expire, value)
            return True
        except:
            return False
    
    def delete(self, key: str):
        """Delete key from cache"""
        if not self.enabled:
            return False
        try:
            self.client.delete(key)
            return True
        except:
            return False
    
    def exists(self, key: str) -> bool:
        """Check if key exists"""
        if not self.enabled:
            return False
        try:
            return bool(self.client.exists(key))
        except:
            return False
    
    def clear_pattern(self, pattern: str):
        """Clear all keys matching pattern"""
        if not self.enabled:
            return
        try:
            keys = self.client.keys(pattern)
            if keys:
                self.client.delete(*keys)
        except:
            pass

# Global cache instance
cache = RedisCache()