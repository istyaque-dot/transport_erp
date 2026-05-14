# Force Upload Unblock Fix

Fixes the old global duplicate-click guard stuck state.

## What changed
- `app.py` now force-restores `st.button` and `st.form_submit_button` if old `action_guard` monkey patch is still loaded in the running Streamlit process.
- Old `_guard_`, `upload_lock`, `saving_lock`, and `button_lock` session keys are cleared on each run.
- `action_guard.py` is now a no-block compatibility module.

## Result
GR/POD upload button will not remain stuck at `Processing... duplicate click blocked`.
