# Ruh Al Quran Academy — Version 4.0

## What's included
- `index.html`: public website, WhatsApp and email links, and direct admission form.
- `admin.html`: private application dashboard with search, filtering and status updates.
- `server.py`: Python standard-library web server, SQLite application storage, password-protected admin sessions, optional SMTP notifications.
- `Dockerfile`: deployable container.

## Local setup
1. Install Python 3.10+.
2. Set environment variables `ADMIN_PASSWORD` (a long unique password) and `SESSION_SECRET` (at least 32 characters, preferably generated with `python -c "import secrets;print(secrets.token_hex(32))"`).
3. Set `COOKIE_SECURE=0` for local HTTP development only.
4. Run `python server.py` from this directory.
5. Visit `http://localhost:8000/` and `http://localhost:8000/admin`.

On Linux/macOS, example:
```
export ADMIN_PASSWORD='YOUR_LONG_UNIQUE_PASSWORD'
export SESSION_SECRET='YOUR_RANDOM_64_CHAR_HEX_STRING'
export COOKIE_SECURE=0
python server.py
```

## Publishing
Use a host that supports a **persistent disk** and Docker (for example, a paid Render web service with a persistent disk, or a VPS). Push this folder to a private Git repository, create a Docker web service, configure environment variables from `.env.example`, attach a persistent disk mounted at `/data`, and set `DATABASE_PATH=/data/admissions.sqlite3`. Set `COOKIE_SECURE=1` when HTTPS is active. Configure your host's domain and DNS per its instructions. **Do not use ephemeral hosting for SQLite**: applications will be lost on redeploy or restart. For scaling across multiple instances, migrate to a managed relational database.

## Important limitations
- Direct form submission saves data to the server. WhatsApp and Email links still require the visitor to press Send in their own app.
- Email notification is optional and only runs after SMTP credentials are configured. Do not put SMTP passwords in HTML or Git.
- Admin access uses a single shared password; use a strong secret, limit staff access, and consider MFA/individual accounts before handling significant volumes of student data.
- Protect and back up the SQLite database. Configure retention and a privacy policy, especially for minors; collect parent/guardian details and consent as needed.
- Server-side per-IP rate limiting is basic and in-memory. Production deployment should add edge rate limiting, bot protection, access logging controls, and periodic security review.
- This package does not purchase a domain, create a hosting account, or publish the site automatically.
