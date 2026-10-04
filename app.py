import streamlit as st
import sqlite3
import pandas as pd
import datetime
import json
import os
import urllib.parse

# Page Configuration for Mobile Responsiveness
st.set_page_config(
    page_title="Rent & Utility Ledger",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling for Clean Mobile & Desktop Look
st.markdown("""
    <style>
    .main-header { font-size: 24px; font-weight: bold; color: #1E3A8A !important; margin-bottom: 10px; }
    .card-box { 
        background-color: #F8FAFC !important; 
        color: #0F172A !important; 
        padding: 18px; 
        border-radius: 12px; 
        border-left: 6px solid #2563EB; 
        margin-bottom: 15px; 
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    .card-box h3, .card-box p, .card-box b, .card-box h2, .card-box i {
        color: #0F172A !important;
    }
    .metric-title { font-size: 14px; color: #64748B !important; font-weight: 600; }
    </style>
""", unsafe_allow_html=True)

# --- DATABASE ENGINE DETECTOR (SUPABASE / POSTGRES vs LOCAL SQLITE) ---
def get_db_uri():
    if "DATABASE_URL" in st.secrets:
        return st.secrets["DATABASE_URL"]
    elif "postgres" in st.secrets and "url" in st.secrets["postgres"]:
        return st.secrets["postgres"]["url"]
    elif "DATABASE_URL" in os.environ:
        return os.environ["DATABASE_URL"]
    return None

DB_URI = get_db_uri()
IS_POSTGRES = DB_URI is not None and DB_URI.startswith(("postgres://", "postgresql://"))

if IS_POSTGRES and DB_URI.startswith("postgres://"):
    # Fix legacy heroku/supabase postgres:// prefix for SQLAlchemy
    DB_URI = DB_URI.replace("postgres://", "postgresql://", 1)

def get_connection():
    if IS_POSTGRES:
        import psycopg2
        return psycopg2.connect(DB_URI)
    else:
        conn = sqlite3.connect("rent_ledger.db")
        conn.row_factory = sqlite3.Row
        return conn

def execute_query(query, params=(), fetchall=False, fetchone=False, commit=False):
    conn = get_connection()
    cursor = conn.cursor()
    
    # Handle %s placeholder for Postgres vs ? placeholder for SQLite
    if IS_POSTGRES:
        query = query.replace("?", "%s")
        
    cursor.execute(query, params)
    
    result = None
    if fetchall:
        result = cursor.fetchall()
    elif fetchone:
        result = cursor.fetchone()
        
    if commit:
        conn.commit()
        
    conn.close()
    return result

def query_to_df(query, params=()):
    conn = get_connection()
    if IS_POSTGRES:
        query = query.replace("?", "%s")
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

# Initialize Tables and Schema
def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    if IS_POSTGRES:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS months (
                id SERIAL PRIMARY KEY,
                month_year VARCHAR(100) UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS properties (
                id SERIAL PRIMARY KEY,
                house_name VARCHAR(150) UNIQUE NOT NULL
            );
            CREATE TABLE IF NOT EXISTS ledger (
                id SERIAL PRIMARY KEY,
                month_year VARCHAR(100) NOT NULL,
                house_name VARCHAR(150) DEFAULT 'Main House',
                tenant_name VARCHAR(150) NOT NULL,
                mobile_no VARCHAR(20) DEFAULT '',
                category VARCHAR(50) NOT NULL,
                base_rent REAL DEFAULT 0,
                previous_balance REAL DEFAULT 0,
                pr_reading REAL DEFAULT 0,
                cr_reading REAL,
                elec_rate REAL DEFAULT 8,
                water_charge REAL DEFAULT 0,
                remarks TEXT,
                UNIQUE(month_year, tenant_name)
            );
        """)
    else:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS months (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                month_year TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS properties (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                house_name TEXT UNIQUE NOT NULL
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                month_year TEXT NOT NULL,
                house_name TEXT DEFAULT 'Main House',
                tenant_name TEXT NOT NULL,
                mobile_no TEXT DEFAULT '',
                category TEXT NOT NULL,
                base_rent REAL DEFAULT 0,
                previous_balance REAL DEFAULT 0,
                pr_reading REAL DEFAULT 0,
                cr_reading REAL,
                elec_rate REAL DEFAULT 8,
                water_charge REAL DEFAULT 0,
                remarks TEXT,
                UNIQUE(month_year, tenant_name)
            );
        """)
        # Migrations for SQLite
        cursor.execute("PRAGMA table_info(ledger)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'house_name' not in columns:
            cursor.execute("ALTER TABLE ledger ADD COLUMN house_name TEXT DEFAULT 'Main House'")
        if 'mobile_no' not in columns:
            cursor.execute("ALTER TABLE ledger ADD COLUMN mobile_no TEXT DEFAULT ''")
        if 'previous_balance' not in columns:
            cursor.execute("ALTER TABLE ledger ADD COLUMN previous_balance REAL DEFAULT 0")

    conn.commit()
    
    # Seed default properties and initial data if empty
    cursor.execute("SELECT COUNT(*) FROM months")
    month_count = cursor.fetchone()[0]

    if month_count == 0:
        if IS_POSTGRES:
            cursor.execute("INSERT INTO properties (house_name) VALUES ('Main House'), ('Shop Building') ON CONFLICT DO NOTHING;")
            cursor.execute("INSERT INTO months (month_year) VALUES ('October 2026') ON CONFLICT DO NOTHING;")
        else:
            cursor.execute("INSERT OR IGNORE INTO properties (house_name) VALUES ('Main House'), ('Shop Building');")
            cursor.execute("INSERT OR IGNORE INTO months (month_year) VALUES ('October 2026');")

        initial_tenants = [
            ("Shop Building", "Gupta Ji", "", "Shop", 5000, 0, 3396, 3428, 9, 0, "Shop - Rate ₹9/unit; Water N/A"),
            ("Main House", "Ashwini", "", "Residential", 4000, 0, 6602, 6618, 8, 142, "Residential - Rate ₹8/unit; Water provisional ₹142"),
            ("Main House", "Anoop Sharma", "", "Residential", 4500, 0, 6363, None, 8, 0, "Residential - Rate ₹8/unit"),
            ("Main House", "Satish Pathak (Sarthak)", "", "Residential", 2700, 0, 1477, None, 8, 0, "Residential - Rate ₹8/unit"),
            ("Main House", "Umesh Pathak", "", "Residential", 3750, 0, 6315, None, 8, 0, "Residential - Rate ₹8/unit"),
            ("Shop Building", "Ramsingh Saini", "", "Shop", 5000, 0, 10379, None, 9, 0, "Shop - Rate ₹9/unit; Water N/A"),
            ("Main House", "Vinod Sharma", "", "Residential", 3750, 0, 6276, None, 8, 0, "Residential - Rate ₹8/unit"),
            ("Main House", "Submersible (Pump)", "", "Common Utility", 0, 0, 6774, None, 8, 0, "Common Utility - Rate ₹8/unit"),
            ("Main House", "Tiwari Ji", "", "Residential", 3000, 0, 4263, None, 8, 0, "Faulty Meter (मीटर खराब है)"),
            ("Main House", "Neeraj Kumar", "", "Residential", 3800, 0, 2447, None, 8, 0, "Residential - Rate ₹8/unit")
        ]
        
        for t in initial_tenants:
            if IS_POSTGRES:
                cursor.execute("""
                    INSERT INTO ledger (month_year, house_name, tenant_name, mobile_no, category, base_rent, previous_balance, pr_reading, cr_reading, elec_rate, water_charge, remarks)
                    VALUES ('October 2026', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, t)
            else:
                cursor.execute("""
                    INSERT OR IGNORE INTO ledger (month_year, house_name, tenant_name, mobile_no, category, base_rent, previous_balance, pr_reading, cr_reading, elec_rate, water_charge, remarks)
                    VALUES ('October 2026', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, t)

        conn.commit()
    conn.close()

init_db()

# --- SIDEBAR: NAVIGATION & CONTROLS ---
st.sidebar.title("🏢 Navigation & Controls")

if IS_POSTGRES:
    st.sidebar.success("⚡ Connected to Cloud Database (Supabase/Postgres)")
else:
    st.sidebar.info("💾 Running on Local Database (SQLite)")

months_df = query_to_df("SELECT month_year FROM months ORDER BY id DESC")
available_months = months_df['month_year'].tolist() if not months_df.empty else ["October 2026"]

selected_month = st.sidebar.selectbox("📅 Select Ledger Month", available_months)

# Property / House Filter
properties_df = query_to_df("SELECT house_name FROM properties ORDER BY house_name ASC")
available_properties = ["All Properties"] + (properties_df['house_name'].tolist() if not properties_df.empty else ["Main House", "Shop Building"])
selected_property = st.sidebar.selectbox("🏠 Filter Property / House", available_properties)

st.sidebar.markdown("---")
st.sidebar.subheader("➕ Create New Month Ledger")
new_month_input = st.sidebar.text_input("New Month Name (e.g. November 2026)")

if st.sidebar.button("🚀 Roll Over & Create Month"):
    if not new_month_input.strip():
        st.sidebar.error("Please enter a valid month name!")
    elif new_month_input.strip() in available_months:
        st.sidebar.warning("This month already exists!")
    else:
        conn = get_connection()
        cursor = conn.cursor()
        if IS_POSTGRES:
            cursor.execute("INSERT INTO months (month_year) VALUES (%s)", (new_month_input.strip(),))
        else:
            cursor.execute("INSERT INTO months (month_year) VALUES (?)", (new_month_input.strip(),))
            
        prev_data = query_to_df("SELECT * FROM ledger WHERE month_year = ?", params=(selected_month,))
        
        for _, row in prev_data.iterrows():
            new_pr = row['cr_reading'] if pd.notnull(row['cr_reading']) else row['pr_reading']
            h_name = row['house_name'] if 'house_name' in row and pd.notnull(row['house_name']) else 'Main House'
            m_no = row['mobile_no'] if 'mobile_no' in row and pd.notnull(row['mobile_no']) else ''
            
            if IS_POSTGRES:
                cursor.execute("""
                    INSERT INTO ledger (month_year, house_name, tenant_name, mobile_no, category, base_rent, previous_balance, pr_reading, cr_reading, elec_rate, water_charge, remarks)
                    VALUES (%s, %s, %s, %s, %s, %s, 0, %s, NULL, %s, %s, %s)
                """, (new_month_input.strip(), h_name, row['tenant_name'], m_no, row['category'], row['base_rent'], new_pr, row['elec_rate'], row['water_charge'], row['remarks']))
            else:
                cursor.execute("""
                    INSERT INTO ledger (month_year, house_name, tenant_name, mobile_no, category, base_rent, previous_balance, pr_reading, cr_reading, elec_rate, water_charge, remarks)
                    VALUES (?, ?, ?, ?, ?, ?, 0, ?, NULL, ?, ?, ?)
                """, (new_month_input.strip(), h_name, row['tenant_name'], m_no, row['category'], row['base_rent'], new_pr, row['elec_rate'], row['water_charge'], row['remarks']))
            
        conn.commit()
        conn.close()
        st.sidebar.success(f"Created {new_month_input}! Auto-rolled P.R. readings from {selected_month}.")
        st.rerun()

# --- MAIN APP BODY ---
st.title("🏢 Property Rent & Utility Management")
filter_text = f" | Property: **{selected_property}**" if selected_property != "All Properties" else " | **All Properties**"
st.caption(f"Currently Viewing: **{selected_month}**{filter_text}")

# Load Current Month Ledger
if selected_property == "All Properties":
    ledger_df = query_to_df("SELECT * FROM ledger WHERE month_year = ?", params=(selected_month,))
else:
    ledger_df = query_to_df("SELECT * FROM ledger WHERE month_year = ? AND house_name = ?", params=(selected_month, selected_property))

# Defensive check for missing columns
for col, default_val in [('house_name', 'Main House'), ('mobile_no', ''), ('previous_balance', 0.0), ('cr_reading', None)]:
    if col not in ledger_df.columns:
        ledger_df[col] = default_val

# Computations
ledger_df['cr_reading_calc'] = ledger_df['cr_reading'].fillna(ledger_df['pr_reading'])
ledger_df['units_consumed'] = ledger_df['cr_reading_calc'] - ledger_df['pr_reading']
ledger_df['units_consumed'] = ledger_df['units_consumed'].apply(lambda x: max(0, x))
ledger_df['elec_charge'] = ledger_df['units_consumed'] * ledger_df['elec_rate']
ledger_df['total_payable'] = ledger_df['base_rent'] + ledger_df['previous_balance'] + ledger_df['elec_charge'] + ledger_df['water_charge']

# --- SUMMARY & UTILITY LIABILITY DASHBOARD ---
st.subheader("📊 Financial Summary & Utility Liability")

m1, m2, m3, m4, m5 = st.columns(5)

total_rent = ledger_df['base_rent'].sum() if not ledger_df.empty else 0
total_arrears = ledger_df['previous_balance'].sum() if not ledger_df.empty else 0
total_elec = ledger_df['elec_charge'].sum() if not ledger_df.empty else 0
total_water = ledger_df['water_charge'].sum() if not ledger_df.empty else 0
grand_total = ledger_df['total_payable'].sum() if not ledger_df.empty else 0

m1.metric("🏠 Base Rent", f"₹{total_rent:,.0f}")
m2.metric("⏳ Prev. Arrears", f"₹{total_arrears:,.0f}")
m3.metric("⚡ Elec Collected", f"₹{total_elec:,.0f}", help="Electricity board payment recovery pool")
m4.metric("💧 Water Charges", f"₹{total_water:,.0f}")
m5.metric("💰 Grand Total", f"₹{grand_total:,.0f}")

st.markdown("---")

# --- TABS ---
tab1, tab2, tab3, tab4 = st.tabs(["📝 Monthly Ledger & Meter Entry", "📱 Individual WhatsApp Receipt", "⚙️ Manage Houses & Tenants Profile", "💾 Backup & Restore Database"])

with tab1:
    st.subheader(f"Ledger Table - {selected_month}")
    st.info("💡 Edit Current Readings (C.R.), Previous Arrears, Water Charges, and Mobile Numbers directly in the table below and click 'Save Changes'.")
    
    if ledger_df.empty:
        st.warning("No tenant records found for this selection.")
    else:
        display_df = ledger_df[['id', 'house_name', 'tenant_name', 'mobile_no', 'category', 'base_rent', 'previous_balance', 'pr_reading', 'cr_reading', 'units_consumed', 'elec_rate', 'elec_charge', 'water_charge', 'total_payable', 'remarks']].copy()
        
        edited_df = st.data_editor(
            display_df,
            column_config={
                "id": None,
                "house_name": st.column_config.TextColumn("House / Property", disabled=True),
                "tenant_name": st.column_config.TextColumn("Tenant Name", disabled=True),
                "mobile_no": st.column_config.TextColumn("Mobile No", help="10-digit phone number"),
                "category": st.column_config.TextColumn("Category", disabled=True),
                "base_rent": st.column_config.NumberColumn("Base Rent (₹)", disabled=True, format="₹%d"),
                "previous_balance": st.column_config.NumberColumn("Prev Arrears (₹)", help="Previous unpaid dues", format="₹%d"),
                "pr_reading": st.column_config.NumberColumn("P.R. (Prev)", disabled=True),
                "cr_reading": st.column_config.NumberColumn("C.R. (Current)", help="Enter latest meter reading"),
                "units_consumed": st.column_config.NumberColumn("Units", disabled=True),
                "elec_rate": st.column_config.NumberColumn("Rate (₹)", disabled=True, format="₹%d"),
                "elec_charge": st.column_config.NumberColumn("Elec Chg (₹)", disabled=True, format="₹%d"),
                "water_charge": st.column_config.NumberColumn("Water Chg (₹)", format="₹%d"),
                "total_payable": st.column_config.NumberColumn("Total (₹)", disabled=True, format="₹%d"),
                "remarks": st.column_config.TextColumn("Remarks / Notes")
            },
            hide_index=True,
            width="stretch"
        )
        
        if st.button("💾 Save Ledger Updates"):
            conn = get_connection()
            cursor = conn.cursor()
            for _, row in edited_df.iterrows():
                cr_val = float(row['cr_reading']) if pd.notnull(row['cr_reading']) else None
                prev_bal_val = float(row['previous_balance']) if pd.notnull(row['previous_balance']) else 0.0
                water_val = float(row['water_charge']) if pd.notnull(row['water_charge']) else 0.0
                mob_val = str(row['mobile_no']).strip() if pd.notnull(row['mobile_no']) else ""
                remarks_val = str(row['remarks']) if pd.notnull(row['remarks']) else ""
                
                if IS_POSTGRES:
                    cursor.execute("""
                        UPDATE ledger 
                        SET cr_reading = %s, previous_balance = %s, water_charge = %s, mobile_no = %s, remarks = %s
                        WHERE id = %s
                    """, (cr_val, prev_bal_val, water_val, mob_val, remarks_val, int(row['id'])))
                else:
                    cursor.execute("""
                        UPDATE ledger 
                        SET cr_reading = ?, previous_balance = ?, water_charge = ?, mobile_no = ?, remarks = ?
                        WHERE id = ?
                    """, (cr_val, prev_bal_val, water_val, mob_val, remarks_val, int(row['id'])))
                    
            conn.commit()
            conn.close()
            st.success("Successfully saved all updates!")
            st.rerun()

with tab2:
    st.subheader("📱 Individual WhatsApp / Mobile Rent Receipt")
    
    if ledger_df.empty:
        st.warning("No tenants available in current view.")
    else:
        tenant_list = ledger_df['tenant_name'].tolist()
        selected_tenant = st.selectbox("Select Tenant for Receipt", tenant_list)
        
        t_data = ledger_df[ledger_df['tenant_name'] == selected_tenant].iloc[0]
        
        c1, c2 = st.columns([1, 1])
        
        with c1:
            prev_bal_html = f"<p><b>Previous Balance (Bakaya):</b> ₹{t_data['previous_balance']:,.0f}</p>" if t_data['previous_balance'] > 0 else ""
            mob_display = f"<p><b>Mobile No:</b> {t_data['mobile_no']}</p>" if t_data['mobile_no'] else ""
            
            st.markdown(f"""
            <div class="card-box">
                <h3 style="color: #1E3A8A !important;">🏢 RENT RECEIPT - {selected_month}</h3>
                <p><b>Property:</b> {t_data['house_name']}</p>
                <p><b>Tenant Name:</b> {t_data['tenant_name']} ({t_data['category']})</p>
                {mob_display}
                <hr>
                <p><b>Base Rent:</b> ₹{t_data['base_rent']:,.0f}</p>
                {prev_bal_html}
                <p><b>Meter Readings:</b> P.R. {t_data['pr_reading']} | C.R. {t_data['cr_reading'] if pd.notnull(t_data['cr_reading']) else 'Pending'}</p>
                <p><b>Units Consumed:</b> {t_data['units_consumed']} units (@ ₹{t_data['elec_rate']}/unit)</p>
                <p><b>Electricity Charge:</b> ₹{t_data['elec_charge']:,.0f}</p>
                <p><b>Water Charge:</b> ₹{t_data['water_charge']:,.0f}</p>
                <hr>
                <h2 style="color: #1E3A8A !important;">Total Payable: ₹{t_data['total_payable']:,.0f}</h2>
                <p><i>Note: {t_data['remarks']}</i></p>
            </div>
            """, unsafe_allow_html=True)
            
        with c2:
            st.write("📲 **Ready-to-Copy WhatsApp Message:**")
            
            prev_bal_wa = f"⏳ *Previous Balance (Bakaya):* ₹{t_data['previous_balance']:,.0f}\n" if t_data['previous_balance'] > 0 else ""
            
            wa_text = f"""*RENT & UTILITY BILL ({selected_month})*
----------------------------------
*Property:* {t_data['house_name']}
*Tenant Name:* {t_data['tenant_name']}
*Category:* {t_data['category']}

🏠 *Base Rent:* ₹{t_data['base_rent']:,.0f}
{prev_bal_wa}⚡ *Meter Readings:* P.R. {t_data['pr_reading']} | C.R. {t_data['cr_reading'] if pd.notnull(t_data['cr_reading']) else 'Pending'}
⚡ *Units Consumed:* {t_data['units_consumed']} (@ ₹{t_data['elec_rate']}/unit) = ₹{t_data['elec_charge']:,.0f}
💧 *Water Charges:* ₹{t_data['water_charge']:,.0f}
----------------------------------
💰 *TOTAL PAYABLE:* *₹{t_data['total_payable']:,.0f}*
----------------------------------
Note: {t_data['remarks']}

_Please pay at your earliest convenience. Thank you!_"""
            
            st.code(wa_text, language="markdown")
            
            if t_data['mobile_no']:
                clean_phone = "".join(filter(str.isdigit, str(t_data['mobile_no'])))
                if len(clean_phone) == 10:
                    clean_phone = "91" + clean_phone
                encoded_msg = urllib.parse.quote(wa_text)
                wa_url = f"https://api.whatsapp.com/send?phone={clean_phone}&text={encoded_msg}"
                st.markdown(f'<a href="{wa_url}" target="_blank" style="display: inline-block; background-color: #25D366; color: white; padding: 10px 20px; border-radius: 8px; text-decoration: none; font-weight: bold;">💬 Open Direct WhatsApp Chat</a>', unsafe_allow_html=True)

with tab3:
    st.subheader("⚙️ Manage Houses & Tenants Profile")
    
    col_h1, col_h2 = st.columns([1, 1])
    
    with col_h1:
        st.markdown("#### 🏢 Add New House / Property")
        with st.form("add_house_form"):
            new_house_name = st.text_input("New House / Building Name (e.g. House 2)")
            add_h_sub = st.form_submit_button("➕ Add House")
            if add_h_sub and new_house_name.strip():
                conn = get_connection()
                cursor = conn.cursor()
                try:
                    if IS_POSTGRES:
                        cursor.execute("INSERT INTO properties (house_name) VALUES (%s)", (new_house_name.strip(),))
                    else:
                        cursor.execute("INSERT INTO properties (house_name) VALUES (?)", (new_house_name.strip(),))
                    conn.commit()
                    st.success(f"Added Property: {new_house_name.strip()}")
                except Exception:
                    st.error("Property already exists or error occurred.")
                conn.close()
                st.rerun()

    with col_h2:
        st.markdown("#### 👤 Add New Tenant Profile")
        with st.form("add_tenant_form"):
            t_house = st.selectbox("Assign Property", available_properties[1:] if len(available_properties)>1 else ["Main House"])
            t_name = st.text_input("Tenant Name")
            t_mob = st.text_input("Mobile No (Optional)")
            t_cat = st.selectbox("Category", ["Residential", "Shop", "Common Utility"])
            t_rent = st.number_input("Base Rent (₹)", min_value=0, value=3000)
            t_prev = st.number_input("Previous Balance (₹)", min_value=0, value=0)
            t_pr = st.number_input("Initial P.R. Reading", min_value=0, value=0)
            t_rate = st.number_input("Elec Rate (₹/unit)", min_value=1, value=9 if t_cat=="Shop" else 8)
            t_rem = st.text_input("Remarks", value=f"{t_cat} - Rate ₹{9 if t_cat=='Shop' else 8}/unit")
            
            add_t_sub = st.form_submit_button("➕ Add Tenant to Current Month")
            if add_t_sub and t_name.strip():
                conn = get_connection()
                cursor = conn.cursor()
                try:
                    if IS_POSTGRES:
                        cursor.execute("""
                            INSERT INTO ledger (month_year, house_name, tenant_name, mobile_no, category, base_rent, previous_balance, pr_reading, cr_reading, elec_rate, water_charge, remarks)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NULL, %s, 0, %s)
                        """, (selected_month, t_house, t_name.strip(), t_mob.strip(), t_cat, t_rent, t_prev, t_pr, t_rate, t_rem))
                    else:
                        cursor.execute("""
                            INSERT INTO ledger (month_year, house_name, tenant_name, mobile_no, category, base_rent, previous_balance, pr_reading, cr_reading, elec_rate, water_charge, remarks)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, 0, ?)
                        """, (selected_month, t_house, t_name.strip(), t_mob.strip(), t_cat, t_rent, t_prev, t_pr, t_rate, t_rem))
                    conn.commit()
                    st.success(f"Added {t_name} to {selected_month}!")
                except Exception as e:
                    st.error(f"Tenant already exists or error: {e}")
                conn.close()
                st.rerun()

    st.markdown("---")
    st.markdown("#### ✏️ Edit or Delete Existing Tenant Profile")
    
    all_tenants_df = query_to_df("SELECT DISTINCT tenant_name FROM ledger ORDER BY tenant_name ASC")
    if not all_tenants_df.empty:
        tenant_to_manage = st.selectbox("Select Tenant to Edit/Delete", all_tenants_df['tenant_name'].tolist())
        
        t_curr_df = query_to_df("SELECT * FROM ledger WHERE tenant_name = ? ORDER BY id DESC LIMIT 1", params=(tenant_to_manage,))
        if not t_curr_df.empty:
            t_curr = t_curr_df.iloc[0]
            
            edit_col1, edit_col2 = st.columns([2, 1])
            
            with edit_col1:
                with st.form("edit_tenant_form"):
                    st.write(f"Editing Profile for: **{tenant_to_manage}**")
                    e_house = st.selectbox("Property", available_properties[1:] if len(available_properties)>1 else ["Main House"], index=0)
                    e_name = st.text_input("Tenant Name", value=t_curr['tenant_name'])
                    e_mob = st.text_input("Mobile No", value=str(t_curr['mobile_no']) if pd.notnull(t_curr['mobile_no']) else "")
                    e_cat = st.selectbox("Category", ["Residential", "Shop", "Common Utility"], index=0 if t_curr['category']=="Residential" else (1 if t_curr['category']=="Shop" else 2))
                    e_rent = st.number_input("Base Rent (₹)", min_value=0, value=int(t_curr['base_rent']))
                    e_rate = st.number_input("Elec Rate (₹/unit)", min_value=1, value=int(t_curr['elec_rate']))
                    e_apply_all = st.checkbox("Apply Rent/House/Category updates to ALL Ledger Months?", value=True)
                    
                    save_edit_sub = st.form_submit_button("💾 Save Profile Updates")
                    if save_edit_sub:
                        conn = get_connection()
                        cursor = conn.cursor()
                        if e_apply_all:
                            if IS_POSTGRES:
                                cursor.execute("""
                                    UPDATE ledger SET tenant_name=%s, house_name=%s, mobile_no=%s, category=%s, base_rent=%s, elec_rate=%s
                                    WHERE tenant_name=%s
                                """, (e_name.strip(), e_house, e_mob.strip(), e_cat, e_rent, e_rate, tenant_to_manage))
                            else:
                                cursor.execute("""
                                    UPDATE ledger SET tenant_name=?, house_name=?, mobile_no=?, category=?, base_rent=?, elec_rate=?
                                    WHERE tenant_name=?
                                """, (e_name.strip(), e_house, e_mob.strip(), e_cat, e_rent, e_rate, tenant_to_manage))
                        else:
                            if IS_POSTGRES:
                                cursor.execute("""
                                    UPDATE ledger SET tenant_name=%s, house_name=%s, mobile_no=%s, category=%s, base_rent=%s, elec_rate=%s
                                    WHERE tenant_name=%s AND month_year=%s
                                """, (e_name.strip(), e_house, e_mob.strip(), e_cat, e_rent, e_rate, tenant_to_manage, selected_month))
                            else:
                                cursor.execute("""
                                    UPDATE ledger SET tenant_name=?, house_name=?, mobile_no=?, category=?, base_rent=?, elec_rate=?
                                    WHERE tenant_name=? AND month_year=?
                                """, (e_name.strip(), e_house, e_mob.strip(), e_cat, e_rent, e_rate, tenant_to_manage, selected_month))
                        conn.commit()
                        conn.close()
                        st.success(f"Updated profile for {e_name.strip()}!")
                        st.rerun()
            
            with edit_col2:
                st.write("🗑️ **Delete Tenant Record**")
                del_mode = st.radio("Delete Scope", ["Current Month Only", "All Months (Permanent)"])
                confirm_del = st.checkbox(f"Confirm delete {tenant_to_manage}")
                
                if st.button("🔴 Delete Tenant") and confirm_del:
                    conn = get_connection()
                    cursor = conn.cursor()
                    if del_mode == "Current Month Only":
                        if IS_POSTGRES:
                            cursor.execute("DELETE FROM ledger WHERE tenant_name=%s AND month_year=%s", (tenant_to_manage, selected_month))
                        else:
                            cursor.execute("DELETE FROM ledger WHERE tenant_name=? AND month_year=?", (tenant_to_manage, selected_month))
                    else:
                        if IS_POSTGRES:
                            cursor.execute("DELETE FROM ledger WHERE tenant_name=%s", (tenant_to_manage,))
                        else:
                            cursor.execute("DELETE FROM ledger WHERE tenant_name=?", (tenant_to_manage,))
                    conn.commit()
                    conn.close()
                    st.success(f"Deleted {tenant_to_manage}!")
                    st.rerun()

with tab4:
    st.subheader("💾 Backup & Restore Database")
    st.info("Export your entire ledger data as JSON to keep a local backup, or upload a backup file to restore your data anytime!")
    
    col_b1, col_b2 = st.columns([1, 1])
    
    with col_b1:
        st.markdown("#### 📥 Export Backup")
        months_backup = query_to_df("SELECT * FROM months").to_dict(orient="records")
        props_backup = query_to_df("SELECT * FROM properties").to_dict(orient="records")
        ledger_backup = query_to_df("SELECT * FROM ledger").to_dict(orient="records")
        
        full_backup_data = {
            "months": months_backup,
            "properties": props_backup,
            "ledger": ledger_backup,
            "exported_at": str(datetime.datetime.now())
        }
        
        json_backup_str = json.dumps(full_backup_data, indent=2)
        st.download_button(
            label="⬇️ Download Complete Database Backup (JSON)",
            data=json_backup_str,
            file_name=f"rent_ledger_backup_{datetime.date.today()}.json",
            mime="application/json"
        )
        
    with col_b2:
        st.markdown("#### 📤 Restore Backup")
        uploaded_backup = st.file_uploader("Upload JSON Backup File", type=["json"])
        if uploaded_backup is not None:
            if st.button("⚠️ Restore Data From Backup"):
                try:
                    backup_obj = json.load(uploaded_backup)
                    conn = get_connection()
                    cursor = conn.cursor()
                    
                    cursor.execute("DELETE FROM ledger;")
                    cursor.execute("DELETE FROM properties;")
                    cursor.execute("DELETE FROM months;")
                    
                    for m in backup_obj.get("months", []):
                        if IS_POSTGRES:
                            cursor.execute("INSERT INTO months (month_year) VALUES (%s) ON CONFLICT DO NOTHING;", (m['month_year'],))
                        else:
                            cursor.execute("INSERT OR IGNORE INTO months (month_year) VALUES (?);", (m['month_year'],))
                            
                    for p in backup_obj.get("properties", []):
                        if IS_POSTGRES:
                            cursor.execute("INSERT INTO properties (house_name) VALUES (%s) ON CONFLICT DO NOTHING;", (p['house_name'],))
                        else:
                            cursor.execute("INSERT OR IGNORE INTO properties (house_name) VALUES (?);", (p['house_name'],))
                            
                    for l in backup_obj.get("ledger", []):
                        h_n = l.get('house_name', 'Main House')
                        m_n = l.get('mobile_no', '')
                        p_b = l.get('previous_balance', 0.0)
                        if IS_POSTGRES:
                            cursor.execute("""
                                INSERT INTO ledger (month_year, house_name, tenant_name, mobile_no, category, base_rent, previous_balance, pr_reading, cr_reading, elec_rate, water_charge, remarks)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT DO NOTHING;
                            """, (l['month_year'], h_n, l['tenant_name'], m_n, l['category'], l['base_rent'], p_b, l['pr_reading'], l.get('cr_reading'), l['elec_rate'], l['water_charge'], l.get('remarks', '')))
                        else:
                            cursor.execute("""
                                INSERT OR IGNORE INTO ledger (month_year, house_name, tenant_name, mobile_no, category, base_rent, previous_balance, pr_reading, cr_reading, elec_rate, water_charge, remarks)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                            """, (l['month_year'], h_n, l['tenant_name'], m_n, l['category'], l['base_rent'], p_b, l['pr_reading'], l.get('cr_reading'), l['elec_rate'], l['water_charge'], l.get('remarks', '')))
                            
                    conn.commit()
                    conn.close()
                    st.success("Database restored successfully from backup!")
                    st.rerun()
                except Exception as ex:
                    st.error(f"Failed to restore backup: {ex}")
