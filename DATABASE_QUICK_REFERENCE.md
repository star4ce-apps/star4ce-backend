# Database Quick Reference

## Open PostgreSQL

**Windows Command Line**:
```powershell
cd "C:\Program Files\PostgreSQL\18\bin"
.\psql.exe -U star4ce_user -d star4ce_db
```
(Enter password when prompted)

**Or use pgAdmin** (GUI tool - comes with PostgreSQL)

---

## Common Commands

### View Data
```sql
-- List all tables
\dt

-- View all users
SELECT * FROM users;

-- View specific user
SELECT * FROM users WHERE email = 'user@example.com';

-- View table structure
\d users
```

### Delete Data
```sql
-- Delete user by email
DELETE FROM users WHERE email = 'user@example.com';

-- Delete user by ID
DELETE FROM users WHERE id = 123;
```

### Exit
```sql
\q
```

---

## Using Python Script

**List all users**:
```bash
cd star4ce-backend
python delete_user.py list
```

**Delete user**:
```bash
python delete_user.py user@example.com
```

---

## Using Admin API

**List users**: `GET /admin/users` (need admin token)  
**Delete user**: `DELETE /admin/users/<id>` (need admin token)

