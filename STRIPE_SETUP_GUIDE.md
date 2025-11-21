# Stripe Subscription Setup Guide

This guide will help you set up both subscription plans in Stripe:
- **Monthly Plan**: $199/month (billed monthly)
- **Annual Plan**: $166/month (billed annually = $1992/year)

---

## Step 1: Access Stripe Dashboard

1. Go to https://dashboard.stripe.com
2. **Switch to Live Mode** (toggle in top right) for production, or **Test Mode** for testing

---

## Step 2: Create Monthly Subscription Price ($199/month)

### Option A: If you already have a $199/month price

1. Go to **Products** → Find your existing product
2. Click on the product
3. Find the price that shows **$199.00 / month**
4. **Copy the Price ID** (starts with `price_...`)
   - This is your `STRIPE_PRICE_ID`

### Option B: Create a new monthly price

1. Go to **Products** → Click **"Add Product"** (or edit existing product)
2. **Product Name**: "Star4ce Pro Subscription"
3. **Description**: "Monthly subscription for Star4ce platform"
4. **Pricing**:
   - **Price**: `199.00`
   - **Currency**: USD
   - **Billing period**: Monthly
   - **Recurring**: Yes
5. Click **"Save"**
6. **Copy the Price ID** (starts with `price_...`)
   - This is your `STRIPE_PRICE_ID`

---

## Step 3: Create Annual Subscription Price ($166/month = $1992/year)

1. Go to **Products** → Click on your product (or create new one)
2. Scroll down to **"Pricing"** section
3. Click **"Add another price"**
4. Configure the annual price:
   - **Price**: `1992.00` (this is the total for the year)
   - **Currency**: USD
   - **Billing period**: Yearly (or "Every year")
   - **Recurring**: Yes
5. Click **"Save"**
6. **Copy the Price ID** (starts with `price_...`)
   - This is your `STRIPE_PRICE_ID_ANNUAL`

**Important Notes:**
- The annual price should be **$1992.00** (which equals $166/month × 12 months)
- Set billing period to **"Yearly"** or **"Every year"**
- Stripe will automatically charge the full amount once per year

---

## Step 4: Set Up Webhook (if not already done)

1. Go to **Developers** → **Webhooks**
2. Click **"Add endpoint"**
3. **Endpoint URL**: `https://your-backend.onrender.com/subscription/webhook`
   - Replace `your-backend.onrender.com` with your actual backend URL
4. **Description**: "Star4ce Subscription Webhooks"
5. **Events to send**: Select these events:
   - `checkout.session.completed`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
6. Click **"Add endpoint"**
7. **Copy the Signing Secret** (starts with `whsec_...`)
   - This is your `STRIPE_WEBHOOK_SECRET`

---

## Step 5: Get Your API Keys

1. Go to **Developers** → **API Keys**
2. **Copy the Secret Key** (starts with `sk_live_...` for production or `sk_test_...` for testing)
   - This is your `STRIPE_SECRET_KEY`

---

## Step 6: Add Environment Variables

Add these to your backend environment variables (Render Dashboard):

```env
# Monthly subscription ($199/month)
STRIPE_PRICE_ID=price_xxxxxxxxxxxxx

# Annual subscription ($166/month = $1992/year)
STRIPE_PRICE_ID_ANNUAL=price_yyyyyyyyyyyyy

# Stripe API Key
STRIPE_SECRET_KEY=sk_live_xxxxxxxxxxxxx

# Webhook Secret
STRIPE_WEBHOOK_SECRET=whsec_xxxxxxxxxxxxx
```

**For Local Development (.env file):**

```env
STRIPE_PRICE_ID=price_test_xxxxxxxxxxxxx
STRIPE_PRICE_ID_ANNUAL=price_test_yyyyyyyyyyyyy
STRIPE_SECRET_KEY=sk_test_xxxxxxxxxxxxx
STRIPE_WEBHOOK_SECRET=whsec_xxxxxxxxxxxxx
```

---

## Step 7: Verify Setup

### Test Monthly Subscription

1. Go to your frontend admin registration page
2. Select "Monthly" plan ($199/month)
3. Complete checkout
4. Check Stripe Dashboard → **Payments** → Should see $199 charge
5. Check Stripe Dashboard → **Subscriptions** → Should show monthly recurring

### Test Annual Subscription

1. Go to your frontend admin registration page
2. Select "Annual" plan ($166/month)
3. Complete checkout
4. Check Stripe Dashboard → **Payments** → Should see $1992 charge
5. Check Stripe Dashboard → **Subscriptions** → Should show yearly recurring

---

## Pricing Summary

| Plan | Display Price | Actual Charge | Billing Frequency |
|------|--------------|---------------|-------------------|
| Monthly | $199/month | $199.00 | Every month |
| Annual | $166/month | $1992.00 | Once per year |

**Annual Savings**: $396/year (12 × $199 = $2388 vs $1992)

---

## Troubleshooting

### "Stripe price ID not configured" Error

**Solution**: 
- Verify `STRIPE_PRICE_ID` is set in environment variables
- For annual plan, also verify `STRIPE_PRICE_ID_ANNUAL` is set
- Restart backend after adding variables

### Wrong Amount Charged

**Solution**:
- Verify the price ID matches the correct price in Stripe
- Check that annual price is set to $1992.00 (not $166.00)
- Verify billing period is set correctly (Monthly vs Yearly)

### Webhook Not Working

**Solution**:
- Verify webhook URL is correct and accessible
- Check webhook signing secret matches `STRIPE_WEBHOOK_SECRET`
- Ensure webhook events are selected correctly
- Check backend logs for webhook errors

---

## Quick Reference

**Monthly Plan Setup:**
- Price: $199.00
- Billing: Monthly
- Environment Variable: `STRIPE_PRICE_ID`

**Annual Plan Setup:**
- Price: $1992.00 (total for year)
- Billing: Yearly
- Environment Variable: `STRIPE_PRICE_ID_ANNUAL`

**Both prices should be on the same product in Stripe.**

