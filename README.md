# QODEX — главная страница qodex.tech (предварительная версия)

Главная страница сайта QODEX: автоматизация учёта отходов для региональных операторов ТКО.
Статический сайт на [Astro](https://astro.build).

- `version2_wide/` — версия на всю ширину экрана: https://kavabangaga.github.io/qodex_new_promo/
- `version 2/` — та же страница с контентом по центру: https://kavabangaga.github.io/qodex_new_promo/v2/

Код у обеих версий общий, отличается только файл `src/config/layout.ts`.

## Запуск на своём компьютере

```bash
cd version2_wide
npm install
npm run dev
```

## Публикация

При каждой отправке в ветку `main` GitHub сам собирает обе версии и выкладывает их на GitHub Pages
(`.github/workflows/deploy.yml`). Предварительная версия закрыта от поисковиков.
