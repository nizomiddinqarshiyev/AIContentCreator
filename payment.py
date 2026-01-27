"""
Stripe payment integration
Subscriptions & One-time purchases
"""
import stripe
import os
from typing import Dict
from datetime import datetime
from sqlalchemy.orm import Session

from models import User, Payment, Subscription

# Stripe configuration
stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "sk_test_...")

# Pricing plans
PLANS = {
    "pro_monthly": {
        "price_id": "price_monthly_...",  # From Stripe Dashboard
        "amount": 9.99,
        "interval": "month",
        "credits": 1000
    },
    "pro_yearly": {
        "price_id": "price_yearly_...",
        "amount": 99.99,
        "interval": "year",
        "credits": 15000
    },
    "credits_100": {
        "price_id": "price_credits_100",
        "amount": 4.99,
        "credits": 100
    },
    "credits_500": {
        "price_id": "price_credits_500",
        "amount": 19.99,
        "credits": 500
    }
}

# ============================================
# CUSTOMER MANAGEMENT
# ============================================

def create_stripe_customer(user: User) -> str:
    """Create Stripe customer for user"""
    customer = stripe.Customer.create(
        email=user.email,
        name=user.full_name,
        metadata={"user_id": user.id}
    )
    return customer.id

def get_or_create_customer(user: User, db: Session) -> str:
    """Get existing or create new Stripe customer"""
    subscription = db.query(Subscription).filter(
        Subscription.user_id == user.id
    ).first()
    
    if subscription and subscription.stripe_customer_id:
        return subscription.stripe_customer_id
    
    return create_stripe_customer(user)

# ============================================
# SUBSCRIPTION MANAGEMENT
# ============================================

def create_subscription(
    user: User,
    plan_type: str,
    payment_method_id: str,
    db: Session
) -> Dict:
    """Create new subscription"""
    
    if plan_type not in PLANS:
        raise ValueError(f"Invalid plan: {plan_type}")
    
    plan = PLANS[plan_type]
    
    # Create or get customer
    customer_id = get_or_create_customer(user, db)
    
    # Attach payment method
    stripe.PaymentMethod.attach(
        payment_method_id,
        customer=customer_id
    )
    
    # Set as default payment method
    stripe.Customer.modify(
        customer_id,
        invoice_settings={"default_payment_method": payment_method_id}
    )
    
    # Create subscription
    stripe_subscription = stripe.Subscription.create(
        customer=customer_id,
        items=[{"price": plan["price_id"]}],
        payment_behavior="default_incomplete",
        expand=["latest_invoice.payment_intent"]
    )
    
    # Save to database
    subscription = Subscription(
        user_id=user.id,
        stripe_subscription_id=stripe_subscription.id,
        stripe_customer_id=customer_id,
        plan_type=plan_type.split("_")[0],  # "pro"
        billing_cycle=plan["interval"],
        amount=plan["amount"],
        status="active",
        current_period_start=datetime.fromtimestamp(
            stripe_subscription.current_period_start
        ),
        current_period_end=datetime.fromtimestamp(
            stripe_subscription.current_period_end
        )
    )
    
    # Update user
    user.subscription_tier = "pro"
    user.credits += plan.get("credits", 0)
    
    db.add(subscription)
    db.commit()
    
    return {
        "subscription_id": stripe_subscription.id,
        "client_secret": stripe_subscription.latest_invoice.payment_intent.client_secret,
        "status": stripe_subscription.status
    }

def cancel_subscription(user: User, db: Session) -> Dict:
    """Cancel user subscription"""
    subscription = db.query(Subscription).filter(
        Subscription.user_id == user.id,
        Subscription.status == "active"
    ).first()
    
    if not subscription:
        raise ValueError("No active subscription found")
    
    # Cancel at period end
    stripe.Subscription.modify(
        subscription.stripe_subscription_id,
        cancel_at_period_end=True
    )
    
    subscription.cancel_at_period_end = True
    subscription.cancelled_at = datetime.utcnow()
    db.commit()
    
    return {"status": "cancelled", "active_until": subscription.current_period_end}

# ============================================
# ONE-TIME PAYMENTS
# ============================================

def purchase_credits(
    user: User,
    plan_type: str,
    payment_method_id: str,
    db: Session
) -> Dict:
    """Purchase credits with one-time payment"""
    
    if plan_type not in PLANS or "credits" not in plan_type:
        raise ValueError("Invalid credits plan")
    
    plan = PLANS[plan_type]
    customer_id = get_or_create_customer(user, db)
    
    # Create payment intent
    payment_intent = stripe.PaymentIntent.create(
        amount=int(plan["amount"] * 100),  # Convert to cents
        currency="usd",
        customer=customer_id,
        payment_method=payment_method_id,
        confirmation_method="automatic",
        confirm=True,
        metadata={
            "user_id": user.id,
            "plan_type": plan_type,
            "credits": plan["credits"]
        }
    )
    
    if payment_intent.status == "succeeded":
        # Add credits
        user.credits += plan["credits"]
        
        # Record payment
        payment = Payment(
            user_id=user.id,
            stripe_payment_id=payment_intent.id,
            stripe_customer_id=customer_id,
            amount=plan["amount"],
            status="completed",
            plan_type=plan_type,
            credits_purchased=plan["credits"],
            completed_at=datetime.utcnow()
        )
        
        db.add(payment)
        db.commit()
        
        return {
            "status": "success",
            "credits_added": plan["credits"],
            "new_balance": user.credits
        }
    
    return {"status": payment_intent.status}

# ============================================
# WEBHOOKS
# ============================================

def handle_webhook(payload: dict, sig_header: str) -> Dict:
    """Handle Stripe webhooks"""
    
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except ValueError:
        raise ValueError("Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise ValueError("Invalid signature")
    
    # Handle event types
    if event["type"] == "payment_intent.succeeded":
        return handle_payment_succeeded(event["data"]["object"])
    elif event["type"] == "customer.subscription.updated":
        return handle_subscription_updated(event["data"]["object"])
    elif event["type"] == "customer.subscription.deleted":
        return handle_subscription_deleted(event["data"]["object"])
    elif event["type"] == "invoice.payment_failed":
        return handle_payment_failed(event["data"]["object"])
    
    return {"status": "unhandled"}

def handle_payment_succeeded(payment_intent):
    """Handle successful payment"""
    # Update payment record
    return {"status": "processed"}

def handle_subscription_updated(subscription):
    """Handle subscription update"""
    # Update subscription in database
    return {"status": "updated"}

def handle_subscription_deleted(subscription):
    """Handle subscription deletion"""
    # Downgrade user to free tier
    return {"status": "deleted"}

def handle_payment_failed(invoice):
    """Handle failed payment"""
    # Send notification to user
    return {"status": "notified"}