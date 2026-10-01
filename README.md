# QODEX — главная страница qodex.tech (предварительная версия)

Главная страница сайта QODEX: автоматизация учёта отходов для региональных операторов ТКО.
Статический сайт на [Astro](https://astro.build).

- `version2_wide/` — версия на всю ширину экрана: https://kavabangaga.github.io/qodex_new_promo/
- `version 2/` — та же страница с контентом по центру: https://kavabangaga.github.io/qodex_new_promo/v2/
- проба шрифта заголовков — широкая версия, заголовки шрифтом Lebowski: https://kavabangaga.github.io/qodex_new_promo/v3/
  (собирается из `version2_wide/` с переменной `HEADING_FONT=lebowski`)
- `version4/` — отдельный редизайн по мотивам calendly.com: https://kavabangaga.github.io/qodex_new_promo/v4/
  (свой код; описание дизайн-системы — `version4/DESIGN.md`)

Код у обеих версий общий, отличается только файл `src/config/layout.ts`.

## Запуск на своём компьютере

```bash
cd version2_wide
npm install
npm run dev
```

## Шрифты

Lebowski by Pragmatica (версия /v3/) — бесплатный шрифт студии Pragmatica,
авторы Tamara Arkatova, Tanya Cherkiz, Olga Pankova: https://www.pragmatica.design/lebowski

Шрифты v4 — Geist и Source Serif 4 (свободная лицензия OFL, пакеты Fontsource).

## Публикация

При каждой отправке в ветку `main` GitHub сам собирает обе версии и выкладывает их на GitHub Pages
(`.github/workflows/deploy.yml`). Предварительная версия закрыта от поисковиков.
