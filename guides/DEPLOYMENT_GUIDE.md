# Star4ce Deployment Guide

Complete guide for deploying Star4ce to production on Vercel (frontend) and Render (backend).

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Database Setup](#database-setup)
3. [Backend Deployment (Render)](#backend-deployment-render)
4. [Frontend Deployment (Vercel)](#frontend-deployment-vercel)
5. [Stripe Configuration](#stripe-configuration)
6. [Email Configuration](#email-configuration)
7. [Database Backups](#database-backups)
8. [Post-Deployment Verification](#post-deployment-verification)
9. [Monitoring & Maintenance](#monitoring--maintenance)

---

## Prerequisites

Before deploying, ensure you have:

- ✅ GitHub account with code repository
- ✅ Render account (free tier available)
- ✅ Vercel account (free tier available)
- ✅ Stripe account (for payments)
- ✅ Email service (Resend or SMTP)
- ✅ Domain name (optional, but recommended)

---

## Database Setup

### Step 1: Create PostgreSQL Database on Render

1. **Go to Render Dashboard**: https://dashboard.render.com
2. **Click "New +"** → **"PostgreSQL"**
3. **Configure Database**:
   - **Name**: `star4ce-production-db`
   - **Database**: `star4ce` (auto-generated)
   - **User**: `star4ce_user` (auto-generated)
   - **Region**: Choose closest to your users (e.g., `US East`)
   - **PostgreSQL Version**: `15` (or latest)
   - **Plan**: Start with **Free** (upgrade later if needed)

4. **Copy Database URL**:
   - After creation, click on your database
   - Find **"Internal Database URL"** or **"External Database URL"**
   - Copy the full URL (starts with `postgresql://`)
   - **⚠️ IMPORTANT**: Save this URL securely - you'll need it for backend configuration

5. **Enable Persistent Disk** (Recommended):
   - In database settings, enable **"Persistent Disk"**
   - This ensures data survives restarts

### Step 2: Initialize Database Tables

The database tables will be created automatically when the backend starts for the first time. However, you can verify by:

1. After deploying backend, check logs for: `"Database initialized successfully"`
2. Or manually verify tables exist in Render database dashboard

---

## Backend Deployment (Render)

### Step 1: Connect GitHub Repository

1. **Go to Render Dashboard** → **"New +"** → **"Web Service"**
2. **Connect Repository**:
   - Click **"Connect GitHub"** (if not connected)
   - Authorize Render to access your repositories
   - Select your repository: `star4ce-backend` (or your repo name)
   - Select branch: `main` (or `master`)

### Step 2: Configure Service

**Basic Settings**:
- **Name**: `star4ce-api` (or `star4ce-backend`)
- **Region**: Same as database (e.g., `US East`)
- **Branch**: `main`
- **Root Directory**: Leave empty (or `star4ce-backend` if in monorepo)
- **Runtime**: `Python 3`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120`

**Environment Variables** (Click "Add Environment Variable" for each):

```bash
# Database
DATABASE_URL=<paste-your-postgresql-url-from-render>

# Application
ENVIRONMENT=production
JWT_SECRET=<generate-a-random-secret-key-here>
FRONTEND_URL=https://your-app.vercel.app

# Email (Choose ONE: Resend OR SMTP)
# Option 1: Resend (Recommended)
RESEND_API_KEY=re_xxxxxxxxxxxxx
EMAIL_FROM=noreply@yourdomain.com

# Option 2: SMTP (Alternative)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=your-email@gmail.com

# Stripe (Production Keys)
STRIPE_SECRET_KEY=sk_live_xxxxxxxxxxxxx
STRIPE_WEBHOOK_SECRET=whsec_xxxxxxxxxxxxx
STRIPE_PRICE_ID=price_xxxxxxxxxxxxx
```

**How to Generate JWT_SECRET**:
```bash
# On Mac/Linux:
openssl rand -hex 32

# Or use online generator:
# https://randomkeygen.com/
```

### Step 3: Deploy

1. Click **"Create Web Service"**
2. Render will automatically:
   - Clone your repository
   - Install dependencies
   - Start your application
3. Wait for deployment to complete (2-5 minutes)
4. Your backend URL will be: `https://star4ce-api.onrender.com` (or your custom name)

### Step 4: Verify Backend is Running

1. **Check Health Endpoint**:
   ```
   https://your-backend.onrender.com/health
   ```
   Should return: `{"ok": true, "service": "star4ce-backend"}`

2. **Check Logs**:
   - In Render dashboard, click **"Logs"** tab
   - Look for: `"Running on http://0.0.0.0:XXXX"`

---

## Frontend Deployment (Vercel)

### Step 1: Import Project

1. **Go to Vercel Dashboard**: https://vercel.com/dashboard
2. **Click "Add New..."** → **"Project"**
3. **Import Git Repository**:
   - Select your GitHub account
   - Choose repository: `star4ce-frontend` (or your repo name)
   - Click **"Import"**

### Step 2: Configure Project

**Project Settings**:
- **Project Name**: `star4ce` (or your preferred name)
- **Framework Preset**: **Next.js** (auto-detected)
- **Root Directory**: `star4ce-frontend` (if in monorepo, otherwise leave empty)
- **Build Command**: `npm run build` (auto-detected)
- **Output Directory**: `.next` (auto-detected)
- **Install Command**: `npm install` (auto-detected)

**Environment Variables**:
Click **"Add"** and add:

```bash
NEXT_PUBLIC_API_BASE=https://your-backend.onrender.com
```

**⚠️ Important**: Replace `your-backend.onrender.com` with your actual Render backend URL.

### Step 3: Deploy

1. Click **"Deploy"**
2. Vercel will:
   - Install dependencies
   - Build your Next.js app
   - Deploy to production
3. Your frontend URL will be: `https://your-app.vercel.app`

### Step 4: Custom Domain (Optional)

1. In Vercel project settings → **"Domains"**
2. Add your custom domain (e.g., `app.star4ce.com`)
3. Follow DNS configuration instructions
4. Update `FRONTEND_URL` in Render backend environment variables

---

## Stripe Configuration

### Step 1: Get Production Keys

1. **Go to Stripe Dashboard**: https://dashboard.stripe.com
2. **Switch to Live Mode** (toggle in top right)
3. **Get API Keys**:
   - Go to **"Developers"** → **"API keys"**
   - Copy **"Secret key"**: `sk_live_...` → This is `STRIPE_SECRET_KEY`

### Step 2: Create Product and Price

1. **Go to "Products"** → **"Add Product"**
2. **Configure**:
   - **Name**: "Star4ce Pro Subscription"
   - **Description**: "Monthly subscription"
   - **Pricing**: Set your monthly price (e.g., $29.99)
   - **Billing period**: Monthly
   - **Recurring**: Yes
3. **Save** and copy the **Price ID**: `price_...` → This is `STRIPE_PRICE_ID`

### Step 3: Set Up Webhook

1. **Go to "Developers"** → **"Webhooks"**
2. **Click "Add endpoint"**
3. **Configure**:
   - **Endpoint URL**: `https://your-backend.onrender.com/subscription/webhook`
   - **Description**: "Star4ce Subscription Webhooks"
   - **Events to send**: Select:
     - `checkout.session.completed`
     - `customer.subscription.updated`
     - `customer.subscription.deleted`
4. **Click "Add endpoint"**
5. **Copy Signing Secret**: `whsec_...` → This is `STRIPE_WEBHOOK_SECRET`
6. **Add to Render environment variables**

### Step 4: Test Webhook

1. In Stripe Dashboard → **"Webhooks"** → Click your endpoint
2. Click **"Send test webhook"**
3. Select event: `checkout.session.completed`
4. Check Render logs to verify webhook received

---

## Email Configuration

### Option 1: Resend (Recommended)

1. **Sign up**: https://resend.com
2. **Verify domain** (or use default)
3. **Get API Key**: Dashboard → **"API Keys"** → **"Create API Key"**
4. **Add to Render**:
   ```
   RESEND_API_KEY=re_xxxxxxxxxxxxx
   EMAIL_FROM=noreply@yourdomain.com
   ```

### Option 2: SMTP (Gmail)

1. **Enable 2-Factor Authentication** on Gmail
2. **Generate App Password**:
   - Google Account → Security → 2-Step Verification → App passwords
   - Generate password for "Mail"
3. **Add to Render**:
   ```
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=your-email@gmail.com
   SMTP_PASSWORD=your-app-password
   SMTP_FROM=your-email@gmail.com
   ```

---

## Database Backups

### Automatic Backups on Render

Render automatically backs up PostgreSQL databases:
- **Free tier**: Daily backups (kept for 7 days)
- **Paid tier**: More frequent backups (configurable)

### Manual Backup Script

Use the included `backup_database.py` script for additional backups:

1. **Set up Render Cron Job**:
   - In Render dashboard → **"New +"** → **"Cron Job"**
   - **Name**: `star4ce-backup`
   - **Schedule**: `0 2 * * *` (Daily at 2 AM)
   - **Command**: 
     ```bash
     cd /opt/render/project/src && python3 backup_database.py
     ```
   - **Environment Variables**: Same as backend service

2. **Or use Render's built-in backups**:
   - Database → **"Backups"** tab
   - Download backups manually
   - Or set up automatic exports to S3

### Backup Retention

- **Daily backups**: Keep for 30 days
- **Weekly backups**: Keep for 12 weeks
- **Monthly backups**: Keep for 12 months
- **Yearly backups**: Keep forever

**⚠️ CRITICAL**: Download and store backups in multiple locations:
- Cloud storage (Google Drive, Dropbox, AWS S3)
- External hard drive
- Another cloud provider

---

## Post-Deployment Verification

### Checklist

- [ ] Backend health check returns `{"ok": true}`
- [ ] Frontend loads without errors
- [ ] User registration works
- [ ] Email verification emails are sent
- [ ] Login works
- [ ] Stripe checkout creates sessions
- [ ] Webhooks are received (check Stripe dashboard)
- [ ] Database tables exist (check Render database dashboard)
- [ ] All environment variables are set correctly

### Test User Registration

1. Go to your frontend URL
2. Click "Register"
3. Enter email and password
4. Check email for verification code
5. Verify account
6. Login
7. Test creating access code
8. Test subscription checkout (use test card: `4242 4242 4242 4242`)

---

## Monitoring & Maintenance

### Health Checks

**Backend**:
```bash
curl https://your-backend.onrender.com/health
```

**Frontend**:
- Just visit the URL - should load without errors

### Logs

**Render Logs**:
- Dashboard → Your service → **"Logs"** tab
- Monitor for errors, warnings

**Vercel Logs**:
- Dashboard → Your project → **"Deployments"** → Click deployment → **"Functions"** tab

### Common Issues

See `TROUBLESHOOTING.md` for common issues and solutions.

### Regular Maintenance

**Weekly**:
- Check logs for errors
- Verify backups are running
- Check Stripe webhook logs

**Monthly**:
- Review database size
- Check subscription statuses
- Review error logs
- Update dependencies (if needed)

**Yearly**:
- Review and update security keys
- Audit user access
- Review backup retention policy
- Update documentation

---

## Environment Variables Reference

See `ENVIRONMENT_VARIABLES.md` for complete list of all environment variables.

---

## Support

If you encounter issues:

1. Check `TROUBLESHOOTING.md`
2. Review Render and Vercel logs
3. Check Stripe webhook logs
4. Contact your developer (if on contract)

---

## Next Steps

After successful deployment:

1. ✅ Set up custom domain (optional)
2. ✅ Configure monitoring alerts
3. ✅ Set up automated backups
4. ✅ Test all features end-to-end
5. ✅ Create first admin user
6. ✅ Document any custom configurations

---

**Last Updated**: 2025-01-20
**Version**: 1.0

