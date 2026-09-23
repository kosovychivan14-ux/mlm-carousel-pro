#!/usr/bin/env python3
"""gen_bg.py — генерує ШІ-фони для neon-каруселі (Nano Banana) зі spend guard.

Читає slides.json, для кожного слайда без готового фону:
  1. guard.py check  -> стоп, якщо бюджет перевищено
  2. bin/gemini image --ref <обличчя> --prompt <scene>
  3. guard.py log

Використання:
    python3 tools/gen_bg.py --slides examples/neon-mlm-system/slides.json \\
        --bgdir examples/neon-mlm-system/bg \\
        --ref assets/face-ref-1.jpg --ref assets/face-ref-2.jpg \\
        [--model gemini-3.1-flash-image] [--size 2K] [--aspect 4:5]
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GUARD = os.path.expanduser("~/workspace/apps/spending/guard.py")
GEMINI = os.path.expanduser("~/workspace/skills/gemini-api/bin/gemini")

# Оцінка вартості одного зображення, USD (див. guard.py GEMINI_IMAGE_USD)
COST = {
    ("gemini-3.1-flash-image", "1K"): 0.067,
    ("gemini-3.1-flash-image", "2K"): 0.101,
    ("gemini-3.1-flash-image", "4K"): 0.151,
    ("gemini-3.1-flash-lite-image", "1K"): 0.034,
    ("gemini-3.1-flash-lite-image", "2K"): 0.050,
    ("gemini-3.1-flash-lite-image", "4K"): 0.076,
    ("gemini-3-pro-image", "1K"): 0.134,
    ("gemini-3-pro-image", "2K"): 0.134,
    ("gemini-3-pro-image", "4K"): 0.240,
}
FALLBACK_COST = 0.15

BASE_PROMPT = (
    "Photorealistic promotional portrait photo, vertical composition. "
    "The same man as in the reference photos — preserve his exact facial features, "
    "green eyes, short hair, light beard. Scene: {scene}. "
    "Dark studio background, deep navy black, neon cyan and purple rim lighting, "
    "cinematic tech atmosphere, ultra detailed. "
    "IMPORTANT: no text, no letters, no words, no watermark, no logo text anywhere."
)


def guard_check(amount: float, action: str) -> bool:
    r = subprocess.run(
        [sys.executable, GUARD, "check", "--service", "gemini",
         "--amount", str(amount), "--action", action],
        capture_output=True, text=True)
    print(f"[guard] {r.stdout.strip()}")
    return r.returncode == 0


def guard_log(amount: float, action: str, note: str = ""):
    subprocess.run(
        [sys.executable, GUARD, "log", "--service", "gemini",
         "--action", action, "--amount", str(amount), "--note", note],
        capture_output=True)


def main():
    ap = argparse.ArgumentParser(description="Генерація ШІ-фонів для neon-каруселі")
    ap.add_argument("--slides", required=True, help="slides.json")
    ap.add_argument("--bgdir", required=True, help="куди складати фони")
    ap.add_argument("--ref", action="append", required=True,
                    help="референс обличчя (можна кілька)")
    ap.add_argument("--model", default="gemini-3.1-flash-image")
    ap.add_argument("--size", default="2K", choices=["1K", "2K", "4K"])
    ap.add_argument("--aspect", default="4:5")
    ap.add_argument("--timeout", type=int, default=300)
    args = ap.parse_args()

    with open(args.slides, encoding="utf-8") as f:
        slides = json.load(f)["slides"]
    os.makedirs(args.bgdir, exist_ok=True)

    cost = COST.get((args.model, args.size), FALLBACK_COST)
    made = skipped = 0
    for i, s in enumerate(slides, start=1):
        out = os.path.join(args.bgdir, s["bg"])
        if os.path.exists(out):
            print(f"[{i}/{len(slides)}] {s['bg']} — вже є, пропускаю")
            skipped += 1
            continue
        action = f"neon bg {i}/{len(slides)} {args.model} {args.size}"
        if not guard_check(cost, action):
            sys.exit(f"Зупинено spend guard перед {s['bg']}")
        prompt = BASE_PROMPT.format(scene=s["scene"])
        cmd = [sys.executable, GEMINI, "image", "--model", args.model,
               "--prompt", prompt, "--size", args.size, "--aspect", args.aspect,
               "--timeout", str(args.timeout)]
        for r in args.ref:
            cmd += ["--ref", r]
        cmd += ["-o", out]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0 or not os.path.exists(out):
            print(f"[{i}/{len(slides)}] ПОМИЛКА {s['bg']}:\n{r.stderr[-800:]}")
            sys.exit(1)
        guard_log(cost, action, note=s["bg"])
        made += 1
        print(f"[{i}/{len(slides)}] {s['bg']} ✓")
    print(f"Готово: згенеровано {made}, пропущено {skipped} (уже були).")


if __name__ == "__main__":
    main()
