import streamlit as st
import datetime
from supabase import create_client, Client

# ==========================================
# 🚀 SUPABASE CONFIG (V2)
# ==========================================
SUPABASE_URL = "https://tsyghmvqrlxwicipkvqw.supabase.co"
SUPABASE_KEY = "sb_publishable_p0_eR7aMIL5KDvUkiwm18g_t1OtXBDv"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="Transport ERP", page_icon="🚛", layout="wide")

# ==========================================
# 🎨 GLOBAL CSS
# ==========================================
st.markdown("""
<style>
/* Sidebar styling */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #001f5b 0%, #003399 60%, #0055cc 100%) !important;
    padding-top: 0.5rem !important;
}
[data-testid="stSidebar"] * { color: white !important; }
[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,0.2) !important; }

/* Sidebar radio buttons */
[data-testid="stSidebar"] [data-testid="stRadio"] label {
    font-size: 0.82rem !important;
    font-weight: 600 !important;
    padding: 3px 0 !important;
    color: rgba(255,255,255,0.9) !important;
}
[data-testid="stSidebar"] [data-testid="stRadio"] div[data-baseweb="radio"] > label {
    background: rgba(255,255,255,0.06) !important;
    border-radius: 6px !important;
    padding: 4px 10px !important;
    margin: 1px 0 !important;
    transition: background 0.15s !important;
}
[data-testid="stSidebar"] [data-testid="stRadio"] div[data-baseweb="radio"]:has(input:checked) > label {
    background: rgba(255,255,255,0.2) !important;
    border-left: 3px solid #fff !important;
}

/* Sidebar logout button */
[data-testid="stSidebar"] [data-testid="stButton"] button {
    background: rgba(255,255,255,0.15) !important;
    color: white !important;
    border: 1px solid rgba(255,255,255,0.3) !important;
    border-radius: 6px !important;
    font-size: 0.8rem !important;
    width: 100% !important;
    min-height: 1.7rem !important;
}
[data-testid="stSidebar"] [data-testid="stButton"] button:hover {
    background: rgba(255,80,80,0.5) !important;
}

.block-container { padding-top: 0.5rem !important; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🔒 LOGIN LOGIC
# ==========================================
def check_password():
    def password_entered():
        u = st.session_state.get("username", "")
        p = st.session_state.get("password", "")
        if u == "admin" and p == "khan786":
            st.session_state["password_correct"] = True
        else:
            st.session_state["password_correct"] = False

    if st.session_state.get("password_correct", False):
        return True

    # ── Login Page UI ──
    st.markdown("""
        <div style='text-align:center; padding: 4vh 0 2vh 0;'>
            <div style='font-size:3.2rem; line-height:1;'>🚛</div>
            <div style='font-size:1.6rem; font-weight:900; color:#003399; letter-spacing:2px;'>
                BAZPUR UP TRANSPORT
            </div>
        </div>
    """, unsafe_allow_html=True)

    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        with st.form("login_form"):
            st.text_input("👤 Username", key="username")
            st.text_input("🔑 Password", type="password", key="password")
            if st.form_submit_button("🚀 Login करें"):
                password_entered()
                st.rerun()
    return False

# ==========================================
# 🖥️ MAIN APP
# ==========================================
if check_password():
    from booking import show_booking_page
    # Note: Baki pages ko bhi migrate karne ke baad yahan import karenge
    
    # ── Sidebar ──
    st.sidebar.markdown("<div style='text-align:center; font-size:1rem; font-weight:900; color:white;'>Transport ERP</div>", unsafe_allow_html=True)
    st.sidebar.markdown(f"<div style='text-align:center; font-size:0.7rem; color:white;'>📅 {datetime.date.today().strftime('%d %b %Y')}</div>", unsafe_allow_html=True)
    
    if st.sidebar.button("🚪 Logout"):
        st.session_state["password_correct"] = False
        st.rerun()

    PAGES = [
        "🏠 होम (Home)",
        "बुकिंग",
        "📊 डेटा ट्रांसफर (Admin Tools)"
    ]
    choice = st.sidebar.radio("मेन्यू", PAGES, label_visibility="collapsed")

    if choice == "🏠 होम (Home)":
        st.title("स्वागत है, इश्तियाक भाई! 👋")
        st.info("आपका सिस्टम अब Supabase (PostgreSQL) डेटाबेस पर चल रहा है।")

    elif choice == "बुकिंग":
        show_booking_page()

    elif choice == "📊 डेटा ट्रांसफर (Admin Tools)":
        st.header("🚀 Google Sheets ➡️ Supabase Migration")
        st.warning("⚠️ कृपया बटन को सिर्फ एक ही बार दबाएं।")
        
        if st.button("🔥 START: सारा डेटा ट्रांसफर करें", type="primary"):
            with st.spinner("डेटा कॉपी हो रहा है, कृपया इंतज़ार करें..."):
                import gspread
                from oauth2client.service_account import ServiceAccountCredentials
                import pandas as pd

                # Connection to Sheets
                scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive", "https://www.googleapis.com/auth/spreadsheets"]
                creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gcp_service_account"]), scope)
                db = gspread.authorize(creds).open("Khan_Transport_ERP")

                def clean_num(val):
                    try: return float(str(val).replace(',', '').strip()) if val else 0.0
                    except: return 0.0
                def clean_str(val):
                    return str(val).strip() if pd.notna(val) and str(val).lower() != "nan" else ""

                # 1. Bookings Migration
                st.write("📦 Bookings कॉपी हो रही हैं...")
                data = db.worksheet("Bookings").get_all_values()
                if len(data) > 1:
                    rows = []
                    for r in data[1:]:
                        if len(r) < 15 or not r[14]: continue
                        rows.append({
                            "date_val": clean_str(r[0]), "from_loc": clean_str(r[1]), "company": clean_str(r[2]),
                            "owner_rate": clean_num(r[3]), "comp_rate": clean_num(r[4]), "weight": clean_num(r[5]),
                            "truck_no": clean_str(r[6]), "to_loc": clean_str(r[7]), "gr_no": clean_str(r[8]),
                            "uni_amt": int(clean_num(r[9])), "comments": clean_str(r[10]), "comp_freight": int(clean_num(r[11])),
                            "owner_freight": int(clean_num(r[12])), "final_uni_amt": int(clean_num(r[13])),
                            "trip_id": clean_str(r[14]), "ish_amt": int(clean_num(r[15])),
                            "gr_link": clean_str(r[16]) if len(r)>16 and "http" in str(r[16]) else None
                        })
                    for i in range(0, len(rows), 500):
                        supabase.table("bookings").insert(rows[i:i+500]).execute()
                    st.success("✅ Bookings Transfer Complete!")

                # 2. Ledgers Migration
                ledgers = {"Company_Ledger": "company_ledger", "Owner_Ledger": "owner_ledger", "Universal_Ledger": "universal_ledger", "Ishtyaque_Ledger": "ishtyaque_ledger"}
                for s, t in ledgers.items():
                    st.write(f"📒 {s} कॉपी हो रहा है...")
                    ldata = db.worksheet(s).get_all_values()
                    if len(ldata) > 1:
                        lrows = []
                        for r in ldata[1:]:
                            if len(r) < 5: continue
                            lrows.append({
                                "date_val": clean_str(r[0]), "trip_id": clean_str(r[1]), "gr_no": clean_str(r[2]),
                                "truck_no": clean_str(r[3]), "description": clean_str(r[4]), "amount": clean_num(r[5])
                            })
                        for i in range(0, len(lrows), 500):
                            supabase.table(t).insert(lrows[i:i+500]).execute()
                    st.success(f"✅ {s} Complete!")

                st.balloons()
                st.success("🎊 सारा डेटा आ गया है! अब आप बुकिंग पेज पर जाकर चेक कर सकते हैं।")
