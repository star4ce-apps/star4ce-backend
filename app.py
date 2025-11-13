import os, datetime, jwt, random
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret")

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
class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False, default="manager")

    # new fields
    is_verified = db.Column(db.Boolean, nullable=False, default=False)
    verify_code = db.Column(db.String(6), nullable=True)

    reset_code = db.Column(db.String(6), nullable=True)
    reset_code_expires_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "role": self.role,
            "is_verified": self.is_verified,
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

    # Check if user already exists
    existing = User.query.filter_by(email=email).first()
    if existing:
        return jsonify(error="email is already registered"), 400

    # Default role for now; later we’ll decide admin/manager/corporate rules
    role = "manager"

    # Generate a 6-digit verification code (for email verification / resets later)
    verify_code = f"{random.randint(0, 999999):06d}"

    user = User(
        email=email,
        password_hash=generate_password_hash(password),
        role=role,
        is_verified=True,          # ✅ keep true for now so login works without blocking
        verify_code=verify_code,   # store latest code (we’ll use this later)
    )

    db.session.add(user)
    db.session.commit()

    # Issue JWT based on stored user (same as before)
    token = make_token(user.email, user.role)

    # Add verification_code for dev so you can see/test it
    return jsonify(
        ok=True,
        token=token,
        role=user.role,
        email=user.email,
        verification_code=verify_code   # dev-only; later sent via email
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

@app.post("/auth/verify")
def verify_account():
    data = request.get_json(force=True)
    email = (data.get("email") or "").strip().lower()
    code = (data.get("code") or "").strip()

    if not email or not code:
        return jsonify(error="email and code required"), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify(error="invalid code or email"), 400

    # Compare with latest stored code
    if not user.verify_code or user.verify_code != code:
        return jsonify(error="invalid code or email"), 400

    # Mark verified and clear code
    user.is_verified = True
    user.verify_code = None
    db.session.commit()

    # Issue a fresh token so the client can log the user in right away
    token = make_token(user.email, user.role)

    return jsonify(ok=True, token=token, email=user.email, role=user.role)

@app.post("/auth/resend-verify")
def resend_verify():
    data = request.get_json(force=True)
    email = (data.get("email") or "").strip().lower()

    if not email:
        return jsonify(error="email required"), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify(error="no such user"), 404

    # If already verified, nothing to do
    if user.is_verified:
        return jsonify(ok=True, already_verified=True)

    import random
    user.verify_code = f"{random.randint(0, 999999):06d}"
    db.session.commit()

    # Dev-only: return the code in JSON. Later, send via email.
    return jsonify(ok=True, verification_code=user.verify_code)

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


if __name__ == "__main__":
    app.run(debug=True)
