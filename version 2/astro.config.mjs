import { defineConfig } from 'astro/config';

// На GitHub Pages сайт живёт по адресу https://логин.github.io/имя-репозитория/ —
// адрес и подпапку передаёт сборка на GitHub (SITE_URL, SITE_BASE).
// Локально и для боевого qodex.tech — корень домена.
// HEADING_FONT=lebowski — пробная версия с другим шрифтом заголовков (на GitHub это /v3/).
export default defineConfig({
  site: process.env.SITE_URL ?? 'https://qodex.tech',
  base: process.env.SITE_BASE ?? '/',
  devToolbar: { enabled: false },
  vite: {
    define: {
      'import.meta.env.HEADING_FONT': JSON.stringify(process.env.HEADING_FONT ?? ''),
    },
  },
});
