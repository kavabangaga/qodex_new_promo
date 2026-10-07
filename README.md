# QODEX — сайт qodex.tech (предварительная версия)

Сайт QODEX: автоматизация учёта отходов для региональных операторов ТКО.
Статический сайт на [Astro](https://astro.build), код — в папке `version4/`.

- сайт: https://kavabangaga.github.io/qodex_new_promo/v4/
- описание дизайн-системы и правила страниц — `version4/DESIGN.md`

Прежние версии (`version 2`, `version2_wide`, пробная /v3/) удалены 7 октября 2026 года — они остались в истории git.
Корень сайта и адреса /v2/, /v3/ перенаправляют на /v4/.

## Запуск на своём компьютере

```bash
cd version4
npm install
npm run dev
```

## Шрифты и иконки

Шрифт — Geist (свободная лицензия OFL, пакет Fontsource).

Иконки — Hugeicons Free, стиль Stroke Rounded (лицензия MIT): https://hugeicons.com

## Публикация

При каждой отправке в ветку `main` GitHub сам собирает сайт и выкладывает его на GitHub Pages
(`.github/workflows/deploy.yml`). Предварительная версия закрыта от поисковиков.
