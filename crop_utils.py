"""Shared crop helpers for POD/GR uploads.

Supports:
- JPG/JPEG/PNG/HEIC/HEIF image crop
- PDF crop by rendering first page, selecting crop box, and applying same box to all pages

Notes:
- Existing Google Drive PDF is not edited in-place. The app creates a new cropped PDF
  from the uploaded/re-uploaded PDF and saves that new file/link.
- PDF crop requires PyMuPDF (package name: PyMuPDF, import: fitz).
"""

from __future__ import annotations

import io
from typing import Any, Dict, Iterable

import streamlit as st
from PIL import Image, ImageOps, UnidentifiedImageError

try:  # Optional HEIC/HEIF support for phone photos.
    from pillow_heif import register_heif_opener  # type: ignore

    register_heif_opener()
except Exception:  # pragma: no cover - optional dependency
    pass

try:  # Optional PDF crop/render support.
    import fitz  # type: ignore  # PyMuPDF
except Exception:  # pragma: no cover - optional dependency
    fitz = None

try:  # Optional component; fallback sliders are used if not installed.
    from streamlit_cropper import st_cropper  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    st_cropper = None

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".heic", ".heif")
PDF_EXTS = (".pdf",)


def is_image_file(uploaded_file) -> bool:
    name = str(getattr(uploaded_file, "name", "")).lower()
    mime = str(getattr(uploaded_file, "type", "")).lower()
    return name.endswith(IMAGE_EXTS) or mime.startswith("image/")


def is_pdf_file(uploaded_file) -> bool:
    name = str(getattr(uploaded_file, "name", "")).lower()
    mime = str(getattr(uploaded_file, "type", "")).lower()
    return name.endswith(PDF_EXTS) or mime == "application/pdf"


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


def _render_pdf_first_page(uploaded_file, max_side: int = 1600) -> tuple[Image.Image, tuple[int, int]]:
    """Render first PDF page as RGB image and return (image, full_render_size)."""
    if fitz is None:
        raise RuntimeError("PDF crop के लिए PyMuPDF install होना जरूरी है। requirements.txt में PyMuPDF add करें।")

    data = _uploaded_file_bytes(uploaded_file)
    doc = fitz.open(stream=data, filetype="pdf")
    if doc.page_count <= 0:
        doc.close()
        raise ValueError("PDF में page नहीं मिला।")

    page = doc.load_page(0)
    rect = page.rect
    scale = min(2.0, max_side / max(float(rect.width), float(rect.height)))
    if scale <= 0:
        scale = 1.0
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    render_size = (pix.width, pix.height)
    doc.close()
    return img, render_size


def _normalize_box(box: Any, img_w: int, img_h: int) -> tuple[int, int, int, int] | None:
    """Normalize crop box from streamlit-cropper/fallback into x1,y1,x2,y2 pixels."""
    if not box:
        return None
    if isinstance(box, dict):
        left = int(float(box.get("left", box.get("x", 0)) or 0))
        top = int(float(box.get("top", box.get("y", 0)) or 0))
        width = int(float(box.get("width", 0) or 0))
        height = int(float(box.get("height", 0) or 0))
        right = left + width
        bottom = top + height
    elif isinstance(box, (list, tuple)) and len(box) >= 4:
        left, top, right, bottom = [int(float(v)) for v in box[:4]]
    else:
        return None

    left = max(0, min(left, img_w - 1))
    top = max(0, min(top, img_h - 1))
    right = max(left + 1, min(right, img_w))
    bottom = max(top + 1, min(bottom, img_h))
    return left, top, right, bottom


def crop_pdf_bytes(uploaded_file, box_pixels: tuple[int, int, int, int], render_size: tuple[int, int]) -> bytes:
    """Return new PDF bytes with the same relative crop applied to every page."""
    if fitz is None:
        raise RuntimeError("PDF crop के लिए PyMuPDF install होना जरूरी है।")

    data = _uploaded_file_bytes(uploaded_file)
    doc = fitz.open(stream=data, filetype="pdf")
    if doc.page_count <= 0:
        doc.close()
        raise ValueError("PDF में page नहीं मिला।")

    x1, y1, x2, y2 = box_pixels
    rw, rh = render_size
    rx1, ry1, rx2, ry2 = x1 / rw, y1 / rh, x2 / rw, y2 / rh

    for page in doc:
        rect = page.rect
        new_rect = fitz.Rect(
            rect.x0 + rect.width * rx1,
            rect.y0 + rect.height * ry1,
            rect.x0 + rect.width * rx2,
            rect.y0 + rect.height * ry2,
        )
        # Keep crop box safely inside the page.
        new_rect = new_rect & rect
        if new_rect.width > 5 and new_rect.height > 5:
            page.set_cropbox(new_rect)

    out = doc.tobytes(garbage=4, deflate=True)
    doc.close()
    return out


def _render_image_crop_ui(img: Image.Image, key_base: str) -> Image.Image | None:
    """Return cropped RGB image from either streamlit-cropper or slider fallback."""
    display_img = limit_image(img, 1600)
    if st_cropper is not None:
        try:
            cropped = st_cropper(
                display_img,
                realtime_update=True,
                box_color="#ff4b4b",
                aspect_ratio=None,
                return_type="image",
                key=f"{key_base}_cropper_img",
            )
            if cropped is not None:
                return cropped.convert("RGB")
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
        return None
    return img.crop((x1, y1, x2, y2)).convert("RGB")


def _render_pdf_crop_ui(uploaded_file, key_base: str) -> bytes | None:
    """Render first PDF page crop UI and return cropped PDF bytes."""
    if fitz is None:
        st.warning("PDF crop के लिए PyMuPDF missing है। requirements.txt update करके Streamlit reboot करें।")
        return None

    try:
        page_img, render_size = _render_pdf_first_page(uploaded_file)
    except Exception as exc:
        st.warning(f"PDF preview open नहीं हुआ: {exc}")
        return None

    st.caption("PDF की first page पर crop area set करें। यही relative crop PDF के सभी pages पर apply होगा।")
    box_pixels = None

    if st_cropper is not None:
        try:
            box = st_cropper(
                page_img,
                realtime_update=True,
                box_color="#ff4b4b",
                aspect_ratio=None,
                return_type="box",
                key=f"{key_base}_cropper_pdf",
            )
            box_pixels = _normalize_box(box, page_img.size[0], page_img.size[1])
        except Exception as exc:
            st.caption(f"PDF cropper fallback slider mode: {exc}")

    if box_pixels is None:
        w, h = page_img.size
        st.image(limit_image(page_img, 900), caption=f"PDF first page preview: {w} × {h}", use_container_width=True)
        x1, x2 = st.slider(
            "PDF Left ↔ Right",
            min_value=0,
            max_value=w,
            value=(0, w),
            step=max(1, w // 200),
            key=f"{key_base}_pdf_x",
        )
        y1, y2 = st.slider(
            "PDF Top ↕ Bottom",
            min_value=0,
            max_value=h,
            value=(0, h),
            step=max(1, h // 200),
            key=f"{key_base}_pdf_y",
        )
        if x2 <= x1 or y2 <= y1:
            st.error("PDF crop area invalid है। Right/Bottom value बढ़ाएँ।")
            return None
        box_pixels = (x1, y1, x2, y2)

    try:
        cropped_pdf = crop_pdf_bytes(uploaded_file, box_pixels, render_size)
        st.caption("✅ PDF crop ready")
        return cropped_pdf
    except Exception as exc:
        st.warning(f"PDF crop create नहीं हुआ: {exc}")
        return None


def render_crop_tool(files: Iterable, key_prefix: str, title: str = "✂️ Crop Tool") -> Dict[str, Any]:
    """Render crop UI and return cropped values keyed by crop_key(file, index).

    Values:
    - image files: PIL.Image.Image
    - PDF files: bytes of cropped PDF
    """
    files = list(files or [])
    crop_items = [(i, f) for i, f in enumerate(files) if is_image_file(f) or is_pdf_file(f)]
    crop_map: Dict[str, Any] = {}
    if not crop_items:
        return crop_map

    with st.expander(title, expanded=False):
        st.caption("JPG/PNG/HEIC photo और PDF दोनों crop हो सकते हैं। PDF crop new cropped PDF बनाकर save करेगा।")
        for index, uploaded_file in crop_items:
            name = str(getattr(uploaded_file, "name", f"File {index + 1}"))
            key_base = f"{key_prefix}_{index}_{abs(hash(name))}"
            use_crop = st.checkbox(f"✂️ Crop करें: {name}", value=False, key=f"{key_base}_enable")
            if not use_crop:
                continue

            if is_pdf_file(uploaded_file):
                cropped_pdf = _render_pdf_crop_ui(uploaded_file, key_base)
                if cropped_pdf:
                    crop_map[crop_key(uploaded_file, index)] = cropped_pdf
                continue

            try:
                img = open_upload_image(uploaded_file)
            except Exception as exc:
                st.warning(f"{name} image open नहीं हुई: {exc}")
                continue

            cropped = _render_image_crop_ui(img, key_base)
            if cropped is not None:
                crop_map[crop_key(uploaded_file, index)] = cropped.convert("RGB")
                st.caption(f"✅ Crop ready: {cropped.size[0]} × {cropped.size[1]}")
    return crop_map


def get_processed_image(uploaded_file, crop_map: Dict[str, Any] | None = None, index: int = 0) -> Image.Image:
    crop_map = crop_map or {}
    key = crop_key(uploaded_file, index)
    value = crop_map.get(key)
    if isinstance(value, Image.Image):
        return value.copy().convert("RGB")
    return open_upload_image(uploaded_file)


def get_processed_pdf_bytes(uploaded_file, crop_map: Dict[str, Any] | None = None, index: int = 0) -> bytes:
    crop_map = crop_map or {}
    key = crop_key(uploaded_file, index)
    value = crop_map.get(key)
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    return _uploaded_file_bytes(uploaded_file)
