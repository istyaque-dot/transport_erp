import datetime
import sys
import streamlit as st

try:
    from auth_utils import login_user, logout_user, restore_login_from_cookie
except Exception:
    login_user = logout_user = restore_login_from_cookie = None

# FORCE UNINSTALL old global button guard if Streamlit process reused old module.
# Old action_guard monkey-patched st.button and caused: "Processing... duplicate click blocked".
_old_guard = sys.modules.get("action_guard")
if _old_guard is not None:
    try:
        _orig_btn = getattr(_old_guard, "_ORIGINAL_BUTTON", None)
        _orig_form = getattr(_old_guard, "_ORIGINAL_FORM_SUBMIT_BUTTON", None)
        if _orig_btn is not None:
            st.button = _orig_btn
        if _orig_form is not None:
            st.form_submit_button = _orig_form
        setattr(_old_guard, "_INSTALLED", False)
    except Exception:
        pass

# Clear old lock keys on every run so upload/save buttons do not remain stuck.
for _k in list(st.session_state.keys()):
    _lk = str(_k).lower()
    if str(_k).startswith("_guard_") or "saving_lock" in _lk or "upload_lock" in _lk or "button_lock" in _lk:
        try:
            del st.session_state[_k]
        except Exception:
            pass

st.set_page_config(page_title="Transport ERP", page_icon="🚛", layout="wide")

st.markdown("""
<style>
[data-testid="stSidebar"] { background: linear-gradient(180deg, #001f5b 0%, #003399 60%, #0055cc 100%) !important; }
[data-testid="stSidebar"] * { color: white !important; }
.block-container { padding-top: 1rem !important; max-width: 98% !important; }
.erp-hero {
    background: linear-gradient(135deg, #0b2a6f 0%, #0757c9 58%, #00a3ff 100%);
    border-radius: 22px;
    padding: 26px 30px;
    color: white;
    margin-bottom: 18px;
    box-shadow: 0 16px 36px rgba(0, 31, 91, 0.18);
}
.erp-hero h1 { margin:0; font-size:2.25rem; letter-spacing:-0.04rem; color:white !important; }
.erp-hero p { margin:8px 0 0 0; color:#dbeafe !important; font-size:1rem; }
.erp-card {
    background:#ffffff;
    border:1px solid #e5eaf3;
    border-radius:18px;
    padding:18px 18px;
    margin:8px 0;
    box-shadow:0 8px 22px rgba(15, 23, 42, 0.06);
}
.erp-card-title { font-size:1.05rem; font-weight:800; margin-bottom:4px; color:#111827; }
.erp-card-sub { font-size:0.86rem; color:#64748b; }
.erp-section-title { font-size:1.25rem; font-weight:800; margin:18px 0 6px 0; color:#111827; }
.stButton > button {
    border-radius:14px !important;
    min-height:46px;
    font-weight:700 !important;
}
</style>
""", unsafe_allow_html=True)


def check_password():
    # 1) Normal Streamlit session login
    if st.session_state.get("password_correct", False):
        return True

    # 2) Hard refresh / browser reload login restore
    # This uses auth_utils.py cookie/query-token logic. If package is missing, app still shows login.
    if restore_login_from_cookie is not None:
        try:
            if restore_login_from_cookie():
                return True
        except Exception:
            pass

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
            remember = st.checkbox("Login याद रखें", value=True)
            if st.form_submit_button("🚀 Login करें", use_container_width=True):
                if u == "admin" and p == "khan786":
                    if login_user is not None:
                        try:
                            login_user("admin", remember=remember, days=30)
                        except Exception:
                            st.session_state["password_correct"] = True
                    else:
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


def go_to_page(page_name):
    # Do not modify the sidebar radio key after the radio widget is created.
    # Store the requested page in a temporary key and apply it before rendering the radio on rerun.
    st.session_state["pending_page_choice"] = page_name


def show_home_page():
    today = datetime.date.today().strftime('%d-%m-%Y')
    st.markdown(f"""
    <div class='erp-hero'>
        <h1>🚛 BAZPUR UP TRANSPORT ERP</h1>
        <p>आज की तारीख: <b>{today}</b></p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<div class='erp-section-title'>Quick Actions</div>", unsafe_allow_html=True)
    q1, q2, q3 = st.columns(3)
    with q1:
        if st.button("📝 New Booking", use_container_width=True):
            go_to_page("📝 Booking")
            st.rerun()
        if st.button("📸 Quick POD Upload", use_container_width=True):
            go_to_page("📸 Quick POD Upload")
            st.rerun()
    with q2:
        if st.button("💸 Advance Entry", use_container_width=True):
            go_to_page("💸 Advance")
            st.rerun()
        if st.button("📥 Receivable", use_container_width=True):
            go_to_page("📥 Receivable")
            st.rerun()
    with q3:
        if st.button("🏁 POD Settlement", use_container_width=True):
            go_to_page("🏁 POD")
            st.rerun()
        if st.button("📑 Reports", use_container_width=True):
            go_to_page("📑 Reports")
            st.rerun()

    st.markdown("<div class='erp-section-title'>Main Work Flow</div>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown("<div class='erp-card'><div class='erp-card-title'>1. Booking</div><div class='erp-card-sub'>Trip entry और GR detail</div></div>", unsafe_allow_html=True)
    with c2:
        st.markdown("<div class='erp-card'><div class='erp-card-title'>2. Advance</div><div class='erp-card-sub'>Driver/party advance entry</div></div>", unsafe_allow_html=True)
    with c3:
        st.markdown("<div class='erp-card'><div class='erp-card-title'>3. POD / Docs</div><div class='erp-card-sub'>POD, GR, bill copy upload</div></div>", unsafe_allow_html=True)
    with c4:
        st.markdown("<div class='erp-card'><div class='erp-card-title'>4. Hisaab</div><div class='erp-card-sub'>Receivable, ledger, report</div></div>", unsafe_allow_html=True)


if check_password():
    st.sidebar.title("🚛 ERP Menu")
    if st.sidebar.button("🚪 Logout"):
        if logout_user is not None:
            try:
                logout_user()
            except Exception:
                st.session_state["password_correct"] = False
        else:
            st.session_state["password_correct"] = False
        st.rerun()

    with st.sidebar.expander("⚙️ Safety", expanded=False):
        if st.button("🔓 Button/Upload Lock Reset", use_container_width=True):
            for k in list(st.session_state.keys()):
                if str(k).startswith("_guard_") or "saving_lock" in str(k).lower() or "upload_lock" in str(k).lower():
                    del st.session_state[k]
            st.success("Locks reset हो गए।")

    PAGES = {
        "🏠 Home": (show_home_page, None),
        "📝 Booking": ("booking", "show_booking_page"),
        "💸 Advance": ("advance", "show_advance_page"),
        "🏁 POD": ("pod", "show_pod_page"),
        "📸 Quick POD Upload": ("quick_pod_upload", "show_quick_pod_upload_page"),
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

    if "page_choice" not in st.session_state or st.session_state["page_choice"] not in PAGES:
        st.session_state["page_choice"] = "🏠 Home"

    pending_page = st.session_state.pop("pending_page_choice", None)
    if pending_page in PAGES:
        st.session_state["page_choice"] = pending_page

    choice = st.sidebar.radio("नेविगेशन", list(PAGES.keys()), key="page_choice")
    target, func = PAGES[choice]
    if callable(target):
        target()
    else:
        safe_open_page(target, func)
