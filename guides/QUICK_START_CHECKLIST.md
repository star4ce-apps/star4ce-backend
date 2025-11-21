# Quick Start Checklist

**Pre-deployment checklist for Star4ce platform.**

Use this checklist to ensure everything is ready before going live.

---

## Pre-Deployment Checklist

### ✅ Code & Repository

- [ ] Code is in GitHub repository
- [ ] All code is committed and pushed
- [ ] No secrets are committed to Git
- [ ] `.env` files are in `.gitignore`
- [ ] `node_modules` is in `.gitignore`
- [ ] README files are updated

### ✅ Backend (Render)

- [ ] Render account created
- [ ] PostgreSQL database created on Render
- [ ] Database URL copied and saved securely
- [ ] Backend service created on Render
- [ ] GitHub repository connected
- [ ] All environment variables set (see below)
- [ ] Backend deploys successfully
- [ ] Health endpoint works: `/health`
- [ ] Database tables created automatically

### ✅ Frontend (Vercel)

- [ ] Vercel account created
- [ ] Frontend project created on Vercel
- [ ] GitHub repository connected
- [ ] Environment variables set:
  - [ ] `NEXT_PUBLIC_API_BASE` = your Render backend URL
- [ ] Frontend deploys successfully
- [ ] Frontend loads without errors
- [ ] Frontend can connect to backend

### ✅ Database

- [ ] Database is running on Render
- [ ] Database has persistent disk enabled
- [ ] Database backup strategy configured
- [ ] Database connection tested
- [ ] Tables created automatically on first start

### ✅ Email Service

**If using Resend**:
- [ ] Resend account created
- [ ] Domain verified (or using default)
- [ ] API key generated
- [ ] `RESEND_API_KEY` set in Render
- [ ] `EMAIL_FROM` set in Render
- [ ] Test email sent successfully

**If using SMTP**:
- [ ] SMTP credentials obtained
- [ ] All `SMTP_*` variables set in Render
- [ ] Test email sent successfully

### ✅ Stripe (Payments)

- [ ] Stripe account created
- [ ] Product and Price created in Stripe
- [ ] Price ID copied: `price_...`
- [ ] Webhook endpoint created:
  - [ ] URL: `https://your-backend.onrender.com/subscription/webhook`
  - [ ] Events selected: `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`
- [ ] Webhook signing secret copied: `whsec_...`
- [ ] All Stripe variables set in Render:
  - [ ] `STRIPE_SECRET_KEY` (production key: `sk_live_...`)
  - [ ] `STRIPE_WEBHOOK_SECRET`
  - [ ] `STRIPE_PRICE_ID`
- [ ] Test checkout works (use test card: `4242 4242 4242 4242`)

### ✅ Environment Variables

**Backend (Render) - All Set**:
- [ ] `DATABASE_URL` = PostgreSQL URL from Render
- [ ] `ENVIRONMENT` = `production`
- [ ] `JWT_SECRET` = Strong random secret (32+ chars)
- [ ] `FRONTEND_URL` = Your Vercel frontend URL
- [ ] Email variables (Resend OR SMTP)
- [ ] Stripe variables (all 3)

**Frontend (Vercel) - All Set**:
- [ ] `NEXT_PUBLIC_API_BASE` = Your Render backend URL

### ✅ Testing

**Backend Testing**:
- [ ] Health endpoint: `GET /health` returns `{"ok": true}`
- [ ] User registration works
- [ ] Email verification works
- [ ] Login works
- [ ] Password reset works
- [ ] Access code creation works
- [ ] Survey submission works
- [ ] Analytics endpoints work
- [ ] Subscription checkout creates session
- [ ] Webhooks are received

**Frontend Testing**:
- [ ] Homepage loads
- [ ] Registration page works
- [ ] Login page works
- [ ] Dashboard loads after login
- [ ] All pages load without errors
- [ ] API calls work (no CORS errors)
- [ ] Forms submit successfully

**End-to-End Testing**:
- [ ] Register new user
- [ ] Verify email
- [ ] Login
- [ ] Create access code
- [ ] Submit survey (using access code)
- [ ] View analytics
- [ ] Start subscription checkout
- [ ] Complete payment (test card)
- [ ] Verify subscription activated

### ✅ Documentation

- [ ] `DEPLOYMENT_GUIDE.md` reviewed
- [ ] `OWNER_GUIDE.md` created and shared with owner
- [ ] `ENVIRONMENT_VARIABLES.md` reviewed
- [ ] `TROUBLESHOOTING.md` reviewed
- [ ] `DATABASE_MAINTENANCE.md` reviewed
- [ ] All URLs and credentials documented securely

### ✅ Security

- [ ] No secrets in Git repository
- [ ] Strong `JWT_SECRET` generated
- [ ] Different secrets for production vs staging
- [ ] Database URL is secure
- [ ] Stripe keys are production keys (not test)
- [ ] Email service credentials are secure
- [ ] CORS is configured correctly
- [ ] Rate limiting is enabled

### ✅ Monitoring

- [ ] Render dashboard access configured
- [ ] Vercel dashboard access configured
- [ ] Stripe dashboard access configured
- [ ] Log monitoring set up
- [ ] Health check endpoints verified
- [ ] Error alerting configured (if available)

### ✅ Backup Strategy

- [ ] Render automatic backups enabled
- [ ] Backup script tested (`backup_database.py`)
- [ ] Backup retention policy set
- [ ] Backup storage locations identified
- [ ] Restore process tested
- [ ] Backup schedule documented

### ✅ Owner Handoff

- [ ] Owner has login credentials
- [ ] Owner has access to dashboards (if needed)
- [ ] `OWNER_GUIDE.md` shared with owner
- [ ] Owner knows how to:
  - [ ] Log in
  - [ ] Create employees
  - [ ] View analytics
  - [ ] Manage subscriptions
  - [ ] Contact developer
- [ ] Emergency contact information shared
- [ ] Important URLs documented for owner

---

## Post-Deployment Verification

### Immediate Checks (First Hour)

- [ ] Backend is running (check Render dashboard)
- [ ] Frontend is accessible (visit URL)
- [ ] Health endpoint works
- [ ] Can register new user
- [ ] Can receive verification email
- [ ] Can log in
- [ ] No errors in logs

### First Day Checks

- [ ] All features work as expected
- [ ] No errors in logs
- [ ] Emails are being sent
- [ ] Webhooks are being received
- [ ] Database backups are working
- [ ] Owner can access and use platform

### First Week Checks

- [ ] Monitor logs for errors
- [ ] Verify backups are being created
- [ ] Check database size
- [ ] Test subscription flow end-to-end
- [ ] Verify analytics are working
- [ ] Owner feedback collected

---

## Critical Information to Save

**Write these down and keep in a secure location**:

### URLs

- Frontend URL: `________________`
- Backend URL: `________________`
- Render Dashboard: `https://dashboard.render.com`
- Vercel Dashboard: `https://vercel.com/dashboard`
- Stripe Dashboard: `https://dashboard.stripe.com`

### Credentials

- Owner Login Email: `________________`
- Owner Login Password: `________________` (or password manager)
- Render Account Email: `________________`
- Vercel Account Email: `________________`
- Stripe Account Email: `________________`

### Database

- Database URL: `________________` (keep secret!)
- Database Name: `________________`
- Backup Location: `________________`

### Secrets (Keep Very Secret!)

- JWT_SECRET: `________________`
- Stripe Secret Key: `________________` (first/last 4 chars only)
- Email API Key: `________________` (first/last 4 chars only)

### Developer Contact

- Name: `________________`
- Email: `________________`
- Phone: `________________`
- Availability: `________________`

---

## Emergency Contacts

**Developer**:
- Email: `________________`
- Phone: `________________`

**Render Support**:
- Website: https://render.com/docs/support
- Status: https://status.render.com

**Vercel Support**:
- Website: https://vercel.com/support
- Status: https://www.vercel-status.com

**Stripe Support**:
- Website: https://support.stripe.com
- Status: https://status.stripe.com

---

## Go-Live Checklist

**Before announcing to users**:

- [ ] All items above checked
- [ ] Tested with real email (not just test)
- [ ] Tested with real payment (small amount)
- [ ] Owner has access and can use platform
- [ ] Documentation is complete
- [ ] Backup strategy is working
- [ ] Monitoring is set up
- [ ] Emergency procedures documented
- [ ] Support contacts shared

**You're ready to go live! 🚀**

---

## Post-Go-Live

**First Month**:
- Monitor daily for issues
- Check backups weekly
- Review logs weekly
- Collect owner feedback
- Address any issues quickly

**Ongoing**:
- Monthly backup verification
- Quarterly security review
- Annual documentation update
- Regular dependency updates (with testing)

---

**Last Updated**: 2025-01-20  
**Version**: 1.0

