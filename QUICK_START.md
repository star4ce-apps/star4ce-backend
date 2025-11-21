# 🚀 Quick Start Guide

Get your Star4ce project running in 5 minutes!

---

## Step 1: Database Setup (One Time)

### Create PostgreSQL Database

```powershell
# Open PowerShell (as Admin)
cd "C:\Program Files\PostgreSQL\18\bin"
.\psql.exe -U postgres
```

Enter your PostgreSQL password, then:

```sql
CREATE DATABASE star4ce_db;
CREATE USER star4ce_user WITH PASSWORD 'star4ce123';
GRANT ALL PRIVILEGES ON DATABASE star4ce_db TO star4ce_user;
\c star4ce_db
GRANT ALL ON SCHEMA public TO star4ce_user;
\q
```

---

## Step 2: Backend Setup

### 1. Create `.env` file in `star4ce-backend/`:

```env
DATABASE_URL=postgresql://star4ce_user:star4ce123@localhost:5432/star4ce_db
ENVIRONMENT=development
JWT_SECRET=your-random-32-char-secret-here
FRONTEND_URL=http://localhost:3000
```

### 2. Install & Run:

```bash
cd star4ce-backend
pip install -r requirements.txt
python app.py
```

Backend runs on: `http://localhost:5000`

---

## Step 3: Frontend Setup

### 1. Create `.env.local` in `star4ce-frontend/`:

```env
NEXT_PUBLIC_API_BASE=http://localhost:5000
```

### 2. Install & Run:

```bash
cd star4ce-frontend
npm install
npm run dev
```

Frontend runs on: `http://localhost:3000`

---

## Step 4: Test It!

1. Go to: `http://localhost:3000`
2. Click "Register"
3. Select "Admin"
4. Complete registration
5. Subscribe to become admin
6. Start using the platform!

---

## 🗄️ Database Management

### Open Database:
```powershell
cd "C:\Program Files\PostgreSQL\18\bin"
.\psql.exe -U star4ce_user -d star4ce_db
```

### Common Commands:
```sql
\dt                    -- List tables
SELECT * FROM users;   -- View users
DELETE FROM users WHERE email = 'user@example.com';  -- Delete user
\q                    -- Exit
```

### Or Use Python Script:
```bash
cd star4ce-backend
python delete_user.py list              # List users
python delete_user.py user@example.com  # Delete user
```

---

## 📝 Notes

- **Database**: PostgreSQL (required)
- **Backend Port**: 5000
- **Frontend Port**: 3000
- **Tables**: Created automatically on first run

---

## ✅ You're All Set!

Your project is ready to use. All features are implemented and working.

For detailed guides, see:
- `POSTGRES_QUICK_SETUP.md` - Database setup
- `STRIPE_SETUP_GUIDE.md` - Payment setup
- `guides/` - Complete documentation

