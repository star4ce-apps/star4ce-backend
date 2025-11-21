# Changelog

All notable changes to the Star4ce backend project.

## [Unreleased]

### Added
- ✅ AdminAuditLog model for tracking admin actions
- ✅ `/audit-logs` endpoint for viewing audit logs
- ✅ Enhanced health check endpoint with system status
- ✅ Phone number validation
- ✅ Comprehensive documentation in `guides/` folder
- ✅ Improved error handling and validation
- ✅ **CSV export functionality** for employees, survey responses, and analytics
- ✅ **Environment variables template** (ENV_SETUP.txt)
- ✅ **Simplified deployment guides** (QUICK_SETUP.md, SIMPLE_DEPLOYMENT.md, SIMPLE_OWNER_GUIDE.md)

### Changed
- ✅ Email debug logging only shows in development mode
- ✅ Health endpoint now shows database, Stripe, and email status
- ✅ Better input validation for phone numbers
- ✅ All documentation organized into `guides/` folder
- ✅ **Improved error messages** - More user-friendly and descriptive
- ✅ **Access code URLs** - Now use dynamic origin instead of hardcoded localhost
- ✅ **Registration error handling** - Better validation feedback
- ✅ **Mobile responsiveness** - Card view for employees table on mobile devices
- ✅ **Form validation** - Frontend email validation for employee forms
- ✅ **Skeleton loaders** - Better loading states on dashboard

### Fixed
- ✅ AdminAuditLog model implementation (was TODO)
- ✅ log_admin_action now saves to database instead of just console
- ✅ Access code survey links now use correct domain

### Documentation
- ✅ Created simplified guides (QUICK_SETUP.md, SIMPLE_DEPLOYMENT.md, SIMPLE_OWNER_GUIDE.md)
- ✅ Created ENV_SETUP.txt for easy environment variable setup
- ✅ Removed long/complex guides, kept only simple ones
- ✅ Updated README.md with simplified documentation index

---

## [1.0.0] - 2025-01-20

### Initial Release
- User authentication (JWT)
- Email verification
- Password reset
- Employee management
- Survey access codes
- Survey responses
- Analytics dashboard
- Stripe subscription management
- Rate limiting
- CORS protection

