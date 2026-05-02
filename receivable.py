# ==========================================
# 🎨 CSS — Updated
# ==========================================

REC_CSS = """
<style>
.block-container {
    padding-top: 0.6rem !important;
    padding-bottom: 0.3rem !important;
    padding-left: 1.2rem !important;
    padding-right: 1.2rem !important;
    max-width: 98% !important;
}
h2 { font-size: 1.1rem !important; margin: 0 0 4px 0 !important; }
.element-container { margin-bottom: 0.1rem !important; margin-top: 0 !important; }
[data-testid="stVerticalBlock"]   { gap: 0.12rem !important; }
[data-testid="stHorizontalBlock"] { gap: 0.45rem !important; }
[data-testid="stForm"] [data-testid="stVerticalBlock"] { gap: 0.18rem !important; }

[data-testid="stForm"] {
    background: #fff !important;
    border: 1px solid #dde3f0 !important;
    border-radius: 10px !important;
    padding: 10px 14px 8px 14px !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.05) !important;
}

[data-baseweb="input"] { border-radius: 6px !important; min-height: 1.7rem !important; }
[data-baseweb="input"] input {
    font-size: 0.81rem !important; padding: 2px 8px !important;
    min-height: 1.7rem !important; background: #fafafa !important;
}
[data-baseweb="input"]:focus-within {
    border-color: #003399 !important;
    box-shadow: 0 0 0 2px rgba(0,51,153,0.08) !important;
}
[data-baseweb="select"] > div:first-child {
    border-radius: 6px !important; min-height: 1.7rem !important;
    font-size: 0.81rem !important; background: #fafafa !important;
}
[data-testid="stDateInput"] input {
    font-size: 0.81rem !important; min-height: 1.7rem !important;
    padding: 2px 8px !important; border-radius: 6px !important;
}
[data-testid="stNumberInput"] [data-baseweb="input"] input {
    font-size: 0.81rem !important; min-height: 1.7rem !important;
}
label, [data-testid="stWidgetLabel"] p {
    font-size: 0.73rem !important; font-weight: 700 !important;
    color: #374151 !important; margin-bottom: 0 !important; line-height: 1.1 !important;
}
[data-testid="stButton"] button {
    border-radius: 6px !important; min-height: 1.7rem !important;
    font-size: 0.81rem !important; font-weight: 600 !important;
    padding: 0 12px !important; border: none !important;
}
[data-testid="stButton"] button[kind="primary"] {
    background: linear-gradient(135deg, #003399, #0055cc) !important; color: #fff !important;
}
[data-testid="stFormSubmitButton"] button {
    background: linear-gradient(135deg, #003399, #0055cc) !important;
    color: #fff !important; border-radius: 6px !important;
    font-size: 0.81rem !important; font-weight: 600 !important; min-height: 1.7rem !important;
}
[data-testid="stAlert"] { border-radius: 6px !important; padding: 4px 10px !important; margin: 2px 0 !important; }
[data-testid="stAlert"] p { font-size: 0.8rem !important; margin: 0 !important; }

[data-testid="metric-container"] {
    background: #f8faff !important;
    border: 1px solid #dde3f0 !important;
    border-radius: 7px !important; padding: 5px 10px !important;
}
[data-testid="stMetricValue"] { font-size: 0.92rem !important; font-weight: 700 !important; color: #003399 !important; line-height: 1.2 !important; }
[data-testid="stMetricLabel"] { font-size: 0.64rem !important; font-weight: 600 !important; color: #666 !important; }
[data-testid="stMetricDelta"] { font-size: 0.64rem !important; }

hr { margin: 0.25em 0 !important; border-color: #e8edf5 !important; }

/* ── Trip info bar ── */
.trip-bar {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 6px;
    background: #f0f4ff;
    border-left: 4px solid #003399;
    border-radius: 0 8px 8px 0;
    padding: 7px 14px;
    margin: 3px 0 5px 0;
    font-size: 0.8rem;
}
.trip-chip {
    background: #fff;
    border: 1px solid #c7d4f5;
    border-radius: 20px;
    padding: 1px 10px;
    font-size: 0.76rem;
    font-weight: 700;
    color: #003399;
}

/* ── Section pill header ── */
.pill-header {
    display: inline-block;
    background: #003399;
    color: white;
    border-radius: 20px;
    padding: 2px 14px;
    font-size: 0.75rem;
    font-weight: 700;
    margin: 5px 0 3px 0;
}

/* ── Status badges ── */
.badge-green {
    background: #d1e7dd; border: 1px solid #0f5132;
    border-radius: 7px; padding: 6px 14px;
    color: #0f5132; font-weight: 700;
    font-size: 0.82rem; text-align: center; margin: 4px 0;
}
.badge-yellow {
    background: #fff3cd; border: 1px solid #ffc107;
    border-radius: 7px; padding: 6px 14px;
    color: #856404; font-weight: 700;
    font-size: 0.82rem; text-align: center; margin: 4px 0;
}

/* ── Confirm box ── */
.confirm-box {
    background: #fffbeb; border: 1.5px solid #f59e0b;
    border-radius: 8px; padding: 8px 14px;
    margin-bottom: 5px; font-size: 0.82rem; line-height: 1.6;
}
</style>
"""

# ==========================================
# 🖥️ MAIN PAGE
# ==========================================

def show_receivable_page():
    st.markdown(REC_CSS, unsafe_allow_html=True)
    st.header("📥 कंपनी से पैसा आया")

    if "rec_ck"           not in st.session_state: st.session_state.rec_ck = 0
    if "show_rec_confirm" not in st.session_state: st.session_state.show_rec_confirm = False

    c  = st.session_state.rec_ck
    df = get_all_trips()

    if df.empty:
        st.info("कोई बुकिंग नहीं मिली। पहले गाड़ी लोड करें।")
        return

    # ── Selectbox ──
    df_last = df.iloc[::-1].copy()
    df_last['label'] = (
        "📅 " + df_last.iloc[:, 0].astype(str) + "  |  🚛 " +
        df_last.iloc[:, 6].astype(str)          + "  |  🏢 " +
        df_last.iloc[:, 2].astype(str)          + "  |  GR: " +
        df_last.iloc[:, 8].astype(str)          + "  |  📍 " +
        df_last.iloc[:, 7].astype(str)
    )

    selected = st.selectbox(
        "गाड़ी खोजें:", ["चुनें..."] + df_last['label'].tolist(),
        key=f"sel_rec_{c}", label_visibility="collapsed"
    )

    if selected == "चुनें...":
        st.caption("👆 GR नंबर, गाड़ी नंबर या कंपनी टाइप करके खोजें।")
        return

    # ── Data ──
    row_data  = df_last[df_last['label'] == selected].iloc[0]
    trip_id   = str(row_data.iloc[14])
    truck_no  = str(row_data.iloc[6])
    comp_name = str(row_data.iloc[2])
    gr_no     = str(row_data.iloc[8]) if len(row_data) > 8 else "N/A"
    dest      = str(row_data.iloc[7])
    trip_date = str(row_data.iloc[0])

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
        balance_msg     = "रुका हुआ बैलेंस"

    # ── Trip Info Bar ──
    st.markdown(f"""
        <div class='trip-bar'>
            <span class='trip-chip'>🚛 {truck_no}</span>
            <span class='trip-chip'>🏢 {comp_name}</span>
            <span class='trip-chip'>📄 GR: {gr_no}</span>
            <span class='trip-chip'>📍 {dest}</span>
            <span class='trip-chip'>📅 {trip_date}</span>
        </div>
    """, unsafe_allow_html=True)

    # ── Bill Breakdown ──
    st.markdown("<div class='pill-header'>📊 बिल का हिसाब</div>", unsafe_allow_html=True)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("💰 Total Bill",  f"₹{comp_total:,}")
    m2.metric("📉 TDS (1%)",    f"- ₹{tds_amount:,}")
    m3.metric("✂️ Shortage",    f"- ₹{company_shortage:,}")
    m4.metric("🔒 10% रोक",    f"- ₹{ruka_hua_paisa:,}")

    # ── Payment Status ──
    st.markdown("<div class='pill-header'>💸 पेमेंट स्टेटस</div>", unsafe_allow_html=True)
    s1, s2, s3 = st.columns(3)
    s1.metric("📥 अब तक आया",      f"₹{already_received:,}")
    s2.metric("⏳ कुल बाकी",        f"₹{max(0, int(pending_balance)):,}")
    s3.metric("🟢 अब मिलेगा",      f"₹{max(0, int(ab_kitna_milega)):,}", balance_msg)

    if pending_balance <= 0:
        st.markdown("<div class='badge-green'>✅ हिसाब पूरा — कोई पेमेंट बाकी नहीं।</div>",
                    unsafe_allow_html=True)
        return

    st.markdown("<hr>", unsafe_allow_html=True)

    # ── Form ──
    if not st.session_state.show_rec_confirm:
        with st.form(key=f"rec_form_{c}"):
            st.markdown("<div class='pill-header'>💳 पेमेंट एंट्री</div>", unsafe_allow_html=True)
            st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

            col1, col2, col3 = st.columns(3)
            with col1: rec_date     = st.date_input("📅 तारीख", datetime.date.today())
            with col2: received_amt = st.number_input("💵 अमाउंट (₹)",
                                                       min_value=0,
                                                       value=int(max(0, ab_kitna_milega)),
                                                       step=100)
            with col3: bank_name   = st.selectbox("🏦 खाता",
                                                   ["N/A", "Cash", "canara bank 311",
                                                    "canara bank 41", "bob"])

            col4, col5 = st.columns([3, 1])
            with col4: remarks = st.text_input("📝 Remarks / Reference No.")
            with col5:
                st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
                submit_rec = st.form_submit_button("➡️ आगे बढ़ें", use_container_width=True)

            # Live preview
            if received_amt > 0:
                st.markdown("<hr>", unsafe_allow_html=True)
                p1, p2, p3 = st.columns(3)
                p1.metric("💵 यह पेमेंट",       f"₹{received_amt:,}")
                p2.metric("⏳ अभी बाकी",         f"₹{max(0,int(pending_balance)):,}")
                p3.metric("🔄 सेव के बाद बचेगा", f"₹{max(0,int(pending_balance - received_amt)):,}")

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

    # ── Confirm ──
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
