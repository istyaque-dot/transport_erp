import streamlit as st
import datetime
import time
import pandas as pd
import gspread
import json  # 🟢 नया जोड़ा गया है
from oauth2client.service_account import ServiceAccountCredentials

# ==========================================
# 🗄️ DATABASE FUNCTIONS
# ==========================================

@st.cache_resource(ttl=86400)
def connect_to_sheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/spreadsheets"
    ]
    # 🟢 ऑनलाइन तिजोरी (Secrets) से चाबी उठाने का कोड
    creds_dict = json.loads(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open("Khan_Transport_ERP")
    return sheet

def save_booking_to_db(row_data):
    try:
        db = connect_to_sheet()
        db.worksheet("Bookings").append_row(row_data, table_range="A1")
        return True
    except: return False

def get_all_trips():
    try:
        db = connect_to_sheet()
        data = db.worksheet("Bookings").get_all_records()
        return pd.DataFrame(data)
    except: return pd.DataFrame()

def update_booking_in_db(trip_id, updated_row):
    try:
        db = connect_to_sheet()
        sheet = db.worksheet("Bookings")
        ids = sheet.col_values(15) 
        if trip_id in ids:
            row_index = ids.index(trip_id) + 1
            sheet.update(f"A{row_index}:P{row_index}", [updated_row])
            return True
    except: return False

def save_to_ledgers(date_val, trip_id, gr_no, truck_no, dest, comp_amt, owner_amt, uni_amt, ish_amt):
    try:
        db = connect_to_sheet()
        gr = str(gr_no).strip() if str(gr_no).strip() else "N/A"
        base = [str(date_val), str(trip_id), gr, str(truck_no), str(dest)]
        
        db.worksheet("Company_Ledger").append_row(base + [int(comp_amt)], table_range="A1")
        db.worksheet("Owner_Ledger").append_row(base + [int(owner_amt)], table_range="A1")
        
        # 🟢 Profit entry ab minus (-) yani DEBIT hogi
        if int(uni_amt) > 0:
            db.worksheet("Universal_Ledger").append_row([str(date_val), str(trip_id), gr, "N/A", f"Freight: {truck_no}", -int(uni_amt)], table_range="A1")
        if int(ish_amt) > 0:
            db.worksheet("Ishtyaque_Ledger").append_row([str(date_val), str(trip_id), gr, "N/A", f"Profit: {truck_no}", -int(ish_amt)], table_range="A1")
        return True
    except: return False

def update_ledgers(date_val, trip_id, gr_no, truck_no, dest, comp_amt, owner_amt, uni_amt, ish_amt):
    try:
        db = connect_to_sheet()
        gr = str(gr_no).strip() if str(gr_no).strip() else "N/A"
        
        # Mapping amounts for update logic
        ledgers = {"Company_Ledger": int(comp_amt), "Owner_Ledger": int(owner_amt)}
        if int(uni_amt) > 0: ledgers["Universal_Ledger"] = -int(uni_amt) # 🟢 Minus for Debit
        if int(ish_amt) > 0: ledgers["Ishtyaque_Ledger"] = -int(ish_amt) # 🟢 Minus for Debit
        
        for sheet_name, amt in ledgers.items():
            ws = db.worksheet(sheet_name)
            records = ws.get_all_values()
            row_to_update = -1
            for i, row in enumerate(records):
                if len(row) > 1 and trip_id in row:
                    row_to_update = i + 1; break
            
            new_row_data = [str(date_val), str(trip_id), gr, str(truck_no), str(dest), amt]
            if sheet_name in ["Universal_Ledger", "Ishtyaque_Ledger"]:
                desc = f"Freight: {truck_no}" if sheet_name == "Universal_Ledger" else f"Profit: {truck_no}"
                new_row_data = [str(date_val), str(trip_id), gr, "N/A", desc, amt]
            
            if row_to_update != -1: 
                ws.update(f"A{row_to_update}:F{row_to_update}", [new_row_data])
            else: 
                ws.append_row(new_row_data, table_range="A1")
        return True
    except: return False

# ==========================================
# 🖥️ USER INTERFACE (बुकिंग पेज)
# ==========================================

def show_booking_page():
    st.markdown("""
        <style>
            div[data-testid="stForm"] > div > div { gap: 0.5rem; }
            .stTextInput > div > div > input, .stNumberInput > div > div > input, .stSelectbox > div > div > select { padding-top: 0.25rem; padding-bottom: 0.25rem; }
            .stMarkdown p { margin-bottom: 0.2rem; }
        </style>
    """, unsafe_allow_html=True)

    st.header("🚛 बुकिंग (नई गाड़ी / एडिट)")
    
    if "bk_ck" not in st.session_state: st.session_state.bk_ck = 0
    if "show_confirm" not in st.session_state: st.session_state.show_confirm = False
    if "bk_saving_lock" not in st.session_state: st.session_state.bk_saving_lock = False
    
    c = st.session_state.bk_ck
    tab1, tab2 = st.tabs(["🆕 नई गाड़ी लगाएँ", "✏️ बुकिंग एडिट करें"])
    
    # --- TAB 1: NAI BOOKING ---
    with tab1:
        if not st.session_state.show_confirm:
            with st.form(key=f"booking_form_{c}"):
                col1, col2 = st.columns(2)
                with col1:
                    b_date = st.date_input("तारीख", datetime.date.today())
                    from_loc = st.text_input("कहाँ से", "Kashipur")
                    company = st.selectbox("कंपनी", ["Universal Industries", "Other"])
                    weight = st.number_input("माल का वज़न", min_value=0, step=1)
                    comp_rate = st.number_input("कंपनी रेट", min_value=0, step=1)
                    universal_amt = st.number_input("Universal (₹)", min_value=0, value=1000, step=10)
                with col2:
                    truck_no = st.text_input("गाड़ी नंबर")
                    to_loc = st.text_input("कहाँ तक")
                    gr_no = st.text_input("GR Number (Optional)")
                    owner_rate = st.number_input("गाड़ी वाला रेट", min_value=0, step=1)
                    comments = st.text_input("टिप्पणी (Comments)")
                    ishtyaque_amt = st.number_input("Ishtyaque Profit (₹)", min_value=0, value=0, step=100)
                    
                comp_freight = int(weight * comp_rate) + universal_amt 
                owner_freight = int(weight * owner_rate)
                tds = int(comp_freight * 0.01)
                hold_10 = int(comp_freight * 0.10)
                advance_approx = int(owner_freight * 0.90)
                
                st.info(f"📊 **कुल भाड़ा (Universal जोड़कर):** ₹{comp_freight:,} | 📉 **TDS (1%):** ₹{tds:,} | 🔒 **10% रोक:** ₹{hold_10:,}")
                st.success(f"➡️ **गाड़ी वाले का एडवांस (90%):** ₹{advance_approx:,}")
                
                submitted = st.form_submit_button("➡️ आगे बढ़ें (Next)")
                
                if submitted:
                    if not truck_no or not to_loc:
                        st.error("⚠️ गाड़ी नंबर और कहाँ तक (Destination) भरना ज़रूरी है!")
                    else:
                        st.session_state.temp_data = {
                            "b_date": b_date, "from_loc": from_loc, "company": company,
                            "weight": weight, "comp_rate": comp_rate, "universal_amt": universal_amt,
                            "truck_no": truck_no, "to_loc": to_loc, "gr_no": gr_no,
                            "owner_rate": owner_rate, "comments": comments, "ishtyaque_amt": ishtyaque_amt,
                            "comp_freight": comp_freight, "owner_freight": owner_freight
                        }
                        st.session_state.show_confirm = True
                        st.rerun()

        if st.session_state.show_confirm:
            d = st.session_state.temp_data
            st.warning(f"❓ क्या आप पक्का **गाड़ी {d['truck_no']}** की बुकिंग सेव करना चाहते हैं?")
            
            c1, c2 = st.columns([1, 4])
            if c1.button("👍 हाँ, सेव करें", type="primary"):
                if st.session_state.bk_saving_lock:
                    st.toast("⏳ प्रोसेस हो रहा है...")
                else:
                    st.session_state.bk_saving_lock = True
                    with st.spinner("⏳ डेटा सेव हो रहा है..."):
                        trip_id = f"TRP-{datetime.datetime.now().strftime('%y%m%d%H%M%S')}"
                        final_uni_amt = int(d['universal_amt'] * 0.99) if d['universal_amt'] > 0 else 0
                        row_data = [
                            str(d['b_date']), str(d['from_loc']), str(d['company']), d['owner_rate'], d['comp_rate'], d['weight'],
                            str(d['truck_no']), str(d['to_loc']), str(d['gr_no']) if d['gr_no'] else "N/A", d['universal_amt'], str(d['comments']),
                            d['comp_freight'], d['owner_freight'], final_uni_amt, trip_id, d['ishtyaque_amt']
                        ]
                        if save_booking_to_db(row_data):
                            save_to_ledgers(d['b_date'], trip_id, d['gr_no'], d['truck_no'], d['to_loc'], d['comp_freight'], d['owner_freight'], final_uni_amt, d['ishtyaque_amt'])
                            st.success(f"✅ गाड़ी {d['truck_no']} की बुकिंग सेव हो गई!")
                            time.sleep(1.5)
                            st.session_state.bk_saving_lock = False
                            st.session_state.show_confirm = False
                            st.session_state.bk_ck += 1 
                            st.rerun()
                        else:
                            st.session_state.bk_saving_lock = False
                            st.error("❌ बुकिंग सेव नहीं हो पाई।")

            if c2.button("❌ कैंसिल"):
                st.session_state.show_confirm = False
                st.rerun()

    # --- TAB 2: EDIT BOOKING ---
    with tab2:
        st.markdown("### ✏️ पुरानी बुकिंग में सुधार करें")
        df_trips = get_all_trips()
        if not df_trips.empty:
            df_last = df_trips.tail(50).iloc[::-1]
            labels = []
            trip_ids = []
            for _, row in df_last.iterrows():
                try:
                    labels.append(f"📅 {row.iloc[0]} | 🚛 {row.iloc[6]} | 📍 {row.iloc[7]} | 🆔 {row.iloc[14]}")
                    trip_ids.append(str(row.iloc[14]))
                except: pass
            
            selected_label = st.selectbox("एडिट करने के लिए गाड़ी चुनें:", ["चुनें..."] + labels)
            if selected_label != "चुनें...":
                idx = labels.index(selected_label)
                selected_trip_id = trip_ids[idx]
                row_data = df_last[df_last.iloc[:, 14].astype(str) == selected_trip_id].iloc[0]
                
                with st.form("edit_booking_form"):
                    
                    # 🟢 सुरक्षा कवच (Empty Cell Fix)
                    def s_int(val):
                        try: return int(float(val))
                        except: return 0

                    c1, c2 = st.columns(2)
                    with c1:
                        e_date = st.text_input("तारीख", str(row_data.iloc[0]))
                        e_from = st.text_input("कहाँ से", str(row_data.iloc[1]))
                        e_company = st.selectbox("कंपनी", ["Universal Industries", "Other"], index=0 if str(row_data.iloc[2]) == "Universal Industries" else 1)
                        e_weight = st.number_input("माल का वज़न", value=s_int(row_data.iloc[5]), step=1)
                        e_comp_rate = st.number_input("कंपनी रेट", value=s_int(row_data.iloc[4]), step=1) 
                        e_uni_amt = st.number_input("Universal (₹)", value=s_int(row_data.iloc[9]), step=10)
                    with c2:
                        e_truck = st.text_input("गाड़ी नंबर", str(row_data.iloc[6]))
                        e_to = st.text_input("कहाँ तक", str(row_data.iloc[7]))
                        e_gr = st.text_input("GR Number", str(row_data.iloc[8]))
                        e_owner_rate = st.number_input("गाड़ी वाला रेट", value=s_int(row_data.iloc[3]), step=1) 
                        e_comments = st.text_input("टिप्पणी", str(row_data.iloc[10]))
                        e_ish_amt = st.number_input("Ishtyaque Profit (₹)", min_value=0, value=s_int(row_data.iloc[15]), step=100)
                        
                    e_comp_freight = int(e_weight * e_comp_rate) + e_uni_amt
                    e_owner_freight = int(e_weight * e_owner_rate)
                    st.info(f"🔄 **अपडेटेड कुल भाड़ा:** ₹{e_comp_freight:,}")
                    
                    if st.form_submit_button("💾 अपडेट करें"):
                        with st.spinner("अपडेट हो रहा है..."):
                            e_final_uni = int(e_uni_amt * 0.99) if e_uni_amt > 0 else 0
                            updated_row = [
                                str(e_date), str(e_from), str(e_company), e_owner_rate, e_comp_rate, e_weight,
                                str(e_truck), str(e_to), str(e_gr), e_uni_amt, str(e_comments),
                                e_comp_freight, e_owner_freight, e_final_uni, selected_trip_id, e_ish_amt
                            ]
                            if update_booking_in_db(selected_trip_id, updated_row):
                                update_ledgers(e_date, selected_trip_id, e_gr, e_truck, e_to, e_comp_freight, e_owner_freight, e_final_uni, e_ish_amt)
                                st.success("✅ बुकिंग सफलतापूर्वक अपडेट हो गई!")
                                time.sleep(1.5)
                                st.rerun()
                            else: st.error("❌ अपडेट फेल हो गया।")
        else: st.info("कोई पुरानी बुकिंग नहीं मिली।")
