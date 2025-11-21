# Troubleshooting Guide

Common issues and solutions for Star4ce platform.

---

## Table of Contents

1. [Backend Issues](#backend-issues)
2. [Frontend Issues](#frontend-issues)
3. [Database Issues](#database-issues)
4. [Email Issues](#email-issues)
5. [Stripe/Payment Issues](#stripepayment-issues)
6. [Authentication Issues](#authentication-issues)
7. [Deployment Issues](#deployment-issues)

---

## Backend Issues

### Backend Won't Start

**Symptoms**:
- Render shows "Deployment failed"
- Logs show errors on startup
- Health endpoint returns error

**Solutions**:

1. **Check Environment Variables**:
   - Go to Render Dashboard → Your Service → Environment
   - Verify all required variables are set (see `ENVIRONMENT_VARIABLES.md`)
   - Check for typos in variable names

2. **Check Logs**:
   - Render Dashboard → Your Service → Logs
   - Look for error messages
   - Common errors:
     - `ModuleNotFoundError`: Missing dependency
     - `Database connection failed`: Wrong `DATABASE_URL`
     - `Invalid JWT_SECRET`: Missing or invalid secret

3. **Check Requirements**:
   - Verify `requirements.txt` is correct
   - Check Python version matches `runtime.txt`

4. **Restart Service**:
   - Render Dashboard → Your Service → Manual Deploy → Clear build cache & deploy

**Still Not Working?**
- Contact developer with error logs

---

### Backend Returns 500 Errors

**Symptoms**:
- API calls return `{"error": "Internal server error"}`
- Features not working

**Solutions**:

1. **Check Logs**:
   - Render Dashboard → Logs
   - Look for Python tracebacks
   - Common causes:
     - Database connection issues
     - Missing environment variables
     - Code errors

2. **Check Database**:
   - Verify database is running (Render Dashboard)
   - Check `DATABASE_URL` is correct
   - Verify database tables exist

3. **Check Environment Variables**:
   - Ensure all required variables are set
   - Verify values are correct (no extra spaces)

4. **Restart Service**:
   - Sometimes a restart fixes temporary issues

**Still Not Working?**
- Share error logs with developer

---

### Backend is Slow

**Symptoms**:
- API calls take a long time
- Timeouts occur

**Solutions**:

1. **Check Render Plan**:
   - Free tier has limitations
   - Consider upgrading to paid plan
   - Free tier services "spin down" after inactivity

2. **Check Database**:
   - Database might be slow
   - Check database plan (free tier is slower)
   - Consider upgrading database

3. **Check Logs**:
   - Look for slow queries
   - Check for errors causing retries

4. **Optimize**:
   - Contact developer to optimize queries
   - Add database indexes if needed

---

## Frontend Issues

### Frontend Won't Load

**Symptoms**:
- Blank page
- "This site can't be reached" error
- 404 error

**Solutions**:

1. **Check Vercel Deployment**:
   - Vercel Dashboard → Your Project → Deployments
   - Verify latest deployment succeeded
   - Check for build errors

2. **Check Environment Variables**:
   - Vercel Dashboard → Your Project → Settings → Environment Variables
   - Verify `NEXT_PUBLIC_API_BASE` is set correctly
   - Should point to your Render backend URL

3. **Check Build Logs**:
   - Vercel Dashboard → Your Project → Deployments → Click deployment → Build Logs
   - Look for errors during build

4. **Clear Browser Cache**:
   - Hard refresh: `Ctrl+Shift+R` (Windows) or `Cmd+Shift+R` (Mac)
   - Or clear browser cache completely

5. **Try Different Browser**:
   - Sometimes browser-specific issues
   - Try Chrome, Firefox, Safari

**Still Not Working?**
- Check Vercel status: https://www.vercel-status.com
- Contact developer

---

### Frontend Shows API Errors

**Symptoms**:
- "Failed to fetch" errors
- "Network error" messages
- Features not loading

**Solutions**:

1. **Check Backend is Running**:
   - Visit: `https://your-backend.onrender.com/health`
   - Should return: `{"ok": true}`
   - If not, backend is down (see Backend Issues)

2. **Check CORS**:
   - Verify `FRONTEND_URL` in backend matches actual frontend URL
   - Check browser console for CORS errors
   - Common: `Access-Control-Allow-Origin` errors

3. **Check API URL**:
   - Verify `NEXT_PUBLIC_API_BASE` in Vercel matches backend URL
   - Should be: `https://your-backend.onrender.com`
   - No trailing slash

4. **Check Network**:
   - Try different network (mobile hotspot)
   - Check firewall isn't blocking

**Still Not Working?**
- Check browser console (F12) for specific errors
- Share error messages with developer

---

## Database Issues

### Can't Connect to Database

**Symptoms**:
- Backend logs show "database connection failed"
- 500 errors on all requests

**Solutions**:

1. **Check Database is Running**:
   - Render Dashboard → Your Database
   - Verify status is "Available"
   - If paused, click "Resume"

2. **Check DATABASE_URL**:
   - Render Dashboard → Your Service → Environment
   - Verify `DATABASE_URL` is correct
   - Should start with `postgresql://`
   - Use "Internal Database URL" from Render

3. **Check Database Credentials**:
   - Verify database user and password are correct
   - Reset password if needed (Render Dashboard)

4. **Check Database Plan**:
   - Free tier databases pause after inactivity
   - Resume database if paused
   - Consider upgrading to paid plan

**Still Not Working?**
- Contact Render support
- Or contact developer

---

### Database Tables Missing

**Symptoms**:
- Features don't work
- Errors about missing tables

**Solutions**:

1. **Check Backend Started Successfully**:
   - Backend creates tables on first start
   - Check logs for: `"Ensured all DB tables exist"`
   - If not, restart backend

2. **Manually Create Tables**:
   - Contact developer to run migration script
   - Or restart backend (tables auto-create)

3. **Check Database Permissions**:
   - Verify database user has CREATE TABLE permissions
   - Usually automatic on Render

**Still Not Working?**
- Contact developer

---

### Data is Missing or Wrong

**Symptoms**:
- Data disappeared
- Wrong data showing

**Solutions**:

1. **Check if Database was Reset**:
   - Render Dashboard → Database → Check recent activity
   - Verify no accidental resets

2. **Check Backups**:
   - Render Dashboard → Database → Backups
   - Restore from backup if needed
   - See `BACKUP_README.md` for restore instructions

3. **Check for Multiple Databases**:
   - Verify you're looking at correct database
   - Staging vs production

4. **Check Application Logic**:
   - Might be application bug
   - Check logs for errors
   - Contact developer

**⚠️ IMPORTANT**: If data is lost, restore from backup immediately!

---

## Email Issues

### Emails Not Sending

**Symptoms**:
- Verification emails not received
- Password reset emails not received
- No email delivery

**Solutions**:

1. **Check Spam Folder**:
   - Look in "Spam" or "Junk" folder
   - Mark as "Not Spam" if found

2. **Check Email Service**:
   - **Resend**: Check dashboard for delivery status
   - **SMTP**: Test SMTP connection
   - Verify API key/credentials are correct

3. **Check Environment Variables**:
   - Verify email service credentials are set
   - For Resend: `RESEND_API_KEY` and `EMAIL_FROM`
   - For SMTP: All `SMTP_*` variables

4. **Check Email Limits**:
   - Resend free tier: 3,000 emails/month
   - Gmail: 500 emails/day
   - Verify you haven't exceeded limits

5. **Check Logs**:
   - Render Dashboard → Logs
   - Look for email sending errors
   - Common: "Invalid API key", "Rate limit exceeded"

6. **Test Email Service**:
   - Resend: Check dashboard for test sends
   - SMTP: Test with email client

**Still Not Working?**
- Verify email domain is verified (for Resend)
- Check email service status page
- Contact developer

---

### Emails Going to Spam

**Symptoms**:
- Emails received but in spam folder

**Solutions**:

1. **Mark as Not Spam**:
   - Move emails to inbox
   - Mark sender as "Not Spam"

2. **Improve Email Setup**:
   - Use verified domain (not default Resend domain)
   - Set up SPF/DKIM records (for custom domain)
   - Use professional "From" address

3. **Contact Developer**:
   - May need to configure email authentication
   - Requires domain DNS changes

---

## Stripe/Payment Issues

### Subscription Not Activating

**Symptoms**:
- Payment went through
- Subscription status still shows "trial" or "expired"

**Solutions**:

1. **Wait 5-10 Minutes**:
   - Webhooks can take a few minutes
   - Refresh page and check again

2. **Check Stripe Dashboard**:
   - Go to Stripe Dashboard → Customers
   - Find customer and check subscription status
   - Verify payment succeeded

3. **Check Webhook Logs**:
   - Stripe Dashboard → Developers → Webhooks
   - Click your webhook endpoint
   - Check for failed deliveries
   - Look for error messages

4. **Check Backend Logs**:
   - Render Dashboard → Logs
   - Look for webhook processing errors
   - Common: "Invalid signature", "Webhook secret mismatch"

5. **Verify Webhook Configuration**:
   - Check `STRIPE_WEBHOOK_SECRET` matches Stripe
   - Verify webhook URL is correct
   - Check webhook events are selected

6. **Manually Trigger Webhook**:
   - Stripe Dashboard → Webhooks → Your endpoint
   - Click "Send test webhook"
   - Select `checkout.session.completed`
   - Check if backend receives it

**Still Not Working?**
- Contact developer with:
  - Payment date and amount
  - Stripe customer ID
  - Webhook log errors

---

### Checkout Session Not Creating

**Symptoms**:
- "Subscribe" button doesn't work
- Error: "Failed to create checkout session"

**Solutions**:

1. **Check Stripe Configuration**:
   - Verify `STRIPE_SECRET_KEY` is set
   - Verify `STRIPE_PRICE_ID` exists in Stripe
   - Check you're using correct mode (test vs live)

2. **Check Backend Logs**:
   - Render Dashboard → Logs
   - Look for Stripe API errors
   - Common: "Invalid API key", "Price not found"

3. **Verify Price ID**:
   - Stripe Dashboard → Products
   - Find your product and price
   - Copy Price ID
   - Verify matches `STRIPE_PRICE_ID` in Render

4. **Check API Key Mode**:
   - Test keys (`sk_test_...`) only work with test prices
   - Live keys (`sk_live_...`) only work with live prices
   - Must match!

**Still Not Working?**
- Contact developer

---

### Webhook Not Receiving Events

**Symptoms**:
- Stripe shows webhook deliveries failed
- Subscription status not updating

**Solutions**:

1. **Check Webhook URL**:
   - Stripe Dashboard → Webhooks → Your endpoint
   - Verify URL is correct: `https://your-backend.onrender.com/subscription/webhook`
   - Must be publicly accessible

2. **Check Webhook Secret**:
   - Verify `STRIPE_WEBHOOK_SECRET` in Render matches Stripe
   - Get from: Stripe Dashboard → Webhooks → Your endpoint → Signing secret

3. **Check Backend is Running**:
   - Verify backend is online
   - Check health endpoint works

4. **Check CORS** (if applicable):
   - Webhooks shouldn't have CORS issues
   - But verify backend accepts POST requests

5. **Test Webhook**:
   - Stripe Dashboard → Webhooks → Send test webhook
   - Check backend logs for receipt

**Still Not Working?**
- Contact developer
- May need to check backend webhook handler code

---

## Authentication Issues

### Can't Log In

**Symptoms**:
- "Invalid email or password" error
- Login fails

**Solutions**:

1. **Check Email and Password**:
   - Verify email is correct
   - Check for typos
   - Try copying/pasting password

2. **Reset Password**:
   - Click "Forgot Password?"
   - Check email for reset code
   - Enter code and new password

3. **Check Account Exists**:
   - Verify user was created
   - Check email verification status
   - Unverified accounts can't log in

4. **Check Backend**:
   - Verify backend is running
   - Check health endpoint

**Still Not Working?**
- Contact developer
- May need to reset account manually

---

### Token Expired Errors

**Symptoms**:
- "Token expired" error
- Logged out unexpectedly

**Solutions**:

1. **Log In Again**:
   - Simply log in again
   - Tokens expire after 24 hours for security

2. **Check System Time**:
   - Verify computer clock is correct
   - Wrong time can cause token issues

3. **Clear Browser Data**:
   - Clear cookies and cache
   - Log in again

**Still Not Working?**
- Contact developer
- May need to adjust token expiration

---

## Deployment Issues

### Deployment Fails on Render

**Symptoms**:
- Render shows "Deployment failed"
- Build errors

**Solutions**:

1. **Check Build Logs**:
   - Render Dashboard → Your Service → Logs
   - Look for specific error messages
   - Common: Missing dependencies, syntax errors

2. **Check Requirements**:
   - Verify `requirements.txt` is correct
   - Check all dependencies are listed
   - Verify Python version in `runtime.txt`

3. **Check Code**:
   - Verify code was pushed to Git
   - Check for syntax errors
   - Test locally first

4. **Clear Build Cache**:
   - Render Dashboard → Manual Deploy
   - Check "Clear build cache"
   - Deploy again

**Still Not Working?**
- Share build logs with developer

---

### Deployment Fails on Vercel

**Symptoms**:
- Vercel shows "Build Failed"
- Deployment errors

**Solutions**:

1. **Check Build Logs**:
   - Vercel Dashboard → Your Project → Deployments
   - Click failed deployment → Build Logs
   - Look for specific errors

2. **Check Environment Variables**:
   - Verify `NEXT_PUBLIC_API_BASE` is set
   - Check for typos

3. **Check Code**:
   - Verify code was pushed to Git
   - Check for TypeScript/JavaScript errors
   - Test build locally: `npm run build`

4. **Check Dependencies**:
   - Verify `package.json` is correct
   - Check `node_modules` isn't committed
   - Try clearing cache and rebuilding

**Still Not Working?**
- Share build logs with developer

---

## Getting More Help

If you've tried the solutions above and still have issues:

1. **Gather Information**:
   - What you were trying to do
   - Exact error message
   - When it started
   - Screenshots if possible

2. **Check Logs**:
   - Render logs (for backend)
   - Vercel logs (for frontend)
   - Browser console (F12) for frontend errors

3. **Contact Developer**:
   - Share all information gathered
   - Include logs and screenshots
   - Be specific about the problem

4. **Check Service Status**:
   - Render: https://status.render.com
   - Vercel: https://www.vercel-status.com
   - Stripe: https://status.stripe.com

---

## Prevention Tips

To avoid issues:

1. ✅ **Regular Backups**: Set up automated backups
2. ✅ **Monitor Logs**: Check logs weekly for errors
3. ✅ **Test Changes**: Test in staging before production
4. ✅ **Keep Secrets Safe**: Never commit secrets to Git
5. ✅ **Update Dependencies**: Keep dependencies updated (with testing)
6. ✅ **Monitor Services**: Check service status pages
7. ✅ **Document Changes**: Keep notes of any changes made

---

**Last Updated**: 2025-01-20  
**Version**: 1.0

