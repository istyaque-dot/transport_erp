import base64
import datetime as _dt
import hashlib
import hmac
import json
from typing import Optional

import streamlit as st

COOKIE_NAME = "transport_erp_login_token"
QUERY_PARAM_NAME = "auth"
COOKIE_DAYS = 30


def _secret() -> str:
    """Return cookie/query-token signing secret. Set AUTH_COOKIE_SECRET in Streamlit secrets."""
    try:
        sec = st.secrets.get("AUTH_COOKIE_SECRET", None)
        if sec:
            return str(sec)
    except Exception:
        pass
    return "transport-erp-change-this-cookie-secret"


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _b64d(txt: str) -> bytes:
    padding = "=" * (-len(txt) % 4)
    return base64.urlsafe_b64decode((txt + padding).encode("utf-8"))


def _sign(data_b64: str) -> str:
    return hmac.new(_secret().encode("utf-8"), data_b64.encode("utf-8"), hashlib.sha256).hexdigest()


def make_login_token(username: str, days: int = COOKIE_DAYS) -> str:
    exp = int((_dt.datetime.utcnow() + _dt.timedelta(days=days)).timestamp())
    payload = {"u": username, "exp": exp}
    data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    data_b64 = _b64e(data)
    sig = _sign(data_b64)
    return f"{data_b64}.{sig}"


def verify_login_token(token: Optional[str]) -> Optional[str]:
    if not token or "." not in str(token):
        return None
    try:
        data_b64, sig = str(token).split(".", 1)
        if not hmac.compare_digest(sig, _sign(data_b64)):
            return None
        payload = json.loads(_b64d(data_b64).decode("utf-8"))
        if int(payload.get("exp", 0)) < int(_dt.datetime.utcnow().timestamp()):
            return None
        username = str(payload.get("u", "")).strip()
        return username or None
    except Exception:
        return None


@st.cache_resource
def _cookie_manager():
    import extra_streamlit_components as stx
    return stx.CookieManager()


def _get_query_token() -> Optional[str]:
    """Hard-refresh safe fallback. Query params survive browser reloads."""
    try:
        val = st.query_params.get(QUERY_PARAM_NAME, None)
        if isinstance(val, list):
            return val[0] if val else None
        return val
    except Exception:
        try:
            qp = st.experimental_get_query_params()
            val = qp.get(QUERY_PARAM_NAME, [None])
            return val[0] if isinstance(val, list) else val
        except Exception:
            return None


def _set_query_token(token: str) -> None:
    try:
        st.query_params[QUERY_PARAM_NAME] = token
    except Exception:
        try:
            st.experimental_set_query_params(**{QUERY_PARAM_NAME: token})
        except Exception:
            pass


def _clear_query_token() -> None:
    try:
        if QUERY_PARAM_NAME in st.query_params:
            del st.query_params[QUERY_PARAM_NAME]
    except Exception:
        try:
            st.experimental_set_query_params()
        except Exception:
            pass


def get_login_cookie() -> Optional[str]:
    try:
        cm = _cookie_manager()
        val = cm.get(COOKIE_NAME)
        if val:
            return val
        all_cookies = cm.get_all() or {}
        return all_cookies.get(COOKIE_NAME)
    except Exception:
        return None


def set_login_cookie_token(token: str, days: int = COOKIE_DAYS) -> bool:
    try:
        cm = _cookie_manager()
        expires_at = _dt.datetime.now() + _dt.timedelta(days=days)
        cm.set(COOKIE_NAME, token, expires_at=expires_at)
        return True
    except Exception:
        return False


def set_login_cookie(username: str, days: int = COOKIE_DAYS) -> bool:
    token = make_login_token(username, days)
    _set_query_token(token)
    return set_login_cookie_token(token, days)


def clear_login_cookie() -> None:
    try:
        cm = _cookie_manager()
        cm.delete(COOKIE_NAME)
    except Exception:
        pass


def _restore_from_token(token: Optional[str]) -> bool:
    username = verify_login_token(token)
    if not username:
        return False
    st.session_state["password_correct"] = True
    st.session_state["logged_in_user"] = username
    st.session_state["login_restored_from_cookie"] = True
    # If token came from cookie, also keep it in the URL so hard refresh works instantly.
    if token:
        _set_query_token(token)
    return True


def restore_login_from_cookie() -> bool:
    """Restore login from URL token first, then browser cookie.

    Cookie components can load late in Streamlit. URL token is signed and refresh-safe,
    so hard refresh will not logout after the user logs in once.
    """
    if _restore_from_token(_get_query_token()):
        return True
    return _restore_from_token(get_login_cookie())


def login_user(username: str, remember: bool = True, days: int = COOKIE_DAYS) -> None:
    st.session_state["password_correct"] = True
    st.session_state["logged_in_user"] = username
    if remember:
        token = make_login_token(username, days)
        _set_query_token(token)
        set_login_cookie_token(token, days)


def logout_user() -> None:
    clear_login_cookie()
    _clear_query_token()
    for key in ["password_correct", "logged_in_user", "login_restored_from_cookie"]:
        try:
            del st.session_state[key]
        except Exception:
            pass
