import streamlit as st
import pandas as pd
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
# 🗄️ DATA FETCHING & LOGIC
# ==========================================

@st.cache_data(ttl=60)
def get_outstanding_data():
    try:
        # 1. Fetch Bookings (Base Data)
        bk_res = supabase.table("bookings").select("*").execute()
        df_bk = pd.DataFrame(bk_res.data) if bk_res.data else pd.DataFrame()
        
        if df_bk.empty: return [], [], 0, 0

        # 2. Fetch Advances (Summary)
        adv_res = supabase.table("advances").select("trip_id, amount").execute()
        df_adv = pd.DataFrame(adv_res.data)
        adv_map = df_adv.groupby("trip_id")["amount"].sum().to_dict() if not df_adv.empty else {}

        # 3. Fetch Owner Ledger (Settlements)
        own_res = supabase.table("owner_ledger").select("trip_id, amount, description").execute()
        df_own = pd.DataFrame(own_res.data)
        # सिर्फ वो एंट्रीज जो फाइनल हिसाब या शॉर्टेज से जुड़ी हैं
        df_own_filt = df_own[df_own['description'].str.contains("Final|Shortage|Extra|Detention", na=False)]
        own_map = df_own_filt.groupby("trip_id")["amount"].sum().to_dict() if not df_own_filt.empty else {}

        # 4. Fetch Company Ledger (Settlements & Receivables)
        comp_res = supabase.table("company_ledger").select("trip_id, amount").execute()
        df_comp = pd.DataFrame(comp_res.data)
        comp_map = df_comp.groupby("trip_id")["amount"].sum().to_dict() if not df_comp.empty else {}

        lena_list, dena_list = [], []
        total_lena, total_dena = 0, 0

        for _, row in df_bk.iterrows():
            tid = str(row['trip_id'])
            
            # --- 🟢 PARTY SE LENA HAI (Company) ---
            comp_fr = float(row['comp_freight'])
            if comp_fr > 0:
                tds = comp_fr * 0.01
                expected = comp_fr - tds
                # Company Ledger me sari entries ka sum (received payment is already negative there)
                c_bal = expected + comp_map.get(tid, 0)
                if c_bal > 10:
                    lena_list.append({
                        "तारीख": row['date_val'], "गाड़ी": row['truck_no'], "कंपनी": row['company'],
                        "कहाँ तक": row['to_loc'], "कुल भाड़ा": int(comp_fr), "बाकी लेना": int(c_bal)
                    })
                    total_lena += c_bal

            # --- 🔴 TRUCK KO DENA HAI (Owner) ---
            own_fr = float(row['owner_freight'])
            if own_fr > 0:
                munshiyana = float(row['uni_amt'])
                adv_given = adv_map.get(tid, 0)
                own_settle = own_map.get(tid, 0)
                
                # Formula: (कुल - मुंशीयाना) - एडवांस + लेजर एडजस्टमेंट
                o_bal = (own_fr - munshiyana) - adv_given + own_settle
                if o_bal > 10:
                    dena_list.append({
                        "तारीख": row['date_val'], "गाड़ी": row['truck_no'], "कहाँ तक": row['to_loc'],
                        "कुल भाड़ा": int(own_fr), "एडवांस": int(adv_given), "बाकी देना": int(o_bal)
                    })
                    total_dena += o_bal

        return lena_list, dena_list, total_lena, total_dena
    except Exception as e:
        st.error(f"Error: {e}")
        return [], [], 0, 0

# ==========================================
# 🖥️ UI DISPLAY
# ==========================================

def show_outstanding_page():
    st.header("💸 लेना और देना (Outstanding V2)")
    st.write("मार्केट से लेना और गाड़ी वालों को देना - पूरा हिसाब यहाँ देखें।")

    if st.button("🔄 हिसाब रिफ्रेश करें", type="primary"):
        st.cache_data.clear()
        st.rerun()

    with st.spinner("⏳ डेटाबेस से लाइव हिसाब जोड़ा जा रहा है..."):
        lena, dena, t_lena, t_dena = get_outstanding_data()

    # Dashboard Metrics
    c1, c2 = st.columns(2)
    c1.metric("🟢 मार्केट से कुल लेना है", f"₹ {int(t_lena):,}")
    c2.metric("🔴 गाड़ी वालों को कुल देना है", f"₹ {int(t_dena):,}")

    st.divider()

    t1, t2 = st.tabs(["🏢 कंपनियों से लेना है", "🚛 गाड़ी वालों को देना है"])

    with t1:
        if lena:
            df_l = pd.DataFrame(lena).sort_values("तारीख", ascending=False)
            st.dataframe(df_l, use_container_width=True, hide_index=True)
            st.download_button("📥 पार्टी लिस्ट डाउनलोड (CSV)", df_l.to_csv(index=False), "Party_Dues.csv")
        else:
            st.success("🎉 मार्केट में कोई पैसा बाकी नहीं है!")

    with t2:
        if dena:
            df_d = pd.DataFrame(dena).sort_values("तारीख", ascending=False)
            st.dataframe(df_d, use_container_width=True, hide_index=True)
            st.download_button("📥 गाड़ी लिस्ट डाउनलोड (CSV)", df_d.to_csv(index=False), "Truck_Dues.csv")
        else:
            st.success("🎉 सब क्लियर है! किसी गाड़ी का बकाया नहीं है।")
