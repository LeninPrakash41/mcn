# MCN Community Telemetry & Feedback Backend (PHP + MySQL)

This directory contains the production-ready PHP/MySQL backend for ingesting developer registrations, feedback, and automated error diagnostics from the MCN Web Playground and Desktop App.

## 🚀 Quick Deployment Guide

### 1. Database Setup
Import `schema.sql` into your MySQL / MariaDB database:
```bash
mysql -u root -p < schema.sql
```

### 2. Environment Configuration
Place the PHP files (`db.php`, `register.php`, `feedback.php`) on your PHP web host (e.g. `https://api.macincode.dev/telemetry/` or `https://your-domain.com/mcn-api/`).

Set your database credentials via Apache / Nginx / `.htaccess` or environment variables:
```apache
# In Apache VirtualHost or .htaccess
SetEnv DB_HOST 127.0.0.1
SetEnv DB_PORT 3306
SetEnv DB_NAME mcn_telemetry
SetEnv DB_USER mcn_user
SetEnv DB_PASS YourStrongPassword123
```

### 3. Connect to MCN Playground & Desktop
In your MCN `.env` file or environment:
```bash
export MCN_TELEMETRY_ENDPOINT="https://your-domain.com/mcn-api/register.php"
export MCN_FEEDBACK_ENDPOINT="https://your-domain.com/mcn-api/feedback.php"
```

## 📊 Database Tables Overview
* **`mcn_registrations`**: Stores developer identity (email, name, organization, platform: `web` vs `desktop_mac` vs `desktop_win`, app version, registration date, last active timestamp).
* **`mcn_feedback_logs`**: Stores submitted feedback, bug reports, and attached runtime error logs linked to the developer registration.
