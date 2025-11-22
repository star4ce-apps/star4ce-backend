# 🧪 Local Testing Checklist

**Test everything locally before production deployment.**

---

## ✅ Setup (Do Once)

- [ ] Backend running: `cd star4ce-backend && python app.py`
- [ ] Frontend running: `cd star4ce-frontend && npm run dev`
- [ ] Backend accessible at: http://localhost:5000/health
- [ ] Frontend accessible at: http://localhost:3000

---

## 1️⃣ Authentication & Registration

### Admin Registration (Most Important!)
- [ ] Go to http://localhost:3000/pricing
- [ ] Click "Get Started" on Monthly ($199/month) or Annual ($166/month)
- [ ] Fill out admin registration form
- [ ] Select billing plan (Monthly or Annual)
- [ ] Submit → Should redirect to Stripe checkout
- [ ] Complete Stripe checkout (use test card: 4242 4242 4242 4242)
- [ ] After payment → Should redirect back to app
- [ ] Check email for verification code
- [ ] Verify email → Should be able to login
- [ ] Login → Should see dashboard as Admin

### Manager Registration
- [ ] Go to http://localhost:3000/register
- [ ] Click "Manager"
- [ ] Fill out registration form
- [ ] Select dealership from dropdown
- [ ] Submit → Should show "pending approval" message
- [ ] Check email for verification code
- [ ] Verify email
- [ ] Login → Should see "pending approval" message (can't access dashboard yet)
- [ ] **As Admin**: Go to Admin → Manager Requests → Approve manager
- [ ] **As Manager**: Login again → Should now see dashboard

### Corporate Registration
- [ ] Go to http://localhost:3000/register
- [ ] Click "Corporate"
- [ ] Fill out registration form
- [ ] Submit → Should show success message
- [ ] Check email for verification code
- [ ] Verify email
- [ ] Login → Should see dashboard (but no dealerships assigned yet)
- [ ] **As Admin**: Go to Admin → Corporate Requests → Assign dealership
- [ ] **As Corporate**: Refresh → Should see assigned dealership

### Login
- [ ] Go to http://localhost:3000/login
- [ ] Enter valid credentials
- [ ] Submit → Should redirect to dashboard
- [ ] Invalid credentials → Should show error message

### Password Reset
- [ ] Go to http://localhost:3000/forgot
- [ ] Enter email
- [ ] Submit → Should send reset code to email
- [ ] Enter code and new password
- [ ] Submit → Should be able to login with new password

---

## 2️⃣ Admin Features

### Dashboard
- [ ] View dashboard → Should show analytics, recent activity
- [ ] All sections load without errors

### Subscription Management
- [ ] Go to /subscription
- [ ] Should show current subscription status
- [ ] If subscribed → Should show plan details
- [ ] If not subscribed → Should show "Subscribe" button
- [ ] Cancel subscription → Should work (if subscribed)

### Employee Management
- [ ] Go to /employees
- [ ] Click "Add Employee"
- [ ] Fill form and submit → Employee should appear in list
- [ ] Click employee → View details
- [ ] Edit employee → Changes should save
- [ ] Delete employee → Should be removed from list
- [ ] Export CSV → Should download file

### Survey Management
- [ ] Go to /surveys
- [ ] Create access code → Should generate code
- [ ] View access codes → Should list all codes
- [ ] Use access code at /survey?code=XXX → Should show survey form
- [ ] Submit survey → Should save response
- [ ] View survey responses → Should show submitted data

### Analytics
- [ ] Go to /analytics
- [ ] Should display charts and statistics
- [ ] All metrics load correctly
- [ ] Export data → Should download CSV

### User Management
- [ ] Go to /users (Admin only)
- [ ] Should list all users
- [ ] Delete user → Should remove from database
- [ ] View user details

### Dealership Management
- [ ] Go to Admin → Dealership Requests
- [ ] View pending requests
- [ ] Approve/Reject requests → Should update status

---

## 3️⃣ Manager Features

### Dashboard
- [ ] Login as Manager (after approval)
- [ ] View dashboard → Should show manager-specific data
- [ ] All sections load correctly

### Employee Management
- [ ] View employees → Should show employees for their dealership
- [ ] Add employee → Should work
- [ ] Edit/Delete → Should work

### Survey Management
- [ ] Create access codes → Should work
- [ ] View survey responses → Should work

### Analytics
- [ ] View analytics → Should show dealership-specific data

---

## 4️⃣ Corporate Features

### Dashboard
- [ ] Login as Corporate
- [ ] View dashboard → Should show corporate view

### Dealership Selection
- [ ] Go to /dealerships
- [ ] Should list available dealerships
- [ ] Request access → Should send request to admin
- [ ] After admin approval → Should see dealership in list

### View Dealership Stats
- [ ] Select assigned dealership
- [ ] View analytics → Should show that dealership's data
- [ ] Switch between dealerships → Should update data

---

## 5️⃣ Candidate Management

### View Candidates
- [ ] Go to /candidates
- [ ] Should list all candidates
- [ ] Search candidates → Should filter results
- [ ] Click candidate → View details

### Score Candidates
- [ ] Go to /candidates/score
- [ ] Fill out scorecard
- [ ] Submit → Should save score
- [ ] View candidate → Should show score

---

## 6️⃣ Common Issues to Check

### Navigation
- [ ] All links work
- [ ] Back button works
- [ ] No broken routes (404 errors)

### Forms
- [ ] All forms validate input
- [ ] Error messages display correctly
- [ ] Success messages display correctly
- [ ] Loading states work

### Permissions
- [ ] Manager can't access admin-only pages
- [ ] Corporate can't access manager-only pages
- [ ] Unauthorized access shows error

### Database
- [ ] Data persists after refresh
- [ ] No duplicate entries
- [ ] Deletions work correctly

### Email (If Configured)
- [ ] Verification emails send
- [ ] Password reset emails send
- [ ] Check spam folder if not receiving

---

## 7️⃣ Stripe Integration (Test Mode)

### Checkout Flow
- [ ] Click "Subscribe" → Opens Stripe checkout
- [ ] Use test card: `4242 4242 4242 4242`
- [ ] Expiry: Any future date (e.g., 12/25)
- [ ] CVC: Any 3 digits (e.g., 123)
- [ ] Complete payment → Redirects back to app
- [ ] Subscription status updates

### Subscription Status
- [ ] After payment → Shows "Active" status
- [ ] Plan details correct (Monthly vs Annual)
- [ ] Cancel subscription works

---

## 8️⃣ Quick Test Scripts

### Delete Test User
```bash
cd star4ce-backend
python delete_user.py list          # List all users
python delete_user.py user@email.com --yes  # Delete user
```

### Check Backend Health
```bash
curl http://localhost:5000/health
# Should return: {"ok": true, "service": "star4ce-backend"}
```

---

## ✅ Final Checks

- [ ] All registration flows work
- [ ] All user roles can access their features
- [ ] Stripe checkout works (test mode)
- [ ] Email verification works
- [ ] Password reset works
- [ ] No console errors in browser
- [ ] No backend errors in terminal
- [ ] Database operations work correctly

---

## 🐛 Found Issues?

1. **Check browser console** (F12) for frontend errors
2. **Check backend terminal** for server errors
3. **Check database** using `delete_user.py list`
4. **Restart servers** if needed

---

**Once all tests pass → Ready for production deployment!** 🚀

