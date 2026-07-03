from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageDraw, ImageEnhance, ImageOps

from photo_mecha_battle.models import MechForm


_FORM_COLORS = {
    MechForm.BIRD: (90, 180, 255),
    MechForm.HUMAN: (180, 180, 200),
    MechForm.BEAST: (220, 140, 90),
}


def render_mech_art(crop: Image.Image, form: MechForm) -> bytes:
    base = ImageOps.fit(crop.convert("RGBA"), (256, 256), method=Image.Resampling.LANCZOS)
    base = ImageEnhance.Color(base).enhance(1.2)
    base = ImageEnhance.Contrast(base).enhance(1.1)
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    tint = _FORM_COLORS[form]
    if form == MechForm.BIRD:
        draw.polygon([(40, 180), (128, 40), (216, 180), (128, 140)], fill=(*tint, 90))
    elif form == MechForm.HUMAN:
        draw.rounded_rectangle((70, 50, 186, 220), radius=24, fill=(*tint, 90))
    else:
        draw.ellipse((35, 70, 221, 220), fill=(*tint, 90))
    composed = Image.alpha_composite(base, overlay)
    buffer = BytesIO()
    composed.save(buffer, format="PNG")
    return buffer.getvalue()
