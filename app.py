import streamlit as st
import sqlite3
import pandas as pd
import urllib.parse

# Page Configuration for Mobile Responsiveness
st.set_page_config(
    page_title="Multi-Property Rent & Utility Ledger",
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
    .card-box h3, .card-box p, .card-box b, .card-box h2, .card-box i, .card-box span {
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
    
    # 1. Months Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS months (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            month_year TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 2. Properties Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS properties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            property_name TEXT UNIQUE NOT NULL,
            address TEXT
        )
    """)
    
    # 3. Ledger Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            month_year TEXT NOT NULL,
            property_name TEXT DEFAULT 'Main House',
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
            UNIQUE(month_year, property_name, tenant_name)
        )
    """)
    
    # Migrations: Add property_name and mobile_no if missing from existing database
    cursor.execute("PRAGMA table_info(ledger)")
    cols = [column[1] for column in cursor.fetchall()]
    if 'property_name' not in cols:
        cursor.execute("ALTER TABLE ledger ADD COLUMN property_name TEXT DEFAULT 'Main House'")
    if 'mobile_no' not in cols:
        cursor.execute("ALTER TABLE ledger ADD COLUMN mobile_no TEXT DEFAULT ''")
        
    # Seed Initial Properties if empty
    cursor.execute("SELECT COUNT(*) FROM properties")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO properties (property_name, address) VALUES ('Main House', 'Property 1')")
        
    # Seed Initial October 2026 Data if empty
    cursor.execute("SELECT COUNT(*) FROM months")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO months (month_year) VALUES ('October 2026')")
        
        initial_tenants = [
            ("Main House", "Gupta Ji", "9876543210", "Shop", 5000, 0, 3396, 3428, 9, 0, "Shop - Rate ₹9/unit; Water N/A"),
            ("Main House", "Ashwini", "9876543211", "Residential", 4000, 0, 6602, 6618, 8, 142, "Residential - Rate ₹8/unit; Water provisional ₹142"),
            ("Main House", "Anoop Sharma", "9876543212", "Residential", 4500, 0, 6363, None, 8, 0, "Residential - Rate ₹8/unit"),
            ("Main House", "Satish Pathak (Sarthak)", "9876543213", "Residential", 2700, 0, 1477, None, 8, 0, "Residential - Rate ₹8/unit"),
            ("Main House", "Umesh Pathak", "9876543214", "Residential", 3750, 0, 6315, None, 8, 0, "Residential - Rate ₹8/unit"),
            ("Main House", "Ramsingh Saini", "9876543215", "Shop", 5000, 0, 10379, None, 9, 0, "Shop - Rate ₹9/unit; Water N/A"),
            ("Main House", "Vinod Sharma", "9876543216", "Residential", 3750, 0, 6276, None, 8, 0, "Residential - Rate ₹8/unit"),
            ("Main House", "Submersible (Pump)", "", "Common Utility", 0, 0, 6774, None, 8, 0, "Common Utility - Rate ₹8/unit"),
            ("Main House", "Tiwari Ji", "9876543217", "Residential", 3000, 0, 4263, None, 8, 0, "Faulty Meter (मीटर खराब है)"),
            ("Main House", "Neeraj Kumar", "9876543218", "Residential", 3800, 0, 2447, None, 8, 0, "Residential - Rate ₹8/unit")
        ]
        
        for t in initial_tenants:
            cursor.execute("""
                INSERT INTO ledger (month_year, property_name, tenant_name, mobile_no, category, base_rent, previous_balance, pr_reading, cr_reading, elec_rate, water_charge, remarks)
                VALUES ('October 2026', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, t)
            
    conn.commit()
    conn.close()

init_db()

# --- SIDEBAR: NAVIGATION & CONTROLS ---
st.sidebar.title("🏢 Navigation & Controls")

conn = get_db_connection()
months_df = pd.read_sql_query("SELECT month_year FROM months ORDER BY id DESC", conn)
props_df = pd.read_sql_query("SELECT property_name FROM properties ORDER BY id ASC", conn)
conn.close()

available_months = months_df['month_year'].tolist()
available_properties = ["All Properties"] + props_df['property_name'].tolist()

selected_month = st.sidebar.selectbox("📅 Select Ledger Month", available_months)
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
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO months (month_year) VALUES (?)", (new_month_input.strip(),))
        
        prev_data = pd.read_sql_query("SELECT * FROM ledger WHERE month_year = ?", conn, params=(selected_month,))
        
        for _, row in prev_data.iterrows():
            new_pr = row['cr_reading'] if row['cr_reading'] is not None else row['pr_reading']
            prop_val = row['property_name'] if 'property_name' in row and pd.notnull(row['property_name']) else 'Main House'
            mob_val = row['mobile_no'] if 'mobile_no' in row and pd.notnull(row['mobile_no']) else ''
            
            cursor.execute("""
                INSERT INTO ledger (month_year, property_name, tenant_name, mobile_no, category, base_rent, previous_balance, pr_reading, cr_reading, elec_rate, water_charge, remarks)
                VALUES (?, ?, ?, ?, ?, ?, 0, ?, NULL, ?, ?, ?)
            """, (new_month_input.strip(), prop_val, row['tenant_name'], mob_val, row['category'], row['base_rent'], new_pr, row['elec_rate'], row['water_charge'], row['remarks']))
            
        conn.commit()
        conn.close()
        st.sidebar.success(f"Created {new_month_input}! Auto-rolled P.R. readings from {selected_month}.")
        st.rerun()

# --- MAIN APP BODY ---
st.title("🏢 Multi-Property Rent & Utility Management")
st.caption(f"Viewing Month: **{selected_month}** | Property Filter: **{selected_property}**")

# Load Current Month Ledger with Property Filter
conn = get_db_connection()
if selected_property == "All Properties":
    ledger_df = pd.read_sql_query("SELECT * FROM ledger WHERE month_year = ?", conn, params=(selected_month,))
else:
    ledger_df = pd.read_sql_query("SELECT * FROM ledger WHERE month_year = ? AND property_name = ?", conn, params=(selected_month, selected_property))
conn.close()

# Ensure columns exist
if 'property_name' not in ledger_df.columns:
    ledger_df['property_name'] = 'Main House'
if 'mobile_no' not in ledger_df.columns:
    ledger_df['mobile_no'] = ''
if 'previous_balance' not in ledger_df.columns:
    ledger_df['previous_balance'] = 0.0

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

# --- TABS FOR LEDGER, RECEIPT & MANAGEMENT ---
tab1, tab2, tab3 = st.tabs(["📝 Monthly Ledger & Meter Entry", "📱 Individual WhatsApp Receipt", "⚙️ Manage Houses & Tenants"])

with tab1:
    st.subheader(f"Ledger Table - {selected_month} ({selected_property})")
    st.info("💡 Edit Current Readings (C.R.), Mobile No, Previous Arrears, and Water Charges directly below and click 'Save Ledger Updates'.")
    
    display_df = ledger_df[['id', 'property_name', 'tenant_name', 'mobile_no', 'category', 'base_rent', 'previous_balance', 'pr_reading', 'cr_reading', 'units_consumed', 'elec_rate', 'elec_charge', 'water_charge', 'total_payable', 'remarks']].copy()
    
    edited_df = st.data_editor(
        display_df,
        column_config={
            "id": None,
            "property_name": st.column_config.TextColumn("House / Property", disabled=True),
            "tenant_name": st.column_config.TextColumn("Tenant Name", disabled=True),
            "mobile_no": st.column_config.TextColumn("Mobile No", help="Tenant mobile number for WhatsApp"),
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
        st.warning("No tenants found in this selection.")
    else:
        tenant_options = ledger_df['tenant_name'] + " (" + ledger_df['property_name'] + ")"
        selected_tenant_opt = st.selectbox("Select Tenant for Receipt", tenant_options)
        
        sel_idx = tenant_options.tolist().index(selected_tenant_opt)
        t_data = ledger_df.iloc[sel_idx]
        
        c1, c2 = st.columns([1, 1])
        
        with c1:
            prev_bal_html = f"<p><b>Previous Balance (Bakaya):</b> ₹{t_data['previous_balance']:,.0f}</p>" if t_data['previous_balance'] > 0 else ""
            mob_display = t_data['mobile_no'] if t_data['mobile_no'] else 'Not Added'
            
            st.markdown(f"""
            <div class="card-box">
                <h3 style="color: #1E3A8A !important;">🏢 RENT RECEIPT - {selected_month}</h3>
                <p><b>Property / House:</b> {t_data['property_name']}</p>
                <p><b>Tenant Name:</b> {t_data['tenant_name']} ({t_data['category']})</p>
                <p><b>Mobile No:</b> 📞 {mob_display}</p>
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
*Property:* {t_data['property_name']}
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
            
            # Direct WhatsApp Click Link
            clean_phone = "".join(filter(str.isdigit, str(t_data['mobile_no'])))
            if clean_phone:
                if not clean_phone.startswith("91") and len(clean_phone) == 10:
                    clean_phone = "91" + clean_phone
                encoded_msg = urllib.parse.quote(wa_text)
                wa_url = f"https://api.whatsapp.com/send?phone={clean_phone}&text={encoded_msg}"
                st.markdown(f'<a href="{wa_url}" target="_blank" style="display: inline-block; background-color: #25D366; color: white; padding: 10px 18px; border-radius: 8px; text-decoration: none; font-weight: bold;">💬 Open Direct WhatsApp Chat</a>', unsafe_allow_html=True)
            else:
                st.info("💡 Add tenant's mobile number to enable 1-click WhatsApp messaging.")

with tab3:
    col_p1, col_p2 = st.columns([1, 1])
    
    with col_p1:
        st.subheader("🏠 Add New House / Property")
        with st.form("add_prop_form"):
            p_name = st.text_input("Property / House Name (e.g. House 2 / Shop Complex B)")
            p_addr = st.text_input("Address / Location Notes")
            p_submit = st.form_submit_button("➕ Save Property")
            
            if p_submit and p_name.strip():
                conn = get_db_connection()
                cursor = conn.cursor()
                try:
                    cursor.execute("INSERT INTO properties (property_name, address) VALUES (?, ?)", (p_name.strip(), p_addr.strip()))
                    conn.commit()
                    st.success(f"Property '{p_name}' added successfully!")
                except sqlite3.IntegrityError:
                    st.warning("Property name already exists!")
                conn.close()
                st.rerun()
                
    with col_p2:
        st.subheader("⚙️ Add New Tenant")
        conn = get_db_connection()
        p_list = pd.read_sql_query("SELECT property_name FROM properties", conn)['property_name'].tolist()
        conn.close()
        
        with st.form("add_tenant_form"):
            t_prop = st.selectbox("Assign to Property / House", p_list if p_list else ["Main House"])
            t_name = st.text_input("Tenant Name")
            t_mob = st.text_input("Mobile Number (WhatsApp)", placeholder="e.g. 9876543210")
            t_cat = st.selectbox("Category", ["Residential", "Shop", "Common Utility"])
            t_rent = st.number_input("Base Rent (₹)", min_value=0, value=3000)
            
            col_d, col_e, col_f, col_g = st.columns(4)
            t_prev_bal = col_d.number_input("Previous Balance (₹)", min_value=0, value=0)
            t_pr = col_e.number_input("Initial P.R. Reading", min_value=0, value=0)
            t_rate = col_f.number_input("Elec Rate (₹/unit)", min_value=1, value=9 if t_cat=="Shop" else 8)
            t_rem = col_g.text_input("Remarks", value=f"{t_cat} - Rate ₹{9 if t_cat=='Shop' else 8}/unit")
            
            t_submitted = st.form_submit_button("➕ Add Tenant")
            if t_submitted and t_name.strip():
                conn = get_db_connection()
                cursor = conn.cursor()
                try:
                    cursor.execute("""
                        INSERT INTO ledger (month_year, property_name, tenant_name, mobile_no, category, base_rent, previous_balance, pr_reading, cr_reading, elec_rate, water_charge, remarks)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, 0, ?)
                    """, (selected_month, t_prop, t_name.strip(), t_mob.strip(), t_cat, t_rent, t_prev_bal, t_pr, t_rate, t_rem))
                    conn.commit()
                    st.success(f"Added {t_name} to {t_prop} in {selected_month}!")
                except sqlite3.IntegrityError:
                    st.error("Tenant with this name already exists in this property for this month!")
                conn.close()
                st.rerun()
