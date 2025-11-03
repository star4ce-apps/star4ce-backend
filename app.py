from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.get("/health")
def health():
    return jsonify(ok=True, service="star4ce-backend")
