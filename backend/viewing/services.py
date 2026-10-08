import base64
import io
import uuid

import pypdfium2 as pdfium
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from PIL import Image, ImageDraw, ImageFont

from core.exceptions import ServiceError
from platform_settings import services as platform
from resources.services import load_pdf_bytes

from .models import ViewActivity


def _watermark_lines(student, course, stamp, watermark_id):
    """Returns (tile_text, footer_lines); every value is derived server-side."""
    tile = f"{student.full_name}  {str(student.id)[:8]}  {watermark_id}"
    return tile, [
        f"{student.full_name} <{student.email}>",
        f"ID {str(student.id)[:8]}  |  {course.title}",
        f"{stamp:%Y-%m-%d %H:%M:%S} UTC  |  {watermark_id}",
    ]


def _composite(layer, stamp, x, y):
    """alpha_composite that tolerates tiles hanging over the top/left edges."""
    source = (max(0, -x), max(0, -y))
    dest = (max(x, 0), max(y, 0))
    if source[0] >= stamp.width or source[1] >= stamp.height or dest[0] >= layer.width or dest[1] >= layer.height:
        return
    layer.alpha_composite(stamp, dest=dest, source=source)


def apply_watermark(image, tile_text, lines):
    """Overlay a tiled, diagonal, semi-transparent watermark plus a footer band. Identity comes from the server."""
    image = image.convert("RGBA")
    width, height = image.size
    font_size = max(14, width // 45)
    font = ImageFont.load_default(size=font_size)

    probe = ImageDraw.Draw(image)
    left, top, right, bottom = probe.textbbox((0, 0), tile_text, font=font)
    text_w, text_h = right - left, bottom - top + 8
    stamp = Image.new("RGBA", (text_w + 20, text_h + 10), (0, 0, 0, 0))
    ImageDraw.Draw(stamp).text((10, 2), tile_text, font=font, fill=(90, 90, 90, 70))
    stamp = stamp.rotate(30, expand=True, resample=Image.BICUBIC)

    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    step_x = int(stamp.width * 0.75)
    step_y = int(stamp.height * 0.45)
    for row, y in enumerate(range(-stamp.height, height + stamp.height, step_y)):
        for x in range(-stamp.width + (row % 2) * (step_x // 2), width + stamp.width, step_x):
            _composite(layer, stamp, x, y)
    image = Image.alpha_composite(image, layer)

    band_h = font_size * 3 + 12
    footer = Image.new("RGBA", (width, band_h), (255, 255, 255, 215))
    draw = ImageDraw.Draw(footer)
    for index, line in enumerate(lines):
        draw.text((10, 4 + index * (font_size + 3)), line, font=font, fill=(40, 40, 40, 255))
    image.alpha_composite(footer, dest=(0, height - band_h))
    return image.convert("RGB")


def render_protected_page(*, student, course, resource, page_number):
    """Render one page of a private PDF on the server, watermark it, and record the view."""
    if page_number < 1 or page_number > resource.page_count:
        raise ServiceError(
            "INVALID_PAGE", "That page does not exist.", 404, {"page_count": resource.page_count}
        )
    try:
        data = load_pdf_bytes(resource)
    except OSError:
        raise ServiceError("STORAGE_ERROR", "The document is temporarily unavailable.", 500)
    try:
        document = pdfium.PdfDocument(data)
        try:
            page = document[page_number - 1]
            page_width = max(page.get_width(), 1)
            scale = min(max(platform.get("viewer_render_width") / page_width, 0.2), 4.0)
            bitmap = page.render(scale=scale)
            image = bitmap.to_pil()
        finally:
            document.close()
    except pdfium.PdfiumError:
        raise ServiceError("RENDER_FAILED", "The page could not be rendered.", 500)

    watermark_id = uuid.uuid4().hex[:12]
    now = timezone.now()
    marked = apply_watermark(image, *_watermark_lines(student, course, now, watermark_id))
    buffer = io.BytesIO()
    marked.save(buffer, format="JPEG", quality=platform.get("viewer_jpeg_quality"))

    activity = ViewActivity.objects.create(
        student=student, course=course, resource=resource, page_number=page_number, watermark_id=watermark_id
    )
    return {
        "view_id": str(activity.id),
        "resource": str(resource.id),
        "page": page_number,
        "page_count": resource.page_count,
        "width": marked.width,
        "height": marked.height,
        "content_type": "image/jpeg",
        "image": base64.b64encode(buffer.getvalue()).decode("ascii"),
        "watermark_id": watermark_id,
    }


def record_duration(*, student, resource, view_id, seconds):
    """Add client-reported reading time to a server-recorded view (capped; own views only)."""
    with transaction.atomic():
        activity = (
            ViewActivity.objects.select_for_update()
            .filter(pk=view_id, student=student, resource=resource)
            .first()
        )
        if activity is None:
            raise ServiceError("VIEW_NOT_FOUND", "No matching page view was found.", 404)
        cap = settings.VIEWER_MAX_DURATION_SECONDS
        activity.duration_seconds = min(activity.duration_seconds + seconds, cap)
        activity.save(update_fields=["duration_seconds"])
    return activity
