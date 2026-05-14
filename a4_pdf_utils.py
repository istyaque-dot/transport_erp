"""A4 full-page PDF utilities for GR/POD copies.

Purpose:
- Old/current uploads often create an A4 page with the document photo pasted small in the center.
- These helpers crop large white borders and rebuild a print-ready A4 PDF.
- Aspect ratio is preserved: no stretching and no content cutting.
"""
from __future__ import annotations

import io
from typing import Any, Iterable

from PIL import Image, ImageChops, ImageOps

try:
    import fitz  # PyMuPDF
except Exception:  # pragma: no cover
    fitz = None

A4_PORTRAIT = (2480, 3508)   # 300 DPI
A4_LANDSCAPE = (3508, 2480)  # 300 DPI
IMAGE_EXTS = ('.jpg', '.jpeg', '.png', '.heic', '.heif')
PDF_EXTS = ('.pdf',)


def _name(uploaded_file: Any) -> str:
    return str(getattr(uploaded_file, 'name', '') or '').lower()


def is_image_upload(uploaded_file: Any) -> bool:
    mime = str(getattr(uploaded_file, 'type', '') or '').lower()
    return _name(uploaded_file).endswith(IMAGE_EXTS) or mime.startswith('image/')


def is_pdf_upload(uploaded_file: Any) -> bool:
    mime = str(getattr(uploaded_file, 'type', '') or '').lower()
    return _name(uploaded_file).endswith(PDF_EXTS) or mime == 'application/pdf'


def uploaded_file_bytes(uploaded_file: Any) -> bytes:
    if hasattr(uploaded_file, 'getvalue'):
        return uploaded_file.getvalue()
    try:
        uploaded_file.seek(0)
    except Exception:
        pass
    data = uploaded_file.read()
    try:
        uploaded_file.seek(0)
    except Exception:
        pass
    return data


def _to_rgb(img: Image.Image) -> Image.Image:
    img = ImageOps.exif_transpose(img)
    if img.mode in ('RGBA', 'LA'):
        bg = Image.new('RGB', img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[-1])
        return bg
    if img.mode != 'RGB':
        return img.convert('RGB')
    return img


def auto_crop_white_border(img: Image.Image, threshold: int = 245, padding: int = 20) -> Image.Image:
    """Remove large white margins around document image.

    threshold 245 means near-white background is treated as blank.
    Padding keeps a thin border so edge text/signatures are not cut.
    """
    img = _to_rgb(img)
    white = Image.new('RGB', img.size, (255, 255, 255))
    diff = ImageChops.difference(img, white).convert('L')
    mask = diff.point(lambda p: 255 if p > (255 - threshold) else 0)
    bbox = mask.getbbox()
    if not bbox:
        return img

    left, top, right, bottom = bbox
    left = max(0, left - padding)
    top = max(0, top - padding)
    right = min(img.width, right + padding)
    bottom = min(img.height, bottom + padding)

    cw, ch = right - left, bottom - top
    if cw < img.width * 0.06 or ch < img.height * 0.06:
        return img
    return img.crop((left, top, right, bottom))


def image_to_a4_full_page(img: Image.Image, margin_px: int = 20) -> Image.Image:
    """Place the image on A4 as large as possible without stretch/cut."""
    img = auto_crop_white_border(img)
    img = _to_rgb(img)
    iw, ih = img.size
    page_w, page_h = A4_LANDSCAPE if iw > ih else A4_PORTRAIT
    usable_w = page_w - 2 * margin_px
    usable_h = page_h - 2 * margin_px
    scale = min(usable_w / iw, usable_h / ih)
    nw = max(1, int(iw * scale))
    nh = max(1, int(ih * scale))
    resized = img.resize((nw, nh), Image.LANCZOS)
    page = Image.new('RGB', (page_w, page_h), (255, 255, 255))
    page.paste(resized, ((page_w - nw) // 2, (page_h - nh) // 2))
    return page


def images_to_a4_pdf_bytes(images: Iterable[Image.Image], resolution: int = 300) -> bytes | None:
    pages = [image_to_a4_full_page(img) for img in images]
    if not pages:
        return None
    out = io.BytesIO()
    if len(pages) == 1:
        pages[0].save(out, format='PDF', resolution=resolution)
    else:
        pages[0].save(out, format='PDF', resolution=resolution, save_all=True, append_images=pages[1:])
    return out.getvalue()


def render_pdf_bytes_to_images(pdf_bytes: bytes, zoom: float = 3.0) -> list[Image.Image]:
    if fitz is None:
        raise RuntimeError('PyMuPDF missing. requirements.txt में PyMuPDF add करें।')
    doc = fitz.open(stream=pdf_bytes, filetype='pdf')
    images: list[Image.Image] = []
    try:
        for page in doc:
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
            img = Image.open(io.BytesIO(pix.tobytes('png'))).convert('RGB')
            images.append(img)
    finally:
        doc.close()
    return images


def normalize_pdf_bytes_to_a4_full_page(pdf_bytes: bytes) -> bytes:
    """Convert already-made PDFs into A4 full-page PDFs.

    This fixes PDFs where the GR/POD photo is small in the center of the page.
    """
    images = render_pdf_bytes_to_images(pdf_bytes)
    final = images_to_a4_pdf_bytes(images)
    return final or pdf_bytes


def open_image_from_upload(uploaded_file: Any) -> Image.Image:
    return Image.open(io.BytesIO(uploaded_file_bytes(uploaded_file)))


def build_a4_full_pdf_from_uploads(files: list[Any], crop_map: dict | None = None, get_processed_image_func=None, get_processed_pdf_func=None) -> bytes | None:
    """Build one full-page A4 PDF from one/multiple image/PDF uploads."""
    pages: list[Image.Image] = []
    crop_map = crop_map or {}
    for index, uploaded_file in enumerate(files or []):
        try:
            if is_image_upload(uploaded_file):
                if get_processed_image_func:
                    img = get_processed_image_func(uploaded_file, crop_map, index)
                else:
                    img = open_image_from_upload(uploaded_file)
                pages.append(img)
            elif is_pdf_upload(uploaded_file):
                if get_processed_pdf_func:
                    pdf_bytes = get_processed_pdf_func(uploaded_file, crop_map=crop_map, index=index)
                else:
                    pdf_bytes = uploaded_file_bytes(uploaded_file)
                pages.extend(render_pdf_bytes_to_images(pdf_bytes))
        except Exception:
            continue
    return images_to_a4_pdf_bytes(pages)


def build_single_upload_as_a4_pdf(uploaded_file: Any, crop_map: dict | None = None, index: int = 0, get_processed_image_func=None, get_processed_pdf_func=None) -> bytes | None:
    return build_a4_full_pdf_from_uploads([uploaded_file], crop_map=crop_map or {}, get_processed_image_func=get_processed_image_func, get_processed_pdf_func=get_processed_pdf_func)
