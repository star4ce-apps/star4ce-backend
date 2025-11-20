import os, datetime, jwt, smtplib, secrets, json, random
from email.message import EmailMessage
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from flask import g

load_dotenv()
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret")

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)

app = Flask(__name__)
CORS(app)

# Dev: uses local SQLite file "star4ce.db"
# app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
#     "DATABASE_URL",
#     "sqlite:///star4ce.db"
# )
#######

# Prod later: set DATABASE_URL in env to use Postgres on Render.
db_url = os.getenv("DATABASE_URL")
if not db_url:
    raise RuntimeError("DATABASE_URL is not set – required in production")

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
######

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
with app.app_context():
    db.create_all()

class Dealership(db.Model):
    __tablename__ = "dealerships"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    address = db.Column(db.String(255), nullable=True)
    city = db.Column(db.String(100), nullable=True)
    state = db.Column(db.String(50), nullable=True)
    zip_code = db.Column(db.String(20), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "address": self.address,
            "city": self.city,
            "state": self.state,
            "zip_code": self.zip_code,
        }


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
    payload = {
        "sub": email,
        "role": role,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=12),
        "iat": datetime.datetime.utcnow(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def verify_token(token: str):
    return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])

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
    try:
        claims = verify_token(token)
    except Exception:
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

def send_verification_email(to_email: str, code: str):
  """
  Sends a simple verification email with a 6-digit code.
  Uses Gmail SMTP settings from .env.
  """
  if not (SMTP_HOST and SMTP_PORT and SMTP_USER and SMTP_PASSWORD and SMTP_FROM):
      # In dev, just print so we don't crash if SMTP is not configured right
      print(f"[DEV] Would send verification code {code} to {to_email}")
      return

  subject = "Star4ce – Verify your email"
  body = f"""Hello,

Thank you for registering with Star4ce.

Your verification code is: {code}

Enter this code on the verification page to activate your account.

If you did not request this, you can ignore this email.

– Star4ce
"""

  msg = EmailMessage()
  msg["Subject"] = subject
  msg["From"] = SMTP_FROM
  msg["To"] = to_email
  msg.set_content(body)

  try:
      with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
          server.starttls()
          server.login(SMTP_USER, SMTP_PASSWORD)
          server.send_message(msg)
      print(f"[EMAIL] Sent verification email to {to_email}")
  except Exception as e:
      # Don't crash the app if email sending fails; just log it in dev
      print(f"[EMAIL ERROR] Could not send verification email to {to_email}: {e}")

def send_verified_email(to_email: str):
    """
    Simple confirmation email once the account is verified.
    """
    if not (SMTP_HOST and SMTP_PORT and SMTP_USER and SMTP_PASSWORD and SMTP_FROM):
        print(f"[DEV] Would send 'account verified' email to {to_email}")
        return

    subject = "Star4ce – Your account is verified"
    body = f"""Hello,

Your Star4ce account ({to_email}) has been verified successfully.

You can now sign in here:
http://localhost:3000/login

– Star4ce
"""

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = to_email
    msg.set_content(body)

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        print(f"[EMAIL] Sent 'account verified' email to {to_email}")
    except Exception as e:
        print(f"[EMAIL ERROR] Could not send 'account verified' email to {to_email}: {e}")

def send_reset_email(to_email: str, code: str):
    """
    Sends a password reset code email.
    """
    if not (SMTP_HOST and SMTP_PORT and SMTP_USER and SMTP_PASSWORD and SMTP_FROM):
        print(f"[DEV] Would send reset code {code} to {to_email}")
        return

    subject = "Star4ce – Password reset code"
    body = f"""Hello,

We received a request to reset the password for your Star4ce account ({to_email}).

Your password reset code is: {code}
This code expires in 10 minutes.

If you did not request this, you can ignore this email.

– Star4ce
"""

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = to_email
    msg.set_content(body)

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        print(f"[EMAIL] Sent reset code email to {to_email}")
    except Exception as e:
        print(f"[EMAIL ERROR] Could not send reset email to {to_email}: {e}")

def send_survey_invite_email(to_email: str, code: str):
    """
    Sends a survey invite email with the access code + link.
    Uses the same SMTP settings as verification emails.
    """
    if not (SMTP_HOST and SMTP_PORT and SMTP_USER and SMTP_PASSWORD and SMTP_FROM):
        print(f"[DEV] Would send SURVEY invite with code {code} to {to_email}")
        return

    subject = "Star4ce – Employee Experience Survey"
    survey_link = f"http://localhost:3000/survey?code={code}"

    body = f"""Hello,

You have been invited to complete an anonymous Employee Experience Survey.

Your access code is: {code}

You can open the survey directly with this link:
{survey_link}

This code is unique to your dealership and may expire after a week.

Thank you for your honest feedback.

– Star4ce
"""

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = to_email
    msg.set_content(body)

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        print(f"[EMAIL] Sent survey invite to {to_email} with code {code}")
    except Exception as e:
        print(f"[EMAIL ERROR] Could not send survey invite to {to_email}: {e}")

# ---- AUTH STUB (no DB yet) ----
@app.post("/auth/login")
def login():
    data = request.get_json(force=True)
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify(error="email and password required"), 400

    

    # Look up user in DB
    user = User.query.filter_by(email=email).first()
    if not user:
        # Do not reveal which part is wrong
        return jsonify(error="invalid credentials"), 401

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
            message="Your email is not verified yet. A new verification code has been sent."
        ), 403


    if not check_password_hash(user.password_hash, password):
        return jsonify(error="invalid credentials"), 401

    # Issue JWT based on DB user
    token = make_token(user.email, user.role)

    return jsonify(
        token=token,
        role=user.role,
        email=user.email
    )

# ---- AUTH REGISTER STUB (no DB yet) ----
@app.post("/auth/register")
def register():
    data = request.get_json(force=True)
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify(error="email and password required"), 400

    if len(password) < 8:
        return jsonify(error="password must be at least 8 characters"), 400

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
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return jsonify(error="missing bearer token"), 401
    token = auth.split(" ", 1)[1]
    try:
        claims = verify_token(token)
        return jsonify(ok=True, user={"email": claims["sub"], "role": claims["role"]})
    except Exception:
        return jsonify(error="invalid token"), 401
    
@app.get("/analytics/summary")
def analytics_summary():
    """
    Protected endpoint.

    - Only verified 'admin' or 'corporate' users can access
    - 'admin' sees data for THEIR dealership only
    - 'corporate' sees overall totals across all dealerships

    Uses SurveyResponse + SurveyAccessCode so survey answers are tied
    to the correct dealership via access_code.
    """
    user, err = get_current_user()
    if err:
        return err  # 401 / 403

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

@app.post("/auth/verify")
def verify_email():
    data = request.get_json(force=True)
    email = (data.get("email") or "").strip().lower()
    code = (data.get("code") or "").strip()

    if not email or not code:
        return jsonify(error="email and code are required"), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify(error="user not found"), 400

    if user.is_verified:
        return jsonify(error="already verified"), 400

    # Check code
    if not user.verification_code or user.verification_code != code:
        return jsonify(error="invalid verification code"), 400

    # Check expiry
    if user.verification_expires_at and user.verification_expires_at < datetime.datetime.utcnow():
        # Delete unverified account so the email can be reused cleanly
        db.session.delete(user)
        db.session.commit()
        return jsonify(error="verification code expired – please register again"), 400

    # Mark verified
    user.is_verified = True
    user.verification_code = None
    user.verification_expires_at = None

    db.session.commit()

    send_verified_email(user.email)

    return jsonify(ok=True, email=user.email, role=user.role)

@app.post("/auth/resend-verify")
def resend_verify():
    data = request.get_json(force=True)
    email = (data.get("email") or "").strip().lower()

    if not email:
        return jsonify(error="email is required"), 400

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
def request_reset():
    data = request.get_json(force=True)
    email = (data.get("email") or "").strip().lower()

    if not email:
        return jsonify(error="email required"), 400

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
def reset_password():
    data = request.get_json(force=True)
    email = (data.get("email") or "").strip().lower()
    code = (data.get("code") or "").strip()
    new_password = data.get("new_password") or ""

    if not email or not code or not new_password:
        return jsonify(error="email, code, and new_password required"), 400

    if len(new_password) < 8:
        return jsonify(error="password must be at least 8 characters"), 400

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
    """
    user, err = get_current_user()
    if err:
        return err  # 401 / 403

    # Must be an admin with a dealership
    if user.role != "admin":
        return jsonify(error="only admins can create survey access codes"), 403

    if not user.dealership_id:
        return jsonify(error="admin has no dealership assigned"), 400

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

    return jsonify(
        ok=True,
        id=access.id,
        code=access.code,
        dealership_id=access.dealership_id,
        created_at=access.created_at.isoformat() + "Z",
        expires_at=access.expires_at.isoformat() + "Z" if access.expires_at else None,
        is_active=access.is_active,
    )

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

    if not user.dealership_id:
        return jsonify(error="admin has no dealership assigned"), 400

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

    if not user.dealership_id:
        return jsonify(error="admin has no dealership assigned"), 400

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

    return jsonify(
        ok=True,
        message=f"Survey invite sent to {to_email}",
        code=code,
        dealership_id=user.dealership_id,
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


if __name__ == "__main__":
    app.run(debug=True)
