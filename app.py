import os, datetime, jwt, smtplib, secrets
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
# Prod later: set DATABASE_URL in env to use Postgres on Render.
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL",
    "sqlite:///star4ce.db"
)
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
        return jsonify(error="unverified"), 403

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
    incoming_role = (data.get("role") or "").strip()

    if not email or not password:
        return jsonify(error="email and password required"), 400

    if len(password) < 8:
        return jsonify(error="password must be at least 8 characters"), 400

    existing = User.query.filter_by(email=email).first()
    if existing:
        return jsonify(error="email is already registered"), 400

    # Only allow known roles; fall back to 'manager'
    valid_roles = {"manager", "admin", "corporate"}
    role = incoming_role if incoming_role in valid_roles else "manager"

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
    Analytics are ONLY visible to verified 'admin' users.

    - 'admin' sees data for their own dealership (by dealership_id)
    - 'manager' and 'corporate' are blocked here
    """

    user, err = get_current_user()
    if err:
        return err  # 401 / 403 from helper

    # Only admins allowed
    if user.role != "admin":
        return jsonify(error="forbidden – analytics only available to admins"), 403

    if not user.dealership_id:
        return jsonify(
            ok=True,
            scope="admin",
            message="No dealership assigned to this admin yet.",
            total_answers=0,
        )

    total_answers = SurveyAnswer.query.filter_by(
        dealership_id=user.dealership_id
    ).count()

    return jsonify(
        ok=True,
        scope="admin",
        dealership_id=user.dealership_id,
        total_answers=total_answers,
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
        return jsonify(error="verification code expired"), 400

    # Mark verified
    user.is_verified = True
    user.verification_code = None
    user.verification_expires_at = None

    db.session.commit()

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
        # For dev, we’ll be explicit. In production you might return ok=True always.
        return jsonify(error="no account with that email"), 404

    # Generate a 6-digit reset code
    reset_code = f"{random.randint(0, 999999):06d}"
    expires_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=15)

    user.reset_code = reset_code
    user.reset_code_expires_at = expires_at
    db.session.commit()

    # Dev-only: return the code in JSON.
    # Later you’ll send this via email instead.
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

@app.post("/survey/submit")
def submit_survey():
    """
    Public endpoint: called by the Survey page.
    Saves one anonymous survey response tied to an access_code.
    """
    data = request.get_json(force=True)

    access_code = (data.get("access_code") or "").strip()
    employee_status = (data.get("employee_status") or "").strip()
    role = (data.get("role") or "").strip()

    satisfaction_answers = data.get("satisfaction_answers") or {}
    training_answers = data.get("training_answers") or {}

    termination_reason = data.get("termination_reason") or None
    termination_other = data.get("termination_other") or None
    leave_reason = data.get("leave_reason") or None
    leave_other = data.get("leave_other") or None
    additional_feedback = data.get("additional_feedback") or None

    # basic validation
    if not access_code or not employee_status or not role:
        return jsonify(error="access_code, employee_status, and role are required"), 400

    if not isinstance(satisfaction_answers, dict):
        return jsonify(error="satisfaction_answers must be an object"), 400

    if training_answers and not isinstance(training_answers, dict):
        return jsonify(error="training_answers must be an object"), 400

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

    db.session.add(resp)
    db.session.commit()

    return jsonify(ok=True, id=resp.id)


if __name__ == "__main__":
    app.run(debug=True)
