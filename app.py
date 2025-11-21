import os, datetime, jwt, smtplib, secrets, json, random, requests
try:
    import stripe
    STRIPE_AVAILABLE = True
except ImportError:
    STRIPE_AVAILABLE = False
    stripe = None
from email.message import EmailMessage
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from flask import g
import re

load_dotenv()
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret")

# Stripe configuration
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID")  # Monthly subscription price ID

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

# Configure CORS - use resources pattern for better control
CORS(app, 
     resources={
         r"/api/*": {
             "origins": allowed_origins,
             "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
             "allow_headers": ["Content-Type", "Authorization", "X-Requested-With"],
             "supports_credentials": True,
             "max_age": 3600
         },
         r"/*": {
             "origins": allowed_origins,
             "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
             "allow_headers": ["Content-Type", "Authorization", "X-Requested-With"],
             "supports_credentials": True,
             "max_age": 3600
         }
     })

# Rate limiting
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"  # Use Redis in production: os.getenv("REDIS_URL", "memory://")
)

# --- DATABASE SETUP ---

# Get DATABASE_URL from Render (or fall back to local sqlite when running locally)
# Use instance folder for local development (Flask convention)
raw_db_url = os.getenv("DATABASE_URL", "sqlite:///instance/star4ce.db")

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


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    # Roles:
    # - "admin"      = owner of a single dealership
    # - "manager"    = manager at a dealership
    # - "corporate"  = can see across dealerships
    role = db.Column(
        db.String(50),
        nullable=False,
        default="manager",
    )

    # Which dealership this user belongs to (can be NULL for corporate)
    dealership_id = db.Column(db.Integer, db.ForeignKey("dealerships.id"), nullable=True)
    dealership = db.relationship("Dealership", backref="users")

    # email verification
    is_verified = db.Column(db.Boolean, nullable=False, default=False)
    verification_code = db.Column(db.String(6), nullable=True)
    verification_expires_at = db.Column(db.DateTime, nullable=True)

    reset_code = db.Column(db.String(6), nullable=True)
    reset_code_expires_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "role": self.role,
            "is_verified": self.is_verified,
            "dealership_id": self.dealership_id,
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

@app.get("/health")
def health():
    return jsonify(ok=True, service="star4ce-backend")

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

    # Require email to be verified to access protected routes
    if not user.is_verified:
        return None, (jsonify(error="unverified"), 403)

    # Store on flask.g if you ever want it elsewhere
    g.current_user = user
    return user, None

def log_admin_action(admin_email: str, action: str, resource_type: str, resource_id: int = None, details: str = None):
    """Log admin actions for audit trail"""
    try:
        # AdminAuditLog model not yet implemented - log to console for now
        # TODO: Add AdminAuditLog model when needed
        ip_address = request.remote_addr
        print(f"[AUDIT] {admin_email} - {action} - {resource_type} - {resource_id} - IP: {ip_address}", flush=True)
        # Uncomment when AdminAuditLog model is added:
        # log_entry = AdminAuditLog(
        #     admin_email=admin_email,
        #     action=action,
        #     resource_type=resource_type,
        #     resource_id=resource_id,
        #     details=details,
        #     ip_address=ip_address,
        # )
        # db.session.add(log_entry)
        # db.session.commit()
    except Exception as e:
        # Don't fail the request if logging fails
        print(f"[AUDIT ERROR] Failed to log action: {e}", flush=True)

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

    # Always log for debugging (especially useful in Render logs)
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

    # Log for debugging
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

# ---- AUTH STUB (no DB yet) ----
@app.post("/auth/login")
@limiter.limit("5 per minute")
def login():
    data = request.get_json(force=True) or {}
    email = sanitize_input(data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify(error="email and password required"), 400
    
    if not validate_email(email):
        return jsonify(error="invalid email format"), 400

    

    # Look up user in DB
    user = User.query.filter_by(email=email).first()
    if not user:
        # Do not reveal which part is wrong
        return jsonify(error="invalid credentials"), 401

    # Check password first (before checking verification status)
    # This way we can give better feedback
    if not check_password_hash(user.password_hash, password):
        return jsonify(error="invalid credentials"), 401

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

    # Issue JWT based on DB user
    token = make_token(user.email, user.role)

    return jsonify(
        token=token,
        role=user.role,
        email=user.email
    )

# ---- AUTH REGISTER STUB (no DB yet) ----
@app.post("/auth/register")
@limiter.limit("3 per hour")
def register():
    data = request.get_json(force=True) or {}
    email = sanitize_input(data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify(error="email and password required"), 400

    if not validate_email(email):
        return jsonify(error="invalid email format"), 400

    if not validate_password(password):
        return jsonify(error="password must be at least 8 characters with letters and numbers"), 400

    existing = User.query.filter_by(email=email).first()
    if existing:
        return jsonify(error="email is already registered"), 400

    # Public registration ALWAYS creates a manager.
    # Admin / corporate accounts will be created/updated internally only.
    role = "manager"

    # Generate 6-digit verification code
    code_int = secrets.randbelow(1_000_000)  # 0..999999
    verification_code = f"{code_int:06d}"
    expires_at = datetime.datetime.utcnow() + datetime.timedelta(hours=1)

    user = User(
        email=email,
        password_hash=generate_password_hash(password),
        role=role,
        is_verified=False,
        verification_code=verification_code,
        verification_expires_at=expires_at,
    )

    db.session.add(user)
    db.session.commit()

    # Send verification email (best-effort)
    send_verification_email(user.email, verification_code)

    # Do NOT log them in yet; they must verify first.
    return jsonify(
        ok=True,
        email=user.email,
        role=user.role,
        message="Verification code sent to your email. Please verify before logging in."
    )

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
        
        if not user.is_verified:
            return jsonify(error="unverified"), 403
        
        return jsonify(ok=True, user={"email": email, "role": claims.get("role", "admin")})
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
        base_q = SurveyResponse.query.filter(SurveyResponse.created_at >= cutoff)
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
        base_q = SurveyResponse.query.filter(SurveyResponse.created_at >= cutoff_30)
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
        base_q = SurveyResponse.query.filter(SurveyResponse.created_at >= cutoff_30)
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
            # All responses, across all dealerships
            total_responses = SurveyResponse.query.count()
            last_30 = SurveyResponse.query.filter(
                SurveyResponse.created_at >= cutoff_30
            ).count()

            return jsonify(
                ok=True,
                scope="corporate",
                total_dealerships=Dealership.query.count(),
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

@app.post("/auth/verify")
@limiter.limit("10 per minute")
def verify_email():
    data = request.get_json(force=True) or {}
    email = sanitize_input(data.get("email") or "").strip().lower()
    code = sanitize_input(data.get("code") or "", max_length=6).strip()
    
    if not validate_email(email):
        return jsonify(error="invalid email format"), 400

    if not email or not code:
        return jsonify(error="email and code required"), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify(error="user not found"), 404

    if user.is_verified:
        return jsonify(ok=True, message="Already verified")

    if user.verification_code != code:
        return jsonify(error="Invalid code"), 400

    if user.verification_expires_at and user.verification_expires_at < datetime.datetime.utcnow():
        return jsonify(error="Code expired"), 400

    user.is_verified = True
    user.verification_code = None
    user.verification_expires_at = None
    db.session.commit()

    # Send confirmation email
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

        # Must be an admin with a dealership
        if user.role != "admin":
            return jsonify(error="only admins can create survey access codes"), 403

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
    Admin-only endpoint.
    Returns all survey access codes for the admin's dealership.
    """
    user, err = get_current_user()
    if err:
        return err  # 401 / 403

    if user.role != "admin":
        return jsonify(error="only admins can list survey access codes"), 403

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
    Admin-only endpoint.
    Sends a survey invite email with a given access code
    to a specific employee email.
    """
    user, err = get_current_user()
    if err:
        return err  # 401/403

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
        return jsonify(error="name, email, and department are required"), 400

    if not validate_email(email):
        return jsonify(error="invalid email format"), 400

    # Check if email already exists for this dealership
    existing = Employee.query.filter_by(
        email=email,
        dealership_id=user.dealership_id
    ).first()
    if existing:
        return jsonify(error="employee with this email already exists"), 400

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
        employee.phone = sanitize_input(data["phone"], max_length=20) or None
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
    """Get current user's subscription status"""
    user, err = get_current_user()
    if err:
        return err

    if not user.dealership_id:
        return jsonify(
            ok=True,
            subscription_status="none",
            message="No dealership associated with this account"
        )

    dealership = Dealership.query.get(user.dealership_id)
    if not dealership:
        return jsonify(error="dealership not found"), 404

    return jsonify(
        ok=True,
        subscription_status=dealership.subscription_status,
        subscription_plan=dealership.subscription_plan,
        trial_ends_at=dealership.trial_ends_at.isoformat() + "Z" if dealership.trial_ends_at else None,
        subscription_ends_at=dealership.subscription_ends_at.isoformat() + "Z" if dealership.subscription_ends_at else None,
        days_remaining_in_trial=dealership.days_remaining_in_trial(),
        is_active=dealership.is_subscription_active(),
    )

@app.post("/subscription/create-checkout")
@limiter.limit("10 per minute")
def create_checkout_session():
    """Create Stripe checkout session for subscription"""
    user, err = get_current_user()
    if err:
        return err

    if not STRIPE_AVAILABLE or not STRIPE_SECRET_KEY:
        return jsonify(error="Stripe not configured"), 503

    if not STRIPE_PRICE_ID:
        return jsonify(error="Stripe price ID not configured"), 503

    try:
        # If user doesn't have a dealership, we'll create one after checkout
        # Store user_id in metadata so webhook can upgrade them to admin
        dealership_id = user.dealership_id
        
        # If user has a dealership, use it; otherwise we'll create one in webhook
        if dealership_id:
            dealership = Dealership.query.get(dealership_id)
            if not dealership:
                dealership_id = None
        
        # Create or get Stripe customer
        customer_id = None
        if dealership_id:
            dealership = Dealership.query.get(dealership_id)
            if dealership and dealership.stripe_customer_id:
                customer_id = dealership.stripe_customer_id
        
        if not customer_id:
            # Create new Stripe customer
            customer = stripe.Customer.create(
                email=user.email,
                metadata={"user_id": user.id, "dealership_id": str(dealership_id) if dealership_id else "new"}
            )
            customer_id = customer.id
            
            # Save customer ID if dealership exists
            if dealership_id:
                dealership = Dealership.query.get(dealership_id)
                if dealership:
                    dealership.stripe_customer_id = customer_id
                    db.session.commit()

        # Create checkout session
        checkout_session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[{
                "price": STRIPE_PRICE_ID,
                "quantity": 1,
            }],
            mode="subscription",
            success_url=f"{FRONTEND_URL}/dashboard?subscription=success",
            cancel_url=f"{FRONTEND_URL}/dashboard?subscription=canceled",
            metadata={
                "user_id": user.id,
                "dealership_id": str(dealership_id) if dealership_id else "new",
                "user_email": user.email
            },
        )

        return jsonify(
            ok=True,
            checkout_url=checkout_session.url,
            session_id=checkout_session.id,
        )
    except Exception as e:
        print(f"[STRIPE ERROR] Checkout creation failed: {e}", flush=True)
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
    except stripe.error.SignatureVerificationError:
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
        
        if not user_id:
            print(f"[WEBHOOK ERROR] No user_id in checkout session metadata", flush=True)
            return

        # Get the user
        user = User.query.get(int(user_id))
        if not user:
            print(f"[WEBHOOK ERROR] User {user_id} not found", flush=True)
            return

        # Create or get dealership
        dealership = None
        if dealership_id_str and dealership_id_str != "new":
            dealership = Dealership.query.get(int(dealership_id_str))
        
        if not dealership:
            # Create new dealership for this user
            dealership = Dealership(
                name=f"Dealership for {user.email}",
                subscription_status="active",
                subscription_plan="pro",
                trial_ends_at=None,  # No trial, they paid
            )
            db.session.add(dealership)
            db.session.flush()  # Get the ID
        
        # Update dealership subscription info
        subscription_id = session.get("subscription")
        if subscription_id:
            dealership.stripe_subscription_id = subscription_id
            dealership.subscription_status = "active"
            dealership.subscription_plan = "pro"
            # Set subscription end date (1 month from now, Stripe will renew)
            dealership.subscription_ends_at = datetime.datetime.utcnow() + datetime.timedelta(days=30)
        
        # Update Stripe customer ID if not set
        customer_id = session.get("customer")
        if customer_id and not dealership.stripe_customer_id:
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

# --- Ensure DB tables exist on startup (Render + local) ---
with app.app_context():
    db.create_all()
    print("✔️ Ensured all DB tables exist in", db.engine.url)

if __name__ == "__main__":
    # For local development only
    # Production uses gunicorn (see Procfile)
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("ENVIRONMENT") != "production"
    app.run(host="0.0.0.0", port=port, debug=debug)