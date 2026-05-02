import streamlit as st
import datetime
import time
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ==========================================
# 🗄️ DATABASE — Unchanged
# ==========================================

@st.cache_resource(ttl=3000)
def connect_to_sheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/spreadsheets"
    ]
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open("Khan_Transport_ERP")

def get_all_trips():
    try:
        db   = connect_to_sheet()
        data = db.worksheet("Bookings").get_all_records()
        return pd.DataFrame(data)
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
    try:
        db      = connect_to_sheet()
        records = db.worksheet("Receivables").get_all_values()
        return sum(int(float(row[4])) for row in records[1:]
                   if len(row) > 4 and row[1] == trip_id)
    except:
        return 0

@st.cache_data(ttl=60)
def get_company_shortage(trip_id):
    try:
        db      = connect_to_sheet()
        records = db.worksheet("Company_PODs").get_all_values()
        return sum(int(float(row[5])) for row in records[1:]
                   if len(row) > 5 and row[1] == trip_id)
    except:
        return 0

def save_receivable_ledgers(date_val, trip_id, gr_no, comp_name,
                             truck_no, received_amt, bank_name):
    try:
        db   = connect_to_sheet()
        desc = f"{comp_name} | {truck_no}"
        base = [str(date_val), str(trip_id), str(gr_no), desc]
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
# 🎨 CSS
# ==========================================

REC_CSS = """
<style>
/* ── Page ── */
.block-container {
    padding-top: 0.8rem !important;
    padding-bottom: 0.3rem !important;
    padding-left: 1.5rem !important;
    padding-right: 1.5rem !important;
    max-width: 98% !important;
}

h2 { font-size: 1.2rem !important; margin: 0 0 4px 0 !important; }
h3 { font-size: 0.95rem !important; margin: 4px 0 2px 0 !important; color: #003399 !important; }
h4 { font-size: 0.88rem !important; margin: 4px 0 2px 0 !important; color: #003399 !important; }

/* ── Spacing ── */
.element-container { margin-bottom: 0.12rem !important; margin-top: 0 !important; }
[data-testid="stVerticalBlock"]   { gap: 0.15rem !important; }
[data-testid="stHorizontalBlock"] { gap: 0.5rem !important; }
[data-testid="stForm"] [data-testid="stVerticalBlock"] { gap: 0.2rem !important; }

/* ── Form card ── */
[data-testid="stForm"] {
    background: #fff !important;
    border: 1px solid #dde3f0 !important;
    border-radius: 10px !important;
    padding: 12px 16px 10px 16px !important;
    box-shadow: 0 1px 5px rgba(0,0,0,0.06) !important;
}

/* ── Inputs ── */
[data-baseweb="input"] { border-radius: 6px !important; min-height: 1.75rem !important; }
[data-baseweb="input"] input {
    font-size: 0.82rem !important;
    padding: 2px 8px !important;
    min-height: 1.75rem !important;
    background: #fafafa !important;
}
[data-baseweb="input"]:focus-within {
    border-color: #003399 !important;
    box-shadow: 0 0 0 2px rgba(0,51,153,0.1) !important;
}
[data-baseweb="select"] > div:first-child {
    border-radius: 6px !important;
    min-height: 1.75rem !important;
    font-size: 0.82rem !important;
    background: #fafafa !important;
}
[data-testid="stDateInput"] input {
    font-size: 0.82rem !important;
    min-height: 1.75rem !important;
    padding: 2px 8px !important;
    border-radius: 6px !important;
}
[data-testid="stNumberInput"] [data-baseweb="input"] input {
    font-size: 0.82rem !important;
    min-height: 1.75rem !important;
}

/* ── Labels ── */
label, [data-testid="stWidgetLabel"] p {
    font-size: 0.75rem !important;
    font-weight: 700 !important;
    color: #374151 !important;
    margin-bottom: 0 !important;
    line-height: 1.1 !important;
}

/* ── Buttons ── */
[data-testid="stButton"] button {
    border-radius: 6px !important;
    min-height: 1.75rem !important;
    font-size: 0.82rem !important;
    font-weight: 600 !important;
    padding: 0 12px !important;
    border: none !important;
}
[data-testid="stButton"] button[kind="primary"] {
    background: linear-gradient(135deg, #003399, #0055cc) !important;
    color: #fff !important;
}
[data-testid="stButton"] button[kind="primary"]:hover {
    background: linear-gradient(135deg, #002277, #0044aa) !important;
    box-shadow: 0 2px 8px rgba(0,51,153,0.3) !important;
}
[data-testid="stFormSubmitButton"] button {
    background: linear-gradient(135deg, #003399, #0055cc) !important;
    color: #fff !important;
    border-radius: 6px !important;
    font-size: 0.82rem !important;
    font-weight: 600 !important;
    min-height: 1.75rem !important;
}

/* ── Alerts ── */
[data-testid="stAlert"] {
    border-radius: 6px !important;
    padding: 5px 10px !important;
    margin: 2px 0 !important;
}
[data-testid="stAlert"] p { font-size: 0.82rem !important; margin: 0 !important; }

/* ── Metrics ── */
[data-testid="metric-container"] {
    background: linear-gradient(135deg, #f0f4ff, #e8eeff) !important;
    border: 1px solid #c7d4f5 !important;
    border-radius: 8px !important;
    padding: 5px 10px !important;
}
[data-testid="stMetricValue"] { font-size: 0.9rem !important; font-weight: 700 !important; color: #003399 !important; line-height: 1.2 !important; }
[data-testid="stMetricLabel"] { font-size: 0.65rem !important; font-weight: 600 !important; color: #555 !important; }
[data-testid="stMetricDelta"] { font-size: 0.65rem !important; }

/* ── HR ── */
hr { margin: 0.3em 0 !important; border-color: #e2e8f0 !important; }

/* ── Custom cards ── */
.trip-card {
    background: linear-gradient(135deg, #f0f4ff, #e8eeff);
    border: 1px solid #c7d4f5;
    border-left: 4px solid #003399;
    border-radius: 8px;
    padding: 7px 14px;
    margin: 3px 0 5px 0;
    font-size: 0.82rem;
    line-height: 1.7;
}
.trip-card b { color: #003399; }

.section-header {
    font-size: 0.82rem;
    font-weight: 700;
    color: #003399;
    background: #f0f4ff;
    border-radius: 6px;
    padding: 4px 10px;
    margin: 6px 0 4px 0;
    border-left: 3px solid #003399;
}

.confirm-box {
    background: #fffbeb;
    border: 1.5px solid #f59e0b;
    border-radius: 8px;
    padding: 9px 14px;
    margin-bottom: 6px;
    font-size: 0.84rem;
}

.status-clear {
    background: #d1e7dd; border: 1px solid #0f5132;
    border-radius: 8px; padding: 7px 14px;
    color: #0f5132; font-weight: 700;
    font-size: 0.84rem; text-align: center;
    margin: 4px 0;
}
.status-pending {
    background: #fff3cd; border: 1px solid #ffc107;
    border-radius: 8px; padding: 7px 14px;
    color: #856404; font-weight: 700;
    font-size: 0.84rem; text-align: center;
    margin: 4px 0;
}
</style>
"""

# ==========================================
# 🖥️ MAIN PAGE
# ==========================================

def show_receivable_page():
    st.markdown(REC_CSS, unsafe_allow_html=True)
    st.header("📥 कंपनी से पैसा आया (Receivables)")

    if "rec_ck"           not in st.session_state: st.session_state.rec_ck = 0
    if "show_rec_confirm" not in st.session_state: st.session_state.show_rec_confirm = False

    c  = st.session_state.rec_ck
    df = get_all_trips()

    if df.empty:
        st.info("कोई बुकिंग नहीं मिली। पहले गाड़ी लोड करें।")
        return

    # ── Trip Selector ──
    df_last = df.iloc[::-1].copy()
    df_last['label'] = (
        "📅 " + df_last.iloc[:, 0].astype(str) + "  |  " +
        "🚛 " + df_last.iloc[:, 6].astype(str) + "  |  " +
        "🏢 " + df_last.iloc[:, 2].astype(str) + "  |  " +
        "📄 GR: " + df_last.iloc[:, 8].astype(str) + "  |  " +
        "📍 " + df_last.iloc[:, 7].astype(str)
    )

    selected = st.selectbox(
        "गाड़ी खोजें:",
        ["चुनें..."] + df_last['label'].tolist(),
        key=f"sel_rec_{c}",
        label_visibility="collapsed"
    )

    if selected == "चुनें...":
        st.info("👆 GR नंबर, गाड़ी नंबर या कंपनी का नाम टाइप करके ऊपर से गाड़ी चुनें।")
        return

    # ── Selected Trip Data ──
    row_data  = df_last[df_last['label'] == selected].iloc[0]
    trip_id   = str(row_data.iloc[14])
    truck_no  = str(row_data.iloc[6])
    comp_name = str(row_data.iloc[2])
    gr_no     = str(row_data.iloc[8]) if len(row_data) > 8 else "N/A"

    comp_total       = int(row_data.iloc[11])
    tds_amount       = int(comp_total * 0.01)
    company_shortage = get_company_shortage(trip_id)
    net_receivable   = comp_total - tds_amount - company_shortage
    ruka_hua_paisa   = int((comp_total * 0.10) // 100) * 100
    already_received = get_total_received_for_trip(trip_id)
    pending_balance  = net_receivable - already_received

    if pending_balance > ruka_hua_paisa:
        ab_kitna_milega = pending_balance - ruka_hua_paisa
        balance_msg     = "TDS, शॉर्टेज, 10% रोक काटकर"
    else:
        ab_kitna_milega = pending_balance
        balance_msg     = "सिर्फ रुका हुआ बैलेंस"

    # ── Trip Info Card ──
    st.markdown(f"""
        <div class='trip-card'>
            🚛 <b>{truck_no}</b> &nbsp;&nbsp;
            🏢 <b>{comp_name}</b> &nbsp;&nbsp;
            📄 GR: <b>{gr_no}</b> &nbsp;&nbsp;
            📍 {str(row_data.iloc[7])} &nbsp;&nbsp;
            📅 {str(row_data.iloc[0])}
        </div>
    """, unsafe_allow_html=True)

    # ── Bill Breakdown ──
    st.markdown("<div class='section-header'>📊 बिल का हिसाब</div>", unsafe_allow_html=True)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("💰 Total Bill",       f"₹{comp_total:,}")
    m2.metric("📉 TDS (1%)",         f"- ₹{tds_amount:,}")
    m3.metric("✂️ Shortage",         f"- ₹{company_shortage:,}")
    m4.metric("🔒 10% रोक",          f"- ₹{ruka_hua_paisa:,}")

    # ── Payment Status ──
    st.markdown("<div class='section-header'>💸 पेमेंट स्टेटस</div>", unsafe_allow_html=True)
    s1, s2, s3 = st.columns(3)
    s1.metric("📥 अब तक आया",     f"₹{already_received:,}")
    s2.metric("⏳ कुल बाकी",       f"₹{max(0, int(pending_balance)):,}")
    s3.metric("🟢 अब मिलेगा",     f"₹{max(0, int(ab_kitna_milega)):,}", balance_msg)

    if pending_balance <= 0:
        st.markdown("<div class='status-clear'>✅ हिसाब पूरा हो चुका है — कोई पेमेंट बाकी नहीं।</div>",
                    unsafe_allow_html=True)
        return

    st.markdown("<hr>", unsafe_allow_html=True)

    # ══════════════════════
    # FORM
    # ══════════════════════
    if not st.session_state.show_rec_confirm:
        with st.form(key=f"rec_form_{c}"):
            st.markdown("#### 💳 पेमेंट एंट्री")
            col1, col2, col3 = st.columns(3)
            with col1: rec_date     = st.date_input("📅 तारीख", datetime.date.today())
            with col2: received_amt = st.number_input("💵 अमाउंट (₹)",
                                                       min_value=0,
                                                       value=int(max(0, ab_kitna_milega)),
                                                       step=100)
            with col3: bank_name = st.selectbox("🏦 खाता",
                                                 ["N/A", "Cash", "canara bank 311",
                                                  "canara bank 41", "bob"])

            col4, col5 = st.columns([3, 1])
            with col4: remarks = st.text_input("📝 Remarks / Reference No.")
            with col5:
                st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
                submit_rec = st.form_submit_button(
                    "➡️ आगे बढ़ें", use_container_width=True)

            # Live preview
            if received_amt > 0:
                bal_after = pending_balance - received_amt
                p1, p2, p3 = st.columns(3)
                p1.metric("💵 यह पेमेंट",    f"₹{received_amt:,}")
                p2.metric("⏳ अभी बाकी",      f"₹{max(0,int(pending_balance)):,}")
                p3.metric("🔄 सेव के बाद बचेगा", f"₹{max(0,int(bal_after)):,}")

        if submit_rec:
            if received_amt <= 0:
                st.error("⚠️ कृपया Received Amount भरें!")
            elif bank_name == "N/A":
                st.error("⚠️ कृपया बैंक खाता भी चुनें!")
            elif received_amt > pending_balance:
                st.error(f"⛔ अमाउंट कुल पेंडिंग ₹{int(pending_balance):,} से ज़्यादा नहीं हो सकता।")
            else:
                st.session_state.rec_temp_data = {
                    "rec_date": rec_date, "received_amt": received_amt,
                    "bank_name": bank_name, "remarks": remarks,
                    "trip_id": trip_id, "truck_no": truck_no,
                    "comp_name": comp_name, "gr_no": gr_no
                }
                st.session_state.show_rec_confirm = True
                st.rerun()

    # ══════════════════════
    # CONFIRM BOX
    # ══════════════════════
    if st.session_state.show_rec_confirm:
        d = st.session_state.rec_temp_data
        st.markdown(f"""
            <div class='confirm-box'>
                ❓ क्या आप पक्का <b>₹{int(d['received_amt']):,}</b> की एंट्री सेव करना चाहते हैं?<br>
                <small>
                    🚛 {d['truck_no']} &nbsp;|&nbsp;
                    🏢 {d['comp_name']} &nbsp;|&nbsp;
                    🏦 {d['bank_name']} &nbsp;|&nbsp;
                    📝 {d['remarks'] or '—'}
                </small>
            </div>
        """, unsafe_allow_html=True)

        cb1, cb2 = st.columns([1, 4])
        if cb1.button("👍 हाँ, सेव करें", type="primary"):
            with st.spinner("⏳ सेव हो रहा है..."):
                row = [
                    str(d['rec_date']), str(d['trip_id']),
                    str(d['truck_no']), str(d['comp_name']),
                    int(d['received_amt']), d['bank_name'], 0, d['remarks']
                ]
                if save_receivable_to_db(row):
                    save_receivable_ledgers(
                        d['rec_date'], d['trip_id'], d['gr_no'],
                        d['comp_name'], d['truck_no'],
                        d['received_amt'], d['bank_name']
                    )
                    st.success("✅ पेमेंट सेव और खाते में अपडेट हो गई!")
                    time.sleep(1.5)
                    st.session_state.show_rec_confirm = False
                    st.session_state.rec_ck += 1
                    st.rerun()
                else:
                    st.error("❌ सेव नहीं हो पाया।")

        if cb2.button("❌ कैंसिल"):
            st.session_state.show_rec_confirm = False
            st.rerun()
