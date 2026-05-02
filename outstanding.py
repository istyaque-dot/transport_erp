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
def get_outstanding_data_v2():
    try:
        # 1. Fetch Bookings
        bk_res = supabase.table("bookings").select("*").execute()
        df_bk = pd.DataFrame(bk_res.data) if bk_res.data else pd.DataFrame()
        if df_bk.empty: return [], [], 0, 0

        # 2. Fetch Advances
        adv_res = supabase.table("advances").select("trip_id, amount").execute()
        df_adv = pd.DataFrame(adv_res.data)
        adv_map = df_adv.groupby("trip_id")["amount"].sum().to_dict() if not df_adv.empty else {}

        # 3. Fetch Ledgers
        own_res = supabase.table("owner_ledger").select("trip_id, amount, description").execute()
        df_own = pd.DataFrame(own_res.data)
        own_map = df_own[df_own['description'].str.contains("Final|Shortage|Extra|Detention", na=False)].groupby("trip_id")["amount"].sum().to_dict() if not df_own.empty else {}

        comp_res = supabase.table("company_ledger").select("trip_id, amount").execute()
        df_comp = pd.DataFrame(comp_res.data)
        comp_map = df_comp.groupby("trip_id")["amount"].sum().to_dict() if not df_comp.empty else {}

        lena_list, dena_list = [], []
        total_lena, total_dena = 0, 0

        for _, row in df_bk.iterrows():
            tid = str(row['trip_id'])
            
            # 🟢 Party Side
            comp_fr = float(row['comp_freight'])
            if comp_fr > 0:
                tds = comp_fr * 0.01
                c_bal = (comp_fr - tds) + comp_map.get(tid, 0)
                if c_bal > 10:
                    lena_list.append({
                        "تारीख": row['date_val'], "गाड़ी": row['truck_no'], "कंपनी": row['company'],
                        "कहाँ तक": row['to_loc'], "कुल भाड़ा": int(comp_fr), "बाकी लेना": int(c_bal)
                    })
                    total_lena += c_bal

            # 🔴 Truck Side
            own_fr = float(row['owner_freight'])
            if own_fr > 0:
                mun = float(row['uni_amt'])
                o_bal = (own_fr - mun) - adv_map.get(tid, 0) + own_map.get(tid, 0)
                if o_bal > 10:
                    dena_list.append({
                        "तारीख": row['date_val'], "गाड़ी": row['truck_no'], "कहाँ तक": row['to_loc'],
                        "कुल भाड़ा": int(own_fr), "एडवांस": int(adv_map.get(tid, 0)), "बाकी देना": int(o_bal)
                    })
                    total_dena += o_bal

        return lena_list, dena_list, total_lena, total_dena
    except Exception as e:
        st.error(f"Data Error: {e}")
        return [], [], 0, 0

# ==========================================
# 🖥️ UI DISPLAY
# ==========================================

def show_outstanding_page():
    st.header("💸 लेना और देना (Outstanding V2)")
    
    # Refresh Row
    r1, r2 = st.columns([4, 1])
    with r1: search = st.text_input("🔍 गाड़ी नंबर या कंपनी से खोजें...", placeholder="उदा. 5050 या Universal")
    with r2:
        if st.button("🔄 Refresh", use_container_width=True, type="primary"):
            st.cache_data.clear(); st.rerun()

    with st.spinner("⏳ हिसाब कैलकुलेट हो रहा है..."):
        lena, dena, t_lena, t_dena = get_outstanding_data_v2()

    # Dashboard Metrics
    m1, m2 = st.columns(2)
    m1.metric("🟢 मार्केट से लेना", f"₹{int(t_lena):,}")
    m2.metric("🔴 गाड़ी वालों को देना", f"₹{int(t_dena):,}")

    st.divider()

    t1, t2 = st.tabs(["🟢 कंपनियों से लेना है", "🔴 गाड़ी वालों को देना है"])

    with t1:
        if lena:
            df_l = pd.DataFrame(lena)
            if search:
                df_l = df_l[df_l.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)]
            st.dataframe(df_l.sort_values("تारीख", ascending=False), use_container_width=True, hide_index=True)
        else: st.success("🎉 मार्केट क्लियर है!")

    with t2:
        if dena:
            df_d = pd.DataFrame(dena)
            if search:
                df_d = df_d[df_d.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)]
            st.dataframe(df_d.sort_values("तारीख", ascending=False), use_container_width=True, hide_index=True)
        else: st.success("🎉 गाड़ी वाले क्लियर हैं!")
