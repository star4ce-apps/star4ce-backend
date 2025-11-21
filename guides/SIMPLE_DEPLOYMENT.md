# Simple Deployment Guide

**Quick steps to get Star4ce running on Vercel + Render**

---

## ✅ What You Already Have

- ✅ Vercel frontend deployed
- ✅ Render backend deployed  
- ✅ Render database with internal URL

---

## Step 1: Set Environment Variables in Render

Go to **Render Dashboard** → Your Backend Service → **Environment** tab

Add these variables:

```
DATABASE_URL=<paste-your-internal-database-url-from-render>
ENVIRONMENT=production
JWT_SECRET=<generate-random-32-character-string>
FRONTEND_URL=https://your-vercel-app.vercel.app
```

**To generate JWT_SECRET**: Use https://randomkeygen.com/ (pick any 32+ character string)

---

## Step 2: Set Up Email (Choose One)

### Option A: Resend (Easiest)

1. Sign up at https://resend.com
2. Get API key from dashboard
3. Add to Render:
   ```
   RESEND_API_KEY=re_xxxxxxxxxxxxx
   EMAIL_FROM=noreply@yourdomain.com
   ```

### Option B: Gmail SMTP

1. Enable 2-Factor Auth on Gmail
2. Generate App Password: Google Account → Security → App passwords
3. Add to Render:
   ```
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=your-email@gmail.com
   SMTP_PASSWORD=your-app-password
   SMTP_FROM=your-email@gmail.com
   ```

---

## Step 3: Set Up Stripe

1. **Go to Stripe Dashboard**: https://dashboard.stripe.com
2. **Switch to Live Mode** (toggle top right)
3. **Get Secret Key**: Developers → API keys → Copy `sk_live_...`
4. **Create Product**:
   - Products → Add Product
   - Name: "Star4ce Subscription"
   - Price: Your monthly price (e.g., $29.99)
   - Billing: Monthly, Recurring
   - Copy the **Price ID** (`price_...`)
5. **Set Up Webhook**:
   - Developers → Webhooks → Add endpoint
   - URL: `https://your-backend.onrender.com/subscription/webhook`
   - Events: Select these 3:
     - `checkout.session.completed`
     - `customer.subscription.updated`
     - `customer.subscription.deleted`
   - Copy the **Signing Secret** (`whsec_...`)
6. **Add to Render**:
   ```
   STRIPE_SECRET_KEY=sk_live_xxxxxxxxxxxxx
   STRIPE_WEBHOOK_SECRET=whsec_xxxxxxxxxxxxx
   STRIPE_PRICE_ID=price_xxxxxxxxxxxxx
   ```

---

## Step 4: Set Frontend Environment Variable

Go to **Vercel Dashboard** → Your Project → Settings → Environment Variables

Add:
```
NEXT_PUBLIC_API_BASE=https://your-backend.onrender.com
```

Redeploy frontend after adding.

---

## Step 5: Test Everything

1. **Check Backend**: Visit `https://your-backend.onrender.com/health`
   - Should show: `{"ok": true, ...}`

2. **Test Registration**:
   - Go to your Vercel site
   - Register a new account
   - Check email for verification code
   - Verify and login

3. **Test Stripe**:
   - Go to Subscription/Pricing page
   - Click Subscribe
   - Use test card: `4242 4242 4242 4242`
   - Complete checkout
   - Check subscription status updates

---

## ✅ Done!

Your platform is now live! Users can register, verify email, and subscribe.

---

## Quick Troubleshooting

**Backend won't start?**
- Check all environment variables are set
- Check Render logs for errors

**Emails not sending?**
- Verify email service credentials
- Check spam folder

**Stripe not working?**
- Verify all 3 Stripe variables are set
- Check webhook URL is correct
- Check Stripe dashboard for webhook events

---

**Need help?** Check the full guides in this folder or contact your developer.

