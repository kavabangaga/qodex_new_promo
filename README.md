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

- **Боевой сайт https://qodex.tech** — из ветки `main` рабочего репозитория SIGNALL-D/qodex-site:
  GitHub Actions собирает, проверяет и выкладывает сайт на сервер (`.github/workflows/deploy-prod.yml`).
  Ветка `dev` — черновики: сборка и проверки без выкладки. Как устроено, как откатить версию и что
  настроено на сервере — [`deploy/README.md`](deploy/README.md).
- **Предварительная версия** — GitHub Pages личного репозитория kavabangaga/qodex_new_promo при отправке
  в его ветку `main` (`.github/workflows/deploy.yml`). Закрыта от поисковиков, форма заявки письма не отправляет.
