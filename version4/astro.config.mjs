import { defineConfig } from 'astro/config';
import sitemap from './integrations/sitemap.mjs';

// На GitHub Pages сайт живёт по адресу https://логин.github.io/имя-репозитория/ —
// адрес и подпапку передаёт сборка на GitHub (SITE_URL, SITE_BASE).
// Локально и для боевого qodex.tech — корень домена.
// Версия v4 — редизайн по мотивам calendly.com (на GitHub это /v4/).
// Переменные сборки для страниц (PUBLIC_*): PUBLIC_BUILD_ID и PUBLIC_NOINDEX — src/config/build.ts,
// PUBLIC_FORM_ENDPOINT и PUBLIC_METRIKA_ID — src/config/site.ts.
export default defineConfig({
  site: process.env.SITE_URL ?? 'https://qodex.tech',
  base: process.env.SITE_BASE ?? '/',
  devToolbar: { enabled: false },
  // sitemap.xml по готовым страницам (integrations/sitemap.mjs)
  integrations: [sitemap()],
});
