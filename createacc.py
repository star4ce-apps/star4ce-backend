from app import app, db, User, Dealership

with app.app_context():
    # 1) Create a dealership (only once)
    dealership = Dealership(
        name="Star4ce Test Dealership",
        address="123 Demo Street",
        city="Demo City",
        state="CA",
        zip_code="99999",
    )
    db.session.add(dealership)
    db.session.commit()

    print("Created dealership with id:", dealership.id)

    # 2) Promote your user to ADMIN for this dealership
    user = User.query.filter_by(email="michaelkhuri@gmail.com").first()
    print("Before:", user.email, user.role, user.dealership_id)

    user.role = "admin"
    user.dealership_id = dealership.id
    db.session.commit()

    print("After:", user.email, user.role, user.dealership_id)
