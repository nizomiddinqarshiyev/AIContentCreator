"""
Database models for AI Trend Content Creator
SQLAlchemy + PostgreSQL
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, Float, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

Base = declarative_base()

def generate_uuid():
    return str(uuid.uuid4())

# ============================================
# USER MODELS
# ============================================

class User(Base):
    """User account model"""
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    
    # Profile
    full_name = Column(String(200))
    avatar_url = Column(String(500))
    bio = Column(Text)
    
    # Subscription
    subscription_tier = Column(String(20), default="free")  # free, pro, enterprise
    credits = Column(Integer, default=100)
    credits_used = Column(Integer, default=0)
    
    # Status
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    email_verified_at = Column(DateTime)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime)
    
    # Relationships
    posts = relationship("GeneratedPost", back_populates="user", cascade="all, delete-orphan")
    templates = relationship("Template", back_populates="user", cascade="all, delete-orphan")
    scheduled_posts = relationship("ScheduledPost", back_populates="user", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User {self.username}>"
    
    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "username": self.username,
            "full_name": self.full_name,
            "avatar_url": self.avatar_url,
            "subscription_tier": self.subscription_tier,
            "credits": self.credits,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


# ============================================
# CONTENT MODELS
# ============================================

class GeneratedPost(Base):
    """Generated social media post"""
    __tablename__ = "generated_posts"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    
    # Content
    topic = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    platform = Column(String(50), nullable=False)  # instagram, telegram, twitter
    language = Column(String(10), nullable=False)  # en, uz, ru
    style = Column(String(50), nullable=False)  # creative, professional, viral, educational
    
    # Image
    image_url = Column(String(1000))
    image_prompt = Column(Text)
    
    # Metadata
    meta_data = Column(JSON)
    character_count = Column(Integer)
    hashtag_count = Column(Integer)
    
    # Engagement (if connected to social media)
    likes = Column(Integer, default=0)
    shares = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    
    # Status
    is_favorite = Column(Boolean, default=False)
    is_archived = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="posts")
    
    def __repr__(self):
        return f"<Post {self.id} - {self.platform}>"
    
    def to_dict(self):
        return {
            "id": self.id,
            "topic": self.topic,
            "content": self.content,
            "platform": self.platform,
            "language": self.language,
            "style": self.style,
            "image_url": self.image_url,
            "meta_data": self.meta_data,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class Template(Base):
    """User-uploaded image templates"""
    __tablename__ = "templates"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    
    # Template details
    name = Column(String(200), nullable=False)
    description = Column(Text)
    file_url = Column(String(1000), nullable=False)
    thumbnail_url = Column(String(1000))
    
    # Dimensions
    width = Column(Integer)
    height = Column(Integer)
    file_size = Column(Integer)  # in bytes
    
    # Usage
    usage_count = Column(Integer, default=0)
    is_public = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="templates")
    
    def __repr__(self):
        return f"<Template {self.name}>"


class ScheduledPost(Base):
    """Scheduled social media posts"""
    __tablename__ = "scheduled_posts"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    
    # Content
    content = Column(Text, nullable=False)
    platform = Column(String(50), nullable=False)
    image_url = Column(String(1000))
    
    # Schedule
    scheduled_for = Column(DateTime, nullable=False, index=True)
    timezone = Column(String(50), default="UTC")
    
    # Status
    status = Column(String(20), default="pending")  # pending, sent, failed, cancelled
    sent_at = Column(DateTime)
    error_message = Column(Text)
    
    # Retry logic
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="scheduled_posts")
    
    def __repr__(self):
        return f"<ScheduledPost {self.id} - {self.status}>"


# ============================================
# PAYMENT MODELS
# ============================================

class Payment(Base):
    """Payment transactions"""
    __tablename__ = "payments"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    
    # Stripe
    stripe_payment_id = Column(String(255), unique=True)
    stripe_customer_id = Column(String(255))
    stripe_subscription_id = Column(String(255))
    
    # Transaction
    amount = Column(Float, nullable=False)
    currency = Column(String(3), default="USD")
    status = Column(String(20), nullable=False)  # pending, completed, failed, refunded
    
    # Plan
    plan_type = Column(String(50))  # pro_monthly, pro_yearly, credits_pack
    credits_purchased = Column(Integer)
    
    # Details
    description = Column(Text)
    receipt_url = Column(String(1000))
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    completed_at = Column(DateTime)
    
    # Relationships
    user = relationship("User", back_populates="payments")
    
    def __repr__(self):
        return f"<Payment {self.id} - ${self.amount}>"


class Subscription(Base):
    """User subscriptions"""
    __tablename__ = "subscriptions"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, unique=True)
    
    # Stripe
    stripe_subscription_id = Column(String(255), unique=True)
    stripe_customer_id = Column(String(255))
    
    # Plan
    plan_type = Column(String(50), nullable=False)  # free, pro, enterprise
    billing_cycle = Column(String(20))  # monthly, yearly
    amount = Column(Float)
    currency = Column(String(3), default="USD")
    
    # Status
    status = Column(String(20), nullable=False)  # active, cancelled, expired, past_due
    
    # Dates
    current_period_start = Column(DateTime)
    current_period_end = Column(DateTime)
    cancel_at_period_end = Column(Boolean, default=False)
    cancelled_at = Column(DateTime)
    
    # Trial
    trial_start = Column(DateTime)
    trial_end = Column(DateTime)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<Subscription {self.user_id} - {self.plan_type}>"


# ============================================
# ANALYTICS MODELS
# ============================================

class AnalyticsEvent(Base):
    """Track user events for analytics"""
    __tablename__ = "analytics_events"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"))
    
    # Event
    event_type = Column(String(100), nullable=False, index=True)  # page_view, generate_content, etc.
    event_category = Column(String(100))
    event_label = Column(String(200))
    event_value = Column(Float)
    
    # Context
    page_url = Column(String(1000))
    referrer = Column(String(1000))
    user_agent = Column(String(500))
    ip_address = Column(String(45))
    
    # Session
    session_id = Column(String(100))
    
    # Metadata
    meta_data = Column(JSON)
    
    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    def __repr__(self):
        return f"<Event {self.event_type}>"


# ============================================
# CACHE MODEL (for Redis fallback)
# ============================================

class CacheEntry(Base):
    """Database cache fallback"""
    __tablename__ = "cache_entries"
    
    key = Column(String(255), primary_key=True)
    value = Column(Text, nullable=False)
    expires_at = Column(DateTime, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<CacheEntry {self.key}>"