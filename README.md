# Star4ce Backend

HR platform backend for car dealerships - built with Flask, PostgreSQL, and Stripe.

---

## 📚 Documentation

All guides are in the **[guides/](./guides/)** folder.

### 🚀 Quick Start Guides

- **[guides/QUICK_SETUP.md](./guides/QUICK_SETUP.md)** - ⭐ Quick checklist if Vercel/Render already connected
- **[guides/SIMPLE_DEPLOYMENT.md](./guides/SIMPLE_DEPLOYMENT.md)** - Simple step-by-step deployment guide
- **[guides/SIMPLE_OWNER_GUIDE.md](./guides/SIMPLE_OWNER_GUIDE.md)** - Simple guide for non-technical owners

### 📖 Complete Guides

- **[guides/DEPLOYMENT_GUIDE.md](./guides/DEPLOYMENT_GUIDE.md)** - Complete deployment instructions
- **[guides/OWNER_GUIDE.md](./guides/OWNER_GUIDE.md)** - Comprehensive owner guide
- **[guides/QUICK_START_CHECKLIST.md](./guides/QUICK_START_CHECKLIST.md)** - Pre-deployment checklist
- **[guides/ENVIRONMENT_VARIABLES.md](./guides/ENVIRONMENT_VARIABLES.md)** - Environment variables reference
- **[guides/DATABASE_MAINTENANCE.md](./guides/DATABASE_MAINTENANCE.md)** - Database backup and maintenance
- **[guides/TROUBLESHOOTING.md](./guides/TROUBLESHOOTING.md)** - Common issues and solutions

### 📝 Setup Files

- **[ENV_SETUP.txt](./ENV_SETUP.txt)** - Environment variables template (copy to Render)

---

## 🚀 Quick Start

### Local Development

1. **Clone repository**:
   ```bash
   git clone <your-repo-url>
   cd star4ce-backend
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your values
   ```

4. **Run database migrations** (if needed):
   ```bash
   python3 app.py  # Tables auto-create on first run
   ```

5. **Start server**:
   ```bash
   python3 app.py
   ```

6. **Verify**:
   - Visit: http://localhost:5000/health
   - Should return: `{"ok": true, "service": "star4ce-backend"}`

### Production Deployment

See **[guides/DEPLOYMENT_GUIDE.md](./guides/DEPLOYMENT_GUIDE.md)** for complete instructions.

**Quick Steps**:
1. Create PostgreSQL database on Render
2. Deploy backend to Render
3. Set all environment variables
4. Deploy frontend to Vercel
5. Configure Stripe webhooks
6. Test everything

---

## 📋 Features

- ✅ User authentication (JWT)
- ✅ Email verification
- ✅ Password reset
- ✅ Employee management
- ✅ Survey access codes
- ✅ Survey responses
- ✅ Analytics dashboard
- ✅ Stripe subscription management
- ✅ Admin audit logging
- ✅ Rate limiting
- ✅ CORS protection

---

## 🗄️ Database

**Production**: PostgreSQL on Render  
**Development**: SQLite (local) or PostgreSQL

**Tables**:
- `users` - User accounts
- `dealerships` - Dealership information and subscriptions
- `employees` - Employee records
- `survey_access_codes` - Survey access codes
- `survey_responses` - Survey submissions
- `admin_audit_logs` - Admin action audit trail

**Auto-creation**: Tables are created automatically on first startup.

---

## 🔐 Environment Variables

See **[guides/ENVIRONMENT_VARIABLES.md](./guides/ENVIRONMENT_VARIABLES.md)** for complete list.

**Required**:
- `DATABASE_URL` - PostgreSQL connection string
- `JWT_SECRET` - Secret for JWT tokens
- `FRONTEND_URL` - Frontend application URL
- `ENVIRONMENT` - `production` | `staging` | `development`

**Email** (choose one):
- Resend: `RESEND_API_KEY`, `EMAIL_FROM`
- SMTP: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`

**Stripe** (for subscriptions):
- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `STRIPE_PRICE_ID`

---

## 💾 Database Backups

**Automatic**: Render provides automatic backups (daily on free tier)

**Manual**: Use `backup_database.py`:
```bash
python3 backup_database.py
```

**Restore**: Use `restore_database.py`:
```bash
python3 restore_database.py /path/to/backup.sql
```

See **[guides/DATABASE_MAINTENANCE.md](./guides/DATABASE_MAINTENANCE.md)** for details.

---

## 🧪 Testing

### Health Check
```bash
curl https://your-backend.onrender.com/health
```

### Test User Registration
```bash
curl -X POST https://your-backend.onrender.com/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "password123"}'
```

### Test Login
```bash
curl -X POST https://your-backend.onrender.com/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "password123"}'
```

---

## 📊 API Endpoints

### Authentication
- `POST /auth/register` - Register new user
- `POST /auth/login` - Login
- `POST /auth/verify` - Verify email
- `POST /auth/forgot` - Request password reset
- `POST /auth/reset` - Reset password
- `GET /auth/me` - Get current user

### Employees
- `GET /employees` - List employees
- `POST /employees` - Create employee
- `GET /employees/<id>` - Get employee
- `PUT /employees/<id>` - Update employee
- `DELETE /employees/<id>` - Delete employee

### Surveys
- `POST /survey/access-codes` - Create access code
- `GET /survey/access-codes` - List access codes
- `POST /survey/submit` - Submit survey response

### Analytics
- `GET /analytics/summary` - Summary statistics
- `GET /analytics/time-series` - Time series data
- `GET /analytics/role-breakdown` - Breakdown by role

### Subscriptions
- `GET /subscription/status` - Get subscription status
- `POST /subscription/create-checkout` - Create Stripe checkout
- `POST /subscription/webhook` - Stripe webhook handler
- `POST /subscription/cancel` - Cancel subscription

### Audit Logs
- `GET /audit-logs` - Get admin audit logs

---

## 🛠️ Development

### Project Structure

```
star4ce-backend/
├── app.py                 # Main application
├── backup_database.py     # Backup script
├── restore_database.py    # Restore script
├── requirements.txt       # Python dependencies
├── Procfile              # Render deployment config
├── runtime.txt           # Python version
└── docs/                 # Documentation
```

### Adding New Features

1. **Create feature branch**:
   ```bash
   git checkout -b feature/new-feature
   ```

2. **Make changes**

3. **Test locally**:
   ```bash
   python3 app.py
   ```

4. **Test in staging** (if available)

5. **Deploy to production**

---

## 🐛 Troubleshooting

See **[guides/TROUBLESHOOTING.md](./guides/TROUBLESHOOTING.md)** for common issues.

**Quick fixes**:
- Backend won't start → Check environment variables
- Database errors → Check `DATABASE_URL`
- Email not sending → Check email service credentials
- Stripe not working → Check Stripe keys and webhook

---

## 📞 Support

**For Technical Issues**:
- Check documentation first
- Review logs (Render Dashboard)
- Check troubleshooting guide
- Contact developer

**For Business/Owner Questions**:
- See **[guides/OWNER_GUIDE.md](./guides/OWNER_GUIDE.md)**
- Contact developer

---

## 🔒 Security

- ✅ JWT authentication
- ✅ Password hashing (bcrypt)
- ✅ Rate limiting
- ✅ CORS protection
- ✅ Input sanitization
- ✅ SQL injection protection (SQLAlchemy)
- ✅ Environment variable secrets
- ✅ Audit logging

**Best Practices**:
- Never commit secrets to Git
- Use strong `JWT_SECRET`
- Keep dependencies updated
- Monitor logs for suspicious activity
- Regular security audits

---

## 📝 License

See [LICENSE](./LICENSE) file.

---

## 🗺️ Roadmap

- [x] Export functionality (CSV)
- [ ] Email templates customization
- [ ] Advanced analytics
- [ ] Multi-language support
- [ ] Mobile app API
- [ ] Webhook notifications
- [ ] Advanced reporting

---

## 📚 Additional Resources

- [Flask Documentation](https://flask.palletsprojects.com/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [Stripe API Documentation](https://stripe.com/docs/api)
- [Render Documentation](https://render.com/docs)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)

---

**Last Updated**: 2025-01-20  
**Version**: 1.0

---

## 🎯 For Contract Developers

When handing off to the owner:

1. ✅ Complete **[guides/QUICK_START_CHECKLIST.md](./guides/QUICK_START_CHECKLIST.md)**
2. ✅ Share **[guides/OWNER_GUIDE.md](./guides/OWNER_GUIDE.md)** with owner
3. ✅ Document all credentials securely
4. ✅ Set up automated backups
5. ✅ Test restore process
6. ✅ Provide emergency contact information
7. ✅ Walk owner through basic operations
8. ✅ Document any custom configurations

**Remember**: The owner is not technical. Keep instructions simple and provide ongoing support as needed.
