from app import app, db, User

with app.app_context():
    u = User.query.filter_by(email="michaelkhuri@gmail.com").first()
    if u:
        u.role = "admin"
        db.session.commit()
        print("Updated:", u.email, u.role)
    else:
        print("User not found")
exit()
