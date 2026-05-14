"""Safe no-block action guard.

Older app versions used this module to monkey-patch Streamlit buttons. That caused
"Processing... duplicate click blocked" and uploads could get stuck.
This version intentionally does NOT monkey-patch buttons.
"""
import streamlit as st

def install_action_guard():
    return None

def clear_click_locks():
    for key in list(st.session_state.keys()):
        if str(key).startswith("_guard_") or "saving_lock" in str(key).lower() or "upload_lock" in str(key).lower():
            del st.session_state[key]
