import streamlit as st
import pandas as pd
import datetime
import time
import os
from database import get_sheet_data_for_reports, save_advance_to_db, save_advance_ledgers, save_owner_adjustment

# POD सेव करने के लिए फोल्डर (अगर नहीं है तो खुद बना लेगा)
POD_DIR = "POD_Files"
if not os.path.exists(POD_DIR):
    os.makedirs(POD_DIR)

def show_pod_page():
    st.header("🧾 POD और फाइनल हिसाब (Settlement)")
    st.write("यहाँ से POD (PDF) अपलोड करें, शॉर्टेज/डिटेंशन काटें और गाड़ी वाले का फाइनल पेमेंट करें।")

    # 1. गाड़ी खोजने का सिस्टम (GR Number से)
    df_owner = get_sheet_data_for_reports("Owner_Ledger")
    if not df_owner.empty:
        df_last = df_owner.tail(100).iloc[::-1] 
        
        labels = []
        trip_ids = []
        owner_data_map = {} 
        
        for _, row in df_last.iterrows():
            try:
                t_id = str(row.iloc[1])
                gr_no = str(row.iloc[2]) 
                t_truck = str(row.iloc[3])
                t_dest = str(row.iloc[4])
                # अगर यह एंट्री 'Adjustment / Penalty' नहीं है, तभी इसे लिस्ट में दिखाएं
                if str(row.iloc[3]) != "Adjustment / Penalty":
                    try: t_freight = int(str(row.iloc[5]).replace(',', ''))
                    except: t_freight = 0
                    
                    label = f"GR: {gr_no} | 🚛 {t_truck} | 📍 {t_dest}"
                    if label not in labels: # डुप्लीकेट से बचने के लिए
                        labels.append(label)
                        trip_ids.append(t_id)
                        owner_data_map[t_id] = {
                            "gr_no": gr_no, "truck_no": t_truck, "destination": t_dest, "freight": t_freight
                        }
            except: pass
            
        selected_label = st.selectbox("🔍 गाड़ी या GR Number खोजें (टाइप करें...)", ["चुनें..."] + labels)
        
        if selected_label != "चुनें...":
            idx = labels.index(selected_label)
            selected_trip_id = trip_ids[idx]
            owner_info = owner_data_map[selected_trip_id]
            
            gr_no = owner_info["gr_no"]
            truck_no = owner_info["truck_no"]
            
            st.write("---")
            col1, col2 = st.columns([1, 1])
            
            # ==========================================
            # SECTION 1: POD PDF UPLOAD & DOWNLOAD
            # ==========================================
            with col1:
                st.markdown(f"### 📄 POD मैनेजमेंट (GR: {gr_no})")
                file_path = os.path.join(POD_DIR, f"{gr_no}.pdf")
                
                # अगर PDF पहले से सेव है
                if os.path.exists(file_path):
                    st.success("✅ इस GR Number की POD पहले से जमा है।")
                    with open(file_path, "rb") as pdf_file:
                        PDFbyte = pdf_file.read()
                    st.download_button(label="📥 POD (PDF) डाउनलोड करें / देखें",
                                       data=PDFbyte,
                                       file_name=f"POD_GR_{gr_no}.pdf",
                                       mime='application/octet-stream')
                    
                    if st.checkbox("🔄 नई POD अपलोड करें (पुरानी मिट जाएगी)"):
                        uploaded_file = st.file_uploader("नई PDF चुनें", type="pdf")
                        if uploaded_file is not None:
                            if st.button("💾 नई POD सेव करें"):
                                with open(file_path, "wb") as f:
                                    f.write(uploaded_file.getbuffer())
                                st.success("नया POD सेव हो गया!")
                                time.sleep(1)
                                st.rerun()
                else:
                    st.warning("⚠️ इस गाड़ी की POD अभी जमा नहीं हुई है!")
                    uploaded_file = st.file_uploader("पार्टी से मिली POD (PDF) अपलोड करें", type="pdf")
                    if uploaded_file is not None:
                        if st.button("💾 POD सेव करें"):
                            with open(file_path, "wb") as f:
                                f.write(uploaded_file.getbuffer())
                            st.success("POD सफलतापूर्वक सुरक्षित हो गई!")
                            time.sleep(1)
                            st.rerun()

            # ==========================================
            # SECTION 2: FINAL SETTLEMENT & PAYMENT
            # ==========================================
            with col2:
                st.markdown("### 💰 फाइनल हिसाब और पेमेंट")
                
                # भाड़ा, एडवांस और एडजस्टमेंट कैलकुलेट करना
                total_freight = owner_info["freight"]
                total_advance = 0
                total_adjustments = 0
                
                # 1. एडवांस निकालना
                df_adv = get_sheet_data_for_reports("Advances")
                if not df_adv.empty:
                    trip_advances = df_adv[df_adv.iloc[:, 1].astype(str) == selected_trip_id]
                    for _, r in trip_advances.iterrows():
                        try: total_advance += abs(int(str(r.iloc[8]).replace(',', '')))
                        except: pass
                
                # 2. पुराने शॉर्टेज/डिटेंशन निकालना
                trip_rows = df_owner[df_owner.iloc[:, 1].astype(str) == selected_trip_id]
                for _, r in trip_rows.iterrows():
                    if str(r.iloc[3]) == "Adjustment / Penalty":
                        try: total_adjustments += int(str(r.iloc[5]).replace(',', ''))
                        except: pass
                
                final_balance = (total_freight + total_adjustments) - total_advance
                
                st.info(f"**मूल भाड़ा:** ₹{total_freight:,} | **एडवांस दिया:** -₹{total_advance:,} | **पुराना एडजस्टमेंट:** ₹{total_adjustments:,}")
                
                if final_balance > 0:
                    st.metric("देना बाकी है (Final Payable)", f"₹{final_balance:,}", "पेमेंट करें ⏳", delta_color="inverse")
                elif final_balance < 0:
                    st.metric("गाड़ी वाले से लेना है (Overpaid)", f"₹{abs(final_balance):,}", "ज़्यादा चला गया", delta_color="normal")
                else:
                    st.metric("हिसाब क्लियर (Settled)", f"₹0", "पूरा पेमेंट हो गया ✅")

                st.write("---")
                st.write("**क्या कोई शॉर्टेज (कठौती) या डिटेंशन (इनाम) जोड़ना है?**")
                
                c_adj1, c_adj2 = st.columns(2)
                with c_adj1:
                    shortage_amt = st.number_input("📉 शॉर्टेज / पेनल्टी (₹ काटें)", min_value=0, step=500)
                with c_adj2:
                    detention_amt = st.number_input("📈 डिटेंशन / एक्स्ट्रा (₹ जोड़ें)", min_value=0, step=500)
                
                if shortage_amt > 0 or detention_amt > 0:
                    adj_remarks = st.text_input("विवरण (कठौती या इनाम का कारण)")
                    if st.button("⚙️ एडजस्टमेंट अपडेट करें"):
                        with st.spinner("अपडेट हो रहा है..."):
                            date_today = datetime.date.today()
                            # शॉर्टेज माइनस में जाएगा, डिटेंशन प्लस में
                            net_adjustment = detention_amt - shortage_amt 
                            if save_owner_adjustment(date_today, selected_trip_id, gr_no, net_adjustment, adj_remarks):
                                st.success("एडजस्टमेंट खाते में जुड़ गया!")
                                time.sleep(1)
                                st.rerun()

                st.write("---")
                if final_balance > 0:
                    st.write("**यहाँ से फाइनल पेमेंट करें:**")
                    with st.form("final_payment_form"):
                        pay_date = st.date_input("पेमेंट की तारीख", datetime.date.today())
                        pay_acc = st.selectbox("कहाँ से पैसा दिया?", ["Cash", "canara bank 311", "canara bank 41", "bob"])
                        pay_amt = st.number_input("कितना अमाउंट दिया?", min_value=0, max_value=final_balance, value=final_balance, step=100)
                        pay_remarks = st.text_input("विवरण (रिमार्क्स)")
                        
                        if st.form_submit_button("✅ फाइनल पेमेंट सेव करें"):
                            if pay_amt > 0:
                                # पेमेंट को 'Advance' की तरह ही सेव करेंगे ताकि लेजर में माइनस हो जाए
                                row_data = [str(pay_date), str(selected_trip_id), str(gr_no), 
                                            pay_amt if pay_acc=="Cash" else 0, 
                                            pay_amt if pay_acc!="Cash" else 0, 
                                            pay_acc if pay_acc!="Cash" else "N/A", 
                                            0, "N/A", pay_amt]
                                
                                if save_advance_to_db(row_data):
                                    save_advance_ledgers(pay_date, selected_trip_id, gr_no, "Final Settlement", 
                                                         pay_amt if pay_acc=="Cash" else 0, 
                                                         pay_amt if pay_acc!="Cash" else 0, 
                                                         pay_acc if pay_acc!="Cash" else "N/A", 0, "N/A")
                                    st.success("फाइनल पेमेंट सफलतापूर्वक सेव हो गया!")
                                    time.sleep(1)
                                    st.rerun()
                            else:
                                st.error("अमाउंट भरें!")