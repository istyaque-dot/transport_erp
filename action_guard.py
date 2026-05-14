"""No-block action guard + old monkey-patch uninstaller.

This module intentionally does NOT monkey-patch Streamlit buttons.
It also restores st.button/st.form_submit_button if an older app session had installed
the previous global duplicate-click guard.
"""
from __future__ import annotations

import streamlit as st

_INSTALLED = False
_ORIGINAL_BUTTON = None
_ORIGINAL_FORM_SUBMIT_BUTTON = None

def uninstall_action_guard() -> None:
    global _INSTALLED
    # In older versions these globals existed in the already-loaded module.
    orig_btn = globals().get("_ORIGINAL_BUTTON")
    orig_form = globals().get("_ORIGINAL_FORM_SUBMIT_BUTTON")
    try:
        if orig_btn is not None:
            st.button = orig_btn
        if orig_form is not None:
            st.form_submit_button = orig_form
    except Exception:
        pass
    _INSTALLED = False

def install_action_guard() -> None:
    uninstall_action_guard()
    return None

def clear_click_locks() -> None:
    for key in list(st.session_state.keys()):
        k = str(key).lower()
        if str(key).startswith("_guard_") or "saving_lock" in k or "upload_lock" in k or "button_lock" in k:
            try:
                del st.session_state[key]
            except Exception:
                pass
