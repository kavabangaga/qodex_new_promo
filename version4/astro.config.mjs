import { defineConfig } from 'astro/config';

// На GitHub Pages сайт живёт по адресу https://логин.github.io/имя-репозитория/ —
// адрес и подпапку передаёт сборка на GitHub (SITE_URL, SITE_BASE).
// Локально и для боевого qodex.tech — корень домена.
// Версия v4 — редизайн по мотивам calendly.com (на GitHub это /v4/).
export default defineConfig({
  site: process.env.SITE_URL ?? 'https://qodex.tech',
  base: process.env.SITE_BASE ?? '/',
  devToolbar: { enabled: false },
});
