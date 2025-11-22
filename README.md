# Star4ce Backend

HR platform backend for car dealerships - built with Flask, SQLite (local) / PostgreSQL (production), and Stripe.

---

## 🚀 Quick Start (Local Development)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Create `.env` File (Optional - SQLite works without it)
```env
# For local development, SQLite is used by default
# Only add these if you want to customize:

JWT_SECRET=your-random-secret-32-chars-minimum
FRONTEND_URL=http://localhost:3000
ENVIRONMENT=development

# Email (Optional - for testing email features)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=your-email@gmail.com

# Stripe (Required for subscription testing)
STRIPE_SECRET_KEY=sk_test_xxxxxxxxxxxxx
STRIPE_PRICE_ID=price_xxxxxxxxxxxxx
STRIPE_PRICE_ID_ANNUAL=price_yyyyyyyyyyyyy
```

### 3. Start Server
```bash
python app.py
```

### 4. Verify It's Running
- Visit: http://localhost:5000/health
- Should return: `{"ok": true, "service": "star4ce-backend"}`

**That's it!** The database (SQLite) will be created automatically in `instance/star4ce.db`

---

## 🧪 Testing

**See [LOCAL_TESTING_CHECKLIST.md](./LOCAL_TESTING_CHECKLIST.md) for complete testing guide.**

### Quick Test
1. Start backend: `python app.py`
2. Start frontend: `cd ../star4ce-frontend && npm run dev`
3. Go to http://localhost:3000
4. Test admin registration and subscription flow

---

## 🗄️ Database

**Local Development**: SQLite (automatic, no setup needed)  
**Production**: PostgreSQL (on Render)

### Manage Users (Local)
```bash
# List all users
python delete_user.py list

# Delete a user
python delete_user.py user@email.com --yes
```

---

## 📋 Key Features

- ✅ User authentication (JWT)
- ✅ Email verification
- ✅ Password reset
- ✅ Employee management
- ✅ Survey system
- ✅ Analytics dashboard
- ✅ Stripe subscriptions (Monthly $199, Annual $166/month)
- ✅ Role-based access (Admin, Manager, Corporate)

---

## 🔐 Environment Variables

**Required for Production** (see `ENV_SETUP.txt`):
- `DATABASE_URL` - PostgreSQL connection string
- `JWT_SECRET` - Secret for JWT tokens
- `FRONTEND_URL` - Frontend URL
- `STRIPE_SECRET_KEY` - Stripe secret key
- `STRIPE_PRICE_ID` - Monthly subscription price ID
- `STRIPE_PRICE_ID_ANNUAL` - Annual subscription price ID

**Optional** (for email features):
- SMTP settings or Resend API key

---

## 📊 API Endpoints

### Authentication
- `POST /auth/register` - Register new user
- `POST /auth/login` - Login
- `POST /auth/verify` - Verify email
- `POST /auth/forgot` - Request password reset
- `POST /auth/reset` - Reset password
- `GET /auth/me` - Get current user

### Subscriptions
- `POST /subscription/create-checkout` - Create Stripe checkout
- `GET /subscription/status` - Get subscription status
- `POST /subscription/cancel` - Cancel subscription
- `POST /subscription/webhook` - Stripe webhook handler

### Employees
- `GET /employees` - List employees
- `POST /employees` - Create employee
- `PUT /employees/<id>` - Update employee
- `DELETE /employees/<id>` - Delete employee

### Surveys
- `POST /survey/access-codes` - Create access code
- `GET /survey/access-codes` - List access codes
- `POST /survey/submit` - Submit survey response

### Analytics
- `GET /analytics/summary` - Summary statistics
- `GET /analytics/time-series` - Time series data

---

## 🛠️ Development

### Project Structure
```
star4ce-backend/
├── app.py                 # Main application
├── delete_user.py         # User management script
├── requirements.txt       # Python dependencies
└── instance/              # SQLite database (auto-created)
    └── star4ce.db
```

### Adding Features
1. Make changes to `app.py`
2. Test locally
3. Restart server: `python app.py`

---

## 🐛 Troubleshooting

**Backend won't start?**
- Check if port 5000 is available
- Check for errors in terminal
- Make sure dependencies are installed: `pip install -r requirements.txt`

**Database errors?**
- SQLite database is auto-created in `instance/star4ce.db`
- If issues, delete `instance/star4ce.db` and restart (will recreate)

**Email not working?**
- Email is optional for local testing
- Check SMTP settings in `.env` if configured

**Stripe not working?**
- Make sure `STRIPE_SECRET_KEY` is set in `.env`
- Use test mode keys (start with `sk_test_`)
- Use test card: `4242 4242 4242 4242`

---

## 📝 Files

- **[LOCAL_TESTING_CHECKLIST.md](./LOCAL_TESTING_CHECKLIST.md)** - Complete testing guide
- **[ENV_SETUP.txt](./ENV_SETUP.txt)** - Environment variables template
- **[delete_user.py](./delete_user.py)** - User management script

---

**Ready to test?** See [LOCAL_TESTING_CHECKLIST.md](./LOCAL_TESTING_CHECKLIST.md) 🚀
