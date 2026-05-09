import datetime
import streamlit as st

st.set_page_config(page_title="Transport ERP", page_icon="🚛", layout="wide")

st.markdown("""
<style>
[data-testid="stSidebar"] { background: linear-gradient(180deg, #001f5b 0%, #003399 60%, #0055cc 100%) !important; }
[data-testid="stSidebar"] * { color: white !important; }
.block-container { padding-top: 1rem !important; max-width: 98% !important; }
.erp-card { background:#f8faff; border:1px solid #dde3f0; border-left:4px solid #003399; border-radius:12px; padding:14px 18px; margin:8px 0; }
.erp-small { color:#64748b; font-size:0.86rem; }
</style>
""", unsafe_allow_html=True)


def check_password():
    if st.session_state.get("password_correct", False):
        return True

    st.markdown(
        "<div style='text-align:center; padding-top:10vh;'><div style='font-size:4rem;'>🚛</div>"
        "<h1 style='color:#003399;'>BAZPUR UP TRANSPORT</h1></div>",
        unsafe_allow_html=True,
    )
    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        with st.form("login_form_new"):
            u = st.text_input("👤 Username")
            p = st.text_input("🔑 Password", type="password")
            if st.form_submit_button("🚀 Login करें", use_container_width=True):
                if u == "admin" and p == "khan786":
                    st.session_state["password_correct"] = True
                    st.rerun()
                else:
                    st.error("❌ गलत यूजरनाम या पासवर्ड")
    return False


def safe_open_page(import_path, function_name):
    try:
        module = __import__(import_path, fromlist=[function_name])
        getattr(module, function_name)()
    except Exception as exc:
        st.error(f"Page load error: {exc}")
        st.info("पहले 🧩 Sheet Setup tab चलाएँ। अगर फिर भी error रहे तो Google Sheet tab/header mismatch check करें।")


def show_home_page():
    st.title("🚛 BAZPUR UP TRANSPORT ERP")
    st.markdown(f"**आज की तारीख:** `{datetime.date.today().strftime('%d-%m-%Y')}`")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Backend", "Google Sheets")
    c2.metric("Mode", "Live")
    c3.metric("Version", "All Tabs Update")
    c4.metric("Status", "Safe Patch")

    st.markdown("""
    <div class='erp-card'>
    <b>Active tabs:</b> Booking, Advance, POD, Receivable, Outstanding, Ledger, Dashboard, Reports,
    Day Book, Transfer, Company Hisaab, Sheet Setup.
    <br><span class='erp-small'>Supabase sync को operational flow से हटाया गया है ताकि backend mixed न रहे।</span>
    </div>
    """, unsafe_allow_html=True)

    st.subheader("Recommended first run")
    st.write("1. Sidebar से **🧩 Sheet Setup** खोलें। 2. Required Sheets Check/Create चलाएँ। 3. फिर Booking → Advance → POD → Receivable test करें।")


if check_password():
    st.sidebar.title("🚛 ERP Menu")
    if st.sidebar.button("🚪 Logout"):
        st.session_state["password_correct"] = False
        st.rerun()

    PAGES = {
        "🏠 Home": (show_home_page, None),
        "📝 Booking": ("booking", "show_booking_page"),
        "💸 Advance": ("advance", "show_advance_page"),
        "🏁 POD": ("pod", "show_pod_page"),
        "📤 Docs Upload": ("documents", "show_documents_upload_page"),
        "📥 Receivable": ("receivable", "show_receivable_page"),
        "💸 Outstanding": ("outstanding", "show_outstanding_page"),
        "📒 Ledger Hub": ("ledger", "show_ledger_page"),
        "📊 Dashboard": ("dashboard", "show_dashboard_page"),
        "📑 Reports": ("reports", "show_reports_page"),
        "📓 Day Book": ("daybook", "show_daybook_page"),
        "🔀 Transfer": ("transfer", "show_transfer_page"),
        "🏢 Company Hisaab": ("company_hisaab", "show_company_page"),
        "🧩 Sheet Setup": ("sheet_setup", "show_sheet_setup_page"),
    }

    choice = st.sidebar.radio("नेविगेशन", list(PAGES.keys()))
    target, func = PAGES[choice]
    if callable(target):
        target()
    else:
        safe_open_page(target, func)
