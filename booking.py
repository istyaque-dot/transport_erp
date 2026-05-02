import streamlit as st
import datetime
import time
import pandas as pd
import gspread
import json
from oauth2client.service_account import ServiceAccountCredentials
import requests        
import base64          
from PIL import Image 
import io              

# ==========================================
# ⚠️ Google Apps Script Web App URL
# ==========================================
WEB_APP_URL = "https://script.google.com/macros/s/AKfycbx2zpk3_Zl_7sdjNP8eZxehjt5B7TfxjPYVNxYqzGSCYjU-k55DLaWgG1E0UISE9vjE/exec"

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
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    
    client = gspread.authorize(creds)
    sheet = client.open("Khan_Transport_ERP")
    return sheet

def upload_to_drive(file_bytes, file_name):
    if file_name.lower().endswith(".pdf"): mime_type = "application/pdf"
    elif file_name.lower().endswith(".png"): mime_type = "image/png"
    else: mime_type = "image/jpeg"
        
    b64_data = base64.b64encode(file_bytes).decode('utf-8')
    payload = {"fileName": file_name, "mimeType": mime_type, "fileData": b64_data}
    
    try:
        res = requests.post(WEB_APP_URL, data=payload)
        result = res.text.strip()
        if "Error" not in result: return result
        else: return None
    except: return None

def prepare_pod_file(uploaded_files):
    if not uploaded_files: return None, None
    if len(uploaded_files) == 1 and uploaded_files[0].name.lower().endswith(".pdf"):
        return uploaded_files[0].read(), "pdf"
    
    images = []
    for file in uploaded_files:
        if file.name.lower().endswith((".jpg", ".jpeg", ".png")):
            img = Image.open(file)
            if img.mode != 'RGB': img = img.convert('RGB')
            images.append(img)
    
    if images:
        pdf_bytes = io.BytesIO()
        if len(images) == 1: images[0].save(pdf_bytes, format="PDF")
        else: images[0].save(pdf_bytes, format="PDF", save_all=True, append_images=images[1:])
        return pdf_bytes.getvalue(), "pdf"
    return None, None

def save_gr_link_to_db(trip_id, gr_url):
    try:
        db = connect_to_sheet()
        sheet = db.worksheet("Bookings")
        ids = sheet.col_values(15) 
        if trip_id in ids:
            row_index = ids.index(trip_id) + 1
            sheet.update_cell(row_index, 17, gr_url) 
            return True
    except: return False

def save_booking_to_db(row_data):
    try:
        db = connect_to_sheet()
        db.worksheet("Bookings").append_row(row_data, table_range="A1")
        return True
    except: return False

def get_all_trips():
    try:
        db = connect_to_sheet()
        data = db.worksheet("Bookings").get_all_values()
        if len(data) > 1:
            return pd.DataFrame(data[1:], columns=data[0])
        return pd.DataFrame()
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
        
        ledgers = {"Company_Ledger": int(comp_amt), "Owner_Ledger": int(owner_amt)}
        if int(uni_amt) > 0: ledgers["Universal_Ledger"] = -int(uni_amt) 
        if int(ish_amt) > 0: ledgers["Ishtyaque_Ledger"] = -int(ish_amt) 
        
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
    # 🟢 11-inch Mac के लिए Compact CSS
    st.markdown("""
        <style>
            /* टॉप पैडिंग कम करना */
            .block-container { padding-top: 1rem; padding-bottom: 1rem; }
            h2 { font-size: 1.4rem !important; margin-bottom: 0 !important; padding-bottom: 0 !important; }
            h3 { font-size: 1.1rem !important; margin-bottom: 5px !important; }
            
            /* फॉर्म के अंदर की स्पेसिंग और फॉन्ट साइज कम करना */
            div[data-testid="stForm"] > div > div { gap: 0.2rem !important; }
            .stTextInput > div > div > input, .stNumberInput > div > div > input, .stSelectbox > div > div > select { 
                padding-top: 0.1rem; padding-bottom: 0.1rem; min-height: 2.1rem; font-size: 0.9rem;
            }
            label { font-size: 0.85rem !important; font-weight: 600 !important; margin-bottom: 0.1rem !important; }
            
            /* कार्ड्स का लुक कॉम्पैक्ट करना */
            div[data-testid="metric-container"] {
                background-color: #ffffff; border: 1px solid #e0e0e0;
                padding: 5px 10px; border-radius: 8px;
                box-shadow: 0px 2px 4px rgba(0,0,0,0.05);
            }
            @media (prefers-color-scheme: dark) {
                div[data-testid="metric-container"] { background-color: #1e1e1e; border-color: #333; }
            }
            div[data-testid="stMetricValue"] { font-size: 1.2rem !important; }
            hr { margin: 0.5em 0px !important; }
        </style>
    """, unsafe_allow_html=True)

    st.header("🚛 बुकिंग मैनेजमेंट")
    
    if "bk_ck" not in st.session_state: st.session_state.bk_ck = 0
    if "show_confirm" not in st.session_state: st.session_state.show_confirm = False
    if "bk_saving_lock" not in st.session_state: st.session_state.bk_saving_lock = False
    
    c = st.session_state.bk_ck
    
    tab1, tab2, tab3 = st.tabs(["🆕 नई गाड़ी (Single)", "✏️ एडिट बुकिंग", "📑 बल्क अपलोड (Excel)"])
    
    # --- TAB 1: NAI BOOKING (SINGLE) ---
    with tab1:
        if not st.session_state.show_confirm:
            with st.form(key=f"booking_form_{c}"):
                # 🟢 4-कॉलम ग्रिड (ताकि सब कुछ 3 लाइनों में सिमट जाए)
                r1c1, r1c2, r1c3, r1c4 = st.columns(4)
                with r1c1: b_date = st.date_input("तारीख", datetime.date.today())
                with r1c2: truck_no = st.text_input("गाड़ी नंबर")
                with r1c3: from_loc = st.text_input("कहाँ से", "Kashipur")
                with r1c4: to_loc = st.text_input("कहाँ तक")

                r2c1, r2c2, r2c3, r2c4 = st.columns(4)
                with r2c1: company = st.selectbox("कंपनी", ["Universal Industries", "Other"])
                with r2c2: weight = st.number_input("माल का वज़न", min_value=0, step=1)
                with r2c3: comp_rate = st.number_input("कंपनी रेट", min_value=0, step=1)
                with r2c4: owner_rate = st.number_input("गाड़ी वाला रेट", min_value=0, step=1)

                r3c1, r3c2, r3c3, r3c4 = st.columns(4)
                with r3c1: universal_amt = st.number_input("Universal (₹)", min_value=0, value=1000, step=10)
                with r3c2: ishtyaque_amt = st.number_input("Ishtyaque (₹)", min_value=0, value=0, step=100)
                with r3c3: gr_no = st.text_input("GR Number (Optional)")
                with r3c4: comments = st.text_input("टिप्पणी")
                
                # Calculations
                comp_freight = int(weight * comp_rate) + universal_amt 
                owner_freight = int(weight * owner_rate)
                tds = int(comp_freight * 0.01)
                hold_10 = int(comp_freight * 0.10)
                advance_approx = int(owner_freight * 0.90)
                
                # 🟢 लाइव कैलकुलेशन के लिए सुंदर कार्ड्स
                st.markdown("---")
                mc1, mc2, mc3, mc4 = st.columns(4)
                mc1.metric("कुल भाड़ा", f"₹{comp_freight:,}")
                mc2.metric("एडवांस (90%)", f"₹{advance_approx:,}")
                mc3.metric("TDS (1%)", f"₹{tds:,}")
                mc4.metric("10% रोक", f"₹{hold_10:,}")
                
                st.markdown("<br>", unsafe_allow_html=True)
                submitted = st.form_submit_button("➡️ सेव करने के लिए आगे बढ़ें", use_container_width=True)
                
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
        st.markdown("### ✏️ पुरानी बुकिंग में सुधार")
        df_trips = get_all_trips()
        if not df_trips.empty:
            df_last = df_trips.tail(50).iloc[::-1]
            labels, trip_ids = [], []
            for _, row in df_last.iterrows():
                try:
                    gr_disp = str(row.iloc[8]) if pd.notna(row.iloc[8]) and str(row.iloc[8]).lower() != "nan" else "N/A"
                    labels.append(f"🚛 {row.iloc[6]} | 📅 {row.iloc[0]} | 📍 {row.iloc[7]} | GR: {gr_disp}")
                    trip_ids.append(str(row.iloc[14]))
                except: pass
            
            selected_label = st.selectbox("एडिट करने के लिए गाड़ी चुनें:", ["चुनें..."] + labels)
            if selected_label != "चुनें...":
                idx = labels.index(selected_label)
                selected_trip_id = trip_ids[idx]
                row_data = df_last[df_last.iloc[:, 14].astype(str) == selected_trip_id].iloc[0]
                
                with st.form("edit_booking_form"):
                    def s_int(val):
                        try: return int(float(val))
                        except: return 0

                    def s_str(val):
                        return str(val) if pd.notna(val) and str(val).lower() != "nan" else ""

                    current_gr = s_str(row_data.iloc[8])
                    if current_gr == "N/A": current_gr = ""

                    # 🟢 Edit फॉर्म को भी 4-कॉलम ग्रिड में सेट किया गया
                    e1, e2, e3, e4 = st.columns(4)
                    with e1: e_date = st.text_input("तारीख", s_str(row_data.iloc[0]))
                    with e2: e_truck = st.text_input("गाड़ी नंबर", s_str(row_data.iloc[6]))
                    with e3: e_from = st.text_input("कहाँ से", s_str(row_data.iloc[1]))
                    with e4: e_to = st.text_input("कहाँ तक", s_str(row_data.iloc[7]))

                    e5, e6, e7, e8 = st.columns(4)
                    with e5: e_company = st.selectbox("कंपनी", ["Universal Industries", "Other"], index=0 if str(row_data.iloc[2]) == "Universal Industries" else 1)
                    with e6: e_weight = st.number_input("माल का वज़न", value=s_int(row_data.iloc[5]), step=1)
                    with e7: e_comp_rate = st.number_input("कंपनी रेट", value=s_int(row_data.iloc[4]), step=1) 
                    with e8: e_owner_rate = st.number_input("गाड़ी वाला रेट", value=s_int(row_data.iloc[3]), step=1) 

                    e9, e10, e11, e12 = st.columns(4)
                    with e9: e_uni_amt = st.number_input("Universal (₹)", value=s_int(row_data.iloc[9]), step=10)
                    with e10: e_ish_amt = st.number_input("Ishtyaque (₹)", min_value=0, value=s_int(row_data.iloc[15]), step=100)
                    with e11: e_gr = st.text_input("GR Number", current_gr)
                    with e12: e_comments = st.text_input("टिप्पणी", s_str(row_data.iloc[10]))
                        
                    e_comp_freight = int(e_weight * e_comp_rate) + e_uni_amt
                    e_owner_freight = int(e_weight * e_owner_rate)
                    
                    st.info(f"🔄 **अपडेटेड कुल भाड़ा:** ₹{e_comp_freight:,}")
                    
                    if st.form_submit_button("💾 अपडेट करें", use_container_width=True):
                        with st.spinner("अपडेट हो रहा है..."):
                            e_final_uni = int(e_uni_amt * 0.99) if e_uni_amt > 0 else 0
                            final_gr = str(e_gr).strip() if str(e_gr).strip() else "N/A"
                            
                            updated_row = [
                                str(e_date), str(e_from), str(e_company), e_owner_rate, e_comp_rate, e_weight,
                                str(e_truck), str(e_to), final_gr, e_uni_amt, str(e_comments),
                                e_comp_freight, e_owner_freight, e_final_uni, selected_trip_id, e_ish_amt
                            ]
                            if update_booking_in_db(selected_trip_id, updated_row):
                                update_ledgers(e_date, selected_trip_id, final_gr, e_truck, e_to, e_comp_freight, e_owner_freight, e_final_uni, e_ish_amt)
                                st.success("✅ बुकिंग सफलतापूर्वक अपडेट हो गई!")
                                time.sleep(1.5)
                                st.rerun()
                            else: st.error("❌ अपडेट फेल हो गया।")

                # ==========================================
                # 🟢 GR (BILTY) UPLOAD SECTION
                # ==========================================
                st.divider()
                st.markdown("#### 📄 GR (बिल्टी) कॉपी अपलोड")
                
                existing_gr_url = ""
                if len(row_data) > 16 and pd.notna(row_data.iloc[16]) and "http" in str(row_data.iloc[16]):
                    existing_gr_url = str(row_data.iloc[16])
                    st.success("✅ इस गाड़ी की GR कॉपी सिस्टम में पहले से सुरक्षित है।")
                    st.link_button("📥 सेव की गई GR कॉपी देखें", existing_gr_url, type="secondary")
                
                gr_c1, gr_c2 = st.columns([3, 1])
                with gr_c1:
                    gr_files = st.file_uploader("GR के पेज चुनें (PDF/JPG)", type=["pdf", "jpg", "jpeg", "png"], accept_multiple_files=True, key=f"gr_up_{selected_trip_id}")
                with gr_c2:
                    st.markdown("<br>", unsafe_allow_html=True) # अलाइनमेंट के लिए
                    if st.button("🚀 अपलोड", type="primary", use_container_width=True):
                        if gr_files:
                            with st.spinner("GR की PDF सेव हो रही है..."):
                                final_bytes, file_ext = prepare_pod_file(gr_files)
                                if final_bytes:
                                    f_name = f"GR_{row_data.iloc[8]}_{row_data.iloc[6]}.{file_ext}"
                                    d_id = upload_to_drive(final_bytes, f_name)
                                    if d_id:
                                        gr_url = f"https://drive.google.com/file/d/{d_id}/view"
                                        if save_gr_link_to_db(selected_trip_id, gr_url):
                                            st.cache_data.clear()
                                            st.success("✅ GR सुरक्षित सेव हो गई!")
                                            time.sleep(2)
                                            st.rerun()
                                        else: st.error("❌ Link सेव नहीं हो पाया!")
                                    else: st.error("❌ Drive पर अपलोड फेल हो गया!")
                                else: st.error("❌ फोटो प्रोसेस करने में दिक्कत आई।")
                        else: st.error("⚠️ पहले फोटो चुनें!")

        else: st.info("कोई पुरानी बुकिंग नहीं मिली।")

    # --- TAB 3: EXCEL BULK UPLOAD ---
    with tab3:
        st.markdown("### 📑 एक्सेल फाइल से बल्क अपलोड")
        
        template_cols = [
            "Date (YYYY-MM-DD)", "From", "Company", "Owner Rate", "Company Rate",
            "Weight", "Truck No", "To", "GR No", "Universal Amt", "Comments", "Ishtyaque Profit"
        ]
        df_template = pd.DataFrame(columns=template_cols)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_template.to_excel(writer, index=False, sheet_name='BulkBooking')
        
        st.download_button(
            label="⬇️ एक्सेल टेम्पलेट डाउनलोड करें",
            data=output.getvalue(),
            file_name="Khan_Transport_Bulk_Format.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        st.divider()
        uploaded_excel = st.file_uploader("📥 अपनी भरी हुई एक्सेल शीट अपलोड करें", type=["xlsx", "xls", "csv"])
        
        if uploaded_excel is not None:
            try:
                if uploaded_excel.name.endswith('.csv'): df_upload = pd.read_csv(uploaded_excel)
                else: df_upload = pd.read_excel(uploaded_excel)
                
                st.dataframe(df_upload, use_container_width=True)
                
                if st.button("🚀 सभी गाड़ियाँ सेव करें", type="primary"):
                    success_count, error_count = 0, 0
                    with st.spinner(f"⏳ {len(df_upload)} गाड़ियाँ सेव हो रही हैं..."):
                        for index, row in df_upload.iterrows():
                            try:
                                def clean_num(val):
                                    try: return float(val) if pd.notna(val) else 0
                                    except: return 0
                                def clean_str(val): return str(val).strip() if pd.notna(val) and str(val).lower() != "nan" else ""

                                date_str = clean_str(row.get("Date (YYYY-MM-DD)", str(datetime.date.today())))
                                if not date_str: date_str = str(datetime.date.today())
                                
                                from_loc = clean_str(row.get("From", "Kashipur"))
                                company = clean_str(row.get("Company", "Other"))
                                owner_rate = clean_num(row.get("Owner Rate", 0))
                                comp_rate = clean_num(row.get("Company Rate", 0))
                                weight = clean_num(row.get("Weight", 0))
                                truck_no = clean_str(row.get("Truck No", ""))
                                to_loc = clean_str(row.get("To", ""))
                                gr_no = clean_str(row.get("GR No", "N/A"))
                                uni_amt = clean_num(row.get("Universal Amt", 0))
                                comments = clean_str(row.get("Comments", ""))
                                ish_amt = clean_num(row.get("Ishtyaque Profit", 0))
                                
                                if not truck_no or not to_loc:
                                    error_count += 1; continue 
                                
                                comp_freight = int(weight * comp_rate) + int(uni_amt)
                                owner_freight = int(weight * owner_rate)
                                final_uni_amt = int(uni_amt * 0.99) if uni_amt > 0 else 0
                                trip_id = f"TRP-{datetime.datetime.now().strftime('%y%m%d%H%M%S')}{index}" 
                                
                                row_data = [
                                    date_str, from_loc, company, owner_rate, comp_rate, weight,
                                    truck_no, to_loc, gr_no if gr_no else "N/A", int(uni_amt), comments,
                                    comp_freight, owner_freight, final_uni_amt, trip_id, int(ish_amt)
                                ]
                                
                                if save_booking_to_db(row_data):
                                    save_to_ledgers(date_str, trip_id, gr_no, truck_no, to_loc, comp_freight, owner_freight, final_uni_amt, int(ish_amt))
                                    success_count += 1
                                    time.sleep(0.5) 
                                else: error_count += 1
                            except: error_count += 1; continue
                        
                        st.cache_data.clear()
                        if success_count > 0: st.success(f"✅ {success_count} गाड़ियाँ सेव हो गईं।")
                        if error_count > 0: st.warning(f"⚠️ {error_count} लाइनों में गाड़ी नंबर या डेटा खाली था।")
            except: st.error("❌ एक्सेल फाइल पढ़ने में दिक्कत आई।")
