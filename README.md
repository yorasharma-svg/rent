# Property Rent & Utility Management Web App (v9 - Cloud Database Enabled)

## 🌟 What's New in Version 9:
1. **Supabase / Postgres Cloud Database Support**: Connects seamlessly to Supabase or any Postgres DB via Streamlit Secrets (`DATABASE_URL`).
2. **Zero-Reset Lifetime Persistence**: Server resets/sleeps will NEVER wipe your data when connected to Supabase!
3. **Local SQLite Fallback**: If no cloud DB credentials are provided, it automatically runs locally on SQLite (`rent_ledger.db`).
4. **1-Click Backup & Restore (JSON)**: Export your complete database backup anytime and restore it in 1 click!

---

## 🚀 How to Setup Free Supabase Database (100% Free Forever):

1. **Create Free Supabase Database**:
   - Go to [supabase.com](https://supabase.com) and sign up / log in.
   - Click **"New project"**, enter project name (e.g., `rent-ledger`) and set a Database Password.
   - Once project is created, go to **Project Settings** -> **Database** -> **Connection string** -> **URI**.
   - Copy the URI string (e.g., `postgresql://postgres.[ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres`).
   - Replace `[password]` with your actual Supabase DB password.

2. **Add Connection to Streamlit Cloud Secrets**:
   - Go to your app dashboard on [share.streamlit.io](https://share.streamlit.io).
   - Click **"Manage app"** (lower right) -> **3 dots menu** -> **Settings** -> **Secrets**.
   - Paste your connection URI under `DATABASE_URL`:
     ```toml
     DATABASE_URL = "postgresql://postgres.xxx:yourpassword@aws-0-xxx.pooler.supabase.com:6543/postgres"
     ```
   - Click **Save**.

🎉 That's it! Your app will automatically connect to Supabase, create all tables, and save all your data permanently in the cloud!
