"""
Celery tasks for background processing
- Scheduled posts
- Email notifications
- Analytics processing
"""
from celery import Celery
from celery.schedules import crontab
from datetime import datetime, timedelta
import os

# Celery configuration
celery_app = Celery(
    "ai_content_creator",
    broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

# ============================================
# SCHEDULED POSTS
# ============================================

@celery_app.task(name="send_scheduled_post")
def send_scheduled_post(post_id: str):
    """Send a scheduled social media post"""
    from database import SessionLocal
    from models import ScheduledPost
    
    db = SessionLocal()
    try:
        post = db.query(ScheduledPost).filter(
            ScheduledPost.id == post_id,
            ScheduledPost.status == "pending"
        ).first()
        
        if not post:
            return {"status": "not_found"}
        
        # TODO: Implement actual posting to social media
        # For now, just mark as sent
        post.status = "sent"
        post.sent_at = datetime.utcnow()
        db.commit()
        
        return {"status": "sent", "post_id": post_id}
        
    except Exception as e:
        if post:
            post.retry_count += 1
            if post.retry_count >= post.max_retries:
                post.status = "failed"
                post.error_message = str(e)
            db.commit()
        return {"status": "error", "message": str(e)}
    finally:
        db.close()

@celery_app.task(name="process_scheduled_posts")
def process_scheduled_posts():
    """Process all due scheduled posts"""
    from database import SessionLocal
    from models import ScheduledPost
    
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        due_posts = db.query(ScheduledPost).filter(
            ScheduledPost.status == "pending",
            ScheduledPost.scheduled_for <= now
        ).all()
        
        for post in due_posts:
            send_scheduled_post.delay(post.id)
        
        return {"processed": len(due_posts)}
    finally:
        db.close()

# ============================================
# EMAIL NOTIFICATIONS
# ============================================

@celery_app.task(name="send_email")
def send_email(to: str, subject: str, body: str, html: str = None):
    """Send email notification"""
    # TODO: Implement email sending (SendGrid, AWS SES, etc.)
    print(f"📧 Sending email to {to}: {subject}")
    return {"status": "sent"}

@celery_app.task(name="send_welcome_email")
def send_welcome_email(user_id: str):
    """Send welcome email to new user"""
    from database import SessionLocal
    from models import User
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            send_email.delay(
                to=user.email,
                subject="Welcome to AI Content Creator!",
                body=f"Hi {user.full_name}, welcome to AI Content Creator!"
            )
    finally:
        db.close()

@celery_app.task(name="send_credit_low_alert")
def send_credit_low_alert(user_id: str):
    """Alert user when credits are low"""
    from database import SessionLocal
    from models import User
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if user and user.credits < 10:
            send_email.delay(
                to=user.email,
                subject="Low Credits Alert",
                body=f"You have only {user.credits} credits left. Upgrade now!"
            )
    finally:
        db.close()

# ============================================
# ANALYTICS & CLEANUP
# ============================================

@celery_app.task(name="process_analytics")
def process_analytics():
    """Process and aggregate analytics data"""
    from database import SessionLocal
    from models import AnalyticsEvent
    
    db = SessionLocal()
    try:
        # Example: Count events per type in last 24h
        yesterday = datetime.utcnow() - timedelta(days=1)
        events = db.query(AnalyticsEvent).filter(
            AnalyticsEvent.created_at >= yesterday
        ).all()
        
        # Process and store aggregated data
        return {"processed_events": len(events)}
    finally:
        db.close()

@celery_app.task(name="cleanup_old_data")
def cleanup_old_data():
    """Clean up old analytics and cache data"""
    from database import SessionLocal
    from models import AnalyticsEvent, CacheEntry
    
    db = SessionLocal()
    try:
        # Delete analytics older than 90 days
        cutoff = datetime.utcnow() - timedelta(days=90)
        deleted_analytics = db.query(AnalyticsEvent).filter(
            AnalyticsEvent.created_at < cutoff
        ).delete()
        
        # Delete expired cache entries
        deleted_cache = db.query(CacheEntry).filter(
            CacheEntry.expires_at < datetime.utcnow()
        ).delete()
        
        db.commit()
        return {
            "deleted_analytics": deleted_analytics,
            "deleted_cache": deleted_cache
        }
    finally:
        db.close()

# ============================================
# SUBSCRIPTION MANAGEMENT
# ============================================

@celery_app.task(name="check_expired_subscriptions")
def check_expired_subscriptions():
    """Check and handle expired subscriptions"""
    from database import SessionLocal
    from models import Subscription, User
    
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        expired = db.query(Subscription).filter(
            Subscription.current_period_end < now,
            Subscription.status == "active"
        ).all()
        
        for sub in expired:
            sub.status = "expired"
            # Downgrade user to free tier
            user = db.query(User).filter(User.id == sub.user_id).first()
            if user:
                user.subscription_tier = "free"
                user.credits = 10  # Free tier credits
        
        db.commit()
        return {"expired_count": len(expired)}
    finally:
        db.close()

# ============================================
# CELERY BEAT SCHEDULE
# ============================================

celery_app.conf.beat_schedule = {
    "process-scheduled-posts": {
        "task": "process_scheduled_posts",
        "schedule": crontab(minute="*/5"),  # Every 5 minutes
    },
    "process-analytics": {
        "task": "process_analytics",
        "schedule": crontab(hour="*/6"),  # Every 6 hours
    },
    "cleanup-old-data": {
        "task": "cleanup_old_data",
        "schedule": crontab(hour=2, minute=0),  # Daily at 2 AM
    },
    "check-expired-subscriptions": {
        "task": "check_expired_subscriptions",
        "schedule": crontab(hour=0, minute=0),  # Daily at midnight
    },
}

# ============================================
# UTILITY TASKS
# ============================================

@celery_app.task(name="generate_monthly_report")
def generate_monthly_report(user_id: str):
    """Generate monthly usage report for user"""
    from database import SessionLocal
    from models import User, GeneratedPost
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"status": "user_not_found"}
        
        # Get posts from last month
        month_ago = datetime.utcnow() - timedelta(days=30)
        posts = db.query(GeneratedPost).filter(
            GeneratedPost.user_id == user_id,
            GeneratedPost.created_at >= month_ago
        ).all()
        
        report = {
            "user": user.username,
            "period": "last_30_days",
            "total_posts": len(posts),
            "credits_used": user.credits_used,
            "platforms": {}
        }
        
        # Aggregate by platform
        for post in posts:
            platform = post.platform
            if platform not in report["platforms"]:
                report["platforms"][platform] = 0
            report["platforms"][platform] += 1
        
        # Send email with report
        send_email.delay(
            to=user.email,
            subject="Your Monthly Content Report",
            body=f"Generated {len(posts)} posts last month!"
        )
        
        return report
    finally:
        db.close()