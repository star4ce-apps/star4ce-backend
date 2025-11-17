from app import app
import json

with app.test_client() as c:
    # First, log in as your admin to get a token
    login_res = c.post(
        "/auth/login",
        json={"email": "michaelkhuri@gmail.com", "password": "12341234"},
    )
    print(login_res.status_code, login_res.json)
    token = login_res.json["token"]

    # Then, call the access-code endpoint
    res = c.post(
        "/survey/access-codes",
        headers={"Authorization": f"Bearer {token}"},
        json={},  # or {"expires_in_hours": 24}
    )
    print(res.status_code, json.dumps(res.json, indent=2))
