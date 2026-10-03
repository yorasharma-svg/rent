import streamlit as st
import sqlite3
import pandas as pd
import datetime

# Page Configuration for Mobile Responsiveness
st.set_page_config(
    page_title="Rent & Utility Ledger",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling for Clean Mobile & Desktop Look with Strict Color Visibility
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

# Database Connection
DB_FILE = "rent_ledger.db"

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create Houses Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS houses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            house_name TEXT UNIQUE NOT NULL
        )
    """)
    
    # Seed default house if empty
    cursor.execute("SELECT COUNT(*) FROM houses")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO houses (house_name) VALUES ('Main House')")
    
    # Create Months Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS months (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            month_year TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create Ledger Table
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
            FOREIGN KEY (month_year) REFERENCES months (month_year),
            UNIQUE(month_year, tenant_name)
        )
    """)
    
    # --- AUTO-MIGRATION / SCHEMA UPGRADES FOR EXISTING DATABASES ---
    cursor.execute("PRAGMA table_info(ledger)")
    existing_cols = [row['name'] for row in cursor.fetchall()]
    
    if 'house_name' not in existing_cols:
        try:
            cursor.execute("ALTER TABLE ledger ADD COLUMN house_name TEXT DEFAULT 'Main House'")
        except Exception:
            pass
            
    if 'mobile_no' not in existing_cols:
        try:
            cursor.execute("ALTER TABLE ledger ADD COLUMN mobile_no TEXT DEFAULT ''")
        except Exception:
            pass
            
    if 'previous_balance' not in existing_cols:
        try:
            cursor.execute("ALTER TABLE ledger ADD COLUMN previous_balance REAL DEFAULT 0")
        except Exception:
            pass

    # Seed Initial October 2026 Data if DB is completely empty
    cursor.execute("SELECT COUNT(*) FROM months")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO months (month_year) VALUES ('October 2026')")
        
        initial_tenants = [
            ("Main House", "Gupta Ji", "Shop", 5000, 0, 3396, 3428, 9, 0, "Shop - Rate ₹9/unit; Water N/A", ""),
            ("Main House", "Ashwini", "Residential", 4000, 0, 6602, 6618, 8, 142, "Residential - Rate ₹8/unit; Water provisional ₹142", ""),
            ("Main House", "Anoop Sharma", "Residential", 4500, 0, 6363, None, 8, 0, "Residential - Rate ₹8/unit", ""),
            ("Main House", "Satish Pathak (Sarthak)", "Residential", 2700, 0, 1477, None, 8, 0, "Residential - Rate ₹8/unit", ""),
            ("Main House", "Umesh Pathak", "Residential", 3750, 0, 6315, None, 8, 0, "Residential - Rate ₹8/unit", ""),
            ("Main House", "Ramsingh Saini", "Shop", 5000, 0, 10379, None, 9, 0, "Shop - Rate ₹9/unit; Water N/A", ""),
            ("Main House", "Vinod Sharma", "Residential", 3750, 0, 6276, None, 8, 0, "Residential - Rate ₹8/unit", ""),
            ("Main House", "Submersible (Pump)", "Common Utility", 0, 0, 6774, None, 8, 0, "Common Utility - Rate ₹8/unit", ""),
            ("Main House", "Tiwari Ji", "Residential", 3000, 0, 4263, None, 8, 0, "Faulty Meter (मीटर खराब है)", ""),
            ("Main House", "Neeraj Kumar", "Residential", 3800, 0, 2447, None, 8, 0, "Residential - Rate ₹8/unit", "")
        ]
        
        for t in initial_tenants:
            cursor.execute("""
                INSERT INTO ledger (month_year, house_name, tenant_name, category, base_rent, previous_balance, pr_reading, cr_reading, elec_rate, water_charge, remarks, mobile_no)
                VALUES ('October 2026', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, t)
            
    conn.commit()
    conn.close()

init_db()

# --- SIDEBAR: NAVIGATION & CONTROLS ---
st.sidebar.title("🏢 Navigation & Controls")

conn = get_db_connection()
months_df = pd.read_sql_query("SELECT month_year FROM months ORDER BY id DESC", conn)
houses_df = pd.read_sql_query("SELECT house_name FROM houses ORDER BY house_name ASC", conn)
conn.close()

available_months = months_df['month_year'].tolist()
available_houses = ["All Properties / Houses"] + houses_df['house_name'].tolist()

selected_month = st.sidebar.selectbox("📅 Select Ledger Month", available_months)
selected_house_filter = st.sidebar.selectbox("🏠 Filter Property / House", available_houses)

st.sidebar.markdown("---")
st.sidebar.subheader("➕ Create New Month Ledger")
new_month_input = st.sidebar.text_input("New Month Name (e.g. November 2026)")

if st.sidebar.button("🚀 Roll Over & Create Month"):
    if not new_month_input.strip():
        st.sidebar.error("Please enter a valid month name!")
    elif new_month_input.strip() in available_months:
        st.sidebar.warning("This month already exists!")
    else:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO months (month_year) VALUES (?)", (new_month_input.strip(),))
        
        prev_data = pd.read_sql_query("SELECT * FROM ledger WHERE month_year = ?", conn, params=(selected_month,))
        
        for _, row in prev_data.iterrows():
            new_pr = row['cr_reading'] if pd.notnull(row.get('cr_reading')) else row.get('pr_reading', 0)
            h_name = row.get('house_name', 'Main House')
            mob_no = row.get('mobile_no', '')
            cursor.execute("""
                INSERT INTO ledger (month_year, house_name, tenant_name, mobile_no, category, base_rent, previous_balance, pr_reading, cr_reading, elec_rate, water_charge, remarks)
                VALUES (?, ?, ?, ?, ?, ?, 0, ?, NULL, ?, ?, ?)
            """, (new_month_input.strip(), h_name, row['tenant_name'], mob_no, row['category'], row['base_rent'], new_pr, row['elec_rate'], row['water_charge'], row['remarks']))
            
        conn.commit()
        conn.close()
        st.sidebar.success(f"Created {new_month_input}! Auto-rolled P.R. readings from {selected_month}.")
        st.rerun()

# --- MAIN APP BODY ---
st.title("🏢 Property Rent & Utility Management")
st.caption(f"Currently Viewing: **{selected_month}** | Filter: **{selected_house_filter}**")

# Load Current Month Ledger
conn = get_db_connection()
ledger_df = pd.read_sql_query("SELECT * FROM ledger WHERE month_year = ?", conn, params=(selected_month,))
conn.close()

# DEFENSIVE PANDAS HANDLING TO PREVENT KEYERROR ON OLD DBs
required_columns_defaults = {
    'id': None,
    'house_name': 'Main House',
    'tenant_name': 'Unknown',
    'mobile_no': '',
    'category': 'Residential',
    'base_rent': 0.0,
    'previous_balance': 0.0,
    'pr_reading': 0.0,
    'cr_reading': None,
    'elec_rate': 8.0,
    'water_charge': 0.0,
    'remarks': ''
}

for col, def_val in required_columns_defaults.items():
    if col not in ledger_df.columns:
        ledger_df[col] = def_val

# Apply House Filter if needed
if selected_house_filter != "All Properties / Houses":
    ledger_df = ledger_df[ledger_df['house_name'] == selected_house_filter].copy()

# Computations
ledger_df['cr_reading_calc'] = ledger_df['cr_reading'].fillna(ledger_df['pr_reading'])
ledger_df['units_consumed'] = ledger_df['cr_reading_calc'] - ledger_df['pr_reading']
ledger_df['units_consumed'] = ledger_df['units_consumed'].apply(lambda x: max(0, x))
ledger_df['elec_charge'] = ledger_df['units_consumed'] * ledger_df['elec_rate']
ledger_df['total_payable'] = ledger_df['base_rent'] + ledger_df['previous_balance'] + ledger_df['elec_charge'] + ledger_df['water_charge']

# --- SUMMARY & UTILITY LIABILITY DASHBOARD ---
st.subheader("📊 Financial Summary & Utility Liability")

m1, m2, m3, m4, m5 = st.columns(5)

total_rent = ledger_df['base_rent'].sum() if len(ledger_df) > 0 else 0
total_arrears = ledger_df['previous_balance'].sum() if len(ledger_df) > 0 else 0
total_elec = ledger_df['elec_charge'].sum() if len(ledger_df) > 0 else 0
total_water = ledger_df['water_charge'].sum() if len(ledger_df) > 0 else 0
grand_total = ledger_df['total_payable'].sum() if len(ledger_df) > 0 else 0

m1.metric("🏠 Base Rent", f"₹{total_rent:,.0f}")
m2.metric("⏳ Prev. Arrears", f"₹{total_arrears:,.0f}")
m3.metric("⚡ Elec Collected", f"₹{total_elec:,.0f}", help="Electricity board payment recovery pool")
m4.metric("💧 Water Charges", f"₹{total_water:,.0f}")
m5.metric("💰 Grand Total", f"₹{grand_total:,.0f}")

st.markdown("---")

# --- TABS FOR LEDGER AND RECEIPT ---
tab1, tab2, tab3 = st.tabs(["📝 Monthly Ledger & Meter Entry", "📱 Individual WhatsApp Receipt", "⚙️ Manage Houses & Tenants Profile"])

with tab1:
    st.subheader(f"Ledger Table - {selected_month}")
    st.info("💡 Edit Current Readings (C.R.), Mobile No, Previous Arrears, and Water Charges directly in the table below and click 'Save Changes'.")
    
    display_df = ledger_df[['id', 'house_name', 'tenant_name', 'mobile_no', 'category', 'base_rent', 'previous_balance', 'pr_reading', 'cr_reading', 'units_consumed', 'elec_rate', 'elec_charge', 'water_charge', 'total_payable', 'remarks']].copy()
    
    edited_df = st.data_editor(
        display_df,
        column_config={
            "id": None,
            "house_name": st.column_config.TextColumn("Property/House", disabled=True),
            "tenant_name": st.column_config.TextColumn("Tenant Name", disabled=True),
            "mobile_no": st.column_config.TextColumn("Mobile No", help="10-digit Mobile Number"),
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
        conn = get_db_connection()
        cursor = conn.cursor()
        for _, row in edited_df.iterrows():
            cr_val = float(row['cr_reading']) if pd.notnull(row['cr_reading']) else None
            mob_val = str(row['mobile_no']).strip() if pd.notnull(row['mobile_no']) else ""
            prev_bal_val = float(row['previous_balance']) if pd.notnull(row['previous_balance']) else 0.0
            water_val = float(row['water_charge']) if pd.notnull(row['water_charge']) else 0.0
            remarks_val = str(row['remarks']) if pd.notnull(row['remarks']) else ""
            
            cursor.execute("""
                UPDATE ledger 
                SET cr_reading = ?, mobile_no = ?, previous_balance = ?, water_charge = ?, remarks = ?
                WHERE id = ?
            """, (cr_val, mob_val, prev_bal_val, water_val, remarks_val, int(row['id'])))
        conn.commit()
        conn.close()
        st.success("Successfully saved all updates!")
        st.rerun()

with tab2:
    st.subheader("📱 Individual WhatsApp / Mobile Rent Receipt")
    
    if len(ledger_df) == 0:
        st.warning("No tenant records found for this filter.")
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
            
            prev_bal_wa = (f"⏳ *Previous Balance (Bakaya):* ₹{t_data['previous_balance']:,.0f}\n" if t_data['previous_balance'] > 0 else "")
            
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
                import urllib.parse
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
        st.write("🏠 **Add New Property / House**")
        new_h_name = st.text_input("New Property / Building Name (e.g. House 2)")
        if st.button("➕ Add House"):
            if new_h_name.strip():
                conn = get_db_connection()
                cursor = conn.cursor()
                try:
                    cursor.execute("INSERT INTO houses (house_name) VALUES (?)", (new_h_name.strip(),))
                    conn.commit()
                    st.success(f"Added {new_h_name} successfully!")
                except sqlite3.IntegrityError:
                    st.warning("House already exists!")
                conn.close()
                st.rerun()
                
    st.markdown("---")
    st.write("➕ **Add New Tenant to Current Month**")
    
    with st.form("add_tenant_form"):
        col_a, col_b, col_c, col_c2 = st.columns(4)
        new_h_select = col_a.selectbox("Select Property", houses_df['house_name'].tolist() if len(houses_df)>0 else ["Main House"])
        new_name = col_b.text_input("Tenant Name")
        new_mob = col_c.text_input("Mobile No")
        new_cat = col_c2.selectbox("Category", ["Residential", "Shop", "Common Utility"])
        
        col_d, col_e, col_f, col_g = st.columns(4)
        new_rent = col_d.number_input("Base Rent (₹)", min_value=0, value=3000)
        new_prev_bal = col_e.number_input("Previous Balance (₹)", min_value=0, value=0)
        new_pr = col_f.number_input("Initial P.R. Reading", min_value=0, value=0)
        new_rate = col_g.number_input("Elec Rate (₹/unit)", min_value=1, value=9 if new_cat=="Shop" else 8)
        
        new_rem = st.text_input("Remarks", value=f"{new_cat} - Rate ₹{9 if new_cat=='Shop' else 8}/unit")
        
        submitted = st.form_submit_button("➕ Add Tenant")
        if submitted and new_name.strip():
            conn = get_db_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO ledger (month_year, house_name, tenant_name, mobile_no, category, base_rent, previous_balance, pr_reading, cr_reading, elec_rate, water_charge, remarks)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, 0, ?)
                """, (selected_month, new_h_select, new_name.strip(), new_mob.strip(), new_cat, new_rent, new_prev_bal, new_pr, new_rate, new_rem))
                conn.commit()
                st.success(f"Added {new_name} to {selected_month}!")
            except sqlite3.IntegrityError:
                st.error("Tenant with this name already exists in this month!")
            conn.close()
            st.rerun()

    st.markdown("---")
    st.subheader("✏️ Edit or Delete Existing Tenant")
    st.info("Select a tenant to modify their details or delete them.")
    
    conn = get_db_connection()
    all_tenants_df = pd.read_sql_query("SELECT DISTINCT tenant_name FROM ledger ORDER BY tenant_name ASC", conn)
    conn.close()
    
    if len(all_tenants_df) > 0:
        edit_tenant_name = st.selectbox("Select Tenant to Edit / Delete", all_tenants_df['tenant_name'].tolist())
        
        # Load latest details of selected tenant
        conn = get_db_connection()
        t_info = pd.read_sql_query("SELECT * FROM ledger WHERE tenant_name = ? ORDER BY id DESC LIMIT 1", conn, params=(edit_tenant_name,)).iloc[0]
        conn.close()
        
        st.write(f"Editing Details for: **{edit_tenant_name}**")
        
        with st.form("edit_tenant_form"):
            e_col1, e_col2, e_col3 = st.columns(3)
            updated_name = e_col1.text_input("Tenant Name", value=t_info['tenant_name'])
            updated_house = e_col2.selectbox("Assigned Property/House", houses_df['house_name'].tolist() if len(houses_df)>0 else ["Main House"], index=0)
            updated_mob = e_col3.text_input("Mobile No", value=t_info.get('mobile_no', ''))
            
            e_col4, e_col5, e_col6 = st.columns(3)
            updated_cat = e_col4.selectbox("Category", ["Residential", "Shop", "Common Utility"], index=["Residential", "Shop", "Common Utility"].index(t_info['category']) if t_info['category'] in ["Residential", "Shop", "Common Utility"] else 0)
            updated_rent = e_col5.number_input("Base Rent (₹)", min_value=0, value=int(t_info['base_rent']))
            updated_rate = e_col6.number_input("Elec Rate (₹/unit)", min_value=1, value=int(t_info['elec_rate']))
            
            update_scope = st.radio("Apply Changes To:", ["Current Month Only (" + selected_month + ")", "All Ledger Months (Global Update)"])
            
            btn_save = st.form_submit_button("💾 Save Tenant Edits")
            
            if btn_save:
                conn = get_db_connection()
                cursor = conn.cursor()
                if "Current Month" in update_scope:
                    cursor.execute("""
                        UPDATE ledger
                        SET tenant_name = ?, house_name = ?, mobile_no = ?, category = ?, base_rent = ?, elec_rate = ?
                        WHERE tenant_name = ? AND month_year = ?
                    """, (updated_name.strip(), updated_house, updated_mob.strip(), updated_cat, updated_rent, updated_rate, edit_tenant_name, selected_month))
                else:
                    cursor.execute("""
                        UPDATE ledger
                        SET tenant_name = ?, house_name = ?, mobile_no = ?, category = ?, base_rent = ?, elec_rate = ?
                        WHERE tenant_name = ?
                    """, (updated_name.strip(), updated_house, updated_mob.strip(), updated_cat, updated_rent, updated_rate, edit_tenant_name))
                conn.commit()
                conn.close()
                st.success(f"Successfully updated details for {updated_name}!")
                st.rerun()
                
        # Delete Option
        with st.expander("🗑️ Delete Tenant"):
            st.warning(f"Are you sure you want to delete **{edit_tenant_name}**?")
            delete_scope = st.radio("Delete Scope:", ["Remove from Current Month Only (" + selected_month + ")", "Permanently Delete from ALL Months"])
            confirm_del = st.checkbox(f"Yes, I confirm deleting {edit_tenant_name}")
            
            if st.button("🚨 Delete Tenant Now"):
                if confirm_del:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    if "Current Month" in delete_scope:
                        cursor.execute("DELETE FROM ledger WHERE tenant_name = ? AND month_year = ?", (edit_tenant_name, selected_month))
                    else:
                        cursor.execute("DELETE FROM ledger WHERE tenant_name = ?", (edit_tenant_name,))
                    conn.commit()
                    conn.close()
                    st.success(f"Deleted {edit_tenant_name}!")
                    st.rerun()
                else:
                    st.error("Please tick the confirmation checkbox first.")
