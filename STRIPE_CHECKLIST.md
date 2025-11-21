# Stripe Setup Checklist

## ✅ What You Have

- ✅ Monthly Price ID: `price_1SVjnJCXpe4LOyWiqGqgmmvF` ($199/month)
- ✅ Annual Price ID: `price_1SW0x1CXpe4LOyWiakgCXxx8` (yearly)

## 📋 What You Need to Complete

### 1. Environment Variables (Add to Render Dashboard)

Go to **Render Dashboard → Your Backend → Environment Variables** and add:

```env
STRIPE_PRICE_ID=price_1SVjnJCXpe4LOyWiqGqgmmvF
STRIPE_PRICE_ID_ANNUAL=price_1SW0x1CXpe4LOyWiakgCXxx8
```

**Also verify these are set:**
- `STRIPE_SECRET_KEY` - Your Stripe API secret key (starts with `sk_live_...` or `sk_test_...`)
- `STRIPE_WEBHOOK_SECRET` - Your webhook signing secret (starts with `whsec_...`)

### 2. Verify Webhook Setup

1. Go to **Stripe Dashboard → Developers → Webhooks**
2. Check if you have a webhook endpoint for: `https://your-backend.onrender.com/subscription/webhook`
   - Replace `your-backend.onrender.com` with your actual backend URL
3. If webhook doesn't exist, create it:
   - Click **"Add endpoint"**
   - URL: `https://your-backend.onrender.com/subscription/webhook`
   - Events to send:
     - `checkout.session.completed`
     - `customer.subscription.updated`
     - `customer.subscription.deleted`
   - Copy the **Signing Secret** → Add as `STRIPE_WEBHOOK_SECRET`

### 3. Verify API Keys

1. Go to **Stripe Dashboard → Developers → API Keys**
2. Copy your **Secret Key** (starts with `sk_live_...` for production or `sk_test_...` for testing)
3. Verify it's set as `STRIPE_SECRET_KEY` in Render

### 4. Restart Backend

After adding/updating environment variables:
1. Go to **Render Dashboard → Your Backend**
2. Click **"Manual Deploy"** → **"Deploy latest commit"**
   - OR click **"Restart"** if variables were already set

### 5. Test Subscriptions

#### Test Monthly Plan:
1. Go to your frontend: `/admin-register`
2. Select **"Monthly"** plan ($199/month)
3. Complete checkout
4. Check **Stripe Dashboard → Payments** → Should see $199 charge
5. Check **Stripe Dashboard → Subscriptions** → Should show monthly recurring

#### Test Annual Plan:
1. Go to your frontend: `/admin-register`
2. Select **"Annual"** plan ($166/month)
3. Complete checkout
4. Check **Stripe Dashboard → Payments** → Should see $1992 charge
5. Check **Stripe Dashboard → Subscriptions** → Should show yearly recurring

### 6. Verify Backend Logs

After a test subscription:
1. Go to **Render Dashboard → Your Backend → Logs**
2. Look for:
   - `[WEBHOOK SUCCESS] User ... upgraded to admin`
   - No error messages about Stripe

---

## 🔍 Quick Verification

Run this to check if all variables are set (in Render logs or locally):

```bash
# Check if variables are loaded (will show in backend startup logs)
# Look for: [OK] Stripe configured
```

---

## ❌ Common Issues

### "Stripe price ID not configured"
- **Fix**: Add `STRIPE_PRICE_ID` and `STRIPE_PRICE_ID_ANNUAL` to environment variables
- **Restart**: Backend after adding

### "Stripe not configured"
- **Fix**: Add `STRIPE_SECRET_KEY` to environment variables
- **Restart**: Backend after adding

### "Invalid webhook signature"
- **Fix**: Verify `STRIPE_WEBHOOK_SECRET` matches the webhook endpoint
- **Check**: Webhook URL in Stripe matches your backend URL

### Wrong amount charged
- **Fix**: Verify price IDs match the correct prices in Stripe
- **Check**: Annual price should be $1992.00 (not $166.00)

---

## 📝 Summary

**Required Environment Variables:**
1. ✅ `STRIPE_PRICE_ID=price_1SVjnJCXpe4LOyWiqGqgmmvF` (Monthly)
2. ✅ `STRIPE_PRICE_ID_ANNUAL=price_1SW0x1CXpe4LOyWiakgCXxx8` (Annual)
3. ⚠️ `STRIPE_SECRET_KEY` (Your API secret key)
4. ⚠️ `STRIPE_WEBHOOK_SECRET` (Your webhook signing secret)

**After adding variables:**
- Restart backend
- Test both subscription plans
- Verify webhook is receiving events

