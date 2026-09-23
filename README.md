# mlm-carousel-pro

Генератор Instagram-каруселі з твого фото. Бере портрет і текст слайдів —
видає готову серію **1080×1350 (4:5)**: обкладинка → слайди → фінал із закликом до дії.

Зроблено для швидкої генерації каруселей асистентом: ти даєш тему й фото,
а скрипт складає оформлені слайди в єдиному стилі.

## Встановлення

```bash
pip install -r requirements.txt
```

## Використання

1. Підготуй `slides.txt` — слайди розділені рядком `---`.
   Перший слайд = обкладинка, останній = фінал (CTA).
   Усередині слайда перший рядок — заголовок, решта — текст.

```
Як я змонтував це відео за 10 хвилин
---
1. Нарізка
Прибираю паузи — лишається тільки суть
---
Хочеш так само?
Напиши «МОНТАЖ» в коментарях
```

2. Запусти:

```bash
python3 carousel.py --photo me.jpg --slides slides.txt --out out/
```

Готові слайди: `out/slide-01-cover.jpg`, `out/slide-02.jpg`, …,
`out/slide-0N-final.jpg`.

## Стиль

`--style styles/default.json` — акцентний колір, сила затемнення,
підказка «гортай →», підпис на фіналі. Скопіюй і прав під себе.

## Приклад

Готовий приклад тексту — в `examples/slides-example.txt`.

## Режим neon-mlm (ШІ-фони + неоновий текст)

Стиль як у темних неонових каруселей з портретом: обличчя, поза, одяг
і емоції змінюються від слайда до слайда (фони генерує Nano Banana
за твоїм референсом обличчя), а заголовки з акцентним словом кладе код.
Структура: проблема → вирішення → заклик до дії.

1. Опиши слайди в `slides.json`:

```json
{"slides": [{
  "bg": "bg-01.png",
  "side": "left",
  "title": "Люди досі роблять контент *вручну* 😅",
  "subtitle": "Поки я натискаю 1 кнопку і отримую все готове за секунди.",
  "accent": "#00E5FF",
  "frame": false,
  "scene": "confident man in black suit next to a glowing holographic pedestal..."
}]}
```

`*слово*` — акцентний колір, емодзі підтримуються.
`scene` — англомовний опис сцени для фону (без тексту на фоні).

2. Згенеруй фони (потрібен підключений Gemini API; spend guard вшито —
перевірка бюджету перед кожним зображенням, запис у леджер після):

```bash
python3 tools/gen_bg.py --slides examples/neon-mlm-system/slides.json \
    --bgdir examples/neon-mlm-system/bg \
    --ref assets/face-ref-1.jpg --ref assets/face-ref-2.jpg
```

Готові фони не перегенеровуються повторно.

3. Наклади текст:

```bash
python3 carousel.py --mode neon \
    --slides examples/neon-mlm-system/slides.json \
    --bgdir examples/neon-mlm-system/bg \
    --out examples/neon-mlm-system/output/ \
    --style styles/neon-mlm.json
```

Повний робочий приклад — в `examples/neon-mlm-system/`.
