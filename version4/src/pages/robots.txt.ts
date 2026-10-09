// robots.txt. Боевой qodex.tech открыт поисковикам целиком и называет карту сайта (sitemap.xml собирает
// integrations/sitemap.mjs). Служебные страницы не запрещаем здесь: их закрывает <meta name="robots"
// content="noindex">, а запрет в robots.txt помешал бы поисковику эту метку прочитать.
// Предварительная версия (PUBLIC_NOINDEX=1, не qodex.tech) закрыта целиком.
import type { APIRoute } from 'astro';
import { SITE } from '../config/site';
import { NOINDEX_ALL } from '../config/build';

export const GET: APIRoute = () => {
  const body = NOINDEX_ALL
    ? 'User-agent: *\nDisallow: /\n'
    : `User-agent: *\nAllow: /\n\nSitemap: ${new URL('/sitemap.xml', SITE.url).href}\n`;
  return new Response(body, { headers: { 'Content-Type': 'text/plain; charset=utf-8' } });
};
