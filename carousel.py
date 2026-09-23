#!/usr/bin/env python3
"""
mlm-carousel-pro — генератор Instagram-каруселі з фото.

Бере портретне фото і текст слайдів, видає серію 1080×1350 (4:5):
  1. Обкладинка — фото на весь екран, великий заголовок
  2..N-1. Слайди — фото з затемненням, текст по центру
  N. Фінал — заклик до дії

Використання:
    python3 carousel.py --photo me.jpg --slides slides.txt --out out/

Формат slides.txt — слайди розділені рядком `---`.
Перший слайд = обкладинка, останній = фінал (CTA).
Усередині слайда перший рядок = заголовок, решта = підзаголовок/текст.
"""
import argparse
import json
import os
import sys
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1350  # Instagram portrait 4:5

FONT_PATHS = [
    "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_PATHS:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def fit_photo(photo_path: str) -> Image.Image:
    """Фото на весь слайд: cover-crop під 1080×1350."""
    img = Image.open(photo_path).convert("RGB")
    scale = max(W / img.width, H / img.height)
    img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
    x = (img.width - W) // 2
    y = (img.height - H) // 2
    return img.crop((x, y, x + W, y + H))


def bottom_gradient(img: Image.Image, top_opacity=0, bottom_opacity=200, start=0.45) -> Image.Image:
    """Затемнення знизу догори для читабельності тексту."""
    overlay = Image.new("L", (1, H))
    for yy in range(H):
        t = yy / H
        if t < start:
            a = top_opacity
        else:
            a = int(top_opacity + (bottom_opacity - top_opacity) * (t - start) / (1 - start))
        overlay.putpixel((0, yy), a)
    overlay = overlay.resize((W, H))
    black = Image.new("RGB", (W, H), (0, 0, 0))
    return Image.composite(black, img, overlay)


def full_dim(img: Image.Image, opacity=150) -> Image.Image:
    black = Image.new("RGB", (W, H), (0, 0, 0))
    mask = Image.new("L", (W, H), opacity)
    return Image.composite(black, img, mask)


def wrap(draw: ImageDraw.ImageDraw, text: str, font, max_w: int):
    words, lines, cur = text.split(), [], ""
    for w_ in words:
        trial = (cur + " " + w_).strip()
        if draw.textlength(trial, font=font) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w_
    if cur:
        lines.append(cur)
    return lines


def fit_font(draw: ImageDraw.ImageDraw, text: str, max_w: int, start_size: int):
    """Зменшує кегль, доки рядок не влізе в ширину (для довгих слів)."""
    size = start_size
    while size > 24:
        f = load_font(size)
        if draw.textlength(text, font=f) <= max_w:
            return f
        size -= 4
    return load_font(24)


def draw_centered_block(draw, cx, top_y, lines, font, fill, line_gap=18,
                        max_w=W - 160, shrink=False):
    y = top_y
    for ln in lines:
        if not ln.strip():
            y += line_gap
            continue
        f = fit_font(draw, ln, max_w, font.size) if shrink else font
        for sub in wrap(draw, ln, f, max_w) or [""]:
            lw = draw.textlength(sub, font=f)
            draw.text((cx - lw / 2, y), sub, font=f, fill=fill)
            y += f.size + line_gap
    return y


def make_cover(photo_path, title_lines, style) -> Image.Image:
    img = bottom_gradient(fit_photo(photo_path),
                          bottom_opacity=style.get("cover_dim", 210))
    d = ImageDraw.Draw(img)
    accent = style.get("accent", "#FFD84D")
    draw_centered_block(d, W / 2, H - 640, title_lines, load_font(104), "white",
                        shrink=True)
    # підказка "гортай"
    hint = style.get("swipe_hint", "гортай →")
    f_hint = load_font(44)
    hw = d.textlength(hint, font=f_hint)
    d.text((W / 2 - hw / 2, H - 170), hint, font=f_hint, fill=accent)
    return img


def make_body(photo_path, title_lines, idx, total, style) -> Image.Image:
    img = full_dim(fit_photo(photo_path), opacity=style.get("body_dim", 165))
    d = ImageDraw.Draw(img)
    accent = style.get("accent", "#FFD84D")
    # лічильник
    counter = f"{idx} / {total}"
    f_c = load_font(40)
    cw = d.textlength(counter, font=f_c)
    d.text((W / 2 - cw / 2, 90), counter, font=f_c, fill=accent)
    # акцентна риска
    d.rectangle([W / 2 - 60, 165, W / 2 + 60, 172], fill=accent)
    title, *rest = title_lines
    y = draw_centered_block(d, W / 2, 420, [title], load_font(76), "white", shrink=True)
    if rest:
        draw_centered_block(d, W / 2, y + 40, rest, load_font(48), (235, 235, 235))
    return img


def make_final(photo_path, cta_lines, style) -> Image.Image:
    img = full_dim(fit_photo(photo_path), opacity=style.get("final_dim", 190))
    d = ImageDraw.Draw(img)
    accent = style.get("accent", "#FFD84D")
    draw_centered_block(d, W / 2, 480, cta_lines, load_font(72), accent, shrink=True)
    sub = style.get("final_sub", "підписуйся, буде ще")
    f_s = load_font(44)
    sw = d.textlength(sub, font=f_s)
    d.text((W / 2 - sw / 2, H - 420), sub, font=f_s, fill="white")
    return img


def read_slides(path: str):
    with open(path, encoding="utf-8") as f:
        raw = f.read().strip()
    slides = [s.strip().split("\n") for s in raw.split("\n---\n")]
    return [s for s in slides if any(x.strip() for x in s)]


def main():
    ap = argparse.ArgumentParser(description="Генератор Instagram-каруселі 1080×1350")
    ap.add_argument("--photo", required=True, help="портретне фото (jpg/png)")
    ap.add_argument("--slides", required=True, help="txt: слайди через рядок ---")
    ap.add_argument("--out", required=True, help="папка для готових слайдів")
    ap.add_argument("--style", default=None, help="json зі стилем (опційно)")
    ap.add_argument("--format", default="jpg", choices=["jpg", "png"])
    args = ap.parse_args()

    style = {}
    if args.style and os.path.exists(args.style):
        with open(args.style, encoding="utf-8") as f:
            style = json.load(f)

    slides = read_slides(args.slides)
    if len(slides) < 2:
        sys.exit("Потрібно мінімум 2 слайди: обкладинка і фінал.")

    os.makedirs(args.out, exist_ok=True)
    total = len(slides)
    ext = args.format

    cover = make_cover(args.photo, slides[0], style)
    cover.save(os.path.join(args.out, f"slide-01-cover.{ext}"), quality=92)
    print(f"slide-01-cover.{ext} ✓")

    for i, s in enumerate(slides[1:-1], start=2):
        img = make_body(args.photo, s, i, total, style)
        img.save(os.path.join(args.out, f"slide-{i:02d}.{ext}"), quality=92)
        print(f"slide-{i:02d}.{ext} ✓")

    final = make_final(args.photo, slides[-1], style)
    final.save(os.path.join(args.out, f"slide-{total:02d}-final.{ext}"), quality=92)
    print(f"slide-{total:02d}-final.{ext} ✓")
    print(f"Готово: {total} слайдів у {args.out}")


if __name__ == "__main__":
    main()
