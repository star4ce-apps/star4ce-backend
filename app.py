import os, datetime, jwt, smtplib, secrets, json, random, requests
from urllib.parse import quote
import csv
import io
try:
    import stripe
    STRIPE_AVAILABLE = True
except ImportError:
    STRIPE_AVAILABLE = False
    stripe = None
from email.message import EmailMessage
from flask import Flask, jsonify, request, Response
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from flask import g
from sqlalchemy import text, inspect
import re

load_dotenv()
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret")

# Stripe configuration
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID")  # Monthly subscription price ID ($199/month)
STRIPE_PRICE_ID_ANNUAL = os.getenv("STRIPE_PRICE_ID_ANNUAL")  # Annual subscription price ID ($166/month = $1992/year)

# Set Stripe API key if available
if STRIPE_AVAILABLE and STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)

RESEND_API_KEY = os.getenv("RESEND_API_KEY")
EMAIL_FROM = os.getenv("EMAIL_FROM", SMTP_FROM or SMTP_USER)
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

app = Flask(__name__)

# CORS configuration - allow localhost in development, restrict in production
frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
is_production = os.getenv("ENVIRONMENT") == "production" or os.getenv("FLASK_ENV") == "production"

if is_production:
    # Production: only allow the configured frontend URL
    allowed_origins = [frontend_url]
    print(f"[CORS] Production mode - allowing only: {allowed_origins}", flush=True)
else:
    # Development: allow localhost variants (more permissive)
    allowed_origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        frontend_url,
    ]
    # Remove duplicates
    allowed_origins = list(dict.fromkeys(allowed_origins))
    print(f"[CORS] Development mode - allowing: {allowed_origins}", flush=True)

# Configure CORS - allow all routes in development
# In production, this should be more restrictive
if is_production:
    # Production: use resources pattern for better control
    CORS(app, 
         resources={
             r"/*": {
                 "origins": allowed_origins,
                 "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
                 "allow_headers": ["Content-Type", "Authorization", "X-Requested-With"],
                 "supports_credentials": True,
                 "max_age": 3600
             }
         })
else:
    # Development: allow all origins and routes for easier testing
    CORS(app, 
         origins=allowed_origins,
         methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
         allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
         supports_credentials=True,
         max_age=3600)

# Rate limiting
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"  # Use Redis in production: os.getenv("REDIS_URL", "memory://")
)

# --- DATABASE SETUP ---

# Get DATABASE_URL from environment (PostgreSQL for production, SQLite for local dev)
# For local development, defaults to SQLite if DATABASE_URL is not set
# For production, set DATABASE_URL in .env file
# Example: DATABASE_URL=postgresql://user:password@localhost:5432/star4ce_db
raw_db_url = os.getenv("DATABASE_URL", "sqlite:///instance/star4ce.db")

# Fix SQLite path for Windows - convert to absolute path if relative
if raw_db_url.startswith("sqlite:///"):
    db_path = raw_db_url.replace("sqlite:///", "")
    if not os.path.isabs(db_path):
        # Make it relative to the app directory
        app_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(app_dir, db_path)
        # Normalize path separators for SQLite
        db_path = db_path.replace("\\", "/")
        raw_db_url = f"sqlite:///{db_path}"

# Render / Heroku sometimes give postgres://, SQLAlchemy needs postgresql://
if raw_db_url.startswith("postgres://"):
    raw_db_url = raw_db_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = raw_db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

class Dealership(db.Model):
    __tablename__ = "dealerships"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    address = db.Column(db.String(255), nullable=True)
    city = db.Column(db.String(100), nullable=True)
    state = db.Column(db.String(50), nullable=True)
    zip_code = db.Column(db.String(20), nullable=True)

    # Subscription fields
    stripe_customer_id = db.Column(db.String(255), nullable=True, unique=True)
    stripe_subscription_id = db.Column(db.String(255), nullable=True, unique=True)
    subscription_status = db.Column(db.String(50), nullable=False, default="trial")  # trial, active, past_due, canceled, expired
    subscription_plan = db.Column(db.String(50), nullable=True)  # basic, pro, enterprise
    trial_ends_at = db.Column(db.DateTime, nullable=True)  # When trial expires
    subscription_ends_at = db.Column(db.DateTime, nullable=True)  # When subscription expires
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "address": self.address,
            "city": self.city,
            "state": self.state,
            "zip_code": self.zip_code,
            "subscription_status": self.subscription_status,
            "subscription_plan": self.subscription_plan,
            "trial_ends_at": self.trial_ends_at.isoformat() + "Z" if self.trial_ends_at else None,
            "subscription_ends_at": self.subscription_ends_at.isoformat() + "Z" if self.subscription_ends_at else None,
        }

    def is_subscription_active(self) -> bool:
        """Check if subscription is active (trial or paid)"""
        if self.subscription_status == "trial":
            return self.trial_ends_at and self.trial_ends_at > datetime.datetime.utcnow()
        return self.subscription_status == "active"

    def days_remaining_in_trial(self) -> int:
        """Get days remaining in trial period"""
        if self.subscription_status == "trial" and self.trial_ends_at:
            remaining = self.trial_ends_at - datetime.datetime.utcnow()
            return max(0, remaining.days)
        return 0


# Association table for corporate users and their assigned dealerships
corporate_dealerships = db.Table(
    'corporate_dealerships',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('dealership_id', db.Integer, db.ForeignKey('dealerships.id'), primary_key=True),
    db.Column('created_at', db.DateTime, nullable=False, default=datetime.datetime.utcnow)
)

class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(255), nullable=True)  # Full name of the user

    # Roles:
    # - "admin"      = owner of a single dealership (uses dealership_id)
    # - "manager"    = manager at a dealership (uses dealership_id)
    # - "corporate"  = can see multiple specific dealerships (uses corporate_dealerships table)
    role = db.Column(
        db.String(50),
        nullable=False,
        default="manager",
    )

    # Which dealership this user belongs to (for admin/manager roles)
    # For corporate users, use the corporate_dealerships relationship instead
    dealership_id = db.Column(db.Integer, db.ForeignKey("dealerships.id"), nullable=True)
    dealership = db.relationship("Dealership", backref="users", foreign_keys=[dealership_id])
    
    # Many-to-many relationship for corporate users to access multiple dealerships
    corporate_dealerships = db.relationship(
        "Dealership",
        secondary=corporate_dealerships,
        backref=db.backref("corporate_users", lazy="dynamic"),
        lazy="dynamic"
    )

    # email verification
    is_verified = db.Column(db.Boolean, nullable=False, default=False)
    verification_code = db.Column(db.String(6), nullable=True)
    verification_expires_at = db.Column(db.DateTime, nullable=True)

    reset_code = db.Column(db.String(6), nullable=True)
    reset_code_expires_at = db.Column(db.DateTime, nullable=True)
    
    # Manager approval (for manager role only)
    # Managers need admin approval before they can access the system
    is_approved = db.Column(db.Boolean, nullable=False, default=False)
    approved_at = db.Column(db.DateTime, nullable=True)
    approved_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)  # Admin who approved
    
    # Timestamp for account creation (for cleanup of unsubscribed accounts)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "role": self.role,
            "is_verified": self.is_verified,
            "dealership_id": self.dealership_id,
            "full_name": self.full_name,
        }


class Employee(db.Model):
    __tablename__ = "employees"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    
    # Employee role/department
    department = db.Column(db.String(100), nullable=False)  # Sales, Service, Parts, etc.
    position = db.Column(db.String(100), nullable=True)  # Manager, Associate, etc.
    
    # Which dealership this employee belongs to
    dealership_id = db.Column(db.Integer, db.ForeignKey("dealerships.id"), nullable=False)
    dealership = db.relationship("Dealership", backref="employees")
    
    # Status
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "department": self.department,
            "position": self.position,
            "dealership_id": self.dealership_id,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() + "Z",
            "updated_at": self.updated_at.isoformat() + "Z",
        }


class SurveyAccessCode(db.Model):
    __tablename__ = "survey_access_codes"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(16), unique=True, nullable=False)

    dealership_id = db.Column(db.Integer, db.ForeignKey("dealerships.id"), nullable=False)
    dealership = db.relationship("Dealership", backref="access_codes")

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)


class SurveyAnswer(db.Model):
    __tablename__ = "survey_answers"

    id = db.Column(db.Integer, primary_key=True)

    dealership_id = db.Column(db.Integer, db.ForeignKey("dealerships.id"), nullable=False)
    dealership = db.relationship("Dealership", backref="survey_answers")

    access_code_id = db.Column(db.Integer, db.ForeignKey("survey_access_codes.id"), nullable=True)
    access_code = db.relationship("SurveyAccessCode", backref="answers")

    # Store survey responses as a JSON string (we’ll parse in Python)
    payload = db.Column(db.Text, nullable=False)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)



class SurveyResponse(db.Model):
    __tablename__ = "survey_responses"

    id = db.Column(db.Integer, primary_key=True)

    # Which dealership / access code
    access_code = db.Column(db.String(50), nullable=False)

    # Employee metadata
    employee_status = db.Column(db.String(50), nullable=False)   # 'newly-hired' | 'termination' | 'leave' | 'none'
    role = db.Column(db.String(100), nullable=False)             # 'Sales Department', etc.

    # Store answers as JSON blobs for now (flexible)
    satisfaction_answers = db.Column(db.JSON, nullable=False)    # { 0: 'Very Satisfied', ... }
    training_answers = db.Column(db.JSON, nullable=True)         # only for newly-hired

    termination_reason = db.Column(db.String(100), nullable=True)
    termination_other = db.Column(db.String(255), nullable=True)

    leave_reason = db.Column(db.String(100), nullable=True)
    leave_other = db.Column(db.String(255), nullable=True)

    additional_feedback = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "access_code": self.access_code,
            "employee_status": self.employee_status,
            "role": self.role,
            "created_at": self.created_at.isoformat() + "Z",
        }

class AdminRequest(db.Model):
    __tablename__ = "admin_requests"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    user = db.relationship("User", foreign_keys=[user_id], backref="admin_requests")
    dealership_id = db.Column(db.Integer, db.ForeignKey("dealerships.id"), nullable=False)
    dealership = db.relationship("Dealership", backref="admin_requests")
    status = db.Column(db.String(50), nullable=False, default="pending")  # pending, approved, rejected
    requested_at = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    reviewed_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)  # Corporate user who reviewed
    reviewer = db.relationship("User", foreign_keys=[reviewed_by])
    notes = db.Column(db.Text, nullable=True)  # Optional notes from reviewer

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "user_email": self.user.email if self.user else None,
            "dealership_id": self.dealership_id,
            "dealership_name": self.dealership.name if self.dealership else None,
            "status": self.status,
            "requested_at": self.requested_at.isoformat() + "Z",
            "reviewed_at": self.reviewed_at.isoformat() + "Z" if self.reviewed_at else None,
            "reviewed_by": self.reviewed_by,
            "notes": self.notes,
        }

class DealershipAccessRequest(db.Model):
    """
    Request from corporate users to access/view a dealership's stats.
    Admins can approve or reject these requests.
    """
    __tablename__ = "dealership_access_requests"

    id = db.Column(db.Integer, primary_key=True)
    corporate_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    corporate_user = db.relationship("User", foreign_keys=[corporate_user_id], backref="dealership_access_requests")
    dealership_id = db.Column(db.Integer, db.ForeignKey("dealerships.id"), nullable=False)
    dealership = db.relationship("Dealership", backref="access_requests")
    status = db.Column(db.String(50), nullable=False, default="pending")  # pending, approved, rejected
    requested_at = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    reviewed_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)  # Admin who reviewed
    reviewer = db.relationship("User", foreign_keys=[reviewed_by])
    notes = db.Column(db.Text, nullable=True)  # Optional notes from reviewer

    def to_dict(self):
        return {
            "id": self.id,
            "corporate_user_id": self.corporate_user_id,
            "corporate_user_email": self.corporate_user.email if self.corporate_user else None,
            "dealership_id": self.dealership_id,
            "dealership_name": self.dealership.name if self.dealership else None,
            "status": self.status,
            "requested_at": self.requested_at.isoformat() + "Z",
            "reviewed_at": self.reviewed_at.isoformat() + "Z" if self.reviewed_at else None,
            "reviewed_by": self.reviewed_by,
            "reviewer_email": self.reviewer.email if self.reviewer else None,
            "notes": self.notes,
        }

class ManagerDealershipRequest(db.Model):
    """
    Request from managers to join/access a specific dealership.
    Admins can approve or reject these requests.
    """
    __tablename__ = "manager_dealership_requests"

    id = db.Column(db.Integer, primary_key=True)
    manager_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    manager = db.relationship("User", foreign_keys=[manager_id], backref="manager_dealership_requests")
    dealership_id = db.Column(db.Integer, db.ForeignKey("dealerships.id"), nullable=False)
    dealership = db.relationship("Dealership", backref="manager_requests")
    status = db.Column(db.String(50), nullable=False, default="pending")  # pending, approved, rejected
    requested_at = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    reviewed_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)  # Admin who reviewed
    reviewer = db.relationship("User", foreign_keys=[reviewed_by])
    notes = db.Column(db.Text, nullable=True)  # Optional notes from reviewer

    def to_dict(self):
        return {
            "id": self.id,
            "manager_id": self.manager_id,
            "manager_email": self.manager.email if self.manager else None,
            "dealership_id": self.dealership_id,
            "dealership_name": self.dealership.name if self.dealership else None,
            "status": self.status,
            "requested_at": self.requested_at.isoformat() + "Z",
            "reviewed_at": self.reviewed_at.isoformat() + "Z" if self.reviewed_at else None,
            "reviewed_by": self.reviewed_by,
            "reviewer_email": self.reviewer.email if self.reviewer else None,
            "notes": self.notes,
        }

class RolePermission(db.Model):
    """
    Stores permissions for each role (manager, corporate, admin).
    Admin can manage these permissions via the UI.
    """
    __tablename__ = "role_permissions"

    id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.String(50), nullable=False)  # "manager", "corporate", "admin"
    permission_key = db.Column(db.String(100), nullable=False)  # e.g., "view_dashboard", "create_survey"
    allowed = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Unique constraint: one permission per role
    __table_args__ = (db.UniqueConstraint('role', 'permission_key', name='_role_permission_uc'),)

    def to_dict(self):
        return {
            "id": self.id,
            "role": self.role,
            "permission_key": self.permission_key,
            "allowed": self.allowed,
        }

class UserPermission(db.Model):
    """
    Stores individual permissions for specific users (managers).
    Allows admins to override role-based permissions for individual managers.
    Corporate users use role-based permissions only.
    """
    __tablename__ = "user_permissions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    user = db.relationship("User", backref="user_permissions")
    permission_key = db.Column(db.String(100), nullable=False)  # e.g., "view_dashboard", "create_survey"
    allowed = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Unique constraint: one permission per user
    __table_args__ = (db.UniqueConstraint('user_id', 'permission_key', name='_user_permission_uc'),)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "permission_key": self.permission_key,
            "allowed": self.allowed,
        }

class AdminAuditLog(db.Model):
    __tablename__ = "admin_audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    admin_email = db.Column(db.String(255), nullable=False)
    action = db.Column(db.String(100), nullable=False)  # e.g., "create_access_code", "update_employee"
    resource_type = db.Column(db.String(100), nullable=False)  # e.g., "access_code", "employee", "dealership"
    resource_id = db.Column(db.Integer, nullable=True)  # ID of the resource that was acted upon
    details = db.Column(db.Text, nullable=True)  # JSON string with additional details
    ip_address = db.Column(db.String(45), nullable=True)  # IPv4 or IPv6 address
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "admin_email": self.admin_email,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "details": self.details,
            "ip_address": self.ip_address,
            "created_at": self.created_at.isoformat() + "Z",
        }

@app.get("/health")
def health():
    """Health check endpoint with system status"""
    try:
        # Check database connection
        db.session.execute(db.text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)[:50]}"
    
    # Check Stripe
    stripe_status = "configured" if (STRIPE_AVAILABLE and STRIPE_SECRET_KEY) else "not_configured"
    
    # Check email
    email_status = "configured" if (RESEND_API_KEY or SMTP_USER) else "not_configured"
    
    return jsonify(
        ok=True,
        service="star4ce-backend",
        database=db_status,
        stripe=stripe_status,
        email=email_status,
        environment=os.getenv("ENVIRONMENT", "development")
    )

def make_token(email: str, role: str = "manager"):
    """Create JWT token with reasonable expiration for better UX"""
    payload = {
        "sub": email,
        "role": role,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=24),  # 24 hours for better UX
        "iat": datetime.datetime.utcnow(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def verify_token(token: str):
    """Verify JWT token, handling expiration gracefully"""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise ValueError("Token expired")
    except jwt.InvalidTokenError:
        raise ValueError("Invalid token")

def get_current_user():
    """
    Reads the Bearer token from Authorization header,
    verifies it, and returns the User object.
    Returns (user, error_response) so callers can handle 401/403 cleanly.
    """
    auth = request.headers.get("Authorization", "") or request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return None, (jsonify(error="missing bearer token"), 401)

    token = auth.split(" ", 1)[1].strip()
    if not token:
        return None, (jsonify(error="empty token"), 401)
    
    try:
        claims = verify_token(token)
    except ValueError as e:
        # Token expired or invalid
        error_msg = str(e)
        if "expired" in error_msg.lower():
            return None, (jsonify(error="token expired"), 401)
        return None, (jsonify(error="invalid token"), 401)
    except Exception as e:
        print(f"[AUTH ERROR] get_current_user failed: {e}", flush=True)
        return None, (jsonify(error="invalid token"), 401)

    email = claims.get("sub")
    if not email:
        return None, (jsonify(error="invalid token payload"), 401)

    user = User.query.filter_by(email=email).first()
    if not user:
        return None, (jsonify(error="user not found"), 401)

    # Auto-upgrade users with active subscriptions to admin
    # This handles cases where webhook didn't fire or user subscribed before webhook was set up
    if user.role == "manager" and user.dealership_id:
        dealership = Dealership.query.get(user.dealership_id)
        if dealership and dealership.is_subscription_active():
            # User has active subscription but is still manager - upgrade to admin
            user.role = "admin"
            user.is_verified = True
            user.is_approved = True
            if not user.approved_at:
                user.approved_at = datetime.datetime.utcnow()
            db.session.commit()
            print(f"[AUTO-UPGRADE] User {user.email} auto-upgraded to admin (has active subscription)", flush=True)
    elif user.role == "manager" and not user.dealership_id:
        # Check if user has any dealership with active subscription (by email matching Stripe customer)
        if STRIPE_AVAILABLE and STRIPE_SECRET_KEY:
            try:
                # Try to find dealership by Stripe customer email
                dealerships = Dealership.query.filter(
                    Dealership.stripe_customer_id.isnot(None)
                ).all()
                for dealership in dealerships:
                    if dealership.stripe_customer_id:
                        try:
                            customer = stripe.Customer.retrieve(dealership.stripe_customer_id)
                            if customer.get("email") == user.email and dealership.is_subscription_active():
                                # User has active subscription - upgrade and assign
                                user.role = "admin"
                                user.dealership_id = dealership.id
                                user.is_verified = True
                                user.is_approved = True
                                if not user.approved_at:
                                    user.approved_at = datetime.datetime.utcnow()
                                db.session.commit()
                                print(f"[AUTO-UPGRADE] User {user.email} auto-upgraded to admin (found by Stripe customer)", flush=True)
                                break
                        except:
                            pass  # Skip if Stripe customer lookup fails
            except:
                pass  # Skip if Stripe is not available

    # Require email to be verified to access protected routes
    if not user.is_verified:
        return None, (jsonify(error="unverified"), 403)
    
    # For managers, check if they're approved by an admin
    if user.role == "manager" and not user.is_approved:
        return None, (jsonify(error="manager_not_approved", message="Your account is pending admin approval"), 403)

    # Store on flask.g if you ever want it elsewhere
    g.current_user = user
    return user, None

def get_accessible_dealership_ids(user) -> list[int]:
    """
    Get list of dealership IDs that a user can access based on their role.
    - admin/manager: returns [user.dealership_id] if set, else []
    - corporate: returns list of dealership IDs from corporate_dealerships relationship
    """
    if user.role in ("admin", "manager"):
        if user.dealership_id:
            return [user.dealership_id]
        return []
    elif user.role == "corporate":
        # Get all dealership IDs from the many-to-many relationship
        return [d.id for d in user.corporate_dealerships.all()]
    return []

def log_admin_action(admin_email: str, action: str, resource_type: str, resource_id: int = None, details: str = None):
    """Log admin actions for audit trail"""
    try:
        ip_address = request.remote_addr if request else None
        # Log to console for debugging
        print(f"[AUDIT] {admin_email} - {action} - {resource_type} - {resource_id} - IP: {ip_address}", flush=True)
        
        # Save to database
        log_entry = AdminAuditLog(
            admin_email=admin_email,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
        )
        db.session.add(log_entry)
        db.session.commit()
    except Exception as e:
        # Don't fail the request if logging fails
        print(f"[AUDIT ERROR] Failed to log action: {e}", flush=True)
        db.session.rollback()

def send_email_via_resend_or_smtp(to_email: str, subject: str, body: str):
    """
    Unified email sending function.
    Tries Resend first (production), falls back to SMTP (local dev).
    Returns True if sent successfully, False otherwise.
    """
    # Always log for debugging
    print(f"[EMAIL] Attempting to send to {to_email}: {subject}", flush=True)
    
    # ---- Preferred: Resend HTTP API (production) ----
    if RESEND_API_KEY and EMAIL_FROM:
        try:
            resp = requests.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {RESEND_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": EMAIL_FROM,
                    "to": [to_email],
                    "subject": subject,
                    "text": body,
                },
                timeout=10,
            )
            if resp.status_code >= 400:
                print(
                    f"[EMAIL ERROR] Resend API error {resp.status_code}: {resp.text}",
                    flush=True,
                )
                # Fall through to SMTP
            else:
                print(f"[EMAIL] ✓ Sent via Resend to {to_email}", flush=True)
                return True
        except Exception as e:
            print(f"[EMAIL ERROR] Resend exception: {e}", flush=True)
            # Fall through to SMTP

    # ---- Fallback: SMTP (local dev) ----
    if not (SMTP_HOST and SMTP_PORT and SMTP_USER and SMTP_PASSWORD and EMAIL_FROM):
        print(
            "[EMAIL WARN] No email provider configured (Resend or SMTP). "
            "Email not sent (check logs for content).",
            flush=True,
        )
        return False

    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = EMAIL_FROM
        msg["To"] = to_email
        msg.set_content(body)

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)

        print(f"[EMAIL] ✓ Sent via SMTP to {to_email}", flush=True)
        return True
    except Exception as e:
        print(
            f"[EMAIL ERROR] SMTP failed for {to_email}: {e}",
            flush=True,
        )
        return False

def send_verification_email(to_email: str, code: str):
    """
    Sends a verification email with a 6-digit code.
    Uses Resend (production) or SMTP (local dev).
    """
    subject = "Star4ce – Verify your email"
    verify_url = f"{FRONTEND_URL}/verify?email={to_email}"
    
    body = f"""Hello,

Thank you for registering with Star4ce.

Your verification code is: {code}

Enter this code on the verification page to activate your account:
{verify_url}

If you did not request this, you can ignore this email.

This code expires in 1 hour.

– Star4ce
"""

    # Log verification code in development only (for testing)
    if os.getenv("ENVIRONMENT") != "production":
        print(f"[EMAIL DEBUG] Verification code for {to_email}: {code}", flush=True)
    
    send_email_via_resend_or_smtp(to_email, subject, body)

def send_verified_email(to_email: str):
    """
    Confirmation email once the account is verified.
    Uses Resend (production) or SMTP (local dev).
    """
    subject = "Star4ce – Your account is verified"
    login_url = f"{FRONTEND_URL}/login"
    
    body = f"""Hello,

Your Star4ce account ({to_email}) has been verified successfully.

You can now sign in here:
{login_url}

Welcome to Star4ce!

– Star4ce
"""

    send_email_via_resend_or_smtp(to_email, subject, body)

def send_reset_email(to_email: str, code: str):
    """
    Sends a password reset code email.
    Uses Resend (production) or SMTP (local dev).
    """
    subject = "Star4ce – Password reset code"
    reset_url = f"{FRONTEND_URL}/forgot?email={to_email}"
    
    body = f"""Hello,

We received a request to reset the password for your Star4ce account ({to_email}).

Your password reset code is: {code}
This code expires in 10 minutes.

Enter this code on the reset page:
{reset_url}

If you did not request this, you can ignore this email.

– Star4ce
"""

    # Log reset code in development only (for testing)
    if os.getenv("ENVIRONMENT") != "production":
        print(f"[EMAIL DEBUG] Reset code for {to_email}: {code}", flush=True)
    
    send_email_via_resend_or_smtp(to_email, subject, body)

def send_survey_invite_email(to_email: str, code: str):
    """
    Sends a survey invite email with the access code + link.
    Uses Resend (production) or SMTP (local dev).
    """
    subject = "Star4ce – Employee Experience Survey"
    survey_link = f"{FRONTEND_URL}/survey?code={code}"

    body = f"""Hello,

You have been invited to complete an anonymous Employee Experience Survey.

Your access code is: {code}

You can open the survey directly with this link:
{survey_link}

This code is unique to your dealership and may expire after a week.

Thank you for your honest feedback.

– Star4ce
"""

    send_email_via_resend_or_smtp(to_email, subject, body)

# Input validation helpers
def validate_email(email: str) -> bool:
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def validate_phone(phone: str) -> bool:
    """Validate phone number format (basic validation)"""
    if not phone:
        return True  # Phone is optional
    # Remove common formatting characters
    cleaned = re.sub(r'[\s\-\(\)\.]', '', phone)
    # Check if it's all digits and reasonable length (10-15 digits)
    return cleaned.isdigit() and 10 <= len(cleaned) <= 15

def validate_password(password: str) -> bool:
    """Validate password strength"""
    if len(password) < 8:
        return False
    # At least one letter and one number
    has_letter = bool(re.search(r'[a-zA-Z]', password))
    has_number = bool(re.search(r'\d', password))
    return has_letter and has_number

def sanitize_input(text: str, max_length: int = 255) -> str:
    """Sanitize user input"""
    if not text:
        return ""
    # Remove null bytes and control characters
    text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
    # Trim and limit length
    return text.strip()[:max_length]

def generate_csv_response(data: list, filename: str) -> Response:
    """Generate CSV response from list of dictionaries"""
    if not data:
        # Return empty CSV with headers
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["No data available"])
        output.seek(0)
        response = Response(output.getvalue(), mimetype='text/csv')
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        return response
    
    # Get headers from first row
    headers = list(data[0].keys())
    
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=headers)
    writer.writeheader()
    
    for row in data:
        # Convert any complex types to strings
        clean_row = {}
        for key, value in row.items():
            if value is None:
                clean_row[key] = ""
            elif isinstance(value, (dict, list)):
                clean_row[key] = json.dumps(value)
            elif isinstance(value, datetime.datetime):
                clean_row[key] = value.isoformat()
            else:
                clean_row[key] = str(value)
        writer.writerow(clean_row)
    
    output.seek(0)
    response = Response(output.getvalue(), mimetype='text/csv')
    response.headers['Content-Disposition'] = f'attachment; filename={filename}'
    return response

# ---- AUTH STUB (no DB yet) ----
@app.post("/auth/login")
@limiter.limit("5 per minute")
def login():
    data = request.get_json(force=True) or {}
    email = sanitize_input(data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify(error="Please enter both email and password"), 400
    
    if not validate_email(email):
        return jsonify(error="Please enter a valid email address"), 400

    

    # Look up user in DB
    user = User.query.filter_by(email=email).first()
    if not user:
        # Do not reveal which part is wrong
        return jsonify(error="invalid credentials"), 401

    # Check password first (before checking verification status)
    # This way we can give better feedback
    if not check_password_hash(user.password_hash, password):
        return jsonify(error="invalid credentials"), 401

    # Auto-upgrade users with active subscriptions to admin
    # This handles cases where webhook didn't fire or user subscribed before webhook was set up
    if user.role == "manager" and user.dealership_id:
        dealership = Dealership.query.get(user.dealership_id)
        if dealership and dealership.is_subscription_active():
            # User has active subscription but is still manager - upgrade to admin
            user.role = "admin"
            user.is_verified = True
            user.is_approved = True
            if not user.approved_at:
                user.approved_at = datetime.datetime.utcnow()
            db.session.commit()
            print(f"[AUTO-UPGRADE] User {user.email} auto-upgraded to admin on login (has active subscription)", flush=True)
    elif user.role == "manager" and not user.dealership_id:
        # Check if user has any dealership with active subscription (by email matching Stripe customer)
        if STRIPE_AVAILABLE and STRIPE_SECRET_KEY:
            try:
                # Try to find dealership by Stripe customer email
                dealerships = Dealership.query.filter(
                    Dealership.stripe_customer_id.isnot(None)
                ).all()
                for dealership in dealerships:
                    if dealership.stripe_customer_id:
                        try:
                            customer = stripe.Customer.retrieve(dealership.stripe_customer_id)
                            if customer.get("email") == user.email and dealership.is_subscription_active():
                                # User has active subscription - upgrade and assign
                                user.role = "admin"
                                user.dealership_id = dealership.id
                                user.is_verified = True
                                user.is_approved = True
                                if not user.approved_at:
                                    user.approved_at = datetime.datetime.utcnow()
                                db.session.commit()
                                print(f"[AUTO-UPGRADE] User {user.email} auto-upgraded to admin on login (found by Stripe customer)", flush=True)
                                break
                        except:
                            pass  # Skip if Stripe customer lookup fails
            except:
                pass  # Skip if Stripe is not available

    # Password is correct, now check verification
    if not user.is_verified:
        # generate a fresh verification code and resend
        code_int = secrets.randbelow(1_000_000)  # 0..999999
        verification_code = f"{code_int:06d}"
        expires_at = datetime.datetime.utcnow() + datetime.timedelta(hours=1)

        user.verification_code = verification_code
        user.verification_expires_at = expires_at
        db.session.commit()

        send_verification_email(user.email, verification_code)

        return jsonify(
            error="unverified",
            message="Your email is not verified yet. A new verification code has been sent to your email."
        ), 403

    # Issue JWT based on DB user (will now have updated role if auto-upgraded)
    token = make_token(user.email, user.role)

    return jsonify(
        token=token,
        role=user.role,
        email=user.email
    )

# ---- AUTH REGISTER STUB (no DB yet) ----
@app.get("/public/dealerships")
@limiter.limit("30 per minute")
def get_public_dealerships():
    """
    Public endpoint to list all dealerships.
    Used for manager registration to select a dealership.
    """
    dealerships = Dealership.query.order_by(Dealership.name).all()
    return jsonify(
        ok=True,
        dealerships=[{
            "id": d.id,
            "name": d.name,
            "city": d.city,
            "state": d.state,
            "address": d.address,
        } for d in dealerships]
    )

@app.post("/auth/register")
@limiter.limit("3 per hour")
def register():
    try:
        data = request.get_json(force=True) or {}
        email = sanitize_input(data.get("email") or "").strip().lower()
        password = data.get("password") or ""
        dealership_id = data.get("dealership_id")  # Optional for manager registration
        is_admin_registration = data.get("is_admin_registration", False)  # Flag for admin registration via subscription

        if not email or not password:
            return jsonify(error="Please enter both email and password"), 400
        
        if not validate_email(email):
            return jsonify(error="Please enter a valid email address"), 400

        if not validate_password(password):
            return jsonify(error="Password must be at least 8 characters and include both letters and numbers"), 400

        existing = User.query.filter_by(email=email).first()
        if existing:
            # If this is an admin registration and the existing user is a pending admin registration
            # (manager, not verified, not approved, no dealership), clean them up and allow re-registration
            if (is_admin_registration and 
                existing.role == "manager" and 
                not existing.is_verified and 
                not existing.is_approved and 
                not existing.dealership_id):
                # This is a pending admin registration that was never completed - delete it
                db.session.delete(existing)
                db.session.commit()
                # Continue with registration below
            else:
                # User exists and is not a pending admin registration - they should sign in
                return jsonify(error="This email is already registered. Please sign in instead."), 400

        # Determine role from request or default to manager
        requested_role = data.get("role", "").strip().lower()
        if requested_role in ("manager", "corporate"):
            role = requested_role
        else:
            # Default to manager for public registration
            # If is_admin_registration is True, user will be upgraded to admin after Stripe payment.
            role = "manager"

        # For manager registration, validate dealership_id but don't assign directly - create a request instead
        manager_request_id = None
        if dealership_id and not is_admin_registration and role == "manager":
            dealership = Dealership.query.get(dealership_id)
            if not dealership:
                return jsonify(error="Invalid dealership selected"), 400

        # Generate 6-digit verification code
        code_int = secrets.randbelow(1_000_000)  # 0..999999
        verification_code = f"{code_int:06d}"
        expires_at = datetime.datetime.utcnow() + datetime.timedelta(hours=1)

        # Get full_name for admin registration
        full_name = None
        if is_admin_registration:
            full_name = data.get("full_name", "").strip() or None
        
        user = User(
            email=email,
            password_hash=generate_password_hash(password),
            role=role,
            full_name=full_name,
            dealership_id=None,  # Managers don't get assigned directly - they must request access
            is_approved=False,  # Managers need admin approval (will be auto-approved after payment for admin registration)
            is_verified=False,  # Will be auto-verified after payment for admin registration
            verification_code=verification_code,
            verification_expires_at=expires_at,
        )

        db.session.add(user)
        db.session.flush()  # Get the user ID

        # For manager registration, create a dealership access request
        if dealership_id and not is_admin_registration and role == "manager":
            manager_request = ManagerDealershipRequest(
                manager_id=user.id,
                dealership_id=dealership_id,
                status="pending"
            )
            db.session.add(manager_request)
            db.session.flush()
            manager_request_id = manager_request.id

        db.session.commit()

        # Send verification email for both admin and manager registration
        # Admin must verify email first, then subscribe
        send_verification_email(user.email, verification_code)
        if is_admin_registration:
            message = "Verification code sent to your email. Please verify your email, then you'll be redirected to subscribe and become an admin."
        elif manager_request_id:
            message = "Verification code sent to your email. Please verify before logging in. Your request to join the dealership is pending admin approval."
        else:
            message = "Verification code sent to your email. Please verify before logging in."

        # Do NOT log them in yet; they must verify first (or complete payment for admin registration).
        return jsonify(
            ok=True,
            email=user.email,
            role=user.role,
            dealership_id=dealership_id,
            user_id=user.id,  # Return user_id for checkout session
            message=message
        )
    except Exception as e:
        db.session.rollback()
        print(f"[REGISTER ERROR] {str(e)}", flush=True)
        import traceback
        traceback.print_exc()
        return jsonify(error=f"Registration failed: {str(e)}"), 500

@app.get("/auth/me")
def me():
    """Verify token and return user info"""
    auth = request.headers.get("authorization", "") or request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return jsonify(error="missing bearer token"), 401
    
    token = auth.split(" ", 1)[1].strip()
    if not token:
        return jsonify(error="empty token"), 401
    
    try:
        claims = verify_token(token)
        # Also verify user exists and is verified
        email = claims.get("sub")
        if not email:
            return jsonify(error="invalid token payload"), 401
        
        user = User.query.filter_by(email=email).first()
        if not user:
            return jsonify(error="user not found"), 401
        
        # Auto-upgrade users with active subscriptions to admin
        # This handles cases where webhook didn't fire or user subscribed before webhook was set up
        if user.role == "manager" and user.dealership_id:
            dealership = Dealership.query.get(user.dealership_id)
            if dealership and dealership.is_subscription_active():
                # User has active subscription but is still manager - upgrade to admin
                user.role = "admin"
                user.is_verified = True
                user.is_approved = True
                if not user.approved_at:
                    user.approved_at = datetime.datetime.utcnow()
                db.session.commit()
                print(f"[AUTO-UPGRADE] User {user.email} auto-upgraded to admin in /auth/me (has active subscription)", flush=True)
        elif user.role == "manager" and not user.dealership_id:
            # Check if user has any dealership with active subscription (by email matching Stripe customer)
            if STRIPE_AVAILABLE and STRIPE_SECRET_KEY:
                try:
                    # First, try to find dealership by Stripe customer email in database
                    dealerships = Dealership.query.filter(
                        Dealership.stripe_customer_id.isnot(None)
                    ).all()
                    for dealership in dealerships:
                        if dealership.stripe_customer_id:
                            try:
                                customer = stripe.Customer.retrieve(dealership.stripe_customer_id)
                                if customer.get("email") == user.email and dealership.is_subscription_active():
                                    # User has active subscription - upgrade and assign
                                    user.role = "admin"
                                    user.dealership_id = dealership.id
                                    user.is_verified = True
                                    user.is_approved = True
                                    if not user.approved_at:
                                        user.approved_at = datetime.datetime.utcnow()
                                    db.session.commit()
                                    print(f"[AUTO-UPGRADE] User {user.email} auto-upgraded to admin in /auth/me (found by Stripe customer)", flush=True)
                                    break
                            except:
                                pass  # Skip if Stripe customer lookup fails
                    
                    # If not found, try querying Stripe directly for customers with this email
                    if user.role == "manager":
                        try:
                            customers = stripe.Customer.list(email=user.email, limit=10)
                            for customer in customers.data:
                                # Check if this customer has an active subscription
                                subscriptions = stripe.Subscription.list(customer=customer.id, status="active", limit=1)
                                if subscriptions.data:
                                    # Customer has active subscription - create or find dealership
                                    dealership = Dealership.query.filter_by(stripe_customer_id=customer.id).first()
                                    if not dealership:
                                        # Create new dealership for this subscription
                                        subscription = subscriptions.data[0]
                                        dealership = Dealership(
                                            name=f"{user.full_name or user.email}'s Dealership",
                                            subscription_status="active",
                                            subscription_plan="pro",
                                            stripe_customer_id=customer.id,
                                            stripe_subscription_id=subscription.id,
                                            trial_ends_at=None,
                                        )
                                        if subscription.get("current_period_end"):
                                            dealership.subscription_ends_at = datetime.datetime.fromtimestamp(subscription.current_period_end)
                                        else:
                                            dealership.subscription_ends_at = datetime.datetime.utcnow() + datetime.timedelta(days=30)
                                        db.session.add(dealership)
                                        db.session.flush()
                                    
                                    # Upgrade user to admin
                                    user.role = "admin"
                                    user.dealership_id = dealership.id
                                    user.is_verified = True
                                    user.is_approved = True
                                    if not user.approved_at:
                                        user.approved_at = datetime.datetime.utcnow()
                                    db.session.commit()
                                    print(f"[AUTO-UPGRADE] User {user.email} auto-upgraded to admin in /auth/me (found active Stripe subscription)", flush=True)
                                    break
                        except Exception as e:
                            print(f"[AUTO-UPGRADE] Error querying Stripe: {e}", flush=True)
                            pass  # Skip if Stripe query fails
                except:
                    pass  # Skip if Stripe is not available

        if not user.is_verified:
            return jsonify(error="unverified"), 403
        
        # Return role from database (not from token) since it may have been auto-upgraded
        return jsonify(ok=True, user={"email": user.email, "role": user.role})
    except ValueError as e:
        # Token expired or invalid
        error_msg = str(e)
        if "expired" in error_msg.lower():
            return jsonify(error="token expired"), 401
        return jsonify(error="invalid token"), 401
    except Exception as e:
        # Any other error
        print(f"[AUTH ERROR] /auth/me failed: {e}", flush=True)
        return jsonify(error="invalid token"), 401
    
@app.get("/analytics/time-series")
@limiter.limit("30 per minute")
def analytics_time_series():
    """
    Returns survey responses over time (grouped by day/week/month).
    Admin sees their dealership, corporate sees all.
    """
    user, err = get_current_user()
    if err:
        return err

    if user.role not in ("admin", "corporate"):
        return jsonify(error="forbidden – insufficient role"), 403

    # Get date range from query params (default: last 30 days)
    days = int(request.args.get("days", 30))
    group_by = request.args.get("group_by", "day")  # day, week, month

    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=days)

    if user.role == "corporate":
        # Corporate users see only their assigned dealerships
        accessible_dealership_ids = get_accessible_dealership_ids(user)
        if not accessible_dealership_ids:
            return jsonify(ok=True, items=[])
        base_q = (
            db.session.query(SurveyResponse)
            .join(SurveyAccessCode, SurveyAccessCode.code == SurveyResponse.access_code)
            .filter(
                SurveyAccessCode.dealership_id.in_(accessible_dealership_ids),
                SurveyResponse.created_at >= cutoff
            )
        )
    else:
        if not user.dealership_id:
            return jsonify(ok=True, items=[])
        base_q = (
            db.session.query(SurveyResponse)
            .join(SurveyAccessCode, SurveyAccessCode.code == SurveyResponse.access_code)
            .filter(
                SurveyAccessCode.dealership_id == user.dealership_id,
                SurveyResponse.created_at >= cutoff
            )
        )

    # Group by time period
    responses = base_q.order_by(SurveyResponse.created_at.asc()).all()
    
    # Group responses by time period
    time_series = {}
    for resp in responses:
        if group_by == "day":
            key = resp.created_at.strftime("%Y-%m-%d")
        elif group_by == "week":
            # Get week start (Monday)
            week_start = resp.created_at - datetime.timedelta(days=resp.created_at.weekday())
            key = week_start.strftime("%Y-%m-%d")
        else:  # month
            key = resp.created_at.strftime("%Y-%m")
        
        if key not in time_series:
            time_series[key] = 0
        time_series[key] += 1

    # Convert to sorted list
    items = [{"date": k, "count": v} for k, v in sorted(time_series.items())]

    return jsonify(ok=True, items=items, group_by=group_by, days=days)

@app.get("/analytics/averages")
@limiter.limit("30 per minute")
def analytics_averages():
    """
    Returns average satisfaction and training scores.
    """
    user, err = get_current_user()
    if err:
        return err

    if user.role not in ("admin", "corporate"):
        return jsonify(error="forbidden – insufficient role"), 403

    cutoff_30 = datetime.datetime.utcnow() - datetime.timedelta(days=30)

    if user.role == "corporate":
        # Corporate users see only their assigned dealerships
        accessible_dealership_ids = get_accessible_dealership_ids(user)
        if not accessible_dealership_ids:
            return jsonify(ok=True, satisfaction_avg=0, training_avg=0, total_responses=0)
        base_q = (
            db.session.query(SurveyResponse)
            .join(SurveyAccessCode, SurveyAccessCode.code == SurveyResponse.access_code)
            .filter(
                SurveyAccessCode.dealership_id.in_(accessible_dealership_ids),
                SurveyResponse.created_at >= cutoff_30
            )
        )
    else:
        if not user.dealership_id:
            return jsonify(ok=True, satisfaction_avg=0, training_avg=0, total_responses=0)
        base_q = (
            db.session.query(SurveyResponse)
            .join(SurveyAccessCode, SurveyAccessCode.code == SurveyResponse.access_code)
            .filter(
                SurveyAccessCode.dealership_id == user.dealership_id,
                SurveyResponse.created_at >= cutoff_30
            )
        )

    responses = base_q.all()

    # Calculate averages
    satisfaction_scores = []
    training_scores = []

    for resp in responses:
        if resp.satisfaction_answers:
            # satisfaction_answers is a dict like {0: "Very Satisfied", 1: "Satisfied", ...}
            # Map to numeric scores: Very Satisfied=5, Satisfied=4, Neutral=3, Dissatisfied=2, Very Dissatisfied=1
            score_map = {
                "Very Satisfied": 5,
                "Satisfied": 4,
                "Neutral": 3,
                "Dissatisfied": 2,
                "Very Dissatisfied": 1,
            }
            for answer in resp.satisfaction_answers.values():
                if answer in score_map:
                    satisfaction_scores.append(score_map[answer])

        if resp.training_answers:
            for answer in resp.training_answers.values():
                if answer in score_map:
                    training_scores.append(score_map[answer])

    satisfaction_avg = sum(satisfaction_scores) / len(satisfaction_scores) if satisfaction_scores else 0
    training_avg = sum(training_scores) / len(training_scores) if training_scores else 0

    return jsonify(
        ok=True,
        satisfaction_avg=round(satisfaction_avg, 2),
        training_avg=round(training_avg, 2),
        total_responses=len(responses),
        satisfaction_count=len(satisfaction_scores),
        training_count=len(training_scores),
    )

@app.get("/analytics/role-breakdown")
@limiter.limit("30 per minute")
def analytics_role_breakdown():
    """
    Returns survey responses broken down by employee role/department.
    """
    user, err = get_current_user()
    if err:
        return err

    if user.role not in ("admin", "corporate"):
        return jsonify(error="forbidden – insufficient role"), 403

    cutoff_30 = datetime.datetime.utcnow() - datetime.timedelta(days=30)

    if user.role == "corporate":
        # Corporate users see only their assigned dealerships
        accessible_dealership_ids = get_accessible_dealership_ids(user)
        if not accessible_dealership_ids:
            return jsonify(ok=True, breakdown={})
        base_q = (
            db.session.query(SurveyResponse)
            .join(SurveyAccessCode, SurveyAccessCode.code == SurveyResponse.access_code)
            .filter(
                SurveyAccessCode.dealership_id.in_(accessible_dealership_ids),
                SurveyResponse.created_at >= cutoff_30
            )
        )
    else:
        if not user.dealership_id:
            return jsonify(ok=True, breakdown={})
        base_q = (
            db.session.query(SurveyResponse)
            .join(SurveyAccessCode, SurveyAccessCode.code == SurveyResponse.access_code)
            .filter(
                SurveyAccessCode.dealership_id == user.dealership_id,
                SurveyResponse.created_at >= cutoff_30
            )
        )

    responses = base_q.all()

    # Group by role
    breakdown = {}
    for resp in responses:
        role = resp.role or "Unknown"
        if role not in breakdown:
            breakdown[role] = {
                "count": 0,
                "by_status": {"newly-hired": 0, "termination": 0, "leave": 0, "none": 0},
            }
        breakdown[role]["count"] += 1
        if resp.employee_status in breakdown[role]["by_status"]:
            breakdown[role]["by_status"][resp.employee_status] += 1

    return jsonify(ok=True, breakdown=breakdown)

@app.get("/analytics/summary")
@limiter.limit("30 per minute")
def analytics_summary():
    """
    Protected endpoint.

    - Only verified 'admin' or 'corporate' users can access
    - 'admin' sees data for THEIR dealership only
    - 'corporate' sees overall totals across all dealerships

    Uses SurveyResponse + SurveyAccessCode so survey answers are tied
    to the correct dealership via access_code.
    """
    try:
        user, err = get_current_user()
        if err:
            return err  # 401 / 403

        # Check subscription limits for admin users
        if user.role == "admin" and user.dealership_id:
            dealership = Dealership.query.get(user.dealership_id)
            if dealership and not dealership.is_subscription_active():
                return jsonify(
                    error="subscription_expired",
                    message="Your subscription has expired. Please renew to view analytics."
                ), 403

        if user.role not in ("admin", "corporate"):
            return jsonify(error="forbidden – insufficient role"), 403

        # last 30 days window
        cutoff_30 = datetime.datetime.utcnow() - datetime.timedelta(days=30)

        if user.role == "corporate":
            # Corporate users see only their assigned dealerships
            accessible_dealership_ids = get_accessible_dealership_ids(user)
            
            if not accessible_dealership_ids:
                return jsonify(
                    ok=True,
                    scope="corporate",
                    total_dealerships=0,
                    total_answers=0,
                    total_responses=0,
                    last_30_days=0,
                    message="No dealerships assigned. Please contact an administrator."
                )
            
            # Filter responses by assigned dealerships via access codes
            base_q = (
                db.session.query(SurveyResponse)
                .join(SurveyAccessCode, SurveyAccessCode.code == SurveyResponse.access_code)
                .filter(SurveyAccessCode.dealership_id.in_(accessible_dealership_ids))
            )
            
            total_responses = base_q.count()
            last_30 = base_q.filter(SurveyResponse.created_at >= cutoff_30).count()

            return jsonify(
                ok=True,
                scope="corporate",
                total_dealerships=len(accessible_dealership_ids),
                total_answers=total_responses,   # keep old name for frontend
                total_responses=total_responses, # extra, if we want later
                last_30_days=last_30,
            )

        # --- admin branch ---
        if not user.dealership_id:
            return jsonify(
                ok=True,
                scope="admin",
                message="No dealership assigned to this admin yet.",
                total_answers=0,
                total_responses=0,
                last_30_days=0,
                by_status={},
            )

        # Join SurveyResponse -> SurveyAccessCode by access_code
        base_q = (
            db.session.query(SurveyResponse)
            .join(SurveyAccessCode, SurveyAccessCode.code == SurveyResponse.access_code)
            .filter(SurveyAccessCode.dealership_id == user.dealership_id)
        )

        total_responses = base_q.count()
        last_30 = base_q.filter(SurveyResponse.created_at >= cutoff_30).count()

        # small breakdown by employee_status
        status_counts = {
            "newly-hired": base_q.filter(SurveyResponse.employee_status == "newly-hired").count(),
            "termination": base_q.filter(SurveyResponse.employee_status == "termination").count(),
            "leave": base_q.filter(SurveyResponse.employee_status == "leave").count(),
            "none": base_q.filter(SurveyResponse.employee_status == "none").count(),
        }

        return jsonify(
            ok=True,
            scope="admin",
            dealership_id=user.dealership_id,
            total_answers=total_responses,   # same name as before for frontend
            total_responses=total_responses,
            last_30_days=last_30,
            by_status=status_counts,
        )
    except Exception as e:
        print(f"[ANALYTICS ERROR] Error in analytics_summary: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return jsonify(error=f"Internal server error: {str(e)}"), 500

@app.get("/audit-logs")
@limiter.limit("30 per minute")
def get_audit_logs():
    """
    Protected endpoint to retrieve admin audit logs.
    
    - Only verified 'admin' or 'corporate' users can access
    - 'admin' sees logs for their dealership only (via user email matching)
    - 'corporate' sees all audit logs across all dealerships
    
    Query parameters:
    - limit: Maximum number of logs to return (default: 100, max: 500)
    - offset: Number of logs to skip for pagination (default: 0)
    - action: Filter by action type (optional)
    - resource_type: Filter by resource type (optional)
    """
    try:
        user, err = get_current_user()
        if err:
            return err  # 401 / 403

        if user.role not in ("admin", "corporate"):
            return jsonify(error="forbidden – insufficient role"), 403

        # Get query parameters
        limit = min(int(request.args.get("limit", 100)), 500)  # Max 500
        offset = int(request.args.get("offset", 0))
        action_filter = request.args.get("action")
        resource_type_filter = request.args.get("resource_type")

        # Build query
        if user.role == "corporate":
            # Corporate sees all logs
            query = AdminAuditLog.query
        else:
            # Admin sees only their own actions (by email)
            query = AdminAuditLog.query.filter_by(admin_email=user.email)

        # Apply filters
        if action_filter:
            query = query.filter_by(action=action_filter)
        if resource_type_filter:
            query = query.filter_by(resource_type=resource_type_filter)

        # Order by most recent first
        query = query.order_by(AdminAuditLog.created_at.desc())

        # Get total count before pagination
        total_count = query.count()

        # Apply pagination
        logs = query.limit(limit).offset(offset).all()

        return jsonify(
            ok=True,
            logs=[log.to_dict() for log in logs],
            total=total_count,
            limit=limit,
            offset=offset,
        )
    except Exception as e:
        print(f"[AUDIT LOGS ERROR] Error retrieving audit logs: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return jsonify(error=f"Internal server error: {str(e)}"), 500

@app.get("/survey/responses/export")
@limiter.limit("10 per minute")
def export_survey_responses():
    """Admin-only: Export survey responses as CSV"""
    user, err = get_current_user()
    if err:
        return err

    if user.role not in ("admin", "corporate"):
        return jsonify(error="only admins can export survey responses"), 403

    # Check subscription limits for admin users
    if user.role == "admin" and user.dealership_id:
        dealership = Dealership.query.get(user.dealership_id)
        if dealership and not dealership.is_subscription_active():
            return jsonify(
                error="subscription_expired",
                message="Your subscription has expired. Please renew to export data."
            ), 403

    # Get date range from query params (optional)
    days = int(request.args.get("days", 0))  # 0 = all time
    cutoff = None
    if days > 0:
        cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=days)

    # Query responses based on role
    if user.role == "corporate":
        # Corporate users see only their assigned dealerships
        accessible_dealership_ids = get_accessible_dealership_ids(user)
        if not accessible_dealership_ids:
            return jsonify(error="no dealerships assigned"), 400
        
        if cutoff:
            base_q = (
                db.session.query(SurveyResponse)
                .join(SurveyAccessCode, SurveyAccessCode.code == SurveyResponse.access_code)
                .filter(
                    SurveyAccessCode.dealership_id.in_(accessible_dealership_ids),
                    SurveyResponse.created_at >= cutoff
                )
            )
        else:
            base_q = (
                db.session.query(SurveyResponse)
                .join(SurveyAccessCode, SurveyAccessCode.code == SurveyResponse.access_code)
                .filter(SurveyAccessCode.dealership_id.in_(accessible_dealership_ids))
            )
    else:
        if not user.dealership_id:
            return jsonify(error="admin has no dealership assigned"), 400
        
        if cutoff:
            base_q = (
                db.session.query(SurveyResponse)
                .join(SurveyAccessCode, SurveyAccessCode.code == SurveyResponse.access_code)
                .filter(
                    SurveyAccessCode.dealership_id == user.dealership_id,
                    SurveyResponse.created_at >= cutoff
                )
            )
        else:
            base_q = (
                db.session.query(SurveyResponse)
                .join(SurveyAccessCode, SurveyAccessCode.code == SurveyResponse.access_code)
                .filter(SurveyAccessCode.dealership_id == user.dealership_id)
            )

    responses = base_q.order_by(SurveyResponse.created_at.desc()).all()

    # Prepare data for CSV
    csv_data = []
    for resp in responses:
        # Flatten satisfaction answers
        satisfaction_str = ", ".join([f"Q{k}: {v}" for k, v in (resp.satisfaction_answers or {}).items()])
        training_str = ", ".join([f"Q{k}: {v}" for k, v in (resp.training_answers or {}).items()]) if resp.training_answers else ""
        
        csv_data.append({
            "ID": resp.id,
            "Access Code": resp.access_code,
            "Employee Status": resp.employee_status,
            "Role/Department": resp.role,
            "Termination Reason": resp.termination_reason or "",
            "Termination Other": resp.termination_other or "",
            "Leave Reason": resp.leave_reason or "",
            "Leave Other": resp.leave_other or "",
            "Satisfaction Answers": satisfaction_str,
            "Training Answers": training_str,
            "Additional Feedback": resp.additional_feedback or "",
            "Submitted At": resp.created_at.isoformat(),
        })

    # Generate filename with timestamp
    timestamp = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"survey_responses_export_{timestamp}.csv"

    # Log admin action
    log_admin_action(
        user.email,
        "export_survey_responses",
        "survey_response",
        None,
        json.dumps({"count": len(csv_data), "days": days})
    )

    return generate_csv_response(csv_data, filename)

@app.get("/analytics/export")
@limiter.limit("10 per minute")
def export_analytics():
    """Admin-only: Export analytics summary as CSV"""
    user, err = get_current_user()
    if err:
        return err

    if user.role not in ("admin", "corporate"):
        return jsonify(error="only admins can export analytics"), 403

    # Check subscription limits for admin users
    if user.role == "admin" and user.dealership_id:
        dealership = Dealership.query.get(user.dealership_id)
        if dealership and not dealership.is_subscription_active():
            return jsonify(
                error="subscription_expired",
                message="Your subscription has expired. Please renew to export data."
            ), 403

    # Get date range from query params
    days = int(request.args.get("days", 30))
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=days)

    # Query responses based on role
    if user.role == "corporate":
        # Corporate users see only their assigned dealerships
        accessible_dealership_ids = get_accessible_dealership_ids(user)
        if not accessible_dealership_ids:
            return jsonify(error="no dealerships assigned"), 400
        base_q = (
            db.session.query(SurveyResponse)
            .join(SurveyAccessCode, SurveyAccessCode.code == SurveyResponse.access_code)
            .filter(
                SurveyAccessCode.dealership_id.in_(accessible_dealership_ids),
                SurveyResponse.created_at >= cutoff
            )
        )
    else:
        if not user.dealership_id:
            return jsonify(error="admin has no dealership assigned"), 400
        base_q = (
            db.session.query(SurveyResponse)
            .join(SurveyAccessCode, SurveyAccessCode.code == SurveyResponse.access_code)
            .filter(
                SurveyAccessCode.dealership_id == user.dealership_id,
                SurveyResponse.created_at >= cutoff
            )
        )

    responses = base_q.all()

    # Calculate analytics
    total_responses = len(responses)
    status_counts = {"newly-hired": 0, "termination": 0, "leave": 0, "none": 0}
    role_counts = {}
    
    for resp in responses:
        # Count by status
        if resp.employee_status in status_counts:
            status_counts[resp.employee_status] += 1
        
        # Count by role
        role = resp.role or "Unknown"
        role_counts[role] = role_counts.get(role, 0) + 1

    # Prepare data for CSV
    csv_data = [
        {"Metric": "Total Responses", "Value": total_responses, "Period": f"Last {days} days"},
        {"Metric": "Newly Hired", "Value": status_counts["newly-hired"], "Period": f"Last {days} days"},
        {"Metric": "Terminations", "Value": status_counts["termination"], "Period": f"Last {days} days"},
        {"Metric": "Leave", "Value": status_counts["leave"], "Period": f"Last {days} days"},
        {"Metric": "None", "Value": status_counts["none"], "Period": f"Last {days} days"},
    ]
    
    # Add role breakdown
    for role, count in sorted(role_counts.items(), key=lambda x: x[1], reverse=True):
        csv_data.append({"Metric": f"Role: {role}", "Value": count, "Period": f"Last {days} days"})

    # Generate filename with timestamp
    timestamp = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"analytics_export_{timestamp}.csv"

    # Log admin action
    log_admin_action(
        user.email,
        "export_analytics",
        "analytics",
        None,
        json.dumps({"days": days, "total_responses": total_responses})
    )

    return generate_csv_response(csv_data, filename)

@app.post("/auth/verify")
@limiter.limit("10 per minute")
def verify_email():
    data = request.get_json(force=True) or {}
    email = sanitize_input(data.get("email") or "").strip().lower()
    code = sanitize_input(data.get("code") or "", max_length=6).strip()
    
    if not validate_email(email):
        return jsonify(error="Please enter a valid email address"), 400

    if not email or not code:
        return jsonify(error="Please enter both email and verification code"), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify(error="user not found"), 404

    if user.is_verified:
        return jsonify(ok=True, message="Already verified")

    if user.verification_code != code:
        return jsonify(error="Invalid verification code. Please check and try again."), 400

    if user.verification_expires_at and user.verification_expires_at < datetime.datetime.utcnow():
        return jsonify(error="Verification code has expired. Please request a new one."), 400

    user.is_verified = True
    user.verification_code = None
    user.verification_expires_at = None
    db.session.commit()

    # Check if this is an admin registration (manager role, no dealership, not approved yet, no pending request)
    # Admin registration = manager with no dealership and no pending manager request
    has_pending_request = ManagerDealershipRequest.query.filter_by(
        manager_id=user.id,
        status="pending"
    ).first() is not None
    
    is_admin_registration = (user.role == "manager" and 
                             not user.dealership_id and 
                             not user.is_approved and
                             not has_pending_request)
    
    if is_admin_registration:
        # Admin registration - they need to subscribe
        # Don't send verified email yet, they need to subscribe first
        return jsonify(
            ok=True, 
            message="Email verified successfully. Please subscribe to become an admin.",
            redirect_to_subscription=True
        )
    elif user.role == "manager" and has_pending_request:
        # Manager with pending request - they need to wait for admin approval
        send_verified_email(user.email)
        return jsonify(
            ok=True, 
            message="Email verified successfully. Your request to join the dealership is pending admin approval. Please wait for an admin to approve your request.",
            is_manager_pending=True
        )
    else:
        # Regular verification - send confirmation email
        send_verified_email(user.email)
        return jsonify(ok=True, message="Email verified successfully")

@app.post("/auth/resend-verify")
@limiter.limit("3 per hour")
def resend_verify():
    data = request.get_json(force=True) or {}
    email = sanitize_input(data.get("email") or "").strip().lower()

    if not email:
        return jsonify(error="email is required"), 400
    
    if not validate_email(email):
        return jsonify(error="invalid email format"), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify(error="user not found"), 400

    if user.is_verified:
        return jsonify(error="already verified"), 400

    # New 6-digit code
    code_int = secrets.randbelow(1_000_000)
    verification_code = f"{code_int:06d}"
    expires_at = datetime.datetime.utcnow() + datetime.timedelta(hours=1)

    user.verification_code = verification_code
    user.verification_expires_at = expires_at
    db.session.commit()

    send_verification_email(user.email, verification_code)

    return jsonify(ok=True, message="Verification code resent")

@app.post("/auth/request-reset")
@limiter.limit("3 per hour")
def request_reset():
    data = request.get_json(force=True) or {}
    email = sanitize_input(data.get("email") or "").strip().lower()

    if not email:
        return jsonify(error="email required"), 400
    
    if not validate_email(email):
        return jsonify(error="invalid email format"), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        # In prod you might return ok=True to avoid leaking which emails exist
        return jsonify(error="no account with that email"), 404

    # Generate a 6-digit reset code
    reset_code = f"{random.randint(0, 999999):06d}"
    expires_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=10)

    user.reset_code = reset_code
    user.reset_code_expires_at = expires_at
    db.session.commit()

    # Send via email
    send_reset_email(user.email, reset_code)

    # Still return in JSON for dev/testing
    return jsonify(
        ok=True,
        reset_code=reset_code,
        expires_at=expires_at.isoformat() + "Z",
    )

@app.post("/auth/reset")
@limiter.limit("5 per hour")
def reset_password():
    data = request.get_json(force=True) or {}
    email = sanitize_input(data.get("email") or "").strip().lower()
    code = sanitize_input(data.get("code") or "", max_length=6).strip()
    new_password = data.get("new_password") or ""

    if not email or not code or not new_password:
        return jsonify(error="email, code, and new_password required"), 400

    if not validate_email(email):
        return jsonify(error="invalid email format"), 400

    if not validate_password(new_password):
        return jsonify(error="password must be at least 8 characters with letters and numbers"), 400

    user = User.query.filter_by(email=email).first()
    if not user or not user.reset_code or user.reset_code != code:
        return jsonify(error="invalid code or email"), 400

    # Check expiration
    if user.reset_code_expires_at and user.reset_code_expires_at < datetime.datetime.utcnow():
        return jsonify(error="reset code expired"), 400

    # Update password
    user.password_hash = generate_password_hash(new_password)
    user.reset_code = None
    user.reset_code_expires_at = None
    db.session.commit()

    # Optional: log them in immediately with a new token
    token = make_token(user.email, user.role)

    return jsonify(
        ok=True,
        token=token,
        email=user.email,
        role=user.role,
    )

def generate_access_code(length: int = 8) -> str:
    """
    Generate a human-friendly code: no 0/O/1/I to avoid confusion.
    Example: 7K2F9QBD
    """
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))

@app.post("/survey/access-codes")
def create_access_code():
    """
    Admin-only endpoint.
    Creates a new survey access code for the admin's dealership.
    If admin doesn't have a dealership, creates one automatically.
    """
    try:
        user, err = get_current_user()
        if err:
            return err  # 401 / 403

        # Check permission
        if not has_permission(user, "create_survey"):
            return jsonify(error="you do not have permission to create surveys"), 403

        # Check subscription limits
        if user.dealership_id:
            dealership = Dealership.query.get(user.dealership_id)
            if dealership and not dealership.is_subscription_active():
                return jsonify(
                    error="subscription_expired",
                    message="Your subscription has expired. Please renew to create access codes."
                ), 403

        # If admin doesn't have a dealership, create one automatically
        if not user.dealership_id:
            # Create a default dealership for this admin with 14-day trial
            now = datetime.datetime.utcnow()
            dealership = Dealership(
                name=f"Dealership for {user.email}",
                address=None,
                subscription_status="trial",
                trial_ends_at=now + datetime.timedelta(days=14),
                city=None,
                state=None,
                zip_code=None,
                created_at=now,
                updated_at=now,
            )
            db.session.add(dealership)
            db.session.flush()  # Get the ID without committing
            
            # Assign the dealership to the admin
            user.dealership_id = dealership.id
            db.session.commit()
        else:
            # Ensure the dealership still exists
            dealership = Dealership.query.get(user.dealership_id)
            if not dealership:
                # Dealership was deleted, create a new one
                now = datetime.datetime.utcnow()
                dealership = Dealership(
                    name=f"Dealership for {user.email}",
                    address=None,
                    city=None,
                    state=None,
                    zip_code=None,
                    subscription_status="trial",
                    trial_ends_at=now + datetime.timedelta(days=14),
                    created_at=now,
                    updated_at=now,
                )
                db.session.add(dealership)
                db.session.flush()
                user.dealership_id = dealership.id
                db.session.commit()

        # Optional: read an expiry from the request body (in hours), else None
        data = request.get_json(silent=True) or {}
        hours = data.get("expires_in_hours")
        expires_at = None
        if isinstance(hours, (int, float)) and hours > 0:
            expires_at = datetime.datetime.utcnow() + datetime.timedelta(hours=hours)

        code = generate_access_code()

        access = SurveyAccessCode(
            code=code,
            dealership_id=user.dealership_id,
            expires_at=expires_at,
            is_active=True,
        )
        db.session.add(access)
        db.session.commit()

        # Log admin action
        log_admin_action(
            user.email,
            "create_access_code",
            "access_code",
            access.id,
            json.dumps({"code": access.code, "expires_at": access.expires_at.isoformat() + "Z" if access.expires_at else None})
        )

        return jsonify(
            ok=True,
            id=access.id,
            code=access.code,
            dealership_id=access.dealership_id,
            created_at=access.created_at.isoformat() + "Z",
            expires_at=access.expires_at.isoformat() + "Z" if access.expires_at else None,
            is_active=access.is_active,
        )
    except Exception as e:
        print(f"[CREATE ACCESS CODE ERROR] {e}", flush=True)
        import traceback
        traceback.print_exc()
        db.session.rollback()
        return jsonify(error=f"Failed to create access code: {str(e)}"), 500

@app.get("/survey/access-codes")
def list_access_codes():
    """
    Returns all survey access codes for the user's dealership.
    Requires 'view_surveys' permission.
    """
    user, err = get_current_user()
    if err:
        return err  # 401 / 403

    # Check permission
    if not has_permission(user, "view_surveys"):
        return jsonify(error="you do not have permission to view surveys"), 403

    # If admin doesn't have a dealership, return empty list
    if not user.dealership_id:
        return jsonify(
            ok=True,
            items=[],
        )

    codes = (
        SurveyAccessCode.query
        .filter_by(dealership_id=user.dealership_id)
        .order_by(SurveyAccessCode.created_at.desc())
        .all()
    )

    return jsonify(
        ok=True,
        items=[
            {
                "id": c.id,
                "code": c.code,
                "dealership_id": c.dealership_id,
                "created_at": c.created_at.isoformat() + "Z",
                "expires_at": c.expires_at.isoformat() + "Z" if c.expires_at else None,
                "is_active": c.is_active,
            }
            for c in codes
        ],
    )

@app.post("/survey/invite")
def survey_invite():
    """
    Sends a survey invite email with a given access code
    to a specific employee email.
    Requires 'manage_survey' permission.
    """
    user, err = get_current_user()
    if err:
        return err  # 401/403
    
    # Check permission
    if not has_permission(user, "manage_survey"):
        return jsonify(error="you do not have permission to manage surveys"), 403

    # For now: only 'admin' can invite employees for their dealership
    if user.role != "admin":
        return jsonify(error="forbidden – only admin can send survey invites"), 403

    data = request.get_json(force=True)
    to_email = (data.get("email") or "").strip().lower()
    code = (data.get("code") or "").strip().upper()

    if not to_email or not code:
        return jsonify(error="email and code are required"), 400

    # If admin doesn't have a dealership, create one automatically
    if not user.dealership_id:
        dealership = Dealership(
            name=f"Dealership for {user.email}",
            address=None,
            city=None,
            state=None,
            zip_code=None,
        )
        db.session.add(dealership)
        db.session.flush()
        user.dealership_id = dealership.id
        db.session.commit()

    # Make sure this code belongs to THIS admin's dealership,
    # is active, and not expired.
    access = SurveyAccessCode.query.filter_by(
        code=code,
        dealership_id=user.dealership_id,
        is_active=True,
    ).first()

    if not access:
        return jsonify(error="access code not found for this dealership"), 400

    if access.expires_at and access.expires_at < datetime.datetime.utcnow():
        return jsonify(error="access code is expired"), 400

    # Send the email
    send_survey_invite_email(to_email, code)

    # Log admin action
    log_admin_action(
        user.email,
        "invite_employee_survey",
        "employee",
        None,
        json.dumps({"email": to_email, "code": code})
    )

    return jsonify(
        ok=True,
        message=f"Survey invite sent to {to_email}",
        code=code,
        dealership_id=user.dealership_id,
    )

# ===== EMPLOYEE MANAGEMENT ENDPOINTS (Admin only) =====

@app.post("/employees")
@limiter.limit("20 per minute")
def create_employee():
    """Admin-only: Create a new employee for their dealership"""
    user, err = get_current_user()
    if err:
        return err

    if user.role != "admin":
        return jsonify(error="only admins can manage employees"), 403

    if not user.dealership_id:
        return jsonify(error="admin has no dealership assigned"), 400

    # Check subscription limits
    dealership = Dealership.query.get(user.dealership_id)
    if dealership and not dealership.is_subscription_active():
        return jsonify(
            error="subscription_expired",
            message="Your subscription has expired. Please renew to manage employees."
        ), 403

    data = request.get_json(force=True) or {}
    name = sanitize_input(data.get("name") or "", max_length=255)
    email = sanitize_input(data.get("email") or "").strip().lower()
    phone = sanitize_input(data.get("phone") or "", max_length=20)
    department = sanitize_input(data.get("department") or "", max_length=100)
    position = sanitize_input(data.get("position") or "", max_length=100)

    if not name or not email or not department:
        return jsonify(error="Name, email, and department are required"), 400

    if not validate_email(email):
        return jsonify(error="Please enter a valid email address"), 400

    if phone and not validate_phone(phone):
        return jsonify(error="Please enter a valid phone number (10-15 digits)"), 400

    # Check if email already exists for this dealership
    existing = Employee.query.filter_by(
        email=email,
        dealership_id=user.dealership_id
    ).first()
    if existing:
        return jsonify(error="An employee with this email already exists"), 400

    employee = Employee(
        name=name,
        email=email,
        phone=phone or None,
        department=department,
        position=position or None,
        dealership_id=user.dealership_id,
        is_active=True,
    )

    db.session.add(employee)
    db.session.commit()

    # Log admin action
    log_admin_action(
        user.email,
        "create_employee",
        "employee",
        employee.id,
        json.dumps({"name": employee.name, "email": employee.email, "department": employee.department})
    )

    return jsonify(ok=True, employee=employee.to_dict()), 201

@app.get("/employees")
@limiter.limit("30 per minute")
def list_employees():
    """Admin-only: List all employees for their dealership"""
    user, err = get_current_user()
    if err:
        return err

    if user.role != "admin":
        return jsonify(error="only admins can view employees"), 403

    if not user.dealership_id:
        return jsonify(ok=True, items=[])

    employees = Employee.query.filter_by(
        dealership_id=user.dealership_id
    ).order_by(Employee.created_at.desc()).all()

    return jsonify(
        ok=True,
        items=[e.to_dict() for e in employees]
    )

@app.get("/employees/export")
@limiter.limit("10 per minute")
def export_employees():
    """Admin-only: Export employees as CSV"""
    user, err = get_current_user()
    if err:
        return err

    if user.role != "admin":
        return jsonify(error="only admins can export employees"), 403

    if not user.dealership_id:
        return jsonify(error="admin has no dealership assigned"), 400

    # Check subscription limits
    dealership = Dealership.query.get(user.dealership_id)
    if dealership and not dealership.is_subscription_active():
        return jsonify(
            error="subscription_expired",
            message="Your subscription has expired. Please renew to export data."
        ), 403

    employees = Employee.query.filter_by(
        dealership_id=user.dealership_id
    ).order_by(Employee.created_at.desc()).all()

    # Prepare data for CSV
    csv_data = []
    for emp in employees:
        csv_data.append({
            "ID": emp.id,
            "Name": emp.name,
            "Email": emp.email,
            "Phone": emp.phone or "",
            "Department": emp.department,
            "Position": emp.position or "",
            "Status": "Active" if emp.is_active else "Inactive",
            "Created At": emp.created_at.isoformat(),
            "Updated At": emp.updated_at.isoformat(),
        })

    # Generate filename with timestamp
    timestamp = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"employees_export_{timestamp}.csv"

    # Log admin action
    log_admin_action(
        user.email,
        "export_employees",
        "employee",
        None,
        json.dumps({"count": len(csv_data)})
    )

    return generate_csv_response(csv_data, filename)

@app.get("/employees/<int:employee_id>")
@limiter.limit("30 per minute")
def get_employee(employee_id: int):
    """Admin-only: Get a specific employee"""
    user, err = get_current_user()
    if err:
        return err

    if user.role != "admin":
        return jsonify(error="only admins can view employees"), 403

    if not user.dealership_id:
        return jsonify(error="admin has no dealership assigned"), 400

    employee = Employee.query.filter_by(
        id=employee_id,
        dealership_id=user.dealership_id
    ).first()

    if not employee:
        return jsonify(error="employee not found"), 404

    return jsonify(ok=True, employee=employee.to_dict())

@app.put("/employees/<int:employee_id>")
@limiter.limit("20 per minute")
def update_employee(employee_id: int):
    """Admin-only: Update an employee"""
    user, err = get_current_user()
    if err:
        return err

    if user.role != "admin":
        return jsonify(error="only admins can update employees"), 403

    if not user.dealership_id:
        return jsonify(error="admin has no dealership assigned"), 400

    employee = Employee.query.filter_by(
        id=employee_id,
        dealership_id=user.dealership_id
    ).first()

    if not employee:
        return jsonify(error="employee not found"), 404

    data = request.get_json(force=True) or {}
    
    if "name" in data:
        employee.name = sanitize_input(data["name"], max_length=255)
    if "email" in data:
        email = sanitize_input(data["email"]).strip().lower()
        if not validate_email(email):
            return jsonify(error="invalid email format"), 400
        # Check if email is taken by another employee
        existing = Employee.query.filter_by(
            email=email,
            dealership_id=user.dealership_id
        ).filter(Employee.id != employee_id).first()
        if existing:
            return jsonify(error="email already in use"), 400
        employee.email = email
    if "phone" in data:
        phone = sanitize_input(data["phone"], max_length=20) or None
        if phone and not validate_phone(phone):
            return jsonify(error="invalid phone number format"), 400
        employee.phone = phone
    if "department" in data:
        employee.department = sanitize_input(data["department"], max_length=100)
    if "position" in data:
        employee.position = sanitize_input(data["position"], max_length=100) or None
    if "is_active" in data:
        employee.is_active = bool(data["is_active"])
    
    employee.updated_at = datetime.datetime.utcnow()
    db.session.commit()

    # Log admin action
    log_admin_action(
        user.email,
        "update_employee",
        "employee",
        employee.id,
        json.dumps({"changes": data})
    )

    return jsonify(ok=True, employee=employee.to_dict())

@app.delete("/employees/<int:employee_id>")
@limiter.limit("10 per minute")
def delete_employee(employee_id: int):
    """Admin-only: Delete an employee (soft delete by setting is_active=False)"""
    user, err = get_current_user()
    if err:
        return err

    if user.role != "admin":
        return jsonify(error="only admins can delete employees"), 403

    if not user.dealership_id:
        return jsonify(error="admin has no dealership assigned"), 400

    employee = Employee.query.filter_by(
        id=employee_id,
        dealership_id=user.dealership_id
    ).first()

    if not employee:
        return jsonify(error="employee not found"), 404

    # Soft delete
    employee.is_active = False
    employee.updated_at = datetime.datetime.utcnow()
    db.session.commit()

    # Log admin action
    log_admin_action(
        user.email,
        "delete_employee",
        "employee",
        employee.id,
        json.dumps({"name": employee.name, "email": employee.email})
    )

    return jsonify(ok=True, message="employee deactivated")

@app.post("/employees/<int:employee_id>/invite")
@limiter.limit("10 per minute")
def invite_employee_to_survey(employee_id: int):
    """Admin-only: Send survey invite to a specific employee"""
    user, err = get_current_user()
    if err:
        return err

    if user.role != "admin":
        return jsonify(error="only admins can invite employees"), 403

    if not user.dealership_id:
        return jsonify(error="admin has no dealership assigned"), 400

    employee = Employee.query.filter_by(
        id=employee_id,
        dealership_id=user.dealership_id
    ).first()

    if not employee:
        return jsonify(error="employee not found"), 404

    if not employee.is_active:
        return jsonify(error="cannot invite inactive employee"), 400

    data = request.get_json(force=True) or {}
    code = (data.get("code") or "").strip().upper()

    if not code:
        return jsonify(error="access code is required"), 400

    # Verify the code belongs to this dealership
    access = SurveyAccessCode.query.filter_by(
        code=code,
        dealership_id=user.dealership_id,
        is_active=True,
    ).first()

    if not access:
        return jsonify(error="access code not found for this dealership"), 400

    if access.expires_at and access.expires_at < datetime.datetime.utcnow():
        return jsonify(error="access code is expired"), 400

    # Send the email
    send_survey_invite_email(employee.email, code)

    # Log admin action
    log_admin_action(
        user.email,
        "invite_employee_survey",
        "employee",
        employee.id,
        json.dumps({"email": employee.email, "code": code})
    )

    return jsonify(
        ok=True,
        message=f"Survey invite sent to {employee.email}",
        employee=employee.to_dict(),
        code=code,
    )

@app.post("/survey/validate-code")
def validate_access_code():
    data = request.get_json(force=True)
    access_code = (data.get("access_code") or "").strip()

    if not access_code:
        return jsonify(error="access_code is required"), 400

    # Look up code in DB
    code_obj = SurveyAccessCode.query.filter_by(code=access_code).first()

    if not code_obj or not code_obj.is_active:
        # You can customize this error text if you want
        return jsonify(error="invalid or inactive access code"), 400

    # Check expiry
    if code_obj.expires_at and code_obj.expires_at < datetime.datetime.utcnow():
        return jsonify(error="invalid or inactive access code"), 400

    # If you want, you can return minimal info for frontend
    return jsonify(
        ok=True,
        code=code_obj.code,
        dealership_id=code_obj.dealership_id,
        expires_at=code_obj.expires_at.isoformat() + "Z" if code_obj.expires_at else None,
    )

@app.post("/survey/submit")
def submit_survey():
    """
    Public endpoint: called by the Survey page.
    Saves one anonymous survey response tied to an access_code
    AND to a specific dealership via SurveyAccessCode.
    Also marks the access_code as used (one-time use).
    """
    data = request.get_json(force=True)

    access_code = (data.get("access_code") or "").strip().upper()
    employee_status = (data.get("employee_status") or "").strip()
    role = (data.get("role") or "").strip()

    satisfaction_answers = data.get("satisfaction_answers") or {}
    training_answers = data.get("training_answers") or {}

    termination_reason = data.get("termination_reason") or None
    termination_other = data.get("termination_other") or None
    leave_reason = data.get("leave_reason") or None
    leave_other = data.get("leave_other") or None
    additional_feedback = data.get("additional_feedback") or None

    # basic validation (same as before)
    if not access_code or not employee_status or not role:
        return jsonify(error="access_code, employee_status, and role are required"), 400

    if not isinstance(satisfaction_answers, dict):
        return jsonify(error="satisfaction_answers must be an object"), 400

    if training_answers and not isinstance(training_answers, dict):
        return jsonify(error="training_answers must be an object"), 400

    # 🔹 1) Look up and validate the access code in the DB
    ac = SurveyAccessCode.query.filter_by(code=access_code, is_active=True).first()
    if not ac:
        return jsonify(error="Invalid or inactive access code"), 400

    if ac.expires_at and ac.expires_at < datetime.datetime.utcnow():
        return jsonify(error="This access code has expired"), 400

    # 🔹 2) One-time use: immediately deactivate the code
    ac.is_active = False

    # 🔹 3) Save the structured response (for detailed analysis later)
    resp = SurveyResponse(
        access_code=access_code,
        employee_status=employee_status,
        role=role,
        satisfaction_answers=satisfaction_answers,
        training_answers=training_answers or None,
        termination_reason=termination_reason,
        termination_other=termination_other,
        leave_reason=leave_reason,
        leave_other=leave_other,
        additional_feedback=additional_feedback,
    )

    # 🔹 4) ALSO save a dealership-level record for dashboards (SurveyAnswer)
    payload = {
        "employee_status": employee_status,
        "role": role,
        "satisfaction_answers": satisfaction_answers,
        "training_answers": training_answers or None,
        "termination_reason": termination_reason,
        "termination_other": termination_other,
        "leave_reason": leave_reason,
        "leave_other": leave_other,
        "additional_feedback": additional_feedback,
    }

    ans = SurveyAnswer(
        dealership_id=ac.dealership_id,
        access_code_id=ac.id,
        payload=json.dumps(payload),
    )

    db.session.add(resp)
    db.session.add(ans)
    db.session.commit()

    return jsonify(ok=True, id=resp.id)

# ===== SUBSCRIPTION ENDPOINTS =====

@app.get("/subscription/status")
@limiter.limit("30 per minute")
def get_subscription_status():
    """
    Get subscription status for a dealership.
    - Admin/Manager: Gets their own dealership's subscription
    - Corporate: Must provide dealership_id query parameter for assigned dealerships
    """
    user, err = get_current_user()
    if err:
        return err
    
    if user.role not in ("admin", "manager", "corporate"):
        return jsonify(error="only admins, managers, and corporate users can view subscriptions"), 403

    # Determine which dealership to check
    dealership_id = None
    if user.role in ("admin", "manager"):
        dealership_id = user.dealership_id
        if not dealership_id:
            return jsonify(
                ok=True,
                subscription_status="none",
                message="No dealership associated with this account"
            )
    elif user.role == "corporate":
        # Corporate users must specify dealership_id
        dealership_id = request.args.get("dealership_id", type=int)
        if not dealership_id:
            return jsonify(error="dealership_id query parameter is required for corporate users"), 400
        
        # Check if corporate user has access to this dealership
        accessible_dealership_ids = get_accessible_dealership_ids(user)
        if dealership_id not in accessible_dealership_ids:
            return jsonify(error="you do not have access to this dealership"), 403

    dealership = Dealership.query.get(dealership_id)
    if not dealership:
        return jsonify(error="dealership not found"), 404

    # Sync with Stripe if we have a subscription ID or customer ID (in case webhook didn't fire)
    cancel_at_period_end = False
    if STRIPE_AVAILABLE and STRIPE_SECRET_KEY:
        try:
            # If we have a subscription ID, check it directly
            if dealership.stripe_subscription_id:
                try:
                    subscription = stripe.Subscription.retrieve(dealership.stripe_subscription_id)
                    cancel_at_period_end = subscription.get("cancel_at_period_end", False)
                    current_period_end = subscription.get("current_period_end")
                    if current_period_end:
                        dealership.subscription_ends_at = datetime.datetime.fromtimestamp(current_period_end)
                    # Update status based on Stripe
                    if subscription.status == "active" and cancel_at_period_end:
                        dealership.subscription_status = "active"  # Still active but will cancel
                    elif subscription.status == "canceled":
                        dealership.subscription_status = "canceled"
                    db.session.commit()
                except stripe._error.InvalidRequestError:
                    # Subscription not found in Stripe, check by customer
                    pass
            
            # Also check for active subscriptions by customer ID
            if dealership.stripe_customer_id:
                subscriptions = stripe.Subscription.list(
                    customer=dealership.stripe_customer_id,
                    status="all",  # Check all statuses to find the subscription
                    limit=10
                )
                
                if subscriptions.data:
                    # Find the most recent subscription
                    active_sub = subscriptions.data[0]
                    cancel_at_period_end = active_sub.get("cancel_at_period_end", False)
                    
                    if dealership.subscription_status != "active" or dealership.stripe_subscription_id != active_sub.id:
                        print(f"[SYNC] Syncing subscription status from Stripe for customer {dealership.stripe_customer_id}", flush=True)
                        dealership.subscription_status = "active" if active_sub.status == "active" else active_sub.status
                        dealership.stripe_subscription_id = active_sub.id
                        dealership.subscription_plan = "pro"
                        current_period_end = active_sub.get("current_period_end")
                        if current_period_end:
                            dealership.subscription_ends_at = datetime.datetime.fromtimestamp(current_period_end)
                        db.session.commit()
            elif dealership.subscription_status == "active":
                # Database says active but Stripe says no active subscription - check all statuses
                all_subs = stripe.Subscription.list(customer=dealership.stripe_customer_id, limit=10)
                if all_subs.data:
                    # Get the most recent subscription
                    latest_sub = sorted(all_subs.data, key=lambda x: x.created, reverse=True)[0]
                    status_map = {
                        "active": "active",
                        "trialing": "active",
                        "past_due": "active",  # Still active, just needs payment
                        "canceled": "canceled",
                        "unpaid": "expired",
                        "incomplete": "expired",
                        "incomplete_expired": "expired",
                    }
                    mapped_status = status_map.get(latest_sub.status, "expired")
                    cancel_at_period_end = latest_sub.get("cancel_at_period_end", False)
                    dealership.subscription_status = mapped_status
                    dealership.stripe_subscription_id = latest_sub.id
                    current_period_end = latest_sub.get("current_period_end")
                    if current_period_end:
                        dealership.subscription_ends_at = datetime.datetime.fromtimestamp(current_period_end)
                    db.session.commit()
        except Exception as e:
            # If Stripe check fails, just use database value
            print(f"[SYNC] Failed to sync with Stripe: {e}", flush=True)

    return jsonify(
        ok=True,
        subscription_status=dealership.subscription_status,
        subscription_plan=dealership.subscription_plan,
        trial_ends_at=dealership.trial_ends_at.isoformat() + "Z" if dealership.trial_ends_at else None,
        subscription_ends_at=dealership.subscription_ends_at.isoformat() + "Z" if dealership.subscription_ends_at else None,
        days_remaining_in_trial=dealership.days_remaining_in_trial(),
        is_active=dealership.is_subscription_active(),
        cancel_at_period_end=cancel_at_period_end,
    )

@app.post("/subscription/create-checkout")
@limiter.limit("10 per minute")
def create_checkout_session():
    """
    Create Stripe checkout session for subscription.
    - Anyone can subscribe to become an admin (new admin registration)
    - Admin: Creates checkout for their own dealership
    - Corporate: Must provide dealership_id in request body for assigned dealerships
    - If user is not authenticated, they can still subscribe (will create account after payment)
    """
    # Try to get current user, but don't require authentication
    user = None
    email = None  # Initialize email variable
    auth = request.headers.get("Authorization", "") or request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        token = auth.split(" ", 1)[1].strip()
        if token:
            try:
                claims = verify_token(token)
                email = claims.get("sub")
                if email:
                    user = User.query.filter_by(email=email).first()
            except:
                pass  # Invalid token, treat as new user
    
    # Get email from request body if user not authenticated
    data = request.get_json(silent=True) or {}
    
    # Check if user_id was provided FIRST (from admin registration page)
    # This should be checked before any other user lookups
    provided_user_id = data.get("user_id")
    if provided_user_id and not user:
        # User was just created in registration - use that user
        temp_user = User.query.get(provided_user_id)
        if temp_user:
            user = temp_user
            email = user.email  # Use email from user
        else:
            return jsonify(error="Invalid user_id provided"), 400
    
    # Get email from request or user
    if not email:
        email = data.get("email", "").strip().lower() if not user else user.email
    
    # If no user found but email provided, try to find user by email
    if not user and email:
        user = User.query.filter_by(email=email).first()
    
    # If no user and no email provided, return error
    if not user and not email:
        return jsonify(error="email is required for new admin registration"), 400
    
    # If user exists but is not admin/corporate, they can still subscribe to become admin
    if user and user.role not in ("admin", "corporate"):
        # Allow managers to subscribe and become admin
        pass

    if not STRIPE_AVAILABLE or not STRIPE_SECRET_KEY:
        return jsonify(error="Stripe not configured"), 503

    # Get billing plan from request
    billing_plan = data.get("billing_plan", "monthly")  # Default to monthly
    
    # Select appropriate price ID
    price_id = None
    if billing_plan == "annual":
        price_id = STRIPE_PRICE_ID_ANNUAL or STRIPE_PRICE_ID  # Fallback to monthly if annual not configured
    else:
        price_id = STRIPE_PRICE_ID
    
    if not price_id:
        return jsonify(error="Stripe price ID not configured"), 503

    try:
        # Determine which dealership to create subscription for
        dealership_id = None
        
        if user:
            if user.role == "admin":
                dealership_id = user.dealership_id
                # If admin doesn't have a dealership, we'll create one after checkout
            elif user.role == "corporate":
                dealership_id = data.get("dealership_id")
                if not dealership_id:
                    return jsonify(error="dealership_id is required in request body for corporate users"), 400
                
                # Check if corporate user has access to this dealership
                accessible_dealership_ids = get_accessible_dealership_ids(user)
                if dealership_id not in accessible_dealership_ids:
                    return jsonify(error="you do not have access to this dealership"), 403
                
                dealership = Dealership.query.get(dealership_id)
                if not dealership:
                    return jsonify(error="dealership not found"), 404
                
                # Check if dealership already has an active subscription
                if dealership.is_subscription_active():
                    return jsonify(error="this dealership already has an active subscription"), 400
            elif user.role == "manager":
                # Managers can subscribe to become admin - will create new dealership
                dealership_id = None
        else:
            # New user registration - will create user and dealership after payment
            # If user_id was already checked above, user should be set now
            # If not, check by email
            if not user:
                # No user_id provided - validate email and check if user exists
                if not validate_email(email):
                    return jsonify(error="Please enter a valid email address"), 400
                
                # Check if user already exists by email
                existing = User.query.filter_by(email=email).first()
                if existing:
                    # Check if this is a pending admin registration (verified or not, but not subscribed)
                    if (existing.role == "manager" and 
                        not existing.is_approved and 
                        not existing.dealership_id):
                        # This is a pending admin registration - allow checkout
                        # They may be verified but not subscribed yet
                        user = existing
                    else:
                        # User exists but not a pending admin registration - they should log in first
                        return jsonify(error="This email is already registered. Please sign in to subscribe."), 400
        
        # If user has a dealership, use it; otherwise we'll create one in webhook
        if dealership_id:
            dealership = Dealership.query.get(dealership_id)
            if not dealership:
                dealership_id = None
        
        # For new admin registration, we need to create a user account first (or use existing)
        user_id_for_checkout = None
        if user:
            user_id_for_checkout = user.id
        else:
            # No user found and no user_id provided - create temporary user
            if not validate_email(email):
                return jsonify(error="Please enter a valid email address"), 400
            
            # Create a temporary user account for checkout (will be activated after payment)
            # This allows us to track the subscription
            temp_user = User(
                email=email,
                password_hash=generate_password_hash("temp"),  # Temporary, user will set real password
                role="manager",  # Temporary, will be upgraded to admin
                is_verified=False,
                is_approved=False,
            )
            db.session.add(temp_user)
            db.session.flush()  # Get the ID
            user_id_for_checkout = temp_user.id
            user = temp_user
        
        # Don't create Stripe customer yet - wait until payment is confirmed in webhook
        # Check if existing dealership has a customer_id (for resubscriptions)
        customer_id = None
        if dealership_id:
            dealership = Dealership.query.get(dealership_id)
            if dealership and dealership.stripe_customer_id:
                customer_id = dealership.stripe_customer_id
                # Verify customer exists in Stripe
                try:
                    stripe.Customer.retrieve(customer_id)
                except stripe._error.InvalidRequestError as e:
                    # Customer doesn't exist in Stripe, clear it from database
                    if "No such customer" in str(e):
                        print(f"[STRIPE] Customer {customer_id} not found in Stripe, will create after payment", flush=True)
                        customer_id = None
                        if dealership:
                            dealership.stripe_customer_id = None
                            db.session.commit()
                    else:
                        raise
                except Exception as e:
                    # Other Stripe errors - log and will create after payment
                    print(f"[STRIPE] Error retrieving customer {customer_id}: {e}, will create after payment", flush=True)
                    customer_id = None
                    if dealership:
                        dealership.stripe_customer_id = None
                        db.session.commit()

        # Ensure email is set (should be set by now, but safety check)
        if not email and user:
            email = user.email
        if not email:
            return jsonify(error="Email is required for checkout"), 400
        
        # Create checkout session - don't require customer_id, use customer_email instead
        # Stripe will create the customer automatically when payment succeeds
        try:
            checkout_params = {
                "customer_email": email,  # Use email instead of customer_id - Stripe will create customer on payment
                "payment_method_types": ["card"],
                "line_items": [{
                    "price": price_id,
                    "quantity": 1,
                }],
                "mode": "subscription",
                "success_url": f"{FRONTEND_URL}/dashboard?subscription=success",
                "cancel_url": f"{FRONTEND_URL}/admin-subscribe?subscription=canceled&email={quote(email)}&user_id={user_id_for_checkout}",
                "metadata": {
                    "user_id": str(user_id_for_checkout),
                    "dealership_id": str(dealership_id) if dealership_id else "new",
                    "user_email": email,
                    "is_new_admin": "true" if not user or user.role != "admin" else "false",
                    # Dealership info for new admin registration
                    # Stripe metadata values must be strings, so convert None to empty string
                    "dealership_name": (data.get("dealership_name") or "").strip() or "",
                    "dealership_address": (data.get("dealership_address") or "").strip() or "",
                    "dealership_city": (data.get("dealership_city") or "").strip() or "",
                    "dealership_state": (data.get("dealership_state") or "").strip() or "",
                    "dealership_zip_code": (data.get("dealership_zip_code") or "").strip() or "",
                },
            }
            
            # Only add customer if we have an existing one (for resubscriptions)
            if customer_id:
                checkout_params["customer"] = customer_id
            
            checkout_session = stripe.checkout.Session.create(**checkout_params)
        except Exception as e:
            # Log error and return
            error_msg = str(e)
            print(f"[STRIPE ERROR] Checkout creation failed: {error_msg}", flush=True)
            import traceback
            traceback.print_exc()
            if os.getenv("ENVIRONMENT") != "production":
                return jsonify(error=f"Failed to create checkout session: {error_msg}"), 500
            return jsonify(error="Failed to create checkout session"), 500
        except AttributeError as ae:
            # Handle Python 3.14 compatibility issue with Stripe
            if "'NoneType' object has no attribute 'Secret'" in str(ae):
                raise Exception("Stripe library has a compatibility issue with Python 3.14. Please downgrade to Python 3.11 or 3.12, or wait for Stripe library update.")
            raise

        return jsonify(
            ok=True,
            checkout_url=checkout_session.url,
            session_id=checkout_session.id,
        )
    except stripe._error.StripeError as e:
        # Catch all Stripe-specific errors
        error_msg = str(e)
        print(f"[STRIPE ERROR] Checkout creation failed: {error_msg}", flush=True)
        import traceback
        traceback.print_exc()
        # Return more detailed error in development
        if os.getenv("ENVIRONMENT") != "production":
            return jsonify(error=f"Failed to create checkout session: {error_msg}"), 500
        return jsonify(error="Failed to create checkout session"), 500
    except Exception as e:
        error_msg = str(e)
        print(f"[ERROR] Unexpected error in checkout creation: {error_msg}", flush=True)
        import traceback
        traceback.print_exc()
        # Return more detailed error in development
        if os.getenv("ENVIRONMENT") != "production":
            return jsonify(error=f"Failed to create checkout session: {error_msg}"), 500
        return jsonify(error="Failed to create checkout session"), 500

@app.post("/subscription/webhook")
def stripe_webhook():
    """Handle Stripe webhook events"""
    if not STRIPE_AVAILABLE or not STRIPE_WEBHOOK_SECRET:
        return jsonify(error="Stripe webhooks not configured"), 503

    payload = request.get_data()
    sig_header = request.headers.get("Stripe-Signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        return jsonify(error="Invalid payload"), 400
    except stripe._error.SignatureVerificationError:
        return jsonify(error="Invalid signature"), 400

    # Handle the event
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        handle_checkout_completed(session)
    elif event["type"] == "customer.subscription.updated":
        subscription = event["data"]["object"]
        handle_subscription_updated(subscription)
    elif event["type"] == "customer.subscription.deleted":
        subscription = event["data"]["object"]
        handle_subscription_deleted(subscription)

    return jsonify(ok=True)

def handle_checkout_completed(session):
    """Handle successful checkout - upgrade user to admin and create/update dealership"""
    try:
        metadata = session.get("metadata", {})
        user_id = metadata.get("user_id")
        dealership_id_str = metadata.get("dealership_id")
        user_email = metadata.get("user_email")
        is_new_admin = metadata.get("is_new_admin", "false") == "true"
        
        if not user_id:
            print(f"[WEBHOOK ERROR] No user_id in checkout session metadata", flush=True)
            return

        # Get the user
        user = User.query.get(int(user_id))
        if not user:
            print(f"[WEBHOOK ERROR] User {user_id} not found", flush=True)
            return
        
        # If this is a new admin registration, user should already be verified
        # (they verified email before subscribing)
        if is_new_admin or (user.role == "manager" and not user.dealership_id):
            # User already verified email before subscribing, so just approve them
            user.is_approved = True  # Auto-approve on payment (they paid)
            if not user.approved_at:
                user.approved_at = datetime.datetime.utcnow()
            
            # Ensure they're verified (should already be true, but safety check)
            if not user.is_verified:
                user.is_verified = True
                print(f"[WEBHOOK] Auto-verified user {user.email} after payment (should have been verified already)", flush=True)
            
            db.session.commit()
            print(f"[WEBHOOK] User {user.email} approved after payment (already verified)", flush=True)

        # Create or get dealership
        dealership = None
        if dealership_id_str and dealership_id_str != "new":
            dealership = Dealership.query.get(int(dealership_id_str))
        
        # Also check if user already has a dealership (for resubscriptions)
        if not dealership and user.dealership_id:
            dealership = Dealership.query.get(user.dealership_id)
        
        if not dealership:
            # Create new dealership for this user
            # Get dealership info from metadata if provided
            dealership_name = metadata.get("dealership_name", "").strip() or f"{user.full_name or user.email}'s Dealership"
            dealership_address = metadata.get("dealership_address", "").strip() or None
            dealership_city = metadata.get("dealership_city", "").strip() or None
            dealership_state = metadata.get("dealership_state", "").strip() or None
            dealership_zip_code = metadata.get("dealership_zip_code", "").strip() or None
            
            dealership = Dealership(
                name=dealership_name,
                address=dealership_address,
                city=dealership_city,
                state=dealership_state,
                zip_code=dealership_zip_code,
                subscription_status="active",
                subscription_plan="pro",
                trial_ends_at=None,  # No trial, they paid
            )
            db.session.add(dealership)
            db.session.flush()  # Get the ID
        
        # Update dealership subscription info (important for resubscriptions)
        subscription_id = session.get("subscription")
        if subscription_id:
            dealership.stripe_subscription_id = subscription_id
            dealership.subscription_status = "active"  # Always set to active on new payment
            dealership.subscription_plan = "pro"
            # Get actual period end from Stripe subscription if available
            try:
                sub = stripe.Subscription.retrieve(subscription_id)
                period_end = sub.get("current_period_end")
                if period_end:
                    dealership.subscription_ends_at = datetime.datetime.fromtimestamp(period_end)
                else:
                    # Fallback: 1 month from now
                    dealership.subscription_ends_at = datetime.datetime.utcnow() + datetime.timedelta(days=30)
            except:
                # Fallback: 1 month from now if we can't retrieve from Stripe
                dealership.subscription_ends_at = datetime.datetime.utcnow() + datetime.timedelta(days=30)
        
        # Get or create Stripe customer - create it now that payment is confirmed
        customer_id = session.get("customer")
        if not customer_id:
            # Customer wasn't created yet - create it now after payment
            try:
                customer = stripe.Customer.create(
                    email=user.email,
                    metadata={
                        "user_id": str(user.id),
                        "dealership_id": str(dealership.id)
                    }
                )
                customer_id = customer.id
                print(f"[WEBHOOK] Created Stripe customer {customer_id} for user {user.email} after payment", flush=True)
            except Exception as e:
                print(f"[WEBHOOK ERROR] Failed to create Stripe customer: {e}", flush=True)
                # Continue without customer_id - subscription will still work
        
        # Save customer ID to dealership
        if customer_id:
            dealership.stripe_customer_id = customer_id

        # Upgrade user to admin and assign to dealership
        user.role = "admin"
        user.dealership_id = dealership.id

        db.session.commit()
        print(f"[WEBHOOK SUCCESS] User {user.email} upgraded to admin, dealership {dealership.id} created/updated", flush=True)
    except Exception as e:
        print(f"[WEBHOOK ERROR] Checkout completed handler failed: {e}", flush=True)
        import traceback
        traceback.print_exc()

def handle_subscription_updated(subscription):
    """Handle subscription updates"""
    try:
        customer_id = subscription.get("customer")
        dealership = Dealership.query.filter_by(stripe_customer_id=customer_id).first()
        if not dealership:
            return

        status = subscription.get("status")
        dealership.subscription_status = status
        dealership.stripe_subscription_id = subscription.get("id")

        # Update subscription end date
        current_period_end = subscription.get("current_period_end")
        if current_period_end:
            dealership.subscription_ends_at = datetime.datetime.fromtimestamp(current_period_end)

        db.session.commit()
    except Exception as e:
        print(f"[WEBHOOK ERROR] Subscription updated handler failed: {e}", flush=True)

def handle_subscription_deleted(subscription):
    """Handle subscription cancellation"""
    try:
        customer_id = subscription.get("customer")
        dealership = Dealership.query.filter_by(stripe_customer_id=customer_id).first()
        if not dealership:
            return

        dealership.subscription_status = "canceled"
        dealership.subscription_ends_at = datetime.datetime.fromtimestamp(
            subscription.get("current_period_end", datetime.datetime.utcnow().timestamp())
        )
        db.session.commit()
    except Exception as e:
        print(f"[WEBHOOK ERROR] Subscription deleted handler failed: {e}", flush=True)

@app.post("/subscription/cancel")
@limiter.limit("5 per hour")
def cancel_subscription():
    """
    Cancel a dealership's subscription.
    - Admin: Cancels their own dealership's subscription
    - Corporate: Must provide dealership_id in request body for assigned dealerships
    """
    user, err = get_current_user()
    if err:
        return err
    
    if user.role not in ("admin", "corporate"):
        return jsonify(error="only admins and corporate users can cancel subscriptions"), 403
    
    if not STRIPE_AVAILABLE or not STRIPE_SECRET_KEY:
        return jsonify(error="Stripe not configured"), 503
    
    # Determine which dealership to cancel subscription for
    dealership_id = None
    if user.role == "admin":
        dealership_id = user.dealership_id
        if not dealership_id:
            return jsonify(error="No subscription found"), 404
    elif user.role == "corporate":
        data = request.get_json(silent=True) or {}
        dealership_id = data.get("dealership_id")
        if not dealership_id:
            return jsonify(error="dealership_id is required in request body for corporate users"), 400
        
        # Check if corporate user has access to this dealership
        accessible_dealership_ids = get_accessible_dealership_ids(user)
        if dealership_id not in accessible_dealership_ids:
            return jsonify(error="you do not have access to this dealership"), 403
    
    dealership = Dealership.query.get(dealership_id)
    if not dealership:
        return jsonify(error="Dealership not found"), 404
    
    if not dealership.stripe_subscription_id:
        # No Stripe subscription, just update database
        dealership.subscription_status = "canceled"
        db.session.commit()
        return jsonify(ok=True, message="Subscription canceled")
    
    try:
        # Cancel subscription in Stripe
        subscription = stripe.Subscription.retrieve(dealership.stripe_subscription_id)
        
        if subscription.status == "canceled":
            # Already canceled, just update database
            dealership.subscription_status = "canceled"
            db.session.commit()
            return jsonify(ok=True, message="Subscription already canceled")
        
        # Cancel immediately (or use cancel_at_period_end=True to cancel at period end)
        data = request.get_json(silent=True) or {}
        cancel_at_period_end = data.get("cancel_at_period_end", False)
        
        if cancel_at_period_end:
            # Cancel at period end - modify subscription
            canceled_sub = stripe.Subscription.modify(
                dealership.stripe_subscription_id,
                cancel_at_period_end=True
            )
            # Still active until period end
            dealership.subscription_status = "active"
            period_end = canceled_sub.get("current_period_end")
            if period_end:
                dealership.subscription_ends_at = datetime.datetime.fromtimestamp(period_end)
            db.session.commit()
            return jsonify(ok=True, message="Subscription will be canceled at the end of the billing period", subscription_status=dealership.subscription_status)
        else:
            # Cancel immediately - delete subscription
            canceled_sub = stripe.Subscription.delete(dealership.stripe_subscription_id)
            # Update database immediately
            dealership.subscription_status = "canceled"
            dealership.subscription_ends_at = datetime.datetime.utcnow()  # Set to now for immediate effect
            db.session.commit()
            return jsonify(ok=True, message="Subscription canceled immediately", subscription_status=dealership.subscription_status)
        
    except stripe._error.InvalidRequestError as e:
        print(f"[STRIPE ERROR] Cancel subscription failed: {e}", flush=True)
        # If subscription not found in Stripe, just update database
        if "No such subscription" in str(e):
            dealership.subscription_status = "canceled"
            db.session.commit()
            return jsonify(ok=True, message="Subscription canceled (not found in Stripe)")
        return jsonify(error=f"Failed to cancel subscription: {str(e)}"), 500
    except Exception as e:
        print(f"[ERROR] Cancel subscription failed: {e}", flush=True)
        import traceback
        traceback.print_exc()

@app.post("/subscription/resume")
@limiter.limit("5 per hour")
def resume_subscription():
    """
    Resume a subscription that was scheduled to cancel at period end.
    - Admin: Resumes their own dealership's subscription
    - Corporate: Must provide dealership_id in request body for assigned dealerships
    """
    user, err = get_current_user()
    if err:
        return err
    
    if user.role not in ("admin", "corporate"):
        return jsonify(error="only admins and corporate users can resume subscriptions"), 403
    
    if not STRIPE_AVAILABLE or not STRIPE_SECRET_KEY:
        return jsonify(error="Stripe not configured"), 503
    
    # Determine which dealership to resume subscription for
    dealership_id = None
    if user.role == "admin":
        dealership_id = user.dealership_id
        if not dealership_id:
            return jsonify(error="No subscription found"), 404
    elif user.role == "corporate":
        data = request.get_json(silent=True) or {}
        dealership_id = data.get("dealership_id")
        if not dealership_id:
            return jsonify(error="dealership_id is required in request body for corporate users"), 400
        
        # Check if corporate user has access to this dealership
        accessible_dealership_ids = get_accessible_dealership_ids(user)
        if dealership_id not in accessible_dealership_ids:
            return jsonify(error="you do not have access to this dealership"), 403
    
    dealership = Dealership.query.get(dealership_id)
    if not dealership:
        return jsonify(error="Dealership not found"), 404
    
    if not dealership.stripe_subscription_id:
        return jsonify(error="No active subscription found"), 404
    
    try:
        # Resume subscription in Stripe by removing cancel_at_period_end
        subscription = stripe.Subscription.retrieve(dealership.stripe_subscription_id)
        
        if subscription.status != "active":
            return jsonify(error="Subscription is not active"), 400
        
        if not subscription.get("cancel_at_period_end", False):
            return jsonify(error="Subscription is not scheduled for cancellation"), 400
        
        # Remove cancellation - resume subscription
        resumed_sub = stripe.Subscription.modify(
            dealership.stripe_subscription_id,
            cancel_at_period_end=False
        )
        
        # Update database
        dealership.subscription_status = "active"
        period_end = resumed_sub.get("current_period_end")
        if period_end:
            dealership.subscription_ends_at = datetime.datetime.fromtimestamp(period_end)
        db.session.commit()
        
        return jsonify(
            ok=True,
            message="Subscription resumed successfully",
            subscription_status=dealership.subscription_status
        )
    except stripe._error.InvalidRequestError as e:
        print(f"[STRIPE ERROR] Resume subscription failed: {e}", flush=True)
        if "No such subscription" in str(e):
            return jsonify(error="Subscription not found in Stripe"), 404
        return jsonify(error=f"Failed to resume subscription: {str(e)}"), 500
    except Exception as e:
        print(f"[ERROR] Resume subscription failed: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return jsonify(error=f"Failed to resume subscription: {str(e)}"), 500
        return jsonify(error="Failed to cancel subscription"), 500

@app.get("/corporate/subscriptions")
@limiter.limit("30 per minute")
def get_corporate_subscriptions():
    """
    Get subscription status for all dealerships assigned to a corporate user.
    Only corporate users can access this endpoint.
    """
    user, err = get_current_user()
    if err:
        return err
    
    if user.role != "corporate":
        return jsonify(error="only corporate users can access this endpoint"), 403
    
    accessible_dealership_ids = get_accessible_dealership_ids(user)
    if not accessible_dealership_ids:
        return jsonify(ok=True, subscriptions=[], total=0)
    
    dealerships = Dealership.query.filter(Dealership.id.in_(accessible_dealership_ids)).all()
    
    subscriptions = []
    for dealership in dealerships:
        # Check cancel_at_period_end from Stripe if subscription exists
        cancel_at_period_end = False
        if STRIPE_AVAILABLE and STRIPE_SECRET_KEY and dealership.stripe_subscription_id:
            try:
                subscription = stripe.Subscription.retrieve(dealership.stripe_subscription_id)
                cancel_at_period_end = subscription.get("cancel_at_period_end", False)
            except:
                pass  # If we can't retrieve, just use False
        
        subscriptions.append({
            "dealership_id": dealership.id,
            "dealership_name": dealership.name,
            "subscription_status": dealership.subscription_status,
            "subscription_plan": dealership.subscription_plan,
            "trial_ends_at": dealership.trial_ends_at.isoformat() + "Z" if dealership.trial_ends_at else None,
            "subscription_ends_at": dealership.subscription_ends_at.isoformat() + "Z" if dealership.subscription_ends_at else None,
            "days_remaining_in_trial": dealership.days_remaining_in_trial(),
            "is_active": dealership.is_subscription_active(),
            "cancel_at_period_end": cancel_at_period_end,
        })
    
    return jsonify(
        ok=True,
        subscriptions=subscriptions,
        total=len(subscriptions)
    )

@app.get("/corporate/dealerships/<int:dealership_id>/managers")
@limiter.limit("30 per minute")
def get_dealership_managers(dealership_id: int):
    """
    Get all managers for a specific dealership.
    Only corporate users can access this endpoint for their assigned dealerships.
    """
    user, err = get_current_user()
    if err:
        return err
    
    if user.role != "corporate":
        return jsonify(error="only corporate users can access this endpoint"), 403
    
    # Check if corporate user has access to this dealership
    accessible_dealership_ids = get_accessible_dealership_ids(user)
    if dealership_id not in accessible_dealership_ids:
        return jsonify(error="you do not have access to this dealership"), 403
    
    managers = User.query.filter_by(dealership_id=dealership_id, role="manager").all()
    
    return jsonify(
        ok=True,
        managers=[m.to_dict() for m in managers],
        total=len(managers)
    )

@app.post("/corporate/managers/<int:manager_id>/promote")
@limiter.limit("20 per minute")
def promote_manager_to_admin(manager_id: int):
    """
    Promote a manager to admin for a specific dealership.
    Only corporate users can promote managers for their assigned dealerships.
    """
    user, err = get_current_user()
    if err:
        return err
    
    if user.role != "corporate":
        return jsonify(error="only corporate users can promote managers to admin"), 403
    
    data = request.get_json(silent=True) or {}
    dealership_id = data.get("dealership_id")
    
    if not dealership_id:
        return jsonify(error="dealership_id is required in request body"), 400
    
    # Check if corporate user has access to this dealership
    accessible_dealership_ids = get_accessible_dealership_ids(user)
    if dealership_id not in accessible_dealership_ids:
        return jsonify(error="you do not have access to this dealership"), 403
    
    manager = User.query.get(manager_id)
    if not manager:
        return jsonify(error="manager not found"), 404
    
    if manager.role != "manager":
        return jsonify(error="user is not a manager"), 400
    
    # Check if manager belongs to this dealership
    if manager.dealership_id != dealership_id:
        return jsonify(error="manager does not belong to this dealership"), 400
    
    # Check if dealership already has an admin
    existing_admin = User.query.filter_by(dealership_id=dealership_id, role="admin").first()
    if existing_admin and existing_admin.id != manager_id:
        return jsonify(error="this dealership already has an admin"), 400
    
    # Promote manager to admin
    manager.role = "admin"
    manager.is_approved = True  # Ensure they're approved
    if not manager.approved_at:
        manager.approved_at = datetime.datetime.utcnow()
    if not manager.approved_by:
        manager.approved_by = user.id
    
    db.session.commit()
    
    # Log admin action
    log_admin_action(
        user.email,
        "promote_manager_to_admin",
        "user",
        manager.id,
        json.dumps({"manager_email": manager.email, "dealership_id": dealership_id})
    )
    
    return jsonify(ok=True, message=f"Manager '{manager.email}' promoted to admin successfully")

@app.get("/subscription/check-limits")
@limiter.limit("30 per minute")
def check_subscription_limits():
    """Check if user has reached subscription limits"""
    user, err = get_current_user()
    if err:
        return err

    if not user.dealership_id:
        return jsonify(
            ok=True,
            can_create_employees=True,
            can_create_access_codes=True,
            can_view_analytics=True,
            message="No subscription limits for accounts without dealership"
        )

    dealership = Dealership.query.get(user.dealership_id)
    if not dealership:
        return jsonify(error="dealership not found"), 404

    is_active = dealership.is_subscription_active()

    # Define limits based on subscription status
    if not is_active:
        return jsonify(
            ok=True,
            can_create_employees=False,
            can_create_access_codes=False,
            can_view_analytics=False,
            message="Subscription expired. Please renew to continue using the service."
        )

    # Trial or active subscription - allow all features
    return jsonify(
        ok=True,
        can_create_employees=True,
        can_create_access_codes=True,
        can_view_analytics=True,
        subscription_status=dealership.subscription_status,
        days_remaining=dealership.days_remaining_in_trial() if dealership.subscription_status == "trial" else None,
    )

# ===== CORPORATE DEALERSHIP MANAGEMENT ENDPOINTS =====

@app.get("/corporate/dealerships")
@limiter.limit("30 per minute")
def get_corporate_dealerships():
    """
    Get all dealerships that a corporate user can access.
    Corporate users only see their assigned dealerships.
    """
    user, err = get_current_user()
    if err:
        return err
    
    if user.role != "corporate":
        return jsonify(error="only corporate users can access this endpoint"), 403
    
    accessible_dealership_ids = get_accessible_dealership_ids(user)
    dealerships = Dealership.query.filter(Dealership.id.in_(accessible_dealership_ids)).all() if accessible_dealership_ids else []
    
    return jsonify(
        ok=True,
        dealerships=[d.to_dict() for d in dealerships],
        total=len(dealerships)
    )

@app.get("/corporate/all-dealerships")
@limiter.limit("30 per minute")
def get_all_dealerships():
    """
    Get ALL dealerships in the system (for corporate users to assign).
    This shows all dealerships so corporate can add them to their access list.
    """
    user, err = get_current_user()
    if err:
        return err
    
    if user.role != "corporate":
        return jsonify(error="only corporate users can access this endpoint"), 403
    
    all_dealerships = Dealership.query.all()
    accessible_dealership_ids = get_accessible_dealership_ids(user)
    
    # Get pending requests for this user
    pending_request_ids = [
        r.dealership_id for r in DealershipAccessRequest.query.filter_by(
            corporate_user_id=user.id,
            status="pending"
        ).all()
    ]
    
    # Include whether each dealership is already assigned or has pending request
    dealerships_with_status = []
    for d in all_dealerships:
        dealer_dict = d.to_dict()
        dealer_dict["is_assigned"] = d.id in accessible_dealership_ids
        dealer_dict["has_pending_request"] = d.id in pending_request_ids
        dealerships_with_status.append(dealer_dict)
    
    return jsonify(
        ok=True,
        dealerships=dealerships_with_status,
        total=len(dealerships_with_status)
    )

# ===== ADMIN MANAGEMENT ENDPOINTS =====

@app.get("/admin/managers")
@limiter.limit("30 per minute")
def get_admin_managers():
    """
    Get all managers for the admin's dealership.
    Only admins can access this endpoint.
    """
    user, err = get_current_user()
    if err:
        return err
    
    if user.role != "admin":
        return jsonify(error="only admins can access this endpoint"), 403
    
    if not user.dealership_id:
        return jsonify(ok=True, managers=[], pending=[], total=0)
    
    # Get all managers for this admin's dealership
    all_managers = User.query.filter_by(dealership_id=user.dealership_id, role="manager").all()
    pending_managers = [m for m in all_managers if not m.is_approved]
    approved_managers = [m for m in all_managers if m.is_approved]
    
    # Get permissions for each manager
    permission_keys = list(DEFAULT_PERMISSIONS["admin"].keys())
    
    def get_manager_with_permissions(manager):
        manager_dict = manager.to_dict()
        # Get user-specific permissions
        user_perms = UserPermission.query.filter_by(user_id=manager.id).all()
        permissions = {}
        for key in permission_keys:
            # Check if user has specific permission
            user_perm = next((p for p in user_perms if p.permission_key == key), None)
            if user_perm is not None:
                permissions[key] = user_perm.allowed
            else:
                # Use role-based permission
                permissions[key] = get_permission(manager.role, key)
        manager_dict["permissions"] = permissions
        return manager_dict
    
    return jsonify(
        ok=True,
        managers=[get_manager_with_permissions(m) for m in approved_managers],
        pending=[m.to_dict() for m in pending_managers],
        total=len(all_managers),
        pending_count=len(pending_managers),
        permission_keys=permission_keys
    )

@app.get("/admin/pending-managers")
@limiter.limit("30 per minute")
def get_pending_managers():
    """
    Get all pending manager approval requests.
    Only admins and corporate users can access this endpoint.
    """
    user, err = get_current_user()
    if err:
        return err
    
    if user.role not in ("admin", "corporate"):
        return jsonify(error="only admins and corporate users can access this endpoint"), 403
    
    # For admin, only show managers for their dealership
    if user.role == "admin":
        if not user.dealership_id:
            return jsonify(ok=True, managers=[], total=0)
        pending_managers = User.query.filter_by(dealership_id=user.dealership_id, role="manager", is_approved=False).all()
    else:
        # Corporate sees all pending managers
        pending_managers = User.query.filter_by(role="manager", is_approved=False).all()
    
    return jsonify(
        ok=True,
        managers=[m.to_dict() for m in pending_managers],
        total=len(pending_managers)
    )

@app.post("/admin/managers")
@limiter.limit("10 per minute")
def create_manager():
    """
    Create a manager account for the admin's dealership.
    Only admins can create managers for their own dealership.
    """
    user, err = get_current_user()
    if err:
        return err
    
    if user.role != "admin":
        return jsonify(error="only admins can create manager accounts"), 403
    
    if not user.dealership_id:
        return jsonify(error="admin must be assigned to a dealership"), 400
    
    data = request.get_json(silent=True) or {}
    email = sanitize_input(data.get("email", "").strip().lower())
    password = data.get("password", "")
    
    if not email or not password:
        return jsonify(error="email and password are required"), 400
    
    if not validate_email(email):
        return jsonify(error="please enter a valid email address"), 400
    
    if not validate_password(password):
        return jsonify(error="password must be at least 8 characters and include both letters and numbers"), 400
    
    # Check if user already exists
    existing = User.query.filter_by(email=email).first()
    if existing:
        return jsonify(error="this email is already registered"), 400
    
    # Generate verification code
    code_int = secrets.randbelow(1_000_000)
    verification_code = f"{code_int:06d}"
    expires_at = datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    
    # Create manager account (auto-verified, but needs approval)
    manager = User(
        email=email,
        password_hash=generate_password_hash(password),
        role="manager",
        dealership_id=user.dealership_id,
        is_verified=True,  # Auto-verify for admin-created managers
        is_approved=False,  # Still needs approval
        verification_code=verification_code,
        verification_expires_at=expires_at,
    )
    db.session.add(manager)
    db.session.commit()
    
    # Log admin action
    log_admin_action(
        user.email,
        "create_manager",
        "user",
        manager.id,
        json.dumps({"manager_email": manager.email, "dealership_id": user.dealership_id})
    )
    
    return jsonify(ok=True, manager=manager.to_dict(), message=f"Manager account created for '{manager.email}' successfully")

@app.post("/admin/managers/<int:manager_id>/approve")
@limiter.limit("20 per minute")
def approve_manager(manager_id: int):
    """
    Approve a manager account.
    Only admins and corporate users can approve managers.
    """
    user, err = get_current_user()
    if err:
        return err
    
    if user.role not in ("admin", "corporate"):
        return jsonify(error="only admins and corporate users can approve managers"), 403
    
    manager = User.query.get(manager_id)
    if not manager:
        return jsonify(error="manager not found"), 404
    
    if manager.role != "manager":
        return jsonify(error="user is not a manager"), 400
    
    if manager.is_approved:
        return jsonify(error="manager already approved"), 400
    
    # Approve the manager
    manager.is_approved = True
    manager.approved_at = datetime.datetime.utcnow()
    manager.approved_by = user.id
    db.session.commit()
    
    # Log admin action
    log_admin_action(
        user.email,
        "approve_manager",
        "user",
        manager_id,
        json.dumps({"manager_email": manager.email})
    )
    
    return jsonify(ok=True, message=f"Manager '{manager.email}' approved successfully")

@app.post("/admin/managers/<int:manager_id>/reject")
@limiter.limit("20 per minute")
def reject_manager(manager_id: int):
    """
    Reject a manager account (delete it).
    Only admins and corporate users can reject managers.
    For admins, they can only reject managers for their own dealership.
    """
    user, err = get_current_user()
    if err:
        return err
    
    if user.role not in ("admin", "corporate"):
        return jsonify(error="only admins and corporate users can reject managers"), 403
    
    manager = User.query.get(manager_id)
    if not manager:
        return jsonify(error="manager not found"), 404
    
    if manager.role != "manager":
        return jsonify(error="user is not a manager"), 400
    
    # For admin, check if manager belongs to their dealership
    if user.role == "admin":
        if not user.dealership_id or manager.dealership_id != user.dealership_id:
            return jsonify(error="you can only reject managers for your own dealership"), 403
    
    manager_email = manager.email
    
    # Delete the manager account
    db.session.delete(manager)
    db.session.commit()
    
    # Log admin action
    log_admin_action(
        user.email,
        "reject_manager",
        "user",
        manager_id,
        json.dumps({"manager_email": manager_email})
    )
    
    return jsonify(ok=True, message=f"Manager '{manager_email}' rejected and removed")

@app.post("/admin/corporate/<int:corporate_user_id>/dealerships/<int:dealership_id>/assign")
@limiter.limit("20 per minute")
def admin_assign_dealership_to_corporate(corporate_user_id: int, dealership_id: int):
    """
    Assign a dealership to a corporate user.
    Only admins and corporate users can assign dealerships to corporate users.
    """
    user, err = get_current_user()
    if err:
        return err
    
    if user.role not in ("admin", "corporate"):
        return jsonify(error="only admins and corporate users can assign dealerships to corporate users"), 403
    
    corporate_user = User.query.get(corporate_user_id)
    if not corporate_user:
        return jsonify(error="corporate user not found"), 404
    
    if corporate_user.role != "corporate":
        return jsonify(error="user is not a corporate user"), 400
    
    dealership = Dealership.query.get(dealership_id)
    if not dealership:
        return jsonify(error="dealership not found"), 404
    
    # Check if already assigned
    if dealership in corporate_user.corporate_dealerships.all():
        return jsonify(error="dealership already assigned to this corporate user"), 400
    
    # Assign the dealership
    corporate_user.corporate_dealerships.append(dealership)
    db.session.commit()
    
    # Log admin action
    log_admin_action(
        user.email,
        "assign_dealership_to_corporate",
        "dealership",
        dealership_id,
        json.dumps({"corporate_user_email": corporate_user.email, "dealership_name": dealership.name})
    )
    
    return jsonify(ok=True, message=f"Dealership '{dealership.name}' assigned to '{corporate_user.email}' successfully")

@app.delete("/admin/corporate/<int:corporate_user_id>/dealerships/<int:dealership_id>/unassign")
@limiter.limit("20 per minute")
def admin_unassign_dealership_from_corporate(corporate_user_id: int, dealership_id: int):
    """
    Unassign a dealership from a corporate user.
    Only admins and corporate users can unassign dealerships from corporate users.
    """
    user, err = get_current_user()
    if err:
        return err
    
    if user.role not in ("admin", "corporate"):
        return jsonify(error="only admins and corporate users can unassign dealerships from corporate users"), 403
    
    corporate_user = User.query.get(corporate_user_id)
    if not corporate_user:
        return jsonify(error="corporate user not found"), 404
    
    if corporate_user.role != "corporate":
        return jsonify(error="user is not a corporate user"), 400
    
    dealership = Dealership.query.get(dealership_id)
    if not dealership:
        return jsonify(error="dealership not found"), 404
    
    # Check if assigned
    if dealership not in corporate_user.corporate_dealerships.all():
        return jsonify(error="dealership not assigned to this corporate user"), 400
    
    # Unassign the dealership
    corporate_user.corporate_dealerships.remove(dealership)
    db.session.commit()
    
    # Log admin action
    log_admin_action(
        user.email,
        "unassign_dealership_from_corporate",
        "dealership",
        dealership_id,
        json.dumps({"corporate_user_email": corporate_user.email, "dealership_name": dealership.name})
    )
    
    return jsonify(ok=True, message=f"Dealership '{dealership.name}' unassigned from '{corporate_user.email}' successfully")

@app.get("/admin/corporate-users")
@limiter.limit("30 per minute")
def get_corporate_users():
    """
    Get all corporate users with their assigned dealerships.
    Only admins and corporate users can access this endpoint.
    """
    user, err = get_current_user()
    if err:
        return err
    
    if user.role not in ("admin", "corporate"):
        return jsonify(error="only admins and corporate users can access this endpoint"), 403
    
    corporate_users = User.query.filter_by(role="corporate").all()
    
    users_with_dealerships = []
    for cu in corporate_users:
        user_dict = cu.to_dict()
        accessible_dealership_ids = get_accessible_dealership_ids(cu)
        dealerships = Dealership.query.filter(Dealership.id.in_(accessible_dealership_ids)).all() if accessible_dealership_ids else []
        user_dict["dealerships"] = [d.to_dict() for d in dealerships]
        user_dict["dealership_count"] = len(dealerships)
        users_with_dealerships.append(user_dict)
    
    return jsonify(
        ok=True,
        corporate_users=users_with_dealerships,
        total=len(users_with_dealerships)
    )

# ===== CORPORATE MANAGEMENT ENDPOINTS =====

@app.post("/corporate/dealerships")
@limiter.limit("10 per minute")
def create_dealership():
    """
    Create a new dealership.
    Only corporate users can create dealerships.
    """
    user, err = get_current_user()
    if err:
        return err
    
    if user.role != "corporate":
        return jsonify(error="only corporate users can create dealerships"), 403
    
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    address = data.get("address", "").strip() or None
    city = data.get("city", "").strip() or None
    state = data.get("state", "").strip() or None
    zip_code = data.get("zip_code", "").strip() or None
    
    if not name:
        return jsonify(error="dealership name is required"), 400
    
    # Create dealership with 14-day trial
    now = datetime.datetime.utcnow()
    dealership = Dealership(
        name=name,
        address=address,
        city=city,
        state=state,
        zip_code=zip_code,
        subscription_status="trial",
        trial_ends_at=now + datetime.timedelta(days=14),
        created_at=now,
        updated_at=now,
    )
    db.session.add(dealership)
    db.session.flush()  # Get the ID
    
    # Automatically assign this dealership to the corporate user
    user.corporate_dealerships.append(dealership)
    db.session.commit()
    
    # Log admin action
    log_admin_action(
        user.email,
        "create_dealership",
        "dealership",
        dealership.id,
        json.dumps({"dealership_name": dealership.name})
    )
    
    return jsonify(ok=True, dealership=dealership.to_dict(), message=f"Dealership '{dealership.name}' created successfully")

@app.post("/corporate/dealerships/<int:dealership_id>/admins")
@limiter.limit("10 per minute")
def create_admin_for_dealership(dealership_id: int):
    """
    Create an admin account for a specific dealership.
    Only corporate users can create admins for their assigned dealerships.
    """
    user, err = get_current_user()
    if err:
        return err
    
    if user.role != "corporate":
        return jsonify(error="only corporate users can create admin accounts"), 403
    
    # Check if corporate user has access to this dealership
    accessible_dealership_ids = get_accessible_dealership_ids(user)
    if dealership_id not in accessible_dealership_ids:
        return jsonify(error="you do not have access to this dealership"), 403
    
    dealership = Dealership.query.get(dealership_id)
    if not dealership:
        return jsonify(error="dealership not found"), 404
    
    data = request.get_json(silent=True) or {}
    email = sanitize_input(data.get("email", "").strip().lower())
    password = data.get("password", "")
    
    if not email or not password:
        return jsonify(error="email and password are required"), 400
    
    if not validate_email(email):
        return jsonify(error="please enter a valid email address"), 400
    
    if not validate_password(password):
        return jsonify(error="password must be at least 8 characters and include both letters and numbers"), 400
    
    # Check if user already exists
    existing = User.query.filter_by(email=email).first()
    if existing:
        return jsonify(error="this email is already registered"), 400
    
    # Check if dealership already has an admin
    existing_admin = User.query.filter_by(dealership_id=dealership_id, role="admin").first()
    if existing_admin:
        return jsonify(error="this dealership already has an admin account"), 400
    
    # Create admin account (auto-verified and approved)
    admin_user = User(
        email=email,
        password_hash=generate_password_hash(password),
        role="admin",
        is_verified=True,  # Auto-verify for corporate-created admins
        is_approved=True,  # Auto-approve
        dealership_id=dealership_id,
    )
    db.session.add(admin_user)
    db.session.commit()
    
    # Log admin action
    log_admin_action(
        user.email,
        "create_admin",
        "user",
        admin_user.id,
        json.dumps({"admin_email": admin_user.email, "dealership_id": dealership_id, "dealership_name": dealership.name})
    )
    
    return jsonify(ok=True, admin=admin_user.to_dict(), message=f"Admin account created for '{dealership.name}' successfully")

# ===== ADMIN REQUEST SYSTEM =====

@app.post("/admin/request")
@limiter.limit("5 per hour")
def request_admin_status():
    """
    Request to become an admin for a dealership.
    Only managers can request admin status.
    """
    user, err = get_current_user()
    if err:
        return err
    
    if user.role != "manager":
        return jsonify(error="only managers can request admin status"), 403
    
    if not user.is_approved:
        return jsonify(error="your manager account must be approved first"), 403
    
    data = request.get_json(silent=True) or {}
    dealership_id = data.get("dealership_id")
    
    if not dealership_id:
        return jsonify(error="dealership_id is required"), 400
    
    dealership = Dealership.query.get(dealership_id)
    if not dealership:
        return jsonify(error="dealership not found"), 404
    
    # Check if dealership already has an admin
    existing_admin = User.query.filter_by(dealership_id=dealership_id, role="admin").first()
    if existing_admin:
        return jsonify(error="this dealership already has an admin"), 400
    
    # Check if user already has a pending request for this dealership
    existing_request = AdminRequest.query.filter_by(
        user_id=user.id,
        dealership_id=dealership_id,
        status="pending"
    ).first()
    
    if existing_request:
        return jsonify(error="you already have a pending request for this dealership"), 400
    
    # Create admin request
    admin_request = AdminRequest(
        user_id=user.id,
        dealership_id=dealership_id,
        status="pending",
    )
    db.session.add(admin_request)
    db.session.commit()
    
    return jsonify(ok=True, request=admin_request.to_dict(), message="Admin request submitted successfully")

@app.get("/corporate/admin-requests")
@limiter.limit("30 per minute")
def get_admin_requests():
    """
    Get all pending admin requests for dealerships assigned to the corporate user.
    Only corporate users can access this endpoint.
    """
    user, err = get_current_user()
    if err:
        return err
    
    if user.role != "corporate":
        return jsonify(error="only corporate users can view admin requests"), 403
    
    # Get accessible dealership IDs
    accessible_dealership_ids = get_accessible_dealership_ids(user)
    if not accessible_dealership_ids:
        return jsonify(ok=True, requests=[], total=0)
    
    # Get pending requests for accessible dealerships
    pending_requests = AdminRequest.query.filter(
        AdminRequest.dealership_id.in_(accessible_dealership_ids),
        AdminRequest.status == "pending"
    ).all()
    
    return jsonify(
        ok=True,
        requests=[r.to_dict() for r in pending_requests],
        total=len(pending_requests)
    )

@app.post("/corporate/admin-requests/<int:request_id>/approve")
@limiter.limit("20 per minute")
def approve_admin_request(request_id: int):
    """
    Approve an admin request.
    Only corporate users can approve admin requests for their assigned dealerships.
    """
    user, err = get_current_user()
    if err:
        return err
    
    if user.role != "corporate":
        return jsonify(error="only corporate users can approve admin requests"), 403
    
    admin_request = AdminRequest.query.get(request_id)
    if not admin_request:
        return jsonify(error="admin request not found"), 404
    
    # Check if corporate user has access to this dealership
    accessible_dealership_ids = get_accessible_dealership_ids(user)
    if admin_request.dealership_id not in accessible_dealership_ids:
        return jsonify(error="you do not have access to this dealership"), 403
    
    if admin_request.status != "pending":
        return jsonify(error="this request has already been processed"), 400
    
    # Check if dealership already has an admin
    existing_admin = User.query.filter_by(dealership_id=admin_request.dealership_id, role="admin").first()
    if existing_admin:
        return jsonify(error="this dealership already has an admin"), 400
    
    # Upgrade manager to admin
    manager = admin_request.user
    manager.role = "admin"
    manager.dealership_id = admin_request.dealership_id
    
    # Update request status
    admin_request.status = "approved"
    admin_request.reviewed_at = datetime.datetime.utcnow()
    admin_request.reviewed_by = user.id
    
    db.session.commit()
    
    # Log admin action
    log_admin_action(
        user.email,
        "approve_admin_request",
        "user",
        manager.id,
        json.dumps({"manager_email": manager.email, "dealership_id": admin_request.dealership_id})
    )
    
    return jsonify(ok=True, message=f"Admin request approved. '{manager.email}' is now admin for this dealership")

# ===== DEALERSHIP ACCESS REQUEST ENDPOINTS =====

@app.post("/corporate/dealerships/<int:dealership_id>/request")
@limiter.limit("10 per hour")
def request_dealership_access(dealership_id: int):
    """
    Corporate user requests access to view a dealership's stats.
    Only corporate users can request access.
    """
    user, err = get_current_user()
    if err:
        return err
    
    if user.role != "corporate":
        return jsonify(error="only corporate users can request dealership access"), 403
    
    dealership = Dealership.query.get(dealership_id)
    if not dealership:
        return jsonify(error="dealership not found"), 404
    
    # Check if already assigned
    accessible_dealership_ids = get_accessible_dealership_ids(user)
    if dealership_id in accessible_dealership_ids:
        return jsonify(error="you already have access to this dealership"), 400
    
    # Check if user already has a pending request for this dealership
    existing_request = DealershipAccessRequest.query.filter_by(
        corporate_user_id=user.id,
        dealership_id=dealership_id,
        status="pending"
    ).first()
    
    if existing_request:
        return jsonify(error="you already have a pending request for this dealership"), 400
    
    # Create access request
    access_request = DealershipAccessRequest(
        corporate_user_id=user.id,
        dealership_id=dealership_id,
        status="pending"
    )
    db.session.add(access_request)
    db.session.commit()
    
    return jsonify(
        ok=True,
        request=access_request.to_dict(),
        message=f"Access request submitted for '{dealership.name}'. Waiting for admin approval."
    )

@app.get("/corporate/dealership-requests")
@limiter.limit("30 per minute")
def get_corporate_dealership_requests():
    """
    Get all dealership access requests made by the current corporate user.
    Only corporate users can access this endpoint.
    """
    user, err = get_current_user()
    if err:
        return err
    
    if user.role != "corporate":
        return jsonify(error="only corporate users can view their own access requests"), 403
    
    requests = DealershipAccessRequest.query.filter_by(corporate_user_id=user.id).order_by(DealershipAccessRequest.requested_at.desc()).all()
    
    return jsonify(
        ok=True,
        requests=[r.to_dict() for r in requests],
        total=len(requests)
    )

@app.get("/admin/dealership-requests")
@limiter.limit("30 per minute")
def get_admin_dealership_requests():
    """
    Get all pending dealership access requests.
    Only admins can access this endpoint.
    """
    user, err = get_current_user()
    if err:
        return err
    
    if user.role != "admin":
        return jsonify(error="only admins can view dealership access requests"), 403
    
    # Get all pending requests
    pending_requests = DealershipAccessRequest.query.filter_by(status="pending").order_by(DealershipAccessRequest.requested_at.desc()).all()
    
    # Also get recent processed requests (last 50)
    processed_requests = DealershipAccessRequest.query.filter(
        DealershipAccessRequest.status != "pending"
    ).order_by(DealershipAccessRequest.reviewed_at.desc()).limit(50).all()
    
    return jsonify(
        ok=True,
        pending=[r.to_dict() for r in pending_requests],
        processed=[r.to_dict() for r in processed_requests],
        total_pending=len(pending_requests),
        total_processed=len(processed_requests)
    )

@app.post("/admin/dealership-requests/<int:request_id>/approve")
@limiter.limit("20 per minute")
def approve_dealership_access_request(request_id: int):
    """
    Approve a dealership access request.
    Only admins can approve requests.
    """
    user, err = get_current_user()
    if err:
        return err
    
    if user.role != "admin":
        return jsonify(error="only admins can approve dealership access requests"), 403
    
    access_request = DealershipAccessRequest.query.get(request_id)
    if not access_request:
        return jsonify(error="access request not found"), 404
    
    if access_request.status != "pending":
        return jsonify(error="this request has already been processed"), 400
    
    corporate_user = User.query.get(access_request.corporate_user_id)
    if not corporate_user or corporate_user.role != "corporate":
        return jsonify(error="corporate user not found"), 404
    
    dealership = Dealership.query.get(access_request.dealership_id)
    if not dealership:
        return jsonify(error="dealership not found"), 404
    
    # Check if already assigned
    if dealership in corporate_user.corporate_dealerships.all():
        # Already assigned, just update request status
        access_request.status = "approved"
        access_request.reviewed_at = datetime.datetime.utcnow()
        access_request.reviewed_by = user.id
        db.session.commit()
        return jsonify(ok=True, message="Dealership already assigned to this corporate user")
    
    # Assign the dealership
    corporate_user.corporate_dealerships.append(dealership)
    
    # Update request status
    access_request.status = "approved"
    access_request.reviewed_at = datetime.datetime.utcnow()
    access_request.reviewed_by = user.id
    
    db.session.commit()
    
    # Log admin action
    log_admin_action(
        user.email,
        "approve_dealership_access_request",
        "dealership_access_request",
        request_id,
        json.dumps({
            "corporate_user_email": corporate_user.email,
            "dealership_id": dealership.id,
            "dealership_name": dealership.name
        })
    )
    
    return jsonify(
        ok=True,
        message=f"Access request approved. '{corporate_user.email}' can now view '{dealership.name}'"
    )

@app.post("/admin/dealership-requests/<int:request_id>/reject")
@limiter.limit("20 per minute")
def reject_dealership_access_request(request_id: int):
    """
    Reject a dealership access request.
    Only admins can reject requests.
    """
    user, err = get_current_user()
    if err:
        return err
    
    if user.role != "admin":
        return jsonify(error="only admins can reject dealership access requests"), 403
    
    access_request = DealershipAccessRequest.query.get(request_id)
    if not access_request:
        return jsonify(error="access request not found"), 404
    
    if access_request.status != "pending":
        return jsonify(error="this request has already been processed"), 400
    
    data = request.get_json(silent=True) or {}
    notes = data.get("notes", "").strip()
    
    # Update request status
    access_request.status = "rejected"
    access_request.reviewed_at = datetime.datetime.utcnow()
    access_request.reviewed_by = user.id
    if notes:
        access_request.notes = notes
    
    db.session.commit()
    
    # Log admin action
    log_admin_action(
        user.email,
        "reject_dealership_access_request",
        "dealership_access_request",
        request_id,
        json.dumps({
            "corporate_user_email": access_request.corporate_user.email if access_request.corporate_user else None,
            "dealership_id": access_request.dealership_id,
            "notes": notes
        })
    )
    
    return jsonify(ok=True, message="Access request rejected")

# ===== ROLE PERMISSIONS ENDPOINTS =====

# Default permissions for each role
DEFAULT_PERMISSIONS = {
    "admin": {
        "view_dashboard": True,
        "view_employees": True,
        "view_candidates": True,
        "view_analytics": True,
        "view_surveys": True,
        "view_subscription": True,
        "create_survey": True,
        "manage_survey": True,
        "create_employee": True,
        "manage_employee": True,
        "create_candidate": True,
        "manage_candidate": True,
    },
    "manager": {
        "view_dashboard": True,
        "view_employees": True,
        "view_candidates": True,
        "view_analytics": False,  # Managers can't view analytics
        "view_surveys": True,
        "view_subscription": True,
        "create_survey": False,  # Managers can't create surveys
        "manage_survey": False,
        "create_employee": False,
        "manage_employee": False,
        "create_candidate": True,
        "manage_candidate": True,
    },
    "corporate": {
        "view_dashboard": True,
        "view_employees": True,
        "view_candidates": True,
        "view_analytics": True,
        "view_surveys": True,
        "view_subscription": True,
        "create_survey": False,
        "manage_survey": False,
        "create_employee": False,
        "manage_employee": False,
        "create_candidate": False,
        "manage_candidate": False,
    },
}

def get_permission(role: str, permission_key: str) -> bool:
    """
    Check if a role has a specific permission.
    Returns True if allowed, False if not.
    Admin always has all permissions.
    """
    if role == "admin":
        return True  # Admin always has all permissions
    
    # Check database first
    perm = RolePermission.query.filter_by(role=role, permission_key=permission_key).first()
    if perm:
        return perm.allowed
    
    # Fall back to defaults
    return DEFAULT_PERMISSIONS.get(role, {}).get(permission_key, False)

def has_permission(user, permission_key: str) -> bool:
    """
    Check if user has a specific permission.
    Priority:
    1. Admin always has all permissions
    2. Check user-specific permissions (for managers)
    3. Fall back to role-based permissions
    """
    if user.role == "admin":
        return True  # Admin always has all permissions
    
    # For corporate users, only use role-based permissions
    if user.role == "corporate":
        return get_permission(user.role, permission_key)
    
    # For managers, check user-specific permissions first
    if user.role == "manager":
        user_perm = UserPermission.query.filter_by(user_id=user.id, permission_key=permission_key).first()
        if user_perm is not None:
            return user_perm.allowed
        # Fall back to role-based permissions
        return get_permission(user.role, permission_key)
    
    # Default fallback
    return get_permission(user.role, permission_key)

@app.get("/admin/permissions")
@limiter.limit("30 per minute")
def get_role_permissions():
    """
    Get all permissions for all roles.
    Only admins can access this endpoint.
    """
    user, err = get_current_user()
    if err:
        return err
    
    if user.role != "admin":
        return jsonify(error="only admins can view permissions"), 403
    
    # Get all permissions from database
    all_permissions = RolePermission.query.all()
    
    # Build permission matrix
    roles = ["manager", "corporate", "admin"]
    permission_keys = list(DEFAULT_PERMISSIONS["admin"].keys())
    
    matrix = {}
    for role in roles:
        matrix[role] = {}
        for key in permission_keys:
            perm = RolePermission.query.filter_by(role=role, permission_key=key).first()
            if perm:
                matrix[role][key] = perm.allowed
            else:
                # Use default
                matrix[role][key] = DEFAULT_PERMISSIONS.get(role, {}).get(key, False)
    
    return jsonify(
        ok=True,
        permissions=matrix,
        roles=roles,
        permission_keys=permission_keys
    )

@app.post("/admin/permissions")
@limiter.limit("20 per minute")
def update_role_permissions():
    """
    Update permissions for a role.
    Only admins can update permissions.
    """
    user, err = get_current_user()
    if err:
        return err
    
    if user.role != "admin":
        return jsonify(error="only admins can update permissions"), 403
    
    data = request.get_json(silent=True) or {}
    role = data.get("role")
    permission_key = data.get("permission_key")
    allowed = data.get("allowed", True)
    
    if not role or not permission_key:
        return jsonify(error="role and permission_key are required"), 400
    
    if role == "admin":
        return jsonify(error="cannot modify admin permissions"), 400
    
    # Find or create permission
    perm = RolePermission.query.filter_by(role=role, permission_key=permission_key).first()
    if perm:
        perm.allowed = allowed
        perm.updated_at = datetime.datetime.utcnow()
    else:
        perm = RolePermission(
            role=role,
            permission_key=permission_key,
            allowed=allowed
        )
        db.session.add(perm)
    
    db.session.commit()
    
    # Log admin action
    log_admin_action(
        user.email,
        "update_permission",
        "permission",
        perm.id,
        json.dumps({"role": role, "permission_key": permission_key, "allowed": allowed})
    )
    
    return jsonify(ok=True, permission=perm.to_dict(), message="Permission updated successfully")

@app.get("/auth/permissions")
@limiter.limit("30 per minute")
def get_user_permissions():
    """
    Get permissions for the current user.
    All authenticated users can access this.
    """
    user, err = get_current_user()
    if err:
        return err
    
    # Build permissions object for this user
    permission_keys = list(DEFAULT_PERMISSIONS["admin"].keys())
    permissions = {}
    for key in permission_keys:
        permissions[key] = has_permission(user, key)
    
    return jsonify(ok=True, permissions=permissions, role=user.role)

@app.get("/admin/managers/<int:manager_id>/permissions")
@limiter.limit("30 per minute")
def get_manager_permissions(manager_id: int):
    """
    Get permissions for a specific manager.
    Only admins can access this endpoint.
    """
    user, err = get_current_user()
    if err:
        return err
    
    if user.role != "admin":
        return jsonify(error="only admins can access this endpoint"), 403
    
    manager = User.query.get(manager_id)
    if not manager:
        return jsonify(error="manager not found"), 404
    
    if manager.role != "manager":
        return jsonify(error="user is not a manager"), 400
    
    # Verify manager belongs to admin's dealership
    if manager.dealership_id != user.dealership_id:
        return jsonify(error="manager does not belong to your dealership"), 403
    
    # Get user-specific permissions
    user_perms = UserPermission.query.filter_by(user_id=manager_id).all()
    permission_keys = list(DEFAULT_PERMISSIONS["admin"].keys())
    
    permissions = {}
    for key in permission_keys:
        user_perm = next((p for p in user_perms if p.permission_key == key), None)
        if user_perm is not None:
            permissions[key] = user_perm.allowed
        else:
            # Use role-based permission
            permissions[key] = get_permission(manager.role, key)
    
    return jsonify(
        ok=True,
        permissions=permissions,
        permission_keys=permission_keys,
        manager_id=manager_id,
        manager_email=manager.email
    )

@app.post("/admin/managers/<int:manager_id>/permissions")
@limiter.limit("20 per minute")
def update_manager_permission(manager_id: int):
    """
    Update a permission for a specific manager.
    Only admins can update manager permissions.
    """
    user, err = get_current_user()
    if err:
        return err
    
    if user.role != "admin":
        return jsonify(error="only admins can update permissions"), 403
    
    manager = User.query.get(manager_id)
    if not manager:
        return jsonify(error="manager not found"), 404
    
    if manager.role != "manager":
        return jsonify(error="user is not a manager"), 400
    
    # Verify manager belongs to admin's dealership
    if manager.dealership_id != user.dealership_id:
        return jsonify(error="manager does not belong to your dealership"), 403
    
    data = request.get_json(silent=True) or {}
    permission_key = data.get("permission_key")
    allowed = data.get("allowed", True)
    
    if not permission_key:
        return jsonify(error="permission_key is required"), 400
    
    # Find or create permission
    perm = UserPermission.query.filter_by(user_id=manager_id, permission_key=permission_key).first()
    if perm:
        perm.allowed = allowed
        perm.updated_at = datetime.datetime.utcnow()
    else:
        perm = UserPermission(
            user_id=manager_id,
            permission_key=permission_key,
            allowed=allowed
        )
        db.session.add(perm)
    
    db.session.commit()
    
    # Log admin action
    log_admin_action(
        user.email,
        "update_manager_permission",
        "permission",
        perm.id,
        json.dumps({"manager_id": manager_id, "manager_email": manager.email, "permission_key": permission_key, "allowed": allowed})
    )
    
    return jsonify(ok=True, permission=perm.to_dict(), message="Permission updated successfully")

@app.delete("/admin/managers/<int:manager_id>/permissions/<permission_key>")
@limiter.limit("20 per minute")
def delete_manager_permission(manager_id: int, permission_key: str):
    """
    Delete a user-specific permission (revert to role-based permission).
    Only admins can delete manager permissions.
    """
    user, err = get_current_user()
    if err:
        return err
    
    if user.role != "admin":
        return jsonify(error="only admins can delete permissions"), 403
    
    manager = User.query.get(manager_id)
    if not manager:
        return jsonify(error="manager not found"), 404
    
    if manager.role != "manager":
        return jsonify(error="user is not a manager"), 400
    
    # Verify manager belongs to admin's dealership
    if manager.dealership_id != user.dealership_id:
        return jsonify(error="manager does not belong to your dealership"), 403
    
    perm = UserPermission.query.filter_by(user_id=manager_id, permission_key=permission_key).first()
    if perm:
        db.session.delete(perm)
        db.session.commit()
        
        # Log admin action
        log_admin_action(
            user.email,
            "delete_manager_permission",
            "permission",
            manager_id,
            json.dumps({"manager_id": manager_id, "manager_email": manager.email, "permission_key": permission_key})
        )
        
        return jsonify(ok=True, message="Permission deleted, will use role-based permission")
    
    return jsonify(error="permission not found"), 404

@app.post("/corporate/admin-requests/<int:request_id>/reject")
@limiter.limit("20 per minute")
def reject_admin_request(request_id: int):
    """
    Reject an admin request.
    Only corporate users can reject admin requests for their assigned dealerships.
    """
    user, err = get_current_user()
    if err:
        return err
    
    if user.role != "corporate":
        return jsonify(error="only corporate users can reject admin requests"), 403
    
    admin_request = AdminRequest.query.get(request_id)
    if not admin_request:
        return jsonify(error="admin request not found"), 404
    
    # Check if corporate user has access to this dealership
    accessible_dealership_ids = get_accessible_dealership_ids(user)
    if admin_request.dealership_id not in accessible_dealership_ids:
        return jsonify(error="you do not have access to this dealership"), 403
    
    if admin_request.status != "pending":
        return jsonify(error="this request has already been processed"), 400
    
    data = request.get_json(silent=True) or {}
    notes = data.get("notes", "").strip() or None
    
    # Update request status
    admin_request.status = "rejected"
    admin_request.reviewed_at = datetime.datetime.utcnow()
    admin_request.reviewed_by = user.id
    admin_request.notes = notes
    
    db.session.commit()
    
    # Log admin action
    log_admin_action(
        user.email,
        "reject_admin_request",
        "user",
        admin_request.user_id,
        json.dumps({"manager_email": admin_request.user.email, "dealership_id": admin_request.dealership_id, "notes": notes})
    )
    
    return jsonify(ok=True, message="Admin request rejected")

# ===== USER MANAGEMENT ENDPOINTS =====

@app.delete("/admin/users/<int:user_id>")
@limiter.limit("10 per minute")
def delete_user(user_id: int):
    """
    Delete a user account.
    Only admins can delete users.
    """
    user, err = get_current_user()
    if err:
        return err
    
    if user.role != "admin":
        return jsonify(error="only admins can delete users"), 403
    
    # Don't allow deleting yourself
    if user.id == user_id:
        return jsonify(error="you cannot delete your own account"), 400
    
    user_to_delete = User.query.get(user_id)
    if not user_to_delete:
        return jsonify(error="user not found"), 404
    
    user_email = user_to_delete.email
    user_role = user_to_delete.role
    
    # Delete related data first (if any)
    # Note: You may want to handle cascading deletes based on your needs
    
    # Delete the user
    db.session.delete(user_to_delete)
    db.session.commit()
    
    # Log admin action
    log_admin_action(
        user.email,
        "delete_user",
        "user",
        user_id,
        json.dumps({"deleted_user_email": user_email, "deleted_user_role": user_role})
    )
    
    return jsonify(ok=True, message=f"User '{user_email}' deleted successfully")

@app.get("/admin/users")
@limiter.limit("30 per minute")
def list_all_users():
    """
    List all users in the system.
    Only admins can access this endpoint.
    """
    user, err = get_current_user()
    if err:
        return err
    
    if user.role != "admin":
        return jsonify(error="only admins can list all users"), 403
    
    users = User.query.order_by(User.created_at.desc()).all()
    
    return jsonify(
        ok=True,
        users=[u.to_dict() for u in users],
        total=len(users)
    )

# --- Ensure DB tables exist on startup (Render + local) ---
with app.app_context():
    db.create_all()
    
    # Migrate: Add new columns to users table if they don't exist
    try:
        inspector = inspect(db.engine)
        
        # Check if is_approved column exists (works for both PostgreSQL and SQLite)
        columns = [col['name'] for col in inspector.get_columns('users')]
        
        if 'is_approved' not in columns:
            print("[MIGRATION] Adding is_approved, approved_at, approved_by columns to users table...", flush=True)
            with db.engine.connect() as conn:
                # PostgreSQL uses different syntax
                if 'postgresql' in str(db.engine.url):
                    conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_approved BOOLEAN NOT NULL DEFAULT FALSE"))
                    conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS approved_at TIMESTAMP"))
                    conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS approved_by INTEGER"))
                else:
                    # SQLite fallback (for backwards compatibility)
                    conn.execute(text("ALTER TABLE users ADD COLUMN is_approved BOOLEAN NOT NULL DEFAULT 0"))
                    conn.execute(text("ALTER TABLE users ADD COLUMN approved_at DATETIME"))
                    conn.execute(text("ALTER TABLE users ADD COLUMN approved_by INTEGER"))
                
                conn.execute(text("UPDATE users SET is_approved = TRUE WHERE role != 'manager'"))  # Auto-approve existing non-managers
                conn.commit()
            print("[MIGRATION] Successfully added new columns to users table", flush=True)
        
    except Exception as e:
        print(f"[MIGRATION] Error during migration (may already be migrated): {e}", flush=True)
    
    print("[OK] Ensured all DB tables exist in", db.engine.url)

@app.post("/admin/cleanup-unsubscribed")
@limiter.limit("10 per hour")
def cleanup_unsubscribed_admins():
    """
    Cleanup endpoint to delete admin accounts that haven't subscribed.
    - Unverified users: Delete immediately (no time threshold)
    - Verified but unsubscribed users: Delete after 24 hours (or configurable time)
    """
    try:
        # Get time threshold for verified users (default 24 hours)
        hours_threshold = int(request.args.get("hours", 24))
        threshold_time = datetime.datetime.utcnow() - datetime.timedelta(hours=hours_threshold)
        
        deleted_count = 0
        
        # 1. Delete unverified admin registrations immediately (no time threshold)
        unverified = User.query.filter(
            User.role == "manager",
            User.is_verified == False,
            User.is_approved == False,
            User.dealership_id == None
        ).all()
        
        for user in unverified:
            print(f"[CLEANUP] Deleting unverified admin account: {user.email} (created {user.created_at})", flush=True)
            db.session.delete(user)
            deleted_count += 1
        
        # 2. Delete verified but unsubscribed admin accounts after time threshold
        verified_unsubscribed = User.query.filter(
            User.role == "manager",
            User.is_verified == True,
            User.is_approved == False,
            User.dealership_id == None,
            User.created_at < threshold_time
        ).all()
        
        for user in verified_unsubscribed:
            print(f"[CLEANUP] Deleting verified but unsubscribed admin account: {user.email} (created {user.created_at}, verified but not subscribed after {hours_threshold}h)", flush=True)
            # Send deletion email for verified users
            try:
                user_email = user.email
                user_full_name = user.full_name or "User"
                subject = "Star4ce – Account Cancellation"
                body = f"""Hello {user_full_name},

Your Star4ce account ({user_email}) has been automatically deleted because you did not complete your subscription within the required time.

If you change your mind, you can register again at any time.

Thank you for your interest in Star4ce.

– Star4ce Team
"""
                send_email_via_resend_or_smtp(user_email, subject, body)
            except Exception as e:
                print(f"[CLEANUP WARNING] Failed to send deletion email to {user.email}: {e}", flush=True)
            
            db.session.delete(user)
            deleted_count += 1
        
        db.session.commit()
        
        return jsonify(
            ok=True,
            message=f"Cleaned up {deleted_count} unsubscribed admin account(s)",
            deleted_count=deleted_count
        )
    except Exception as e:
        db.session.rollback()
        print(f"[CLEANUP ERROR] {str(e)}", flush=True)
        return jsonify(error=f"Cleanup failed: {str(e)}"), 500

@app.get("/auth/check-unsubscribed")
@limiter.limit("20 per minute")
def check_unsubscribed():
    """Check if a user is verified but not subscribed (should be deleted)"""
    try:
        email = request.args.get("email", "").strip().lower()
        if not email:
            return jsonify(error="email is required"), 400
        
        user = User.query.filter_by(email=email).first()
        if not user:
            return jsonify(should_delete=False, message="User not found")
        
        # Check if user is verified but not subscribed (not approved, no dealership)
        should_delete = (
            user.role == "manager" and
            user.is_verified == True and
            user.is_approved == False and
            user.dealership_id == None
        )
        
        return jsonify(
            should_delete=should_delete,
            is_verified=user.is_verified,
            is_approved=user.is_approved,
            has_dealership=user.dealership_id is not None
        )
    except Exception as e:
        print(f"[CHECK ERROR] {str(e)}", flush=True)
        return jsonify(error=f"Check failed: {str(e)}"), 500

@app.post("/admin/delete-unsubscribed")
@limiter.limit("10 per hour")
def delete_unsubscribed():
    """Delete an unsubscribed admin account and send notification email"""
    try:
        data = request.get_json(force=True) or {}
        email = sanitize_input(data.get("email") or "").strip().lower()
        user_id = data.get("user_id")
        
        if not email and not user_id:
            return jsonify(error="email or user_id is required"), 400
        
        # Find user by email or user_id
        if user_id:
            user = User.query.get(int(user_id))
        else:
            user = User.query.filter_by(email=email).first()
        
        if not user:
            return jsonify(error="user not found"), 404
        
        # Only delete if they're verified but not subscribed
        if not (user.role == "manager" and user.is_verified and not user.is_approved and not user.dealership_id):
            return jsonify(error="User does not match criteria for deletion"), 400
        
        user_email = user.email
        user_full_name = user.full_name or "User"
        
        # Delete the user
        db.session.delete(user)
        db.session.commit()
        
        # Send deletion notification email
        try:
            subject = "Star4ce – Account Cancellation"
            body = f"""Hello {user_full_name},

Your Star4ce account ({user_email}) has been canceled and deleted as requested.

If you change your mind, you can register again at any time.

Thank you for your interest in Star4ce.

– Star4ce Team
"""
            send_email_via_resend_or_smtp(user_email, subject, body)
            print(f"[DELETION] Account deleted and notification sent to {user_email}", flush=True)
        except Exception as e:
            print(f"[DELETION WARNING] Account deleted but email failed: {e}", flush=True)
            # Don't fail the deletion if email fails
        
        return jsonify(
            ok=True,
            message=f"Account deleted successfully. Notification email sent to {user_email}."
        )
    except Exception as e:
        db.session.rollback()
        print(f"[DELETION ERROR] {str(e)}", flush=True)
        return jsonify(error=f"Deletion failed: {str(e)}"), 500

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("ENVIRONMENT") != "production"
    app.run(host="0.0.0.0", port=port, debug=debug)