import os
from app import app, db

with app.app_context():
    path = "instance/star4ce.db"
    if os.path.exists(path):
        os.remove(path)
        print("DB removed")

    db.create_all()
    print("DB recreated")
