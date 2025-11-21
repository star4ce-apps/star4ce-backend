# Environment Variables Reference

Complete list of all environment variables used in Star4ce backend.

---

## Required Variables

### Database

**`DATABASE_URL`**
- **Description**: PostgreSQL database connection URL
- **Format**: `postgresql://user:password@host:port/database`
- **Example**: `postgresql://star4ce_user:password123@dpg-xxxxx.oregon-postgres.render.com:5432/star4ce_db`
- **Where to Get**: Render Dashboard → Your Database → "Internal Database URL"
- **Required**: ✅ Yes
- **Notes**: 
  - Render provides this automatically
  - Never commit this to Git
  - Keep it secret

---

### Application

**`ENVIRONMENT`**
- **Description**: Environment mode (production, staging, development)
- **Values**: `production` | `staging` | `development`
- **Example**: `production`
- **Required**: ✅ Yes (for production)
- **Default**: `development`
- **Notes**: 
  - Set to `production` for live site
  - Affects CORS, logging, error messages

**`JWT_SECRET`**
- **Description**: Secret key for signing JWT tokens
- **Format**: Random string (32+ characters recommended)
- **Example**: `a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6`
- **How to Generate**:
  ```bash
  # Mac/Linux:
  openssl rand -hex 32
  
  # Or use: https://randomkeygen.com/
  ```
- **Required**: ✅ Yes
- **Notes**: 
  - Must be unique and secret
  - Never commit to Git
  - Changing this invalidates all user sessions

**`FRONTEND_URL`**
- **Description**: URL of your frontend application
- **Format**: `https://your-app.vercel.app` or `http://localhost:3000`
- **Example**: `https://star4ce.vercel.app`
- **Required**: ✅ Yes
- **Notes**: 
  - Used for CORS configuration
  - Used in email links
  - Must match your actual frontend URL

---

## Email Configuration

Choose **ONE** of the following options:

### Option 1: Resend (Recommended)

**`RESEND_API_KEY`**
- **Description**: API key for Resend email service
- **Format**: `re_xxxxxxxxxxxxx`
- **Example**: `re_1234567890abcdef`
- **Where to Get**: Resend Dashboard → API Keys → Create API Key
- **Required**: ✅ Yes (if using Resend)
- **Notes**: 
  - Sign up at https://resend.com
  - Free tier: 3,000 emails/month
  - Better deliverability than SMTP

**`EMAIL_FROM`**
- **Description**: Email address to send from
- **Format**: `noreply@yourdomain.com` or `name@yourdomain.com`
- **Example**: `noreply@star4ce.com`
- **Required**: ✅ Yes (if using Resend)
- **Notes**: 
  - Must be verified in Resend
  - Can use default Resend domain for testing

### Option 2: SMTP (Alternative)

**`SMTP_HOST`**
- **Description**: SMTP server hostname
- **Format**: `smtp.gmail.com` or `smtp.yourdomain.com`
- **Example**: `smtp.gmail.com`
- **Required**: ✅ Yes (if using SMTP)
- **Default**: `smtp.gmail.com`

**`SMTP_PORT`**
- **Description**: SMTP server port
- **Format**: Number (usually 587 or 465)
- **Example**: `587`
- **Required**: ✅ Yes (if using SMTP)
- **Default**: `587`
- **Notes**: 
  - 587 = TLS (recommended)
  - 465 = SSL

**`SMTP_USER`**
- **Description**: SMTP username (usually your email)
- **Format**: `your-email@gmail.com`
- **Example**: `admin@star4ce.com`
- **Required**: ✅ Yes (if using SMTP)

**`SMTP_PASSWORD`**
- **Description**: SMTP password or app password
- **Format**: Your password or app-specific password
- **Example**: `your-app-password-here`
- **Required**: ✅ Yes (if using SMTP)
- **Notes**: 
  - For Gmail: Use App Password (not regular password)
  - Generate at: Google Account → Security → App passwords

**`SMTP_FROM`**
- **Description**: Email address to send from
- **Format**: `your-email@gmail.com`
- **Example**: `admin@star4ce.com`
- **Required**: ✅ Yes (if using SMTP)
- **Default**: Uses `SMTP_USER` if not set

---

## Stripe Configuration

**`STRIPE_SECRET_KEY`**
- **Description**: Stripe API secret key
- **Format**: `sk_live_...` (production) or `sk_test_...` (testing)
- **Example**: `sk_live_51AbCdEfGhIjKlMnOpQrStUvWxYz`
- **Where to Get**: Stripe Dashboard → Developers → API Keys
- **Required**: ✅ Yes (for subscriptions)
- **Notes**: 
  - Use `sk_live_...` for production
  - Use `sk_test_...` for testing/staging
  - Never commit to Git

**`STRIPE_WEBHOOK_SECRET`**
- **Description**: Webhook signing secret from Stripe
- **Format**: `whsec_...`
- **Example**: `whsec_1234567890abcdef`
- **Where to Get**: 
  - Stripe Dashboard → Developers → Webhooks → Your endpoint → Signing secret
  - Or from Stripe CLI: `stripe listen --forward-to localhost:5000/subscription/webhook`
- **Required**: ✅ Yes (for subscriptions)
- **Notes**: 
  - Different for each webhook endpoint
  - Must match the endpoint URL

**`STRIPE_PRICE_ID`**
- **Description**: Stripe Price ID for monthly subscription ($199/month)
- **Format**: `price_...`
- **Example**: `price_1234567890abcdef`
- **Where to Get**: Stripe Dashboard → Products → Your Product → Monthly Price ID
- **Required**: ✅ Yes (for subscriptions)
- **Notes**: 
  - Create product and monthly price ($199/month) in Stripe first
  - Use test price ID for staging
  - Use live price ID for production

**`STRIPE_PRICE_ID_ANNUAL`**
- **Description**: Stripe Price ID for annual subscription ($166/month = $1992/year)
- **Format**: `price_...`
- **Example**: `price_9876543210fedcba`
- **Where to Get**: Stripe Dashboard → Products → Your Product → Annual Price ID
- **Required**: ❌ No (optional, for annual billing)
- **Notes**: 
  - Create annual price ($1992/year, billed yearly) in Stripe
  - If not set, annual plan will fallback to monthly price
  - Use test price ID for staging
  - Use live price ID for production

---

## Optional Variables

### Backup Configuration

**`BACKUP_DIR`**
- **Description**: Directory to store backups
- **Format**: Path to directory
- **Example**: `backups` or `/var/backups/star4ce`
- **Required**: ❌ No
- **Default**: `backups`
- **Notes**: 
  - Used by `backup_database.py` script
  - Must be writable

**`BACKUP_RETENTION_DAYS`**
- **Description**: How many days to keep backups
- **Format**: Number
- **Example**: `30`
- **Required**: ❌ No
- **Default**: `30`
- **Notes**: 
  - Older backups are automatically deleted
  - Set to `0` to keep all backups

### Port Configuration

**`PORT`**
- **Description**: Port to run server on
- **Format**: Number
- **Example**: `5000`
- **Required**: ❌ No
- **Default**: `5000`
- **Notes**: 
  - Render sets this automatically (`$PORT`)
  - Don't set manually on Render
  - Only set for local development

---

## Environment-Specific Examples

### Local Development (.env file)

```env
# Database (PostgreSQL - REQUIRED)
DATABASE_URL=postgresql://star4ce_user:password@localhost:5432/star4ce_db

# Application
ENVIRONMENT=development
JWT_SECRET=dev-secret-key-change-in-production
FRONTEND_URL=http://localhost:3000

# Email (Resend)
RESEND_API_KEY=re_test_xxxxxxxxxxxxx
EMAIL_FROM=noreply@yourdomain.com

# Stripe (Test Mode)
STRIPE_SECRET_KEY=sk_test_xxxxxxxxxxxxx
STRIPE_WEBHOOK_SECRET=whsec_xxxxxxxxxxxxx
STRIPE_PRICE_ID=price_test_xxxxxxxxxxxxx
STRIPE_PRICE_ID_ANNUAL=price_test_yyyyyyyyyyyyy
```

### Production (Render)

```env
# Database (from Render)
DATABASE_URL=postgresql://user:pass@host:port/db

# Application
ENVIRONMENT=production
JWT_SECRET=<generate-random-32-char-string>
FRONTEND_URL=https://star4ce.vercel.app

# Email (Resend)
RESEND_API_KEY=re_live_xxxxxxxxxxxxx
EMAIL_FROM=noreply@star4ce.com

# Stripe (Live Mode)
STRIPE_SECRET_KEY=sk_live_xxxxxxxxxxxxx
STRIPE_WEBHOOK_SECRET=whsec_xxxxxxxxxxxxx
STRIPE_PRICE_ID=price_live_xxxxxxxxxxxxx
STRIPE_PRICE_ID_ANNUAL=price_live_yyyyyyyyyyyyy
```

### Staging (Render)

```env
# Database (from Render)
DATABASE_URL=postgresql://user:pass@host:port/staging_db

# Application
ENVIRONMENT=staging
JWT_SECRET=<different-from-production>
FRONTEND_URL=https://star4ce-staging.vercel.app

# Email (Resend - can use same or separate)
RESEND_API_KEY=re_test_xxxxxxxxxxxxx
EMAIL_FROM=staging@star4ce.com

# Stripe (Test Mode)
STRIPE_SECRET_KEY=sk_test_xxxxxxxxxxxxx
STRIPE_WEBHOOK_SECRET=whsec_xxxxxxxxxxxxx
STRIPE_PRICE_ID=price_test_xxxxxxxxxxxxx
STRIPE_PRICE_ID_ANNUAL=price_test_yyyyyyyyyyyyy
```

---

## Security Best Practices

### ✅ DO:

- ✅ Use strong, unique values for `JWT_SECRET`
- ✅ Use different secrets for production and staging
- ✅ Store secrets securely (environment variables, not code)
- ✅ Rotate secrets periodically (especially if compromised)
- ✅ Use production Stripe keys only in production
- ✅ Verify email domains in Resend
- ✅ Use App Passwords for Gmail (not regular password)

### ❌ DON'T:

- ❌ Commit secrets to Git
- ❌ Share secrets in emails or chat
- ❌ Use the same `JWT_SECRET` in multiple environments
- ❌ Use test Stripe keys in production
- ❌ Hardcode secrets in code
- ❌ Share database URLs publicly

---

## Verification Checklist

Before going live, verify:

- [ ] All required variables are set
- [ ] `ENVIRONMENT=production` for production
- [ ] `JWT_SECRET` is strong and unique
- [ ] `FRONTEND_URL` matches your actual frontend URL
- [ ] Email service is configured and tested
- [ ] Stripe keys are for correct mode (test vs live)
- [ ] `STRIPE_WEBHOOK_SECRET` matches your webhook endpoint
- [ ] `STRIPE_PRICE_ID` exists in Stripe (monthly plan)
- [ ] `STRIPE_PRICE_ID_ANNUAL` exists in Stripe (annual plan, optional)
- [ ] Database URL is correct and accessible
- [ ] All secrets are kept secure (not in Git)

---

## Troubleshooting

### "Missing environment variable" Error

**Solution**: Check that all required variables are set in Render dashboard.

### "Invalid database URL" Error

**Solution**: 
- Verify `DATABASE_URL` format is correct
- Check database is accessible from Render
- Ensure database credentials are correct

### "Stripe not configured" Error

**Solution**:
- Verify `STRIPE_SECRET_KEY` is set
- Check Stripe package is installed
- Restart backend after adding variables

### "Email sending failed" Error

**Solution**:
- Verify email service credentials (Resend API key or SMTP)
- Check email domain is verified (for Resend)
- Test SMTP connection (for SMTP)
- Check email service limits/quota

---

## Getting Help

If you need help with environment variables:

1. Check this document first
2. Review error messages in Render logs
3. Verify variables are set correctly in Render dashboard
4. Contact your developer with:
   - Which variable is causing issues
   - Error message (if any)
   - What you're trying to do

---

**Last Updated**: 2025-01-20  
**Version**: 1.0

