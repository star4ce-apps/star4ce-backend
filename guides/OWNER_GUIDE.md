# Star4ce Owner's Guide

**Simple instructions for managing your Star4ce platform without technical knowledge.**

---

## 📋 Table of Contents

1. [What is Star4ce?](#what-is-star4ce)
2. [How to Access Your Platform](#how-to-access-your-platform)
3. [Daily Operations](#daily-operations)
4. [Managing Users](#managing-users)
5. [Viewing Analytics](#viewing-analytics)
6. [Managing Subscriptions](#managing-subscriptions)
7. [Common Tasks](#common-tasks)
8. [When Things Go Wrong](#when-things-go-wrong)
9. [Important Contacts](#important-contacts)

---

## What is Star4ce?

Star4ce is your HR platform for car dealerships. It helps you:
- ✅ Understand employee satisfaction
- ✅ Track retention and turnover
- ✅ Make data-driven hiring decisions
- ✅ Improve workplace culture

**Your platform consists of**:
- **Website/App** (Frontend): Where you and your team log in
- **Backend Server**: Handles all the data and logic
- **Database**: Stores all your information safely

---

## How to Access Your Platform

### Step 1: Open Your Website

1. Open your web browser (Chrome, Firefox, Safari, etc.)
2. Go to: **`https://your-app.vercel.app`** (or your custom domain)
3. You should see the Star4ce homepage

### Step 2: Log In

1. Click **"Login"** button (top right)
2. Enter your **email address**
3. Enter your **password**
4. Click **"Sign In"**

**Forgot Password?**
- Click **"Forgot Password?"** link
- Enter your email
- Check your email for reset code
- Enter code and new password

### Step 3: Access Dashboard

After logging in, you'll see your **Dashboard** with:
- Overview of your dealership
- Recent survey responses
- Analytics summary
- Subscription status

---

## Daily Operations

### What You Should Check Daily

**Morning (5 minutes)**:
1. ✅ Log in to your dashboard
2. ✅ Check for new survey responses
3. ✅ Review any alerts or notifications

**Weekly (15 minutes)**:
1. ✅ Review analytics dashboard
2. ✅ Check subscription status
3. ✅ Review employee list
4. ✅ Check access codes (if needed)

---

## Managing Users

### Adding New Employees

1. Go to **"Employees"** page (left sidebar)
2. Click **"Add Employee"** button
3. Fill in:
   - **Name**: Employee's full name
   - **Email**: Employee's email address
   - **Phone**: (Optional) Phone number
   - **Department**: Select from dropdown (Sales, Service, Parts, etc.)
   - **Position**: (Optional) Job title
4. Click **"Save"**

### Editing Employees

1. Go to **"Employees"** page
2. Find the employee in the list
3. Click **"Edit"** button
4. Make changes
5. Click **"Save"**

### Deactivating Employees

1. Go to **"Employees"** page
2. Find the employee
3. Click **"Deactivate"** button
4. Confirm deactivation

**Note**: Deactivated employees won't appear in active lists but data is preserved.

---

## Viewing Analytics

### Accessing Analytics

1. Click **"Analytics"** in left sidebar
2. You'll see:
   - **Summary**: Total responses, recent activity
   - **Time Series**: Responses over time (graph)
   - **Role Breakdown**: Responses by department
   - **Status Breakdown**: New hires, terminations, etc.

### Understanding the Data

**Summary Dashboard Shows**:
- **Total Responses**: How many surveys completed
- **Last 30 Days**: Recent activity
- **By Status**: New hires, terminations, etc.

**Time Series Graph**:
- Shows survey responses over time
- Helps identify trends
- Can filter by days (7, 30, 90, etc.)

**Role Breakdown**:
- See responses by department
- Identify which departments need attention
- Track satisfaction by role

---

## Managing Subscriptions

### Checking Subscription Status

1. Go to **"Settings"** page (or **"Subscription"** page)
2. You'll see:
   - **Status**: Active, Trial, Expired, etc.
   - **Plan**: Your current plan
   - **Expires**: When subscription ends
   - **Days Remaining**: If on trial

### Upgrading Subscription

1. Go to **"Subscription"** or **"Pricing"** page
2. Click **"Subscribe"** or **"Upgrade"** button
3. You'll be redirected to Stripe checkout
4. Enter payment information
5. Complete payment
6. Subscription activates automatically

### Canceling Subscription

1. Go to **"Settings"** → **"Subscription"**
2. Click **"Cancel Subscription"**
3. Confirm cancellation
4. You'll have access until period ends

**⚠️ Important**: After cancellation, you'll lose access when period ends. Data is preserved for 30 days.

---

## Common Tasks

### Creating Access Codes for Surveys

1. Go to **"Access Codes"** page
2. Click **"Create New Code"**
3. (Optional) Set expiration time (in hours)
4. Click **"Generate"**
5. **Copy the code** and share with employees
6. Employees use this code to access surveys

**Tip**: Create separate codes for different departments or time periods.

### Viewing Survey Responses

1. Go to **"Analytics"** page
2. Click on any chart or section to see details
3. Responses are anonymous (no personal info shown)

### Exporting Data

Currently, data export is available through the API. Contact your developer if you need data exports.

---

## When Things Go Wrong

### Problem: Can't Log In

**Try These Steps**:

1. **Check your email and password**:
   - Make sure Caps Lock is off
   - Check for typos
   - Try copying/pasting password

2. **Reset Password**:
   - Click "Forgot Password?"
   - Check email for reset code
   - Enter code and new password

3. **Check Internet Connection**:
   - Make sure you're connected to internet
   - Try refreshing the page

4. **Still Not Working?**
   - Contact your developer
   - Provide: Your email, what error you see, when it started

### Problem: Website Won't Load

**Try These Steps**:

1. **Refresh the page**: Press `F5` or `Ctrl+R` (Windows) / `Cmd+R` (Mac)

2. **Clear Browser Cache**:
   - Chrome: `Ctrl+Shift+Delete` → Clear browsing data
   - Firefox: `Ctrl+Shift+Delete` → Clear recent history
   - Safari: `Cmd+Option+E` → Empty caches

3. **Try Different Browser**:
   - If Chrome doesn't work, try Firefox or Safari

4. **Check Internet Connection**:
   - Try loading other websites
   - Restart your router if needed

5. **Still Not Working?**
   - The website might be down for maintenance
   - Contact your developer
   - Check if others can access it

### Problem: Emails Not Sending

**Symptoms**:
- Verification emails not received
- Password reset emails not received
- Invitation emails not received

**Try These Steps**:

1. **Check Spam Folder**:
   - Look in "Spam" or "Junk" folder
   - Mark as "Not Spam" if found

2. **Wait a Few Minutes**:
   - Sometimes emails are delayed
   - Check again in 5-10 minutes

3. **Verify Email Address**:
   - Make sure email is correct
   - Try a different email address

4. **Still Not Working?**
   - Contact your developer
   - Provide: Your email, what you're trying to do, when you tried

### Problem: Subscription Not Working

**Symptoms**:
- Can't access features
- Says "subscription expired" but you paid
- Payment went through but status didn't update

**Try These Steps**:

1. **Check Subscription Status**:
   - Go to Settings → Subscription
   - See what status shows

2. **Wait 5-10 Minutes**:
   - Sometimes updates take a few minutes
   - Refresh the page

3. **Check Payment**:
   - Log into Stripe (if you have access)
   - Or check your bank/credit card statement
   - Verify payment went through

4. **Still Not Working?**
   - Contact your developer immediately
   - Provide: Payment date, amount, subscription status shown

### Problem: Data Looks Wrong

**Symptoms**:
- Analytics show incorrect numbers
- Missing survey responses
- Wrong employee information

**Try These Steps**:

1. **Refresh the Page**:
   - Press `F5` or `Ctrl+R`
   - Data might need to reload

2. **Check Date Range**:
   - Make sure you're looking at correct time period
   - Try different date ranges

3. **Verify Data Entry**:
   - Check if employees were added correctly
   - Verify access codes were created

4. **Still Not Working?**
   - Contact your developer
   - Provide: What data looks wrong, when you noticed, screenshots if possible

---

## Important Contacts

### Your Developer

**Name**: [Your Developer's Name]  
**Email**: [Developer's Email]  
**Phone**: [Developer's Phone] (if provided)

**When to Contact**:
- Technical issues you can't solve
- Need new features
- Questions about how things work
- Emergency issues (site down, data loss)

**What to Include When Contacting**:
- What you were trying to do
- What error message you saw (if any)
- When it happened
- Screenshots (if possible)

### Support Services

**Render (Backend Hosting)**:
- Website: https://render.com
- Support: https://render.com/docs/support
- Status: https://status.render.com

**Vercel (Frontend Hosting)**:
- Website: https://vercel.com
- Support: https://vercel.com/support
- Status: https://www.vercel-status.com

**Stripe (Payments)**:
- Website: https://stripe.com
- Support: https://support.stripe.com
- Dashboard: https://dashboard.stripe.com

---

## Quick Reference

### Important URLs

- **Your Website**: `https://your-app.vercel.app`
- **Backend API**: `https://your-backend.onrender.com`
- **Stripe Dashboard**: https://dashboard.stripe.com
- **Render Dashboard**: https://dashboard.render.com
- **Vercel Dashboard**: https://vercel.com/dashboard

### Important Information to Keep Safe

**Write these down and keep in a safe place**:

1. **Your Login Email**: ________________
2. **Your Login Password**: ________________ (or password manager)
3. **Website URL**: ________________
4. **Developer Contact**: ________________
5. **Stripe Account Email**: ________________
6. **Database Backup Location**: ________________

---

## Tips for Success

### Best Practices

1. **Regular Logins**: Log in at least once a week to check status
2. **Review Analytics**: Check analytics monthly to track trends
3. **Keep Employees Updated**: Make sure employee list is current
4. **Monitor Subscriptions**: Check subscription status regularly
5. **Backup Awareness**: Know where your backups are stored

### Security Tips

1. **Strong Password**: Use a unique, strong password
2. **Don't Share Login**: Keep your login credentials private
3. **Log Out**: Always log out when done (especially on shared computers)
4. **Report Suspicious Activity**: Contact developer immediately if something seems wrong

### Getting Help

**Before Contacting Developer**:
1. ✅ Check this guide
2. ✅ Try the troubleshooting steps
3. ✅ Check if others can access the site
4. ✅ Take screenshots of any errors

**When Contacting Developer**:
1. ✅ Be specific about the problem
2. ✅ Include error messages
3. ✅ Say when it started
4. ✅ Include screenshots if possible

---

## Glossary

**Access Code**: A code employees use to access surveys

**Analytics**: Data and charts showing survey results and trends

**Backend**: The server that handles all data and logic

**Dashboard**: Your main page after logging in

**Database**: Where all your data is stored

**Deployment**: When code is published to make it live

**Frontend**: The website/app you see and interact with

**Subscription**: Your paid plan to use Star4ce

**Webhook**: Automatic notifications from Stripe about payments

---

## Updates and Changes

This guide will be updated as the platform evolves. Check with your developer for the latest version.

**Last Updated**: 2025-01-20  
**Version**: 1.0

---

**Remember**: You don't need to be technical to use Star4ce! If something doesn't make sense or you're stuck, contact your developer. That's what they're here for! 🚀

