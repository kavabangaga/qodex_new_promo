// Карта сайта sitemap.xml. Собирается после сборки по готовым страницам: в карту попадает страница,
// открытая поисковикам (нет <meta name="robots" content="…noindex…">), которая сама себе canonical, —
// под адресом из canonical. Служебные (/preview/), переадресации со старых адресов и 404 закрыты noindex
// или ссылаются на другой адрес, поэтому в карту не попадают; новая страница попадёт в неё сама.
// У предварительной версии (PUBLIC_NOINDEX=1) закрыты все страницы — карта пустая.
import { readdir, readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const escapeXml = (s) =>
  s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;' })[c]);

export default function sitemap() {
  return {
    name: 'qodex-sitemap',
    hooks: {
      'astro:build:done': async ({ dir, logger }) => {
        const root = fileURLToPath(dir);
        const files = (await readdir(root, { recursive: true }))
          .map((f) => f.split(path.sep).join('/'))
          .filter((f) => f.endsWith('.html') && f !== '404.html' && !f.startsWith('preview/') && !f.startsWith('s/'));

        const urls = new Set();
        for (const rel of files) {
          const html = await readFile(path.join(root, rel), 'utf8');
          if (/<meta name="robots" content="[^"]*noindex/i.test(html)) continue;
          const canonical = /<link rel="canonical" href="([^"]+)"/.exec(html)?.[1];
          if (!canonical) continue;
          // адрес самой страницы: ro-bot/index.html → /ro-bot/, privacy.html → /privacy
          const own = `/${rel.replace(/(^|\/)index\.html$/, '$1').replace(/\.html$/, '')}`;
          const url = new URL(canonical);
          if (url.pathname !== own || url.search || url.hash) continue;
          urls.add(url.href);
        }

        const sorted = [...urls].sort((a, b) => new URL(a).pathname.localeCompare(new URL(b).pathname, 'en'));
        const xml = [
          '<?xml version="1.0" encoding="UTF-8"?>',
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
          ...sorted.map((u) => `  <url><loc>${escapeXml(u)}</loc></url>`),
          '</urlset>',
          '',
        ].join('\n');
        await writeFile(path.join(root, 'sitemap.xml'), xml);
        logger.info(`sitemap.xml: страниц — ${sorted.length}`);
      },
    },
  };
}
