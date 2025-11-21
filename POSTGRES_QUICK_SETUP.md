# PostgreSQL Quick Setup

✅ **PostgreSQL is already installed!** (Version 18)

---

## Create Database (One Time Setup)

### Option 1: Use Setup Script (Easiest)

1. **Open PowerShell** (as Administrator)
2. **Run**:
   ```powershell
   cd star4ce-backend
   .\SETUP_DATABASE.ps1
   ```
3. **Enter** your PostgreSQL `postgres` user password when prompted

### Option 2: Manual Setup

1. **Open PowerShell** (as Admin)
2. **Go to PostgreSQL folder**:
   ```powershell
   cd "C:\Program Files\PostgreSQL\18\bin"
   ```

3. **Connect**:
   ```powershell
   .\psql.exe -U postgres
   ```
   (Enter your password)

4. **Create database**:
   ```sql
   CREATE DATABASE star4ce_db;
   CREATE USER star4ce_user WITH PASSWORD 'yourpassword';
   GRANT ALL PRIVILEGES ON DATABASE star4ce_db TO star4ce_user;
   \c star4ce_db
   GRANT ALL ON SCHEMA public TO star4ce_user;
   \q
   ```

---

## Add to .env File

Update `star4ce-backend/.env`:
```env
DATABASE_URL=postgresql://star4ce_user:star4ce123@localhost:5432/star4ce_db
```

**Note**: Change `star4ce123` to your preferred password (must match what you set when creating the user)

---

## How to Open & Manage Tables

### Open Database

**Option 1: Command Line**
```powershell
cd "C:\Program Files\PostgreSQL\18\bin"
.\psql.exe -U star4ce_user -d star4ce_db
```
(Password: `star4ce123` or whatever you set)

**Option 2: pgAdmin** (GUI - comes with PostgreSQL)
- Open **pgAdmin 4** from Start Menu
- Connect to server (enter postgres password)
- Find `star4ce_db` → Browse tables

### Common Commands

```sql
-- List all tables
\dt

-- View users table
SELECT * FROM users;

-- Delete a user
DELETE FROM users WHERE email = 'user@example.com';

-- View table structure
\d users

-- Exit
\q
```

---

## That's It!

Your app will use PostgreSQL. Tables are created automatically when you run `python app.py`.

