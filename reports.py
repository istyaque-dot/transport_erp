import streamlit as st
import pandas as pd
import datetime
from supabase import create_client, Client

# ==========================================
# 🚀 SUPABASE CONFIG
# ==========================================
SUPABASE_URL = "https://tsyghmvqrlxwicipkvqw.supabase.co"
SUPABASE_KEY = "sb_publishable_p0_eR7aMIL5KDvUkiwm18g_t1OtXBDv"

@st.cache_resource
def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase: Client = init_supabase()

# ==========================================
# 🗄️ DATABASE QUERIES (Supabase)
# ==========================================

@st.cache_data(ttl=10)
def get_ledger_data(table_name, start_date, end_date):
    try:
        res = supabase.table(table_name).select("*")\
            .gte("date_val", str(start_date))\
            .lte("date_val", str(end_date))\
            .order("date_val", desc=True).execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except: return pd.DataFrame()

@st.cache_data(ttl=10)
def get_trip_passbook(trip_id):
    try:
        # 1. Booking Info
        bk = supabase.table("bookings").select("*").eq("trip_id", trip_id).single().execute()
        # 2. Advance History
        adv = supabase.table("advances").select("*").eq("trip_id", trip_id).execute()
        # 3. Settlement History
        ledg = supabase.table("owner_ledger").select("*").eq("trip_id", trip_id).execute()
        return bk.data, adv.data, ledg.data
    except: return None, [], []

# ==========================================
# 🖥️ USER INTERFACE
# ==========================================

def show_reports_page():
    st.header("📑 बिज़नेस रिपोर्ट्स (V2 Superfast)")
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🏦 खाता स्टेटमेंट", 
        "🚚 सिंगल गाड़ी हिसाब", 
        "📅 आज का काम", 
        "💸 आज की पेमेंट्स", 
        "📄 डॉक्यूमेंट प्रिंट"
    ])

    # --- TAB 1: Ledger Report ---
    with tab1:
        st.markdown("### 📊 लेजर स्टेटमेंट")
        c1, c2, c3 = st.columns(3)
        with c1: account = st.selectbox("खाता चुनें:", ["bank_ledgers", "company_ledger", "owner_ledger", "ishtyaque_ledger", "universal_ledger"])
        with c2: s_date = st.date_input("कब से?", datetime.date.today().replace(day=1))
        with c3: e_date = st.date_input("कब तक?", datetime.date.today())

        if st.button("📊 स्टेटमेंट दिखाएं"):
            df = get_ledger_data(account, s_date, e_date)
            if not df.empty:
                # Bank account filter if table is bank_ledgers
                if account == "bank_ledgers":
                    st.write("बैंक वाइज फिल्टर उपलब्ध है")
                
                total = df['amount'].sum()
                st.metric("कुल बैलेंस (इस अवधि का)", f"₹{int(total):,}")
                st.dataframe(df[['date_val', 'description', 'amount', 'truck_no', 'gr_no']], use_container_width=True)
                st.download_button("📥 Excel डाउनलोड", df.to_csv(index=False), f"{account}.csv")
            else: st.warning("इस अवधि में कोई डेटा नहीं मिला।")

    # --- TAB 2: SINGLE TRIP PASSBOOK ---
    with tab3:
        st.markdown("### 🚚 गाड़ी का पक्का हिसाब (WhatsApp Ready)")
        # Get last 50 bookings for dropdown
        res_bk = supabase.table("bookings").select("trip_id, truck_no, gr_no, date_val").order("created_at", desc=True).limit(50).execute()
        options = [f"🚛 {r['truck_no']} | GR: {r['gr_no']} | ID: {r['trip_id']}" for r in res_bk.data]
        selected = st.selectbox("गाड़ी चुनें:", ["चुनें..."] + options)

        if selected != "चुनें...":
            tid = selected.split("ID: ")[1]
            bk, advs, ledg = get_trip_passbook(tid)
            
            if bk:
                # Basic Math
                total_fr = int(bk['owner_freight'])
                munshiyana = int(bk['weight'])
                total_adv = sum(a['amount'] for a in advs)
                total_adj = sum(l['amount'] for l in ledg if "Final" in l['description'] or "Shortage" in l['description'])
                rem = (total_fr - munshiyana) - total_adv + total_adj

                # Display
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("कुल भाड़ा", f"₹{total_fr:,}")
                c2.metric("मुंशीयाना", f"-₹{munshiyana:,}")
                c3.metric("कुल एडवांस", f"₹{total_adv:,}")
                c4.metric("बाकी बकाया", f"₹{rem:,}")

                # WhatsApp Message Builder
                msg = f"*गाड़ी का हिसाब*\n" \
                      f"गाड़ी: {bk['truck_no']} | GR: {bk['gr_no']}\n" \
                      f"भाड़ा: ₹{total_fr:,} | मुंशी: ₹{munshiyana:,}\n" \
                      f"एडवांस: ₹{total_adv:,}\n" \
                      f"*बाकी: ₹{rem:,}*"
                st.text_area("WhatsApp के लिए कॉपी करें:", msg, height=150)

    # --- TAB 4: Today's Work ---
    with tab4:
        st.subheader("💸 आज के लेन-देन (Cash/Bank Outflow)")
        t_date = st.date_input("तारीख चुनें", datetime.date.today(), key="pay_rep")
        if st.button("🔄 पेमेंट्स लोड करें"):
            # Combined query for Daybook and Bank Ledgers for that day
            res = supabase.table("bank_ledgers").select("*").eq("date_val", str(t_date)).execute()
            if res.data:
                df_p = pd.DataFrame(res.data)
                st.error(f"आज का कुल आउटफ्लो: ₹{abs(df_p[df_p['amount'] < 0]['amount'].sum()):,}")
                st.dataframe(df_p, use_container_width=True)
            else: st.info("आज कोई ट्रांजेक्शन नहीं हुआ।")

    # --- TAB 5: GR & POD Print ---
    with tab5:
        st.subheader("🖨️ GR और POD लिंक सर्च")
        gr_input = st.text_input("GR नंबर दर्ज करें:")
        if gr_input:
            # Query by GR No
            res_gr = supabase.table("bookings").select("*").eq("gr_no", gr_input).execute()
            if res_gr.data:
                r = res_gr.data[0]
                st.success(f"गाड़ी {r['truck_no']} का डेटा मिल गया!")
                if r['gr_link']: st.link_button("📄 GR कॉपी देखें", r['gr_link'])
                
                # Search for POD in ledger
                res_pod = supabase.table("owner_ledger").select("description").eq("trip_id", r['trip_id']).ilike("description", "%POD Link%").execute()
                if res_pod.data:
                    url = res_pod.data[0]['description'].replace("POD Link:", "").strip()
                    st.link_button("🏁 POD कॉपी देखें", url)
            else: st.error("GR नंबर नहीं मिला।")
