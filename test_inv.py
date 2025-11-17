from app import app
import json

ADMIN_EMAIL = "michaelkhuri@gmail.com"
ADMIN_PASSWORD = "12341234"   # <-- use your real admin password
EMPLOYEE_EMAIL = "michaelkhuri@gmail.com"    # <-- test address (can be your gmail again)

with app.test_client() as c:
    # 1) Log in as admin to get JWT
    login_res = c.post(
        "/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    print("LOGIN:", login_res.status_code, login_res.json)

    if login_res.status_code != 200:
        raise SystemExit("Login failed, fix credentials or verification first.")

    token = login_res.json["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2) Create a new access code for this admin's dealership
    code_res = c.post(
        "/survey/access-codes",
        headers=headers,
        json={},   # or {"expires_in_hours": 168} for 7 days if you wired that in
    )
    print("ACCESS CODE:", code_res.status_code, json.dumps(code_res.json, indent=2))

    if code_res.status_code != 200:
        raise SystemExit("Could not create access code, check backend logs.")

    code = code_res.json["code"]

    # 3) Send survey invite email using that code
    invite_res = c.post(
        "/survey/invite",
        headers=headers,
        json={"email": EMPLOYEE_EMAIL, "code": code},
    )
    print("INVITE:", invite_res.status_code, json.dumps(invite_res.json, indent=2))
