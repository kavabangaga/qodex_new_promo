// Типографика при генерации HTML: предлоги и союзы не висят в конце строки,
// тире не переносится в начало строки, число не отрывается от слова,
// «РО-БОТ» и «IT-компания» не рвутся по дефису.
// Меняется только текст между тегами; скрипты, стили, <title> и атрибуты не трогаются.
// Вторым проходом раздвигаются буквы, которые слипаются в заголовках (lib/tight-pairs.ts).
import { defineMiddleware } from 'astro:middleware';
import { spaceTightPairs } from './lib/tight-pairs';

const NB = ' ';
const NB_HYPHEN = '‑';

// Тег начинается с «<» и буквы (или «/», «!», «?») — как в самом HTML: «< 5 минут» в тексте остаётся текстом.
const SKIP = /(<!--[\s\S]*?-->|<script\b[\s\S]*?<\/script>|<style\b[\s\S]*?<\/style>|<title\b[\s\S]*?<\/title>|<textarea\b[\s\S]*?<\/textarea>|<[a-z/!?](?:[^>"']|"[^"]*"|'[^']*')*>)/gi;

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
  const parts = html.split(SKIP).map((part, i) => (i % 2 === 1 ? part : typograph(part)));
  const out = spaceTightPairs(parts).join('');
  return new Response(out, { status: res.status, headers: res.headers });
});
