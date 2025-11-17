from app import app, db, User, Dealership

ADMIN_EMAIL = "michaelkhuri@gmail.com"

with app.app_context():
    # 1) Make sure there is at least one dealership
    dealership = Dealership.query.first()
    if not dealership:
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
    else:
        print("Using existing dealership with id:", dealership.id)

    # 2) Attach the admin user to this dealership
    user = User.query.filter_by(email=ADMIN_EMAIL).first()
    if not user:
        raise SystemExit(f"User with email {ADMIN_EMAIL} not found")

    print("Before:", user.email, user.role, user.dealership_id)

    user.role = "admin"
    user.dealership_id = dealership.id

    db.session.commit()

    print("After:", user.email, user.role, user.dealership_id)
