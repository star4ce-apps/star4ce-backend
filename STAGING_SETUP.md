# Staging Environment Setup Guide

This guide explains how to set up a staging environment for Star4ce to test changes before deploying to production.

## Overview

A staging environment is a copy of your production environment used for testing. It should:
- Mirror production as closely as possible
- Use separate databases and services
- Allow safe testing of new features
- Prevent accidental impact on production data

## Architecture

```
Production:
  Frontend: https://star4ce.vercel.app
  Backend: https://star4ce-api.onrender.com
  Database: Production PostgreSQL (Render)

Staging:
  Frontend: https://star4ce-staging.vercel.app
  Backend: https://star4ce-api-staging.onrender.com
  Database: Staging PostgreSQL (Render)
```

## Step 1: Create Staging Database

### Option A: Render PostgreSQL (Recommended)

1. Go to Render Dashboard
2. Create new PostgreSQL database
3. Name it: `star4ce-staging-db`
4. Copy the `DATABASE_URL` for staging

### Option B: Local PostgreSQL

```bash
# Install PostgreSQL (if not installed)
brew install postgresql  # macOS
sudo apt-get install postgresql  # Linux

# Create database
createdb star4ce_staging

# Set DATABASE_URL
export DATABASE_URL="postgresql://user:password@localhost:5432/star4ce_staging"
```

## Step 2: Set Up Staging Backend

### On Render

1. **Fork your backend service**:
   - Go to your production backend service
   - Click "Manual Deploy" → "Create Blueprint"
   - Create new service from blueprint

2. **Configure environment variables**:
   ```
   ENVIRONMENT=staging
   DATABASE_URL=<staging-database-url>
   FRONTEND_URL=https://star4ce-staging.vercel.app
   JWT_SECRET=<different-secret-from-production>
   RESEND_API_KEY=<same-or-separate>
   EMAIL_FROM=staging@yourdomain.com
   STRIPE_SECRET_KEY=<stripe-test-key>
   STRIPE_WEBHOOK_SECRET=<staging-webhook-secret>
   STRIPE_PRICE_ID=<test-price-id>
   ```

3. **Deploy staging backend**

### Local Staging Backend

```bash
# Clone or copy your backend
cd star4ce-backend-staging

# Create .env file
cat > .env << EOF
ENVIRONMENT=staging
DATABASE_URL=postgresql://user:pass@localhost:5432/star4ce_staging
FRONTEND_URL=http://localhost:3001
JWT_SECRET=staging-secret-key-different-from-prod
RESEND_API_KEY=your-resend-key
EMAIL_FROM=staging@yourdomain.com
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_ID=price_test_...
EOF

# Run migrations
python3 migrate_subscription_columns.py

# Start server
python3 app.py
```

## Step 3: Set Up Staging Frontend

### On Vercel

1. **Create new Vercel project**:
   - Import your GitHub repository
   - Name it: `star4ce-staging`
   - Set as separate project (not production)

2. **Configure environment variables**:
   ```
   NEXT_PUBLIC_API_BASE=https://star4ce-api-staging.onrender.com
   ```

3. **Deploy**

### Local Staging Frontend

```bash
# Clone or copy your frontend
cd star4ce-frontend-staging

# Create .env.local file
cat > .env.local << EOF
NEXT_PUBLIC_API_BASE=http://localhost:5001
EOF

# Install dependencies
npm install

# Run dev server on different port
npm run dev -- -p 3001
```

## Step 4: Initialize Staging Database

```bash
# Connect to staging backend
cd star4ce-backend-staging

# Run migrations
python3 migrate_subscription_columns.py

# (Optional) Seed test data
python3 seed_staging_data.py  # Create this if needed
```

## Step 5: Configure Stripe for Staging

1. **Use Stripe Test Mode**:
   - Go to Stripe Dashboard → Test Mode
   - Create test products and prices
   - Use test webhook endpoints

2. **Set up webhook endpoint**:
   - URL: `https://star4ce-api-staging.onrender.com/subscription/webhook`
   - Events: `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`

## Step 6: Testing Checklist

Before deploying to production, test in staging:

- [ ] User registration and email verification
- [ ] Login and authentication
- [ ] Password reset flow
- [ ] Employee management (CRUD)
- [ ] Access code creation
- [ ] Survey submission
- [ ] Analytics dashboard
- [ ] Subscription checkout
- [ ] Webhook handling
- [ ] Email sending (verification, invites, etc.)

## Step 7: Data Management

### Copy Production Data to Staging (Optional)

**⚠️ WARNING: Only use anonymized/sanitized production data!**

```bash
# Export production data (anonymize sensitive info)
pg_dump $PRODUCTION_DATABASE_URL > production_dump.sql

# Anonymize emails and personal data
sed -i 's/@.*/@example.com/g' production_dump.sql

# Import to staging
psql $STAGING_DATABASE_URL < production_dump.sql
```

### Reset Staging Database

```bash
# Drop and recreate
dropdb star4ce_staging
createdb star4ce_staging

# Run migrations
python3 migrate_subscription_columns.py
```

## Environment-Specific Configuration

### Backend (`app.py`)

The app already checks `ENVIRONMENT` variable:

```python
is_production = os.getenv("ENVIRONMENT") == "production"
```

Use this for:
- Different CORS settings
- Different rate limits
- Different logging levels
- Feature flags

### Frontend

Use environment variables for API endpoints:

```typescript
// Automatically uses NEXT_PUBLIC_API_BASE
const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:5000"
```

## Deployment Workflow

### Recommended Flow

1. **Develop locally** → Test on `localhost`
2. **Deploy to staging** → Test with staging database
3. **Run staging tests** → Verify all features
4. **Deploy to production** → Only after staging approval

### Git Branch Strategy

```
main (production)
  └── staging (staging environment)
      └── feature/* (development branches)
```

## Monitoring Staging

### Health Checks

```bash
# Backend health
curl https://star4ce-api-staging.onrender.com/health

# Frontend
curl https://star4ce-staging.vercel.app
```

### Logs

- **Render**: View logs in dashboard
- **Vercel**: View logs in dashboard
- **Local**: `tail -f logs/app.log`

## Troubleshooting

### Staging backend can't connect to database
- Verify `DATABASE_URL` is correct
- Check database is accessible from Render
- Verify database credentials

### CORS errors in staging
- Check `FRONTEND_URL` matches staging frontend URL
- Verify CORS configuration in `app.py`

### Stripe webhooks not working
- Use Stripe CLI for local testing: `stripe listen --forward-to localhost:5000/subscription/webhook`
- Verify webhook secret matches staging environment

## Best Practices

1. **Keep staging in sync** with production code (but not data)
2. **Test all features** in staging before production
3. **Use test data** - never use real customer data in staging
4. **Monitor staging** - catch issues before production
5. **Document changes** - keep staging setup updated
6. **Automate deployments** - use CI/CD for staging
7. **Regular resets** - reset staging database monthly

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Deploy to Staging

on:
  push:
    branches: [staging]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Deploy to Render
        run: |
          # Trigger Render deployment
          curl -X POST $RENDER_DEPLOY_HOOK
```

## Cost Considerations

- **Render**: Free tier available for staging
- **Vercel**: Free tier for staging frontend
- **Database**: Use smaller instance for staging
- **Stripe**: Test mode is free

## Next Steps

1. Set up staging environment
2. Configure CI/CD pipeline
3. Create staging test suite
4. Document staging-specific features
5. Set up staging monitoring

