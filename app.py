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
    try:
        if "DATABASE_URL" in st.secrets:
            return st.secrets["DATABASE_URL"]
        elif "postgres" in st.secrets and "url" in st.secrets["postgres"]:
            return st.secrets["postgres"]["url"]
    except Exception:
        pass
    if "DATABASE_URL" in os.environ:
        return os.environ["DATABASE_URL"]
    return None

RAW_DB_URI = get_db_uri()

# Session State for Database Connection Status
if "db_type" not in st.session_state:
    st.session_state.db_type = "UNKNOWN"
if "db_error" not in st.session_state:
    st.session_state.db_error = None

def get_connection():
    uri = RAW_DB_URI
    if uri and uri.startswith(("postgres://", "postgresql://")):
        if uri.startswith("postgres://"):
            uri = uri.replace("postgres://", "postgresql://", 1)
        try:
            import psycopg2
            conn = psycopg2.connect(uri, connect_timeout=5)
            st.session_state.db_type = "POSTGRES"
            st.session_state.db_error = None
            return conn, "POSTGRES"
        except Exception as e:
            st.session_state.db_type = "SQLITE_FALLBACK"
            st.session_state.db_error = str(e)
            conn = sqlite3.connect("rent_ledger.db")
            conn.row_factory = sqlite3.Row
            return conn, "SQLITE"
    else:
        st.session_state.db_type = "SQLITE"
        st.session_state.db_error = None
        conn = sqlite3.connect("rent_ledger.db")
        conn.row_factory = sqlite3.Row
        return conn, "SQLITE"

def execute_query(query, params=(), fetchall=False, fetchone=False, commit=False):
    conn, db_mode = get_connection()
    cursor = conn.cursor()
    
    if db_mode == "POSTGRES":
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
    conn, db_mode = get_connection()
    if db_mode == "POSTGRES":
        query = query.replace("?", "%s")
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

# Initialize Tables and Schema
def init_db():
    conn, db_mode = get_connection()
    cursor = conn.cursor()
    
    if db_mode == "POSTGRES":
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
        conn.commit()
        
        # Seed initial data for Postgres if empty
        cursor.execute("SELECT COUNT(*) FROM months")
        count = cursor.fetchone()[0]
        if count == 0:
            cursor.execute("INSERT INTO months (month_year) VALUES ('October 2026')")
            cursor.execute("INSERT INTO properties (house_name) VALUES ('Main House')")
            
            initial_tenants = [
                ("Main House", "Gupta Ji", "", "Shop", 5000, 0, 3396, 3428, 9, 0, "Shop - Rate ₹9/unit; Water N/A"),
                ("Main House", "Ashwini", "", "Residential", 4000, 0, 6602, 6618, 8, 142, "Residential - Rate ₹8/unit; Water provisional ₹142"),
                ("Main House", "Anoop Sharma", "", "Residential", 4500, 0, 6363, None, 8, 0, "Residential - Rate ₹8/unit"),
                ("Main House", "Satish Pathak (Sarthak)", "", "Residential", 2700, 0, 1477, None, 8, 0, "Residential - Rate ₹8/unit"),
                ("Main House", "Umesh Pathak", "", "Residential", 3750, 0, 6315, None, 8, 0, "Residential - Rate ₹8/unit"),
                ("Main House", "Ramsingh Saini", "", "Shop", 5000, 0, 10379, None, 9, 0, "Shop - Rate ₹9/unit; Water N/A"),
                ("Main House", "Vinod Sharma", "", "Residential", 3750, 0, 6276, None, 8, 0, "Residential - Rate ₹8/unit"),
                ("Main House", "Submersible (Pump)", "", "Common Utility", 0, 0, 6774, None, 8, 0, "Common Utility - Rate ₹8/unit"),
                ("Main House", "Tiwari Ji", "", "Residential", 3000, 0, 4263, None, 8, 0, "Faulty Meter (मीटर खराब है)"),
                ("Main House", "Neeraj Kumar", "", "Residential", 3800, 0, 2447, None, 8, 0, "Residential - Rate ₹8/unit")
            ]
            for t in initial_tenants:
                cursor.execute("""
                    INSERT INTO ledger (house_name, tenant_name, mobile_no, category, base_rent, previous_balance, pr_reading, cr_reading, elec_rate, water_charge, remarks, month_year)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'October 2026')
                """, t)
            conn.commit()
    else:
        # SQLite Engine
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
        conn.commit()
        
        # Schema Migrations for SQLite
        cursor.execute("PRAGMA table_info(ledger)")
        cols = [c[1] for c in cursor.fetchall()]
        if 'house_name' not in cols:
            cursor.execute("ALTER TABLE ledger ADD COLUMN house_name TEXT DEFAULT 'Main House'")
        if 'mobile_no' not in cols:
            cursor.execute("ALTER TABLE ledger ADD COLUMN mobile_no TEXT DEFAULT ''")
        if 'previous_balance' not in cols:
            cursor.execute("ALTER TABLE ledger ADD COLUMN previous_balance REAL DEFAULT 0")
        conn.commit()
        
        cursor.execute("SELECT COUNT(*) FROM months")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO months (month_year) VALUES ('October 2026')")
            cursor.execute("INSERT INTO properties (house_name) VALUES ('Main House')")
            
            initial_tenants = [
                ("Main House", "Gupta Ji", "", "Shop", 5000, 0, 3396, 3428, 9, 0, "Shop - Rate ₹9/unit; Water N/A"),
                ("Main House", "Ashwini", "", "Residential", 4000, 0, 6602, 6618, 8, 142, "Residential - Rate ₹8/unit; Water provisional ₹142"),
                ("Main House", "Anoop Sharma", "", "Residential", 4500, 0, 6363, None, 8, 0, "Residential - Rate ₹8/unit"),
                ("Main House", "Satish Pathak (Sarthak)", "", "Residential", 2700, 0, 1477, None, 8, 0, "Residential - Rate ₹8/unit"),
                ("Main House", "Umesh Pathak", "", "Residential", 3750, 0, 6315, None, 8, 0, "Residential - Rate ₹8/unit"),
                ("Main House", "Ramsingh Saini", "", "Shop", 5000, 0, 10379, None, 9, 0, "Shop - Rate ₹9/unit; Water N/A"),
                ("Main House", "Vinod Sharma", "", "Residential", 3750, 0, 6276, None, 8, 0, "Residential - Rate ₹8/unit"),
                ("Main House", "Submersible (Pump)", "", "Common Utility", 0, 0, 6774, None, 8, 0, "Common Utility - Rate ₹8/unit"),
                ("Main House", "Tiwari Ji", "", "Residential", 3000, 0, 4263, None, 8, 0, "Faulty Meter (मीटर खराब है)"),
                ("Main House", "Neeraj Kumar", "", "Residential", 3800, 0, 2447, None, 8, 0, "Residential - Rate ₹8/unit")
            ]
            for t in initial_tenants:
                cursor.execute("""
                    INSERT INTO ledger (house_name, tenant_name, mobile_no, category, base_rent, previous_balance, pr_reading, cr_reading, elec_rate, water_charge, remarks, month_year)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'October 2026')
                """, t)
            conn.commit()

    conn.close()

init_db()

# --- SIDEBAR: NAVIGATION & CONTROLS ---
st.sidebar.title("🏢 Controls & Settings")

if st.session_state.db_type == "POSTGRES":
    st.sidebar.success("⚡ Connected to Cloud Database (Supabase/Postgres)")
elif st.session_state.db_type == "SQLITE_FALLBACK":
    st.sidebar.warning("⚠️ Could not connect to Supabase/Postgres URL. Using local SQLite database as fallback.")
    st.sidebar.caption(f"Error: {st.session_state.db_error}")
else:
    st.sidebar.info("💾 Running on Local SQLite Database")

# Load Available Months & Properties
months_df = query_to_df("SELECT month_year FROM months ORDER BY id DESC")
available_months = months_df['month_year'].tolist() if not months_df.empty else ['October 2026']

props_df = query_to_df("SELECT house_name FROM properties ORDER BY id ASC")
available_props = ["All Properties"] + (props_df['house_name'].tolist() if not props_df.empty else ["Main House"])

selected_month = st.sidebar.selectbox("📅 Select Ledger Month", available_months)
selected_property_filter = st.sidebar.selectbox("🏠 Filter Property / House", available_props)

st.sidebar.markdown("---")
st.sidebar.subheader("➕ Create New Month Ledger")
new_month_input = st.sidebar.text_input("New Month Name (e.g. November 2026)")

if st.sidebar.button("🚀 Roll Over & Create Month"):
    if not new_month_input.strip():
        st.sidebar.error("Please enter a valid month name!")
    elif new_month_input.strip() in available_months:
        st.sidebar.warning("This month already exists!")
    else:
        execute_query("INSERT INTO months (month_year) VALUES (?)", (new_month_input.strip(),), commit=True)
        prev_data = query_to_df("SELECT * FROM ledger WHERE month_year = ?", params=(selected_month,))
        
        for _, row in prev_data.iterrows():
            new_pr = row['cr_reading'] if pd.notnull(row['cr_reading']) else row['pr_reading']
            h_name = row['house_name'] if 'house_name' in row and pd.notnull(row['house_name']) else 'Main House'
            m_no = row['mobile_no'] if 'mobile_no' in row and pd.notnull(row['mobile_no']) else ''
            execute_query("""
                INSERT INTO ledger (month_year, house_name, tenant_name, mobile_no, category, base_rent, previous_balance, pr_reading, cr_reading, elec_rate, water_charge, remarks)
                VALUES (?, ?, ?, ?, ?, ?, 0, ?, NULL, ?, ?, ?)
            """, (new_month_input.strip(), h_name, row['tenant_name'], m_no, row['category'], row['base_rent'], new_pr, row['elec_rate'], row['water_charge'], row['remarks']), commit=True)
            
        st.sidebar.success(f"Created {new_month_input}! Auto-rolled P.R. readings.")
        st.rerun()

# --- MAIN APP BODY ---
st.title("🏢 Property Rent & Utility Management")
st.caption(f"Viewing: **{selected_month}** | Property: **{selected_property_filter}**")

# Load Current Ledger Data
if selected_property_filter == "All Properties":
    ledger_df = query_to_df("SELECT * FROM ledger WHERE month_year = ?", params=(selected_month,))
else:
    ledger_df = query_to_df("SELECT * FROM ledger WHERE month_year = ? AND house_name = ?", params=(selected_month, selected_property_filter))

# Ensure required columns exist cleanly
for col in ['house_name', 'mobile_no', 'previous_balance']:
    if col not in ledger_df.columns:
        ledger_df[col] = '' if col != 'previous_balance' else 0.0

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
m3.metric("⚡ Elec Collected", f"₹{total_elec:,.0f}", help="Electricity board recovery pool")
m4.metric("💧 Water Charges", f"₹{total_water:,.0f}")
m5.metric("💰 Grand Total", f"₹{grand_total:,.0f}")

st.markdown("---")

# --- TABS FOR LEDGER, RECEIPT, TENANT/HOUSE MANAGEMENT & BACKUP ---
tab1, tab2, tab3, tab4 = st.tabs(["📝 Monthly Ledger & Meter Entry", "📱 Individual WhatsApp Receipt", "⚙️ Manage Houses & Tenants Profile", "💾 Backup & Restore Database"])

with tab1:
    st.subheader(f"Ledger Table - {selected_month} ({selected_property_filter})")
    st.info("💡 Edit Current Readings (C.R.), Previous Arrears, and Water Charges directly in the table below and click 'Save Changes'.")
    
    if ledger_df.empty:
        st.warning("No records found for this selection.")
    else:
        display_df = ledger_df[['id', 'house_name', 'tenant_name', 'mobile_no', 'category', 'base_rent', 'previous_balance', 'pr_reading', 'cr_reading', 'units_consumed', 'elec_rate', 'elec_charge', 'water_charge', 'total_payable', 'remarks']].copy()
        
        edited_df = st.data_editor(
            display_df,
            column_config={
                "id": None,
                "house_name": st.column_config.TextColumn("House / Property", disabled=True),
                "tenant_name": st.column_config.TextColumn("Tenant Name", disabled=True),
                "mobile_no": st.column_config.TextColumn("Mobile No", help="Tenant phone number"),
                "category": st.column_config.TextColumn("Category", disabled=True),
                "base_rent": st.column_config.NumberColumn("Base Rent (₹)", disabled=True, format="₹%d"),
                "previous_balance": st.column_config.NumberColumn("Prev Arrears (₹)", help="Unpaid dues", format="₹%d"),
                "pr_reading": st.column_config.NumberColumn("P.R. (Prev)", disabled=True),
                "cr_reading": st.column_config.NumberColumn("C.R. (Current)", help="Latest meter reading"),
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
            for _, row in edited_df.iterrows():
                cr_val = float(row['cr_reading']) if pd.notnull(row['cr_reading']) else None
                prev_bal_val = float(row['previous_balance']) if pd.notnull(row['previous_balance']) else 0.0
                water_val = float(row['water_charge']) if pd.notnull(row['water_charge']) else 0.0
                mob_val = str(row['mobile_no']) if pd.notnull(row['mobile_no']) else ""
                remarks_val = str(row['remarks']) if pd.notnull(row['remarks']) else ""
                
                execute_query("""
                    UPDATE ledger 
                    SET cr_reading = ?, previous_balance = ?, water_charge = ?, mobile_no = ?, remarks = ?
                    WHERE id = ?
                """, (cr_val, prev_bal_val, water_val, mob_val, remarks_val, int(row['id'])), commit=True)
            st.success("Successfully saved all updates!")
            st.rerun()

with tab2:
    st.subheader("📱 Individual WhatsApp / Mobile Rent Receipt")
    
    if ledger_df.empty:
        st.warning("No tenants found in current selection.")
    else:
        tenant_list = ledger_df['tenant_name'].tolist()
        selected_tenant = st.selectbox("Select Tenant for Receipt", tenant_list)
        
        t_data = ledger_df[ledger_df['tenant_name'] == selected_tenant].iloc[0]
        
        c1, c2 = st.columns([1, 1])
        
        with c1:
            prev_bal_val = t_data['previous_balance'] if pd.notnull(t_data['previous_balance']) else 0
            prev_bal_html = f"<p><b>Previous Balance (Bakaya):</b> ₹{prev_bal_val:,.0f}</p>" if prev_bal_val > 0 else ""
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
            
            pb_line = f"⏳ *Previous Balance (Bakaya):* ₹{prev_bal_val:,.0f}\n" if prev_bal_val > 0 else ""
            
            wa_text = f"""*RENT & UTILITY BILL ({selected_month})*
----------------------------------
*Property:* {t_data['house_name']}
*Tenant Name:* {t_data['tenant_name']}
*Category:* {t_data['category']}

🏠 *Base Rent:* ₹{t_data['base_rent']:,.0f}
{pb_line}⚡ *Meter Readings:* P.R. {t_data['pr_reading']} | C.R. {t_data['cr_reading'] if pd.notnull(t_data['cr_reading']) else 'Pending'}
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
        st.write("🏠 **Add New Property / House:**")
        with st.form("add_house_form"):
            new_house_name = st.text_input("New House / Building Name (e.g. House 2)")
            sub_h = st.form_submit_button("➕ Save Property")
            if sub_h and new_house_name.strip():
                try:
                    execute_query("INSERT INTO properties (house_name) VALUES (?)", (new_house_name.strip(),), commit=True)
                    st.success(f"Added {new_house_name}!")
                    st.rerun()
                except Exception:
                    st.error("Property name already exists or error occurred.")

    with col_h2:
        st.write("➕ **Add New Tenant to Current Month:**")
        all_props = query_to_df("SELECT house_name FROM properties ORDER BY id ASC")['house_name'].tolist()
        if not all_props:
            all_props = ["Main House"]
            
        with st.form("add_tenant_form"):
            t_house = st.selectbox("Assign Property / House", all_props)
            t_name = st.text_input("Tenant Name")
            t_mob = st.text_input("Mobile Number")
            t_cat = st.selectbox("Category", ["Residential", "Shop", "Common Utility"])
            t_rent = st.number_input("Base Rent (₹)", min_value=0, value=3000)
            t_prev_bal = st.number_input("Previous Balance (₹)", min_value=0, value=0)
            t_pr = st.number_input("Initial P.R. Reading", min_value=0, value=0)
            t_rate = st.number_input("Elec Rate (₹/unit)", min_value=1, value=9 if t_cat=="Shop" else 8)
            t_rem = st.text_input("Remarks", value=f"{t_cat} - Rate ₹{9 if t_cat=='Shop' else 8}/unit")
            
            sub_t = st.form_submit_button("➕ Add Tenant")
            if sub_t and t_name.strip():
                try:
                    execute_query("""
                        INSERT INTO ledger (month_year, house_name, tenant_name, mobile_no, category, base_rent, previous_balance, pr_reading, cr_reading, elec_rate, water_charge, remarks)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, 0, ?)
                    """, (selected_month, t_house, t_name.strip(), t_mob.strip(), t_cat, t_rent, t_prev_bal, t_pr, t_rate, t_rem), commit=True)
                    st.success(f"Added {t_name} to {selected_month}!")
                    st.rerun()
                except Exception:
                    st.error("Tenant already exists in this month!")

    st.markdown("---")
    st.subheader("✏️ Edit or Delete Existing Tenant")
    
    all_current_tenants = query_to_df("SELECT * FROM ledger WHERE month_year = ?", params=(selected_month,))
    if not all_current_tenants.empty:
        tenant_to_edit = st.selectbox("Select Tenant to Edit / Delete", all_current_tenants['tenant_name'].tolist())
        e_row = all_current_tenants[all_current_tenants['tenant_name'] == tenant_to_edit].iloc[0]
        
        col_ed1, col_ed2 = st.columns(2)
        
        with col_ed1:
            st.write("✏️ **Update Tenant Profile:**")
            with st.form("edit_tenant_profile_form"):
                ed_house = st.selectbox("House", all_props, index=all_props.index(e_row['house_name']) if 'house_name' in e_row and e_row['house_name'] in all_props else 0)
                ed_name = st.text_input("Tenant Name", value=e_row['tenant_name'])
                ed_mob = st.text_input("Mobile No", value=e_row['mobile_no'] if 'mobile_no' in e_row else "")
                ed_cat = st.selectbox("Category", ["Residential", "Shop", "Common Utility"], index=["Residential", "Shop", "Common Utility"].index(e_row['category']))
                ed_rent = st.number_input("Base Rent (₹)", min_value=0, value=int(e_row['base_rent']))
                ed_rate = st.number_input("Elec Rate (₹/unit)", min_value=1, value=int(e_row['elec_rate']))
                update_all_months = st.checkbox("Apply changes to ALL ledger months", value=False)
                
                if st.form_submit_button("💾 Save Profile Changes"):
                    if update_all_months:
                        execute_query("""
                            UPDATE ledger
                            SET tenant_name = ?, house_name = ?, mobile_no = ?, category = ?, base_rent = ?, elec_rate = ?
                            WHERE tenant_name = ?
                        """, (ed_name.strip(), ed_house, ed_mob.strip(), ed_cat, ed_rent, ed_rate, tenant_to_edit), commit=True)
                    else:
                        execute_query("""
                            UPDATE ledger
                            SET tenant_name = ?, house_name = ?, mobile_no = ?, category = ?, base_rent = ?, elec_rate = ?
                            WHERE id = ?
                        """, (ed_name.strip(), ed_house, ed_mob.strip(), ed_cat, ed_rent, ed_rate, int(e_row['id'])), commit=True)
                    st.success(f"Updated profile for {ed_name}!")
                    st.rerun()

        with col_ed2:
            st.write("🗑️ **Delete Tenant:**")
            with st.form("delete_tenant_form"):
                st.warning(f"Delete '{tenant_to_edit}' from record?")
                del_mode = st.radio("Delete Scope", ["Current Month Only", "All Months (Permanent Delete)"])
                confirm_del = st.checkbox("Confirm deletion")
                
                if st.form_submit_button("❌ Delete Tenant"):
                    if confirm_del:
                        if del_mode == "Current Month Only":
                            execute_query("DELETE FROM ledger WHERE id = ?", (int(e_row['id']),), commit=True)
                        else:
                            execute_query("DELETE FROM ledger WHERE tenant_name = ?", (tenant_to_edit,), commit=True)
                        st.success(f"Deleted {tenant_to_edit}!")
                        st.rerun()
                    else:
                        st.error("Please check 'Confirm deletion' first!")

with tab4:
    st.subheader("💾 Backup & Restore Database")
    st.info("Download a complete JSON backup of your database records or upload a backup file to restore.")
    
    col_b1, col_b2 = st.columns(2)
    
    with col_b1:
        st.write("⬇️ **Download Database Backup:**")
        if st.button("📦 Generate Backup File"):
            m_data = query_to_df("SELECT * FROM months").to_dict(orient="records")
            p_data = query_to_df("SELECT * FROM properties").to_dict(orient="records")
            l_data = query_to_df("SELECT * FROM ledger").to_dict(orient="records")
            
            backup_dict = {
                "months": m_data,
                "properties": p_data,
                "ledger": l_data,
                "exported_at": str(datetime.datetime.now())
            }
            json_str = json.dumps(backup_dict, indent=2)
            st.download_button("💾 Download Backup (.json)", data=json_str, file_name=f"rent_ledger_backup_{datetime.date.today()}.json", mime="application/json")

    with col_b2:
        st.write("⬆️ **Restore Database from Backup:**")
        uploaded_backup = st.file_uploader("Upload Backup JSON File", type=["json"])
        if uploaded_backup is not None:
            if st.button("🚀 Restore Data Now"):
                try:
                    data = json.load(uploaded_backup)
                    if "ledger" in data:
                        for m in data.get("months", []):
                            try:
                                execute_query("INSERT INTO months (month_year) VALUES (?)", (m['month_year'],), commit=True)
                            except Exception:
                                pass
                        for p in data.get("properties", []):
                            try:
                                execute_query("INSERT INTO properties (house_name) VALUES (?)", (p['house_name'],), commit=True)
                            except Exception:
                                pass
                        for l in data.get("ledger", []):
                            try:
                                execute_query("""
                                    INSERT INTO ledger (month_year, house_name, tenant_name, mobile_no, category, base_rent, previous_balance, pr_reading, cr_reading, elec_rate, water_charge, remarks)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """, (l['month_year'], l.get('house_name', 'Main House'), l['tenant_name'], l.get('mobile_no', ''), l['category'], l['base_rent'], l.get('previous_balance', 0), l['pr_reading'], l.get('cr_reading'), l['elec_rate'], l.get('water_charge', 0), l.get('remarks', '')), commit=True)
                            except Exception:
                                pass
                        st.success("Successfully restored data from backup!")
                        st.rerun()
                except Exception as e:
                    st.error(f"Failed to restore: {str(e)}")
