#!/usr/bin/env python3
"""
mlm-carousel-pro — генератор Instagram-каруселі з фото.

Бере портретне фото і текст слайдів, видає серію 1080×1350 (4:5):
  1. Обкладинка — фото на весь екран, великий заголовок
  2..N-1. Слайди — фото з затемненням, текст по центру
  N. Фінал — заклик до дії

Використання (класика):
    python3 carousel.py --photo me.jpg --slides slides.txt --out out/

Використання (neon-mlm — фони генерує ШІ, текст кладе код):
    python3 tools/gen_bg.py --slides examples/neon-mlm-system/slides.json \
        --bgdir bgs --ref assets/face-ref-1.jpg --ref assets/face-ref-2.jpg
    python3 carousel.py --mode neon --slides examples/neon-mlm-system/slides.json \
        --bgdir bgs --out out/ --style styles/neon-mlm.json

Формат slides.txt — слайди розділені рядком `---`.
Перший слайд = обкладинка, останній = фінал (CTA).
Усередині слайда перший рядок = заголовок, решта = підзаголовок/текст.

Формат neon slides.json: {"slides": [{bg, side(left|right), title, subtitle,
accent(#hex), frame(bool), scene(промпт для фону)}]}.
У title/subtitle *слово* = акцентний колір. Емодзі підтримуються.
"""
import argparse
import json
import os
import re
import sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter

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


# =====================================================================
# NEON-MLM режим: темна неонова карусель з портретом.
# Фон генерується ШІ (обличчя/поза/одяг/емоції змінюються),
# текст кладеться кодом: заголовок з акцентним словом (*слово*),
# підзаголовок, емодзі підтримуються.
# Формат slides: JSON {"slides": [{bg, side, title, subtitle, accent, frame, scene}]}
# =====================================================================

EMOJI_FONT_PATH = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
EMOJI_RE = re.compile(r'[\U0001F300-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF]')


def hex_to_rgb(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def load_emoji_font(size: int):
    # NotoColorEmoji — бітмапний CBDT, працює лише фіксований розмір 109.
    return ImageFont.truetype(EMOJI_FONT_PATH, 109)


_emoji_cache = {}


def emoji_image(word: str, target_h: int):
    """Рендерить емодзі-слово у RGBA-картинку висотою target_h. Повертає (img, w)."""
    key = (word, target_h)
    if key in _emoji_cache:
        return _emoji_cache[key]
    font = load_emoji_font(109)
    tmp = Image.new("RGBA", (800, 300), (0, 0, 0, 0))
    d = ImageDraw.Draw(tmp)
    bbox = d.textbbox((0, 0), word, font=font, embedded_color=True)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    if w <= 0 or h <= 0:
        return Image.new("RGBA", (1, 1), (0, 0, 0, 0)), 1
    crop = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(crop).text((-bbox[0], -bbox[1]), word, font=font,
                              embedded_color=True)
    scale = target_h / h
    out = crop.resize((max(1, int(w * scale)), max(1, int(h * scale))),
                      Image.LANCZOS)
    _emoji_cache[key] = (out, out.width)
    return _emoji_cache[key]


def word_metrics(draw, word: str, size: int):
    """Повертає (font|None, ширина, висота_емодзі|None)."""
    if EMOJI_RE.search(word):
        th = int(size * 0.95)
        img, w = emoji_image(word, th)
        return None, w, th
    f = load_font(size)
    return f, draw.textlength(word, font=f), None


def parse_rich(text: str):
    """Розбиває текст на слова: *акцент* -> (слово, True), решта -> (слово, False)."""
    tokens = []
    for m in re.finditer(r'\*([^*]+)\*|(\S+)', text):
        if m.group(1) is not None:
            for w_ in m.group(1).split():
                tokens.append((w_, True))
        else:
            tokens.append((m.group(2), False))
    return tokens


def rich_block_size(draw, tokens, size, max_w, line_gap):
    """Вимірює блок: повертає (рядки, ширина, висота)."""
    lines, cur, cur_w = [], [], 0
    sp = draw.textlength(" ", font=load_font(size))
    for word, _acc in tokens:
        f, ww, _eh = word_metrics(draw, word, size)
        add = ww if not cur else sp + ww
        if cur_w + add <= max_w or not cur:
            cur.append((word, _acc, f, ww))
            cur_w += add
        else:
            lines.append((cur, cur_w))
            cur, cur_w = [(word, _acc, f, ww)], ww
    if cur:
        lines.append((cur, cur_w))
    lh = size + line_gap
    return lines, (lh * len(lines) - line_gap if lines else 0)


def draw_rich_block(img, x, y, tokens, size, max_w, fill, accent_fill,
                    line_gap=14, max_h=None, min_size=48, align="left"):
    """Малює текст зі shrink-to-fit. Повертає y після блока."""
    draw = ImageDraw.Draw(img)
    probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    s = size
    while s > min_size:
        lines, h = rich_block_size(probe, tokens, s, max_w, line_gap)
        if max_h is None or h <= max_h:
            break
        s -= 4
    lines, h = rich_block_size(probe, tokens, s, max_w, line_gap)
    sp_cache = {}
    yy = y
    for words, lw in lines:
        xx = x if align == "left" else x + max_w - lw
        for i, (word, acc, f, ww) in enumerate(words):
            if i:
                xx += sp_cache.setdefault(s, probe.textlength(" ", font=load_font(s)))
            if f is None:
                eimg, _ = emoji_image(word, int(s * 0.95))
                img.paste(eimg, (int(xx), int(yy + (s - eimg.height) / 2)), eimg)
            else:
                draw.text((xx, yy), word, font=f,
                          fill=accent_fill if acc else fill)
            xx += ww
        yy += s + line_gap
    return yy


def side_dim_gradient(img: Image.Image, side: str, alpha=225, fade=0.66) -> Image.Image:
    """Затемнення з боку тексту для читабельності."""
    w, h = img.size
    mask = Image.new("L", (w, 1))
    for xx in range(w):
        t = xx / w if side == "left" else 1 - xx / w
        a = int(alpha * max(0.0, 1 - t / fade)) if t < fade else 0
        mask.putpixel((xx, 0), a)
    mask = mask.resize((w, h))
    black = Image.new("RGB", (w, h), (0, 0, 0))
    return Image.composite(black, img, mask)


def neon_frame(img: Image.Image, inset=34, radius=44, width=5,
               color="#00E5FF", glow=16) -> Image.Image:
    rgba = img.convert("RGBA")
    glow_layer = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    dg = ImageDraw.Draw(glow_layer)
    box = [inset, inset, W - inset, H - inset]
    dg.rounded_rectangle(box, radius=radius,
                         outline=hex_to_rgb(color) + (255,), width=width + 10)
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(glow))
    rgba = Image.alpha_composite(rgba, glow_layer)
    d = ImageDraw.Draw(rgba)
    d.rounded_rectangle(box, radius=radius,
                        outline=hex_to_rgb(color) + (255,), width=width)
    return rgba.convert("RGB")


def fit_bg(bg_path: str) -> Image.Image:
    img = Image.open(bg_path).convert("RGB")
    scale = max(W / img.width, H / img.height)
    img = img.resize((int(img.width * scale) + 1, int(img.height * scale) + 1),
                     Image.LANCZOS)
    x = (img.width - W) // 2
    y = (img.height - H) // 2
    return img.crop((x, y, x + W, y + H))


def render_neon_slide(bg_path: str, slide: dict, style: dict) -> Image.Image:
    img = side_dim_gradient(
        fit_bg(bg_path), slide.get("side", "left"),
        alpha=style.get("side_dim_alpha", 225),
        fade=style.get("side_dim_fade", 0.66))
    d = ImageDraw.Draw(img)
    accent = slide.get("accent") or style.get("accent", "#00E5FF")
    accent_rgb = hex_to_rgb(accent)
    margin = style.get("text_margin", 80)
    text_w = style.get("text_width", 640)
    side = slide.get("side", "left")
    x = margin if side == "left" else W - margin - text_w
    top_y = slide.get("top_y", style.get("top_y", 110))

    y = draw_rich_block(img, x, top_y, parse_rich(slide["title"]),
                        style.get("title_size", 88), text_w, "white",
                        accent_rgb, line_gap=style.get("line_gap", 14),
                        max_h=560, min_size=style.get("title_min_size", 56))
    if slide.get("subtitle"):
        draw_rich_block(img, x, y + style.get("sub_gap", 36),
                        parse_rich(slide["subtitle"]),
                        style.get("subtitle_size", 44), text_w,
                        (232, 236, 240), accent_rgb,
                        line_gap=12, max_h=420, min_size=34)
    if slide.get("frame"):
        fr = style.get("frame", {})
        img = neon_frame(img, inset=fr.get("inset", 34),
                         radius=fr.get("radius", 44),
                         width=fr.get("width", 5),
                         color=accent, glow=fr.get("glow", 16))
    return img


def read_slides_json(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def run_neon(args, style: dict):
    data = read_slides_json(args.slides)
    slides = data["slides"]
    os.makedirs(args.out, exist_ok=True)
    ext = args.format
    for i, s in enumerate(slides, start=1):
        bg_path = os.path.join(args.bgdir, s["bg"])
        if not os.path.exists(bg_path):
            sys.exit(f"Немає фону: {bg_path} — згенеруй через tools/gen_bg.py")
        img = render_neon_slide(bg_path, s, style)
        name = f"slide-{i:02d}.{ext}"
        img.save(os.path.join(args.out, name), quality=92)
        print(f"{name} ✓")
    print(f"Готово: {len(slides)} слайдів у {args.out}")


def read_slides(path: str):
    with open(path, encoding="utf-8") as f:
        raw = f.read().strip()
    slides = [s.strip().split("\n") for s in raw.split("\n---\n")]
    return [s for s in slides if any(x.strip() for x in s)]


def main():
    ap = argparse.ArgumentParser(description="Генератор Instagram-каруселі 1080×1350")
    ap.add_argument("--photo", required=False, help="портретне фото (jpg/png), режим classic")
    ap.add_argument("--slides", required=True, help="txt (classic) або slides.json (neon)")
    ap.add_argument("--out", required=True, help="папка для готових слайдів")
    ap.add_argument("--style", default=None, help="json зі стилем (опційно)")
    ap.add_argument("--format", default="jpg", choices=["jpg", "png"])
    ap.add_argument("--mode", default="classic", choices=["classic", "neon"],
                    help="classic: фото+текст; neon: ШІ-фони + неоновий текст")
    ap.add_argument("--bgdir", default=None, help="папка з фонами (режим neon)")
    args = ap.parse_args()

    style = {}
    if args.style and os.path.exists(args.style):
        with open(args.style, encoding="utf-8") as f:
            style = json.load(f)

    if args.mode == "neon":
        if not args.bgdir:
            sys.exit("Режим neon потребує --bgdir з фонами (згенеруй через tools/gen_bg.py).")
        run_neon(args, style)
        return

    if not args.photo:
        sys.exit("Режим classic потребує --photo.")

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
