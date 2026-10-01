// Типографика при генерации HTML: предлоги и союзы не висят в конце строки,
// тире не переносится в начало строки, число не отрывается от слова,
// «РО-БОТ» и «IT-компания» не рвутся по дефису.
// Меняется только текст между тегами; скрипты, стили, <title> и атрибуты не трогаются.
import { defineMiddleware } from 'astro:middleware';

const NB = ' ';
const NB_HYPHEN = '‑';

const SKIP = /(<script[\s\S]*?<\/script>|<style[\s\S]*?<\/style>|<title[\s\S]*?<\/title>|<textarea[\s\S]*?<\/textarea>|<[^>]+>)/g;

function typograph(text: string): string {
  if (!text.trim()) return text;
  return (
    text
      // неразрывный пробел перед тире
      .replace(/[ \t\n]+—(?=\s)/g, `${NB}—`)
      // число не отрывается от следующего слова: «73 клиента», «10 объектов»
      .replace(/(?<=^|[\s («„])(\d+)[ \t\n]+(?=[А-Яа-яЁё])/g, `$1${NB}`)
      // короткие слова (1–2 буквы) привязываются к следующему слову
      .replace(/(?<=^|[\s («„])([А-Яа-яЁё]{1,2})[ \t\n]+(?=\S)/g, `$1${NB}`)
      // короткая первая часть слова через дефис: РО-БОТ, IT-компания, Эко-Сити
      .replace(/(?<=^|[\s («„])([A-Za-zА-Яа-яЁё]{1,3})-(?=[A-Za-zА-Яа-яЁё])/g, `$1${NB_HYPHEN}`)
  );
}

export const onRequest = defineMiddleware(async (_ctx, next) => {
  const res = await next();
  if (!res.headers.get('content-type')?.includes('text/html')) return res;
  const html = await res.text();
  const out = html
    .split(SKIP)
    .map((part, i) => (i % 2 === 1 ? part : typograph(part)))
    .join('');
  return new Response(out, { status: res.status, headers: res.headers });
});
