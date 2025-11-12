import os, datetime, jwt
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
import os, datetime, jwt, random

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


if __name__ == "__main__":
    app.run(debug=True)
