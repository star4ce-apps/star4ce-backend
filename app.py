import os, datetime, jwt
from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret")

app = Flask(__name__)
CORS(app)

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

    # TEMP RULE: accept any password >= 8 chars; set role by domain (demo)
    if len(password) < 8:
        return jsonify(error="invalid credentials"), 401

    role = "corporate" if email.endswith("@corp.com") else "manager"
    token = make_token(email, role)
    return jsonify(token=token, role=role, email=email)

# ---- AUTH REGISTER STUB (no DB yet) ----
@app.post("/auth/register")
def register():
    data = request.get_json(force=True)
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify(error="email and password required"), 400
    if len(password) < 8:
        return jsonify(error="password too short"), 400

    role = "manager"
    token = make_token(email, role)
    return jsonify(token=token, role=role, email=email), 201

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
