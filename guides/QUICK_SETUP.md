# Quick Setup Checklist

**For when Vercel and Render are already connected**

---

## ✅ Pre-Check

- [ ] Vercel frontend is deployed
- [ ] Render backend is deployed
- [ ] Render database exists (you have the internal URL)

---

## Step 1: Render Backend Environment Variables

**Go to**: Render Dashboard → Your Backend → Environment

**Add these** (one per line):

```
DATABASE_URL=<your-internal-database-url>
ENVIRONMENT=production
JWT_SECRET=<random-32-chars>
FRONTEND_URL=https://your-app.vercel.app
RESEND_API_KEY=re_xxxxx
EMAIL_FROM=noreply@yourdomain.com
STRIPE_SECRET_KEY=sk_live_xxxxx
STRIPE_WEBHOOK_SECRET=whsec_xxxxx
STRIPE_PRICE_ID=price_xxxxx
```

**Get JWT_SECRET**: https://randomkeygen.com/ (use any 32+ char string)

---

## Step 2: Stripe Setup (5 minutes)

1. **Stripe Dashboard** → Switch to **Live Mode**
2. **Get Secret Key**: Developers → API keys → Copy `sk_live_...`
3. **Create Product**: 
   - Products → Add Product
   - Set price → Copy `price_...`
4. **Create Webhook**:
   - Developers → Webhooks → Add endpoint
   - URL: `https://your-backend.onrender.com/subscription/webhook`
   - Events: `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`
   - Copy `whsec_...`
5. **Add to Render**: All 3 values from above

---

## Step 3: Email Setup (Choose One)

**Resend** (Easiest):
- Sign up → Get API key → Add `RESEND_API_KEY` and `EMAIL_FROM`

**Gmail**:
- Enable 2FA → Generate App Password → Add all `SMTP_*` variables

---

## Step 4: Vercel Frontend

**Go to**: Vercel Dashboard → Your Project → Settings → Environment Variables

**Add**:
```
NEXT_PUBLIC_API_BASE=https://your-backend.onrender.com
```

**Redeploy** after adding.

---

## Step 5: Test

1. Visit: `https://your-backend.onrender.com/health` → Should show `{"ok": true}`
2. Register account on your site
3. Check email for verification code
4. Login
5. Test subscription checkout (use card: `4242 4242 4242 4242`)

---

## ✅ Done!

Your platform is live. Share the owner guide with the owner.

---

## Quick Reference

**Backend URL**: `https://your-backend.onrender.com`  
**Frontend URL**: `https://your-app.vercel.app`  
**Health Check**: `/health` endpoint  
**Stripe Test Card**: `4242 4242 4242 4242`

---

**Need more details?** See `SIMPLE_DEPLOYMENT.md` for step-by-step instructions.

