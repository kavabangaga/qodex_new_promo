// Сведения о сборке: номер версии на боевом сервере, закрыта ли сборка от поисковиков
// и адрес страницы на qodex.tech для canonical.
import { SITE } from './site';

/**
 * Номер версии (ГГГГММДД-ЧЧММСС-коммит). Его задаёт выкладка на боевой (.github/workflows/deploy-prod.yml)
 * переменной PUBLIC_BUILD_ID; страницы показывают его в <meta name="qodex-build">, и проверка после выкладки
 * (deploy/ci/smoke.sh) по нему узнаёт, что qodex.tech отдаёт именно эту версию. Без переменной метки нет.
 */
export const BUILD_ID: string = import.meta.env.PUBLIC_BUILD_ID ?? '';

/**
 * Вся сборка закрыта от поисковиков: предварительная версия на GitHub Pages (сборка с PUBLIC_NOINDEX=1)
 * и любая сборка не для qodex.tech (SITE_URL с другим доменом).
 */
export const NOINDEX_ALL: boolean =
  import.meta.env.PUBLIC_NOINDEX === '1' ||
  new URL(import.meta.env.SITE ?? SITE.url).hostname !== new URL(SITE.url).hostname;

/**
 * Адрес на боевом сайте: https://qodex.tech/путь. Подпапка предварительной версии (/qodex_new_promo/v4/)
 * срезается — canonical страниц на GitHub Pages указывает на ту же страницу qodex.tech.
 */
export function prodUrl(pathname: string): string {
  const base = import.meta.env.BASE_URL.replace(/\/$/, '');
  const inBase = base !== '' && (pathname === base || pathname.startsWith(`${base}/`));
  return new URL(inBase ? pathname.slice(base.length) || '/' : pathname, SITE.url).href;
}
