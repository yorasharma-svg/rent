# Rent & Utility Ledger Web App (v10)

## Features
- **Supabase Cloud Database & Local SQLite Dual Engine** with automatic fallback mechanism so the app NEVER crashes if cloud DB connects fail!
- **Multi-Property / Multi-House Management**
- **Mobile Numbers & WhatsApp 1-Click Chat Integration**
- **Dynamic Month Rollover & Unlimited Storage**
- **Utility Liability & Collections Summary Cards**
- **Full Edit / Delete Tenant Management**
- **JSON Backup & Restore System**

## Deployment on Streamlit Cloud
1. Upload `app.py` and `requirements.txt` to your GitHub repo.
2. Deploy on [share.streamlit.io](https://share.streamlit.io).
3. (Optional) In Streamlit Cloud -> Manage App -> Settings -> Secrets, add:
   ```toml
   DATABASE_URL = "postgresql://postgres.xxx:yourpassword@aws-0-xxx.pooler.supabase.com:6543/postgres"
   ```
