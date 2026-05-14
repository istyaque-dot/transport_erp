"""Global click / save guard for Streamlit.

Purpose:
- Give immediate feedback after any save/upload/submit/update click.
- Block repeated clicks for a short cooldown window so duplicate rows/files are not saved.
- Works without changing every page: app.py installs a monkey patch once.
"""
from __future__ import annotations

import hashlib
import inspect
import time
from typing import Any, Callable

import streamlit as st

_INSTALLED = False
_ORIGINAL_BUTTON: Callable[..., Any] | None = None
_ORIGINAL_FORM_SUBMIT_BUTTON: Callable[..., Any] | None = None

# Labels containing these words are treated as write/actions and get a longer lock.
WRITE_KEYWORDS = (
    "save", "saved", "submit", "upload", "update", "create", "transfer", "final", "payment",
    "entry", "delete", "remove", "approve", "settle", "settlement",
    "सेव", "सबमिट", "अपलोड", "अपडेट", "बन", "क्रिएट", "ट्रांसफर", "फाइनल",
    "पेमेंट", "एंट्री", "डिलीट", "हट", "अप्रूव", "सेटल",
)

# Read/navigation buttons get only a very small lock so the UI still feels responsive.
READ_KEYWORDS = (
    "refresh", "load", "show", "search", "login", "open", "download", "report", "statement",
    "रिफ्रेश", "लोड", "दिख", "खोज", "लॉगिन", "खोल", "डाउनलोड", "रिपोर्ट",
)


def _label_text(label: Any) -> str:
    return str(label or "").strip().lower()


def _button_kind(label: Any) -> str:
    text = _label_text(label)
    if any(k in text for k in WRITE_KEYWORDS):
        return "write"
    if any(k in text for k in READ_KEYWORDS):
        return "read"
    return "normal"


def _callsite_id(label: Any, explicit_key: Any = None) -> str:
    if explicit_key is not None:
        raw = f"key::{explicit_key}"
    else:
        raw = f"label::{label}"
        # Pick the first caller outside this helper module. This gives stable,
        # per-button locks even when buttons are inside columns/forms.
        for frame in inspect.stack()[2:]:
            filename = str(frame.filename)
            if not filename.endswith("action_guard.py") and "site-packages/streamlit" not in filename:
                raw = f"{filename}:{frame.lineno}:{label}"
                break
    digest = hashlib.md5(raw.encode("utf-8", errors="ignore")).hexdigest()[:12]
    return f"_guard_{digest}"


def _lock_seconds(kind: str) -> int:
    if kind == "write":
        return 12
    if kind == "read":
        return 3
    return 2


def _is_locked(lock_key: str) -> bool:
    until = float(st.session_state.get(lock_key, 0) or 0)
    return time.time() < until


def _set_lock(lock_key: str, seconds: int) -> None:
    st.session_state[lock_key] = time.time() + seconds


def _feedback(kind: str) -> None:
    if kind == "write":
        msg = "⏳ Click received. Save/Upload process चल रहा है — दोबारा click न करें."
    elif kind == "read":
        msg = "⏳ Request received. कृपया wait करें."
    else:
        msg = "⏳ Click received."
    try:
        st.toast(msg)
    except Exception:
        pass
    # Toast sometimes disappears quickly on mobile, so show a small visible message too.
    st.info(msg, icon="⏳")


def _already_processing_message(kind: str) -> None:
    if kind == "write":
        st.warning("⏳ पिछला save/upload अभी process में है. Duplicate entry रोक दी गई है.")
    else:
        st.warning("⏳ पिछला click अभी process में है. थोड़ा wait करें.")


def _wrap_button(original: Callable[..., Any], label: Any, *args: Any, **kwargs: Any) -> bool:
    kind = _button_kind(label)
    lock_key = _callsite_id(label, kwargs.get("key"))
    locked = _is_locked(lock_key)

    # Preserve any disabled flag already set by app code.
    existing_disabled = bool(kwargs.get("disabled", False))
    kwargs["disabled"] = existing_disabled or locked

    clicked = bool(original(label, *args, **kwargs))
    if locked:
        # Show only a small hint, not a big error.
        if kind == "write":
            st.caption("⏳ Processing... duplicate click blocked")
        return False

    if clicked:
        _set_lock(lock_key, _lock_seconds(kind))
        _feedback(kind)
        return True
    return False


def _wrap_form_submit_button(original: Callable[..., Any], label: Any = "Submit", *args: Any, **kwargs: Any) -> bool:
    kind = _button_kind(label)
    lock_key = _callsite_id(label, kwargs.get("key"))
    locked = _is_locked(lock_key)

    existing_disabled = bool(kwargs.get("disabled", False))
    kwargs["disabled"] = existing_disabled or locked

    clicked = bool(original(label, *args, **kwargs))
    if locked:
        if kind == "write":
            st.caption("⏳ Processing... duplicate submit blocked")
        return False

    if clicked:
        _set_lock(lock_key, _lock_seconds(kind))
        _feedback(kind)
        return True
    return False



def guarded_container_button(container: Any, label: Any, *args: Any, **kwargs: Any) -> bool:
    """Guard a button rendered on a column/sidebar/container object."""
    return _wrap_button(container.button, label, *args, **kwargs)


def guarded_form_submit(label: Any = "Submit", *args: Any, **kwargs: Any) -> bool:
    """Direct helper for forms when a page wants an explicit guarded submit."""
    return _wrap_form_submit_button(st.form_submit_button, label, *args, **kwargs)

def install_action_guard() -> None:
    """Install global guard once. Call immediately after st.set_page_config in app.py."""
    global _INSTALLED, _ORIGINAL_BUTTON, _ORIGINAL_FORM_SUBMIT_BUTTON
    if _INSTALLED:
        return

    _ORIGINAL_BUTTON = st.button
    _ORIGINAL_FORM_SUBMIT_BUTTON = st.form_submit_button

    def guarded_button(label: Any, *args: Any, **kwargs: Any) -> bool:
        return _wrap_button(_ORIGINAL_BUTTON, label, *args, **kwargs)  # type: ignore[arg-type]

    def guarded_form_submit_button(label: Any = "Submit", *args: Any, **kwargs: Any) -> bool:
        return _wrap_form_submit_button(_ORIGINAL_FORM_SUBMIT_BUTTON, label, *args, **kwargs)  # type: ignore[arg-type]

    st.button = guarded_button  # type: ignore[assignment]
    st.form_submit_button = guarded_form_submit_button  # type: ignore[assignment]
    _INSTALLED = True


def clear_click_locks() -> None:
    """Manual escape hatch if any button remains locked due to browser/session issue."""
    for key in list(st.session_state.keys()):
        if str(key).startswith("_guard_"):
            del st.session_state[key]
