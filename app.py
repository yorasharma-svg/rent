import streamlit as st
import sqlite3
import pandas as pd
import urllib.parse

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
    .card-box h3, .card-box p, .card-box b, .card-box h2, .card-box i, .card-box hr {
        color: #0F172A !important;
        border-color: #CBD5E1 !important;
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
    
    # Create Houses/Properties Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS houses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            house_name TEXT UNIQUE NOT NULL
        )
    """)
    
    # Create Months Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS months (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            month_year TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create Ledger Table with Multi-House, Mobile No, and Previous Balance
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            month_year TEXT NOT NULL,
            house_name TEXT DEFAULT 'Main Property',
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
    
    # Seed Initial Houses
    cursor.execute("SELECT COUNT(*) FROM houses")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO houses (house_name) VALUES ('Main Property')")
        cursor.execute("INSERT INTO houses (house_name) VALUES ('Shop Complex')")
    
    # Seed Initial October 2026 Data if DB is empty
    cursor.execute("SELECT COUNT(*) FROM months")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO months (month_year) VALUES ('October 2026')")
        
        initial_tenants = [
            ("Gupta Ji", "Shop Complex", "Shop", "", 5000, 0, 3396, 3428, 9, 0, "Shop - Rate ₹9/unit; Water N/A"),
            ("Ashwini", "Main Property", "Residential", "", 4000, 0, 6602, 6618, 8, 142, "Residential - Rate ₹8/unit; Water provisional ₹142"),
            ("Anoop Sharma", "Main Property", "Residential", "", 4500, 0, 6363, None, 8, 0, "Residential - Rate ₹8/unit"),
            ("Satish Pathak (Sarthak)", "Main Property", "Residential", "", 2700, 0, 1477, None, 8, 0, "Residential - Rate ₹8/unit"),
            ("Umesh Pathak", "Main Property", "Residential", "", 3750, 0, 6315, None, 8, 0, "Residential - Rate ₹8/unit"),
            ("Ramsingh Saini", "Shop Complex", "Shop", "", 5000, 0, 10379, None, 9, 0, "Shop - Rate ₹9/unit; Water N/A"),
            ("Vinod Sharma", "Main Property", "Residential", "", 3750, 0, 6276, None, 8, 0, "Residential - Rate ₹8/unit"),
            ("Submersible (Pump)", "Main Property", "Common Utility", "", 0, 0, 6774, None, 8, 0, "Common Utility - Rate ₹8/unit"),
            ("Tiwari Ji", "Main Property", "Residential", "", 3000, 0, 4263, None, 8, 0, "Faulty Meter (मीटर खराब है)"),
            ("Neeraj Kumar", "Main Property", "Residential", "", 3800, 0, 2447, None, 8, 0, "Residential - Rate ₹8/unit")
        ]
        
        for t in initial_tenants:
            cursor.execute("""
                INSERT INTO ledger (tenant_name, house_name, category, mobile_no, base_rent, previous_balance, pr_reading, cr_reading, elec_rate, water_charge, remarks, month_year)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'October 2026')
            """, t)
            
    conn.commit()
    conn.close()

init_db()

# --- SIDEBAR: NAVIGATION, PROPERTY FILTER & MONTH CREATION ---
st.sidebar.title("🏢 Controls & Filters")

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
            new_pr = row['cr_reading'] if row['cr_reading'] is not None else row['pr_reading']
            cursor.execute("""
                INSERT INTO ledger (month_year, house_name, tenant_name, mobile_no, category, base_rent, previous_balance, pr_reading, cr_reading, elec_rate, water_charge, remarks)
                VALUES (?, ?, ?, ?, ?, ?, 0, ?, NULL, ?, ?, ?)
            """, (new_month_input.strip(), row['house_name'], row['tenant_name'], row['mobile_no'], row['category'], row['base_rent'], new_pr, row['elec_rate'], row['water_charge'], row['remarks']))
            
        conn.commit()
        conn.close()
        st.sidebar.success(f"Created {new_month_input}! Auto-rolled readings from {selected_month}.")
        st.rerun()

# --- MAIN APP BODY ---
st.title("🏢 Property Rent & Utility Management")
st.caption(f"Viewing: **{selected_month}** | Property Filter: **{selected_house_filter}**")

# Load Current Month Ledger
conn = get_db_connection()
if selected_house_filter == "All Properties / Houses":
    ledger_df = pd.read_sql_query("SELECT * FROM ledger WHERE month_year = ?", conn, params=(selected_month,))
else:
    ledger_df = pd.read_sql_query("SELECT * FROM ledger WHERE month_year = ? AND house_name = ?", conn, params=(selected_month, selected_house_filter))
conn.close()

# Computations
ledger_df['cr_reading_calc'] = ledger_df['cr_reading'].fillna(ledger_df['pr_reading'])
ledger_df['units_consumed'] = ledger_df['cr_reading_calc'] - ledger_df['pr_reading']
ledger_df['units_consumed'] = ledger_df['units_consumed'].apply(lambda x: max(0, x))
ledger_df['elec_charge'] = ledger_df['units_consumed'] * ledger_df['elec_rate']
ledger_df['total_payable'] = ledger_df['base_rent'] + ledger_df['previous_balance'] + ledger_df['elec_charge'] + ledger_df['water_charge']

# --- SUMMARY & UTILITY LIABILITY DASHBOARD ---
st.subheader("📊 Financial Summary & Utility Liability")

m1, m2, m3, m4, m5 = st.columns(5)

total_rent = ledger_df['base_rent'].sum()
total_arrears = ledger_df['previous_balance'].sum()
total_elec = ledger_df['elec_charge'].sum()
total_water = ledger_df['water_charge'].sum()
grand_total = ledger_df['total_payable'].sum()

m1.metric("🏠 Base Rent", f"₹{total_rent:,.0f}")
m2.metric("⏳ Prev. Arrears", f"₹{total_arrears:,.0f}")
m3.metric("⚡ Elec Collected", f"₹{total_elec:,.0f}", help="Electricity board payment recovery pool")
m4.metric("💧 Water Charges", f"₹{total_water:,.0f}")
m5.metric("💰 Grand Total", f"₹{grand_total:,.0f}")

st.markdown("---")

# --- TABS FOR LEDGER, RECEIPT & TENANT MANAGEMENT ---
tab1, tab2, tab3 = st.tabs(["📝 Monthly Ledger & Meter Entry", "📱 Individual WhatsApp Receipt", "⚙️ Manage Houses & Tenants Profile"])

with tab1:
    st.subheader(f"Ledger Table - {selected_month}")
    st.info("💡 Edit Current Readings (C.R.), Previous Arrears, Water Charges, and Mobile Numbers directly in the table below and click 'Save Ledger Updates'.")
    
    display_df = ledger_df[['id', 'house_name', 'tenant_name', 'mobile_no', 'category', 'base_rent', 'previous_balance', 'pr_reading', 'cr_reading', 'units_consumed', 'elec_rate', 'elec_charge', 'water_charge', 'total_payable', 'remarks']].copy()
    
    edited_df = st.data_editor(
        display_df,
        column_config={
            "id": None,
            "house_name": st.column_config.TextColumn("Property / House", disabled=True),
            "tenant_name": st.column_config.TextColumn("Tenant Name", disabled=True),
            "mobile_no": st.column_config.TextColumn("Mobile Number", help="Tenant mobile number for WhatsApp"),
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
        use_container_width=True
    )
    
    if st.button("💾 Save Ledger Updates"):
        conn = get_db_connection()
        cursor = conn.cursor()
        for _, row in edited_df.iterrows():
            cr_val = float(row['cr_reading']) if pd.notnull(row['cr_reading']) else None
            prev_bal_val = float(row['previous_balance']) if pd.notnull(row['previous_balance']) else 0.0
            water_val = float(row['water_charge']) if pd.notnull(row['water_charge']) else 0.0
            mob_val = str(row['mobile_no']).strip() if pd.notnull(row['mobile_no']) else ""
            remarks_val = str(row['remarks']) if pd.notnull(row['remarks']) else ""
            
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
    
    if len(ledger_df) == 0:
        st.warning("No tenants found for this property filter!")
    else:
        tenant_list = ledger_df['tenant_name'].tolist()
        selected_tenant = st.selectbox("Select Tenant for Receipt", tenant_list)
        
        t_data = ledger_df[ledger_df['tenant_name'] == selected_tenant].iloc[0]
        
        c1, c2 = st.columns([1, 1])
        
        with c1:
            prev_bal_html = f"<p><b>Previous Balance (Bakaya):</b> ₹{t_data['previous_balance']:,.0f}</p>" if t_data['previous_balance'] > 0 else ""
            mob_display = f" | 📞 {t_data['mobile_no']}" if t_data['mobile_no'] else ""
            
            st.markdown(f"""
            <div class="card-box">
                <h3 style="color: #1E3A8A !important;">🏢 RENT RECEIPT - {selected_month}</h3>
                <p><b>Tenant Name:</b> {t_data['tenant_name']} ({t_data['category']}){mob_display}</p>
                <p><b>Property:</b> {t_data['house_name']}</p>
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
*Tenant Name:* {t_data['tenant_name']}
*Property:* {t_data['house_name']}

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
            
            clean_phone = "".join(filter(str.isdigit, str(t_data['mobile_no']))) if t_data['mobile_no'] else ""
            if clean_phone:
                if len(clean_phone) == 10:
                    clean_phone = "91" + clean_phone
                encoded_msg = urllib.parse.quote(wa_text)
                wa_url = f"https://wa.me/{clean_phone}?text={encoded_msg}"
                st.markdown(f'<a href="{wa_url}" target="_blank"><button style="background-color: #25D366; color: white; padding: 10px 20px; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; width: 100%;">💬 Open Direct WhatsApp Chat</button></a>', unsafe_allow_html=True)
            else:
                st.caption("💡 Tip: Add mobile number in Tab 1 or Tab 3 to enable 1-Click WhatsApp Direct Chat button!")

with tab3:
    st.subheader("⚙️ Manage Houses, Tenant Profiles (Edit / Delete)")
    
    # --- SUB-SECTION 1: EDIT / DELETE EXISTING TENANTS ---
    st.markdown("### ✏️ Edit or Delete Existing Tenant")
    st.info("Select a tenant below to change their details (Name, Property, Rent, Rate, Phone) or delete them.")
    
    conn = get_db_connection()
    all_tenants_df = pd.read_sql_query("SELECT DISTINCT tenant_name FROM ledger ORDER BY tenant_name ASC", conn)
    conn.close()
    
    all_tenant_names = all_tenants_df['tenant_name'].tolist() if len(all_tenants_df) > 0 else []
    
    if len(all_tenant_names) == 0:
        st.warning("No tenants in system!")
    else:
        edit_tenant_selected = st.selectbox("Select Tenant to Edit or Delete", all_tenant_names)
        
        # Load details of selected tenant from current month ledger (or latest)
        conn = get_db_connection()
        t_curr = pd.read_sql_query("SELECT * FROM ledger WHERE tenant_name = ? AND month_year = ?", conn, params=(edit_tenant_selected, selected_month))
        if len(t_curr) == 0:
            t_curr = pd.read_sql_query("SELECT * FROM ledger WHERE tenant_name = ? ORDER BY id DESC LIMIT 1", conn, params=(edit_tenant_selected,))
        conn.close()
        
        if len(t_curr) > 0:
            t_info = t_curr.iloc[0]
            
            edit_col1, edit_col2 = st.columns(2)
            
            with edit_col1:
                st.markdown("#### 📝 Edit Tenant Details")
                with st.form("edit_tenant_form"):
                    e_name = st.text_input("Tenant Name", value=t_info['tenant_name'])
                    e_house = st.selectbox("Property / House", houses_df['house_name'].tolist(), index=houses_df['house_name'].tolist().index(t_info['house_name']) if t_info['house_name'] in houses_df['house_name'].tolist() else 0)
                    e_cat = st.selectbox("Category", ["Residential", "Shop", "Common Utility"], index=["Residential", "Shop", "Common Utility"].index(t_info['category']) if t_info['category'] in ["Residential", "Shop", "Common Utility"] else 0)
                    e_rent = st.number_input("Base Rent (₹)", min_value=0, value=int(t_info['base_rent']))
                    e_rate = st.number_input("Elec Rate (₹/unit)", min_value=1, value=int(t_info['elec_rate']))
                    e_mob = st.text_input("Mobile Number", value=str(t_info['mobile_no'] if t_info['mobile_no'] else ""))
                    
                    update_scope = st.radio("Apply Changes To:", [f"Current Month Only ({selected_month})", "All Ledger Months (Global Update)"])
                    
                    update_btn = st.form_submit_button("💾 Save Tenant Profile Updates")
                    if update_btn:
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        
                        if update_scope.startswith("Current Month Only"):
                            cursor.execute("""
                                UPDATE ledger
                                SET tenant_name = ?, house_name = ?, category = ?, base_rent = ?, elec_rate = ?, mobile_no = ?
                                WHERE tenant_name = ? AND month_year = ?
                            """, (e_name.strip(), e_house, e_cat, e_rent, e_rate, e_mob.strip(), edit_tenant_selected, selected_month))
                        else:
                            cursor.execute("""
                                UPDATE ledger
                                SET tenant_name = ?, house_name = ?, category = ?, base_rent = ?, elec_rate = ?, mobile_no = ?
                                WHERE tenant_name = ?
                            """, (e_name.strip(), e_house, e_cat, e_rent, e_rate, e_mob.strip(), edit_tenant_selected))
                            
                        conn.commit()
                        conn.close()
                        st.success(f"Updated profile for {e_name}!")
                        st.rerun()
            
            with edit_col2:
                st.markdown("#### 🗑️ Delete Tenant")
                st.warning("⚠️ Deleting a tenant will remove them from the ledger.")
                
                del_scope = st.radio("Delete Scope:", [f"Delete from {selected_month} only", "Delete permanently from ALL months"])
                confirm_del = st.checkbox(f"Yes, I really want to delete '{edit_tenant_selected}'")
                
                if st.button("🗑️ Confirm Delete Tenant"):
                    if not confirm_del:
                        st.error("Please tick the confirmation checkbox above first!")
                    else:
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        if del_scope.startswith("Delete from"):
                            cursor.execute("DELETE FROM ledger WHERE tenant_name = ? AND month_year = ?", (edit_tenant_selected, selected_month))
                        else:
                            cursor.execute("DELETE FROM ledger WHERE tenant_name = ?", (edit_tenant_selected,))
                        conn.commit()
                        conn.close()
                        st.success(f"Successfully deleted {edit_tenant_selected}!")
                        st.rerun()

    st.markdown("---")
    
    # --- SUB-SECTION 2: ADD NEW TENANT ---
    st.markdown("### ➕ Add New Tenant")
    with st.form("add_tenant_form"):
        col_a, col_b, col_c = st.columns(3)
        new_name = col_a.text_input("Tenant Name")
        new_house = col_b.selectbox("Assign Property / House", houses_df['house_name'].tolist())
        new_cat = col_c.selectbox("Category", ["Residential", "Shop", "Common Utility"])
        
        col_d, col_e, col_f, col_g, col_h = st.columns(5)
        new_rent = col_d.number_input("Base Rent (₹)", min_value=0, value=3000)
        new_prev_bal = col_e.number_input("Previous Balance (₹)", min_value=0, value=0)
        new_pr = col_f.number_input("Initial P.R. Reading", min_value=0, value=0)
        new_rate = col_g.number_input("Elec Rate (₹/unit)", min_value=1, value=9 if new_cat=="Shop" else 8)
        new_mob = col_h.text_input("Mobile Number")
        
        new_rem = st.text_input("Remarks / Notes", value=f"{new_cat} - Rate ₹{9 if new_cat=='Shop' else 8}/unit")
        
        submitted = st.form_submit_button("➕ Save New Tenant")
        if submitted and new_name.strip():
            conn = get_db_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO ledger (month_year, house_name, tenant_name, mobile_no, category, base_rent, previous_balance, pr_reading, cr_reading, elec_rate, water_charge, remarks)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, 0, ?)
                """, (selected_month, new_house, new_name.strip(), new_mob.strip(), new_cat, new_rent, new_prev_bal, new_pr, new_rate, new_rem))
                conn.commit()
                st.success(f"Added {new_name} to {selected_month}!")
            except sqlite3.IntegrityError:
                st.error("Tenant with this name already exists in this month!")
            conn.close()
            st.rerun()
            
    st.markdown("---")
    
    # --- SUB-SECTION 3: ADD NEW PROPERTY / HOUSE ---
    st.markdown("### 🏠 Add New Property / House")
    with st.form("add_house_form"):
        new_house_name = st.text_input("Property / House Name (e.g. House 2, Shop Complex B)")
        add_h_btn = st.form_submit_button("🏠 Save Property")
        if add_h_btn and new_house_name.strip():
            conn = get_db_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("INSERT INTO houses (house_name) VALUES (?)", (new_house_name.strip(),))
                conn.commit()
                st.success(f"Added property '{new_house_name.strip()}'!")
            except sqlite3.IntegrityError:
                st.error("Property with this name already exists!")
            conn.close()
            st.rerun()
