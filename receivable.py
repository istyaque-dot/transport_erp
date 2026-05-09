import streamlit as st
import datetime
import time
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# ==========================================
# 🗄️ DATABASE — Google Sheets Connection
# ==========================================

@st.cache_resource(ttl=3000)
def connect_to_sheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/spreadsheets"
    ]
    creds_dict = json.loads(st.secrets["gcp_service_account"]) if isinstance(st.secrets["gcp_service_account"], str) else dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open("Khan_Transport_ERP")

def get_all_trips():
    try:
        db   = connect_to_sheet()
        # Header के साथ सारा डेटा उठाना
        data = db.worksheet("Bookings").get_all_values()
        if len(data) > 1:
            return pd.DataFrame(data[1:], columns=data[0])
        return pd.DataFrame()
    except:
        return pd.DataFrame()

def save_receivable_to_db(row_data):
    try:
        connect_to_sheet().worksheet("Receivables").append_row(row_data, table_range="A1")
        st.cache_data.clear()
        return True
    except:
        return False

@st.cache_data(ttl=60)
def get_total_received_for_trip(trip_id):
    """एक ट्रिप के लिए अब तक कितना पेमेंट आया है"""
    try:
        db      = connect_to_sheet()
        records = db.worksheet("Receivables").get_all_values()
        return sum(int(float(str(row[4]).replace(',', '') or 0)) for row in records[1:]
                   if len(row) > 4 and str(row[1]).strip() == str(trip_id).strip())
    except:
        return 0

@st.cache_data(ttl=60)
def get_company_shortage(trip_id):
    """कंपनी की शॉर्टेज (कटौती) निकालना"""
    try:
        db      = connect_to_sheet()
        records = db.worksheet("Company_PODs").get_all_values()
        return sum(int(float(str(row[5]).replace(',', '') or 0)) for row in records[1:]
                   if len(row) > 5 and str(row[1]).strip() == str(trip_id).strip())
    except:
        return 0

def save_receivable_ledgers(date_val, trip_id, gr_no, comp_name, truck_no, received_amt, bank_name):
    try:
        db   = connect_to_sheet()
        desc = f"Comp Payment: {comp_name} | {truck_no}"
        base = [str(date_val), str(trip_id), str(gr_no), desc]
        
        # बैंक खाते की मैपिंग
        s_name = {
            "Cash":            "Cash_Ledger",
            "canara bank 311": "Canara_311_Ledger",
            "canara bank 41":  "Canara_41_Ledger",
            "bob":             "BOB_Ledger"
        }.get(bank_name)
        
        if s_name:
            db.worksheet(s_name).append_row(base + [int(received_amt)], table_range="A1")
        st.cache_data.clear()
        return True
    except:
        return False

# ==========================================
# 🏢 GET COMPANY BALANCE & DOCS LOGIC (पुरानी लिस्ट के लिए)
# ==========================================
@st.cache_data(ttl=60)
def get_company_receivable_and_docs():
    try:
        db = connect_to_sheet()
        bk_data = db.worksheet("Bookings").get_all_values()
        owner_data = db.worksheet("Owner_Ledger").get_all_values()
        
        # सभी POD लिंक निकाल लें
        pod_dict = {}
        if len(owner_data) > 1:
            for r in owner_data[1:]:
                if len(r) > 4 and "POD Link:" in str(r[4]):
                    trip_id = str(r[1]).strip()
                    pod_dict[trip_id] = str(r[4]).replace("POD Link:", "").strip()
                
        receivable_list = []
        if len(bk_data) > 1:
            for r in bk_data[1:]:
                if len(r) > 14:
                    trip_id = str(r[14]).strip()
                    
                    # कंपनी का भाड़ा निकालना
                    comp_freight = 0
                    try: 
                        comp_freight = float(str(r[11]).replace(',', ''))
                    except: 
                        try: comp_freight = float(str(r[5]).replace(',', '')) * float(str(r[10]).replace(',', ''))
                        except: pass
                    
                    # GR लिंक निकालना
                    gr_link = str(r[16]).strip() if len(r) > 16 and "http" in str(r[16]) else None
                    pod_link = pod_dict.get(trip_id, None)
                    
                    receivable_list.append({
                        "तारीख": str(r[0]),
                        "GR नंबर": str(r[8]),
                        "गाड़ी नंबर": str(r[6]),
                        "कहाँ तक": str(r[7]),
                        "कंपनी का भाड़ा (₹)": int(comp_freight),
                        "GR (बिल्टी)": gr_link,
                        "POD (रिसीविंग)": pod_link
                    })
        return receivable_list[::-1] 
    except Exception as e:
        return []

# ==========================================
# 🎨 CSS
# ==========================================

REC_CSS = """
<style>
.block-container { padding-top: 0.8rem !important; max-width: 98% !important; }
h2 { font-size: 1.2rem !important; margin-bottom: 4px !important; }
[data-testid="stForm"] { background: #fff !important; border: 1px solid #dde3f0 !important; border-radius: 10px !important; padding: 15px !important; }
.trip-card { background: linear-gradient(135deg, #f0f4ff, #e8eeff); border-left: 4px solid #003399; border-radius: 8px; padding: 10px; margin-bottom: 10px; font-size: 0.85rem; }
.section-header { font-size: 0.85rem; font-weight: 700; color: #003399; background: #f0f4ff; padding: 5px 10px; border-radius: 5px; margin-top: 10px; }
.status-clear { background: #d1e7dd; border: 1px solid #0f5132; border-radius: 8px; padding: 10px; color: #0f5132; font-weight: bold; text-align: center; }
</style>
"""

# ==========================================
# 🖥️ MAIN PAGE
# ==========================================

def show_receivable_page():
    st.markdown(REC_CSS, unsafe_allow_html=True)
    st.header("📥 कंपनी रिसीवेबल (Company Payments)")

    # 🟢 2 टैब बनाए गए हैं
    tab1, tab2 = st.tabs(["💳 1. नई पेमेंट की एंट्री करें", "📄 2. कंपनी का बैलेंस और बिल्टी डाउनलोड"])

    # --- TAB 1: PAYMENT ENTRY (आपका बनाया हुआ एडवांस सिस्टम) ---
    with tab1:
        if "rec_ck" not in st.session_state: st.session_state.rec_ck = 0
        if "show_rec_confirm" not in st.session_state: st.session_state.show_rec_confirm = False

        c  = st.session_state.rec_ck
        df = get_all_trips()

        if df.empty:
            st.info("कोई बुकिंग नहीं मिली। पहले गाड़ी लोड करें।")
        else:
            # ── Trip Selector ──
            df_last = df.iloc[::-1].copy()
            df_last['label'] = (
                "📅 " + df_last.iloc[:, 0].astype(str) + "  |  " +
                "🚛 " + df_last.iloc[:, 6].astype(str) + "  |  " +
                "🏢 " + df_last.iloc[:, 2].astype(str) + "  |  " +
                "📄 GR: " + df_last.iloc[:, 8].astype(str)
            )

            selected = st.selectbox("गाड़ी खोजें:", ["चुनें..."] + df_last['label'].tolist(), key=f"sel_rec_{c}", label_visibility="collapsed")
            if selected == "चुनें...":
                st.info("👆 ऊपर से गाड़ी चुनें जिसका पेमेंट आया है।")
            else:
                # ── Selected Trip Data ──
                row_data  = df_last[df_last['label'] == selected].iloc[0]
                trip_id   = str(row_data.iloc[14]).strip()
                truck_no  = str(row_data.iloc[6])
                comp_name = str(row_data.iloc[2])
                gr_no     = str(row_data.iloc[8])

                try:
                    comp_total = int(float(str(row_data.iloc[11]).replace(',', '') or 0)) # Total Freight
                except: comp_total = 0
                
                tds_amount       = int(comp_total * 0.01)
                company_shortage = get_company_shortage(trip_id)
                ruka_hua_paisa   = int((comp_total * 0.10) // 100) * 100 # 10% रोक
                
                net_receivable   = comp_total - tds_amount - company_shortage
                already_received = get_total_received_for_trip(trip_id)
                pending_balance  = net_receivable - already_received

                ab_kitna_milega = max(0, pending_balance - ruka_hua_paisa) if pending_balance > ruka_hua_paisa else pending_balance

                # ── UI Display ──
                st.markdown(f"<div class='trip-card'>🚛 <b>{truck_no}</b> | 🏢 {comp_name} | 📍 {row_data.iloc[7]} | 📅 {row_data.iloc[0]}</div>", unsafe_allow_html=True)

                st.markdown("<div class='section-header'>📊 बिल और पेमेंट समरी</div>", unsafe_allow_html=True)
                col_m1, col_m2, col_m3, col_m4 = st.columns(4)
                col_m1.metric("💰 Total Bill", f"₹{comp_total:,}")
                col_m2.metric("📉 TDS (1%) + Shortage", f"- ₹{tds_amount + company_shortage:,}")
                col_m3.metric("📥 अब तक आया", f"₹{already_received:,}")
                col_m4.metric("⏳ बाकी बैलेंस", f"₹{max(0, pending_balance):,}")

                if pending_balance <= 0:
                    st.markdown("<div class='status-clear'>✅ हिसाब पूरा हो चुका है।</div>", unsafe_allow_html=True)
                else:
                    st.markdown("<hr>", unsafe_allow_html=True)

                    # ── Entry Form ──
                    if not st.session_state.show_rec_confirm:
                        with st.form(key=f"rec_form_{c}"):
                            st.markdown("#### 💳 पेमेंट एंट्री दर्ज करें")
                            c1, c2, c3 = st.columns(3)
                            with c1: rec_date = st.date_input("तारीख", datetime.date.today())
                            with c2: amount_in = st.number_input("अमाउंट (₹)", min_value=0, value=int(ab_kitna_milega), step=100)
                            with c3: bank_name = st.selectbox("खाता", ["N/A", "Cash", "canara bank 311", "canara bank 41", "bob"])
                            
                            remark = st.text_input("Remarks / Ref No.")
                            if st.form_submit_button("➡️ सेव करने के लिए आगे बढ़ें", use_container_width=True):
                                if amount_in <= 0 or bank_name == "N/A":
                                    st.error("⚠️ कृपया सही अमाउंट और बैंक चुनें!")
                                else:
                                    st.session_state.rec_temp_data = {
                                        "date": rec_date, "amt": amount_in, "bank": bank_name, "rem": remark,
                                        "tid": trip_id, "truck": truck_no, "comp": comp_name, "gr": gr_no
                                    }
                                    st.session_state.show_rec_confirm = True
                                    st.rerun()

                    # ── Confirm Box ──
                    if st.session_state.show_rec_confirm:
                        d = st.session_state.rec_temp_data
                        st.warning(f"❓ क्या आप ₹{int(d['amt']):,} का पेमेंट **{d['bank']}** में सेव करना चाहते हैं?")
                        ca1, ca2 = st.columns([1, 4])
                        if ca1.button("👍 हाँ", type="primary"):
                            with st.spinner("सेव हो रहा है..."):
                                row = [str(d['date']), d['tid'], d['truck'], d['comp'], int(d['amt']), d['bank'], 0, d['rem']]
                                if save_receivable_to_db(row):
                                    save_receivable_ledgers(d['date'], d['tid'], d['gr'], d['comp'], d['truck'], d['amt'], d['bank'])
                                    st.success("✅ पेमेंट सेव हो गई!"); time.sleep(1.5)
                                    st.session_state.show_rec_confirm = False
                                    st.session_state.rec_ck += 1; st.rerun()
                        if ca2.button("❌ कैंसिल"):
                            st.session_state.show_rec_confirm = False; st.rerun()

    # --- TAB 2: COMPANY RECEIVABLE LIST & DOCS (पुरानी लिस्ट) ---
    with tab2:
        st.write("यहाँ से आप चेक कर सकते हैं कि किस गाड़ी का कितना भाड़ा कंपनी से लेना बाकी है, और उनके GR/POD लिंक डाउनलोड कर सकते हैं।")
        
        with st.spinner("डेटा लोड हो रहा है..."):
            company_data = get_company_receivable_and_docs()
            
            if company_data:
                df_comp = pd.DataFrame(company_data)
                
                st.dataframe(
                    df_comp,
                    column_config={
                        "तारीख": st.column_config.TextColumn("तारीख", width="small"),
                        "GR नंबर": st.column_config.TextColumn("GR नंबर", width="small"),
                        "गाड़ी नंबर": st.column_config.TextColumn("गाड़ी नंबर", width="medium"),
                        "कहाँ तक": st.column_config.TextColumn("कहाँ तक", width="medium"),
                        "कंपनी का भाड़ा (₹)": st.column_config.NumberColumn("कंपनी भाड़ा (₹)", format="₹%d", width="small"),
                        "GR (बिल्टी)": st.column_config.LinkColumn("📄 GR कॉपी", display_text="📥 Download GR"),
                        "POD (रिसीविंग)": st.column_config.LinkColumn("🏁 POD कॉपी", display_text="📥 Download POD")
                    },
                    hide_index=True,
                    use_container_width=True
                )
            else:
                st.info("🟢 कोई डेटा नहीं मिला।")
