import os
import uuid
import shutil
from pathlib import Path
from fastapi import UploadFile, HTTPException
from PIL import Image

from app.core.config import settings

ALLOWED_IMAGES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
ALLOWED_VIDEOS = {"video/mp4", "video/webm", "video/quicktime", "video/x-msvideo"}
ALLOWED_FILES = {
    "application/pdf",
    "application/zip",
    "application/x-zip-compressed",
    "application/octet-stream",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

MAX_BYTES = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024


async def save_product_image(file: UploadFile) -> str:
    _validate_type(file, ALLOWED_IMAGES, "image")
    ext = _ext(file.filename)
    filename = f"{uuid.uuid4().hex}{ext}"
    dest = Path(settings.UPLOAD_DIR) / "products" / "images" / filename
    await _save(file, dest)
    # Resize to max 1920px wide while keeping aspect ratio
    try:
        with Image.open(dest) as img:
            if img.width > 1920:
                ratio = 1920 / img.width
                new_size = (1920, int(img.height * ratio))
                img = img.resize(new_size, Image.LANCZOS)
                img.save(dest, optimize=True, quality=88)
    except Exception:
        pass
    return filename


async def save_product_video(file: UploadFile) -> str:
    _validate_type(file, ALLOWED_VIDEOS, "video")
    ext = _ext(file.filename)
    filename = f"{uuid.uuid4().hex}{ext}"
    dest = Path(settings.UPLOAD_DIR) / "products" / "videos" / filename
    await _save(file, dest)
    return filename


async def save_product_file(file: UploadFile) -> str:
    _validate_type(file, ALLOWED_FILES, "file")
    ext = _ext(file.filename)
    filename = f"{uuid.uuid4().hex}{ext}"
    dest = Path(settings.UPLOAD_DIR) / "products" / "files" / filename
    await _save(file, dest)
    return filename


def delete_upload(subpath: str):
    path = Path(settings.UPLOAD_DIR) / subpath
    if path.exists() and path.is_file():
        path.unlink()


def _validate_type(file: UploadFile, allowed: set, kind: str):
    if file.content_type not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {kind} type: {file.content_type}. Allowed: {', '.join(allowed)}",
        )


def _ext(filename: str) -> str:
    if not filename or "." not in filename:
        return ""
    return "." + filename.rsplit(".", 1)[-1].lower()


async def _save(file: UploadFile, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with open(dest, "wb") as f:
        while chunk := await file.read(1024 * 256):
            total += len(chunk)
            if total > MAX_BYTES:
                f.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=413,
                    detail=f"File too large. Max {settings.MAX_UPLOAD_SIZE_MB}MB.",
                )
            f.write(chunk)
