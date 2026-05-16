
import base64
import hashlib
import hmac
import json
import time
import streamlit as st

TOKEN_DAYS = 30

def _secret() -> str:
    try:
        value = st.secrets.get("AUTH_COOKIE_SECRET", "")
    except Exception:
        value = ""
    return value or "bazpur-up-transport-erp-local-secret-change-this"

def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")

def _b64d(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("utf-8"))

def make_auth_token(username: str) -> str:
    payload = {
        "u": username,
        "exp": int(time.time()) + TOKEN_DAYS * 24 * 60 * 60,
        "v": 1,
    }
    body = _b64e(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    sig = hmac.new(_secret().encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"

def validate_auth_token(token: str):
    if not token or "." not in str(token):
        return False, None
    try:
        body, sig = str(token).split(".", 1)
        expected = hmac.new(_secret().encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return False, None
        payload = json.loads(_b64d(body).decode("utf-8"))
        if int(payload.get("exp", 0)) < int(time.time()):
            return False, None
        return True, payload.get("u")
    except Exception:
        return False, None

def read_auth_token_from_url() -> str:
    try:
        val = st.query_params.get("auth", "")
        if isinstance(val, list):
            return val[0] if val else ""
        return val or ""
    except Exception:
        try:
            params = st.experimental_get_query_params()
            val = params.get("auth", [""])
            return val[0] if isinstance(val, list) else val
        except Exception:
            return ""

def set_auth_token_in_url(token: str) -> None:
    try:
        st.query_params["auth"] = token
    except Exception:
        try:
            st.experimental_set_query_params(auth=token)
        except Exception:
            pass

def clear_auth_token_from_url() -> None:
    try:
        if "auth" in st.query_params:
            del st.query_params["auth"]
    except Exception:
        try:
            st.experimental_set_query_params()
        except Exception:
            pass
