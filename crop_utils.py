"""Shared image crop helpers for POD/GR uploads.

Robust for Streamlit UploadedFile objects:
- Reads uploaded file through getvalue()/BytesIO instead of passing UploadedFile directly to PIL.
- Resets file pointer after reading so later upload/save code can reuse the same file.
- Supports JPG/JPEG/PNG and, if pillow-heif is installed, HEIC/HEIF phone photos.
- Uses streamlit-cropper when installed; otherwise slider-based crop fallback is shown.
"""

from __future__ import annotations

import io
from typing import Dict, Iterable

import streamlit as st
from PIL import Image, ImageOps, UnidentifiedImageError

try:  # Optional HEIC/HEIF support for phone photos.
    from pillow_heif import register_heif_opener  # type: ignore

    register_heif_opener()
except Exception:  # pragma: no cover - optional dependency
    pass

try:  # Optional component; fallback sliders are used if not installed.
    from streamlit_cropper import st_cropper  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    st_cropper = None

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".heic", ".heif")


def is_image_file(uploaded_file) -> bool:
    name = str(getattr(uploaded_file, "name", "")).lower()
    mime = str(getattr(uploaded_file, "type", "")).lower()
    return name.endswith(IMAGE_EXTS) or mime.startswith("image/")


def crop_key(uploaded_file, index: int) -> str:
    name = str(getattr(uploaded_file, "name", f"file_{index}"))
    size = str(getattr(uploaded_file, "size", ""))
    return f"{index}_{name}_{size}"


def _uploaded_file_bytes(uploaded_file) -> bytes:
    """Return bytes from a Streamlit UploadedFile without leaving pointer at EOF."""
    data: bytes | None = None

    if hasattr(uploaded_file, "getvalue"):
        data = uploaded_file.getvalue()
    else:
        try:
            uploaded_file.seek(0)
        except Exception:
            pass
        data = uploaded_file.read()

    try:
        uploaded_file.seek(0)
    except Exception:
        pass

    if not data:
        name = str(getattr(uploaded_file, "name", "selected file"))
        raise ValueError(f"{name} empty/blank file है।")
    return data


def open_upload_image(uploaded_file) -> Image.Image:
    """Open an uploaded image safely and return RGB PIL image copy."""
    data = _uploaded_file_bytes(uploaded_file)
    bio = io.BytesIO(data)

    try:
        img = Image.open(bio)
        img.load()  # force decode before BytesIO closes/reuses
    except UnidentifiedImageError as exc:
        name = str(getattr(uploaded_file, "name", "image"))
        mime = str(getattr(uploaded_file, "type", "unknown"))
        raise ValueError(
            f"{name} valid JPG/PNG image नहीं पढ़ी जा सकी। "
            f"Type: {mime}. File को phone/gallery से JPG में convert करके upload करें."
        ) from exc

    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "LA"):
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[-1])
        img = bg
    elif img.mode != "RGB":
        img = img.convert("RGB")

    try:
        uploaded_file.seek(0)
    except Exception:
        pass
    return img.copy()


def limit_image(img: Image.Image, max_side: int = 1600) -> Image.Image:
    w, h = img.size
    if max(w, h) <= max_side:
        return img.copy()
    scale = max_side / max(w, h)
    return img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)


def render_crop_tool(files: Iterable, key_prefix: str, title: str = "✂️ Crop Tool") -> Dict[str, Image.Image]:
    """Render crop UI and return cropped PIL images keyed by crop_key(file, index).

    PDF files are ignored because this tool only crops image files.
    """
    files = list(files or [])
    image_items = [(i, f) for i, f in enumerate(files) if is_image_file(f)]
    crop_map: Dict[str, Image.Image] = {}
    if not image_items:
        if files:
            st.caption("✂️ Crop JPG/PNG/HEIC photos पर available है; PDF files as-is upload होंगी।")
        return crop_map

    with st.expander(title, expanded=False):
        st.caption("Photo select करें, crop set करें, फिर Upload/Save button दबाएँ। PDF crop नहीं होगी।")
        for index, uploaded_file in image_items:
            name = str(getattr(uploaded_file, "name", f"Image {index + 1}"))
            key_base = f"{key_prefix}_{index}_{abs(hash(name))}"
            use_crop = st.checkbox(f"✂️ Crop करें: {name}", value=False, key=f"{key_base}_enable")
            if not use_crop:
                continue

            try:
                img = open_upload_image(uploaded_file)
            except Exception as exc:
                st.warning(f"{name} image open नहीं हुई: {exc}")
                continue

            display_img = limit_image(img, 1600)
            if st_cropper is not None:
                try:
                    cropped = st_cropper(
                        display_img,
                        realtime_update=True,
                        box_color="#ff4b4b",
                        aspect_ratio=None,
                        return_type="image",
                        key=f"{key_base}_cropper",
                    )
                    if cropped is not None:
                        crop_map[crop_key(uploaded_file, index)] = cropped.convert("RGB")
                        st.caption(f"✅ Crop ready: {cropped.size[0]} × {cropped.size[1]}")
                    continue
                except Exception as exc:
                    st.caption(f"Cropper component fallback slider mode: {exc}")

            w, h = img.size
            st.image(limit_image(img, 900), caption=f"Original: {w} × {h}", use_container_width=True)
            x1, x2 = st.slider(
                "Left ↔ Right",
                min_value=0,
                max_value=w,
                value=(0, w),
                step=max(1, w // 200),
                key=f"{key_base}_x",
            )
            y1, y2 = st.slider(
                "Top ↕ Bottom",
                min_value=0,
                max_value=h,
                value=(0, h),
                step=max(1, h // 200),
                key=f"{key_base}_y",
            )
            if x2 <= x1 or y2 <= y1:
                st.error("Crop area invalid है। Right/Bottom value बढ़ाएँ।")
                continue
            cropped = img.crop((x1, y1, x2, y2)).convert("RGB")
            st.image(limit_image(cropped, 900), caption=f"Cropped preview: {cropped.size[0]} × {cropped.size[1]}", use_container_width=True)
            crop_map[crop_key(uploaded_file, index)] = cropped
    return crop_map


def get_processed_image(uploaded_file, crop_map: Dict[str, Image.Image] | None = None, index: int = 0) -> Image.Image:
    crop_map = crop_map or {}
    key = crop_key(uploaded_file, index)
    if key in crop_map:
        return crop_map[key].copy().convert("RGB")
    return open_upload_image(uploaded_file)
