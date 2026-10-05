// Типографика при генерации HTML: предлоги и союзы не висят в конце строки,
// тире не переносится в начало строки, число не отрывается от слова,
// «РО-БОТ» и «IT-компания» не рвутся по дефису.
// Меняется только текст между тегами; скрипты, стили, <title> и атрибуты не трогаются.
// Вторым проходом раздвигаются буквы, которые слипаются в заголовках (lib/tight-pairs.ts).
//
// Внутри элемента с атрибутом data-verbatim дефис остаётся обычным: неразрывный дефис (U+2011)
// не находится поиском по странице с обычным дефисом в Chrome и Safari, копируется другим символом
// и рисуется запасным шрифтом. Так размечены тексты, которые сверяют дословно: страница «Документы»
// и реквизиты в подвале (их проверяет Минцифры). Остальные правила там действуют — они меняют
// только вид пробела.
import { defineMiddleware } from 'astro:middleware';
import { spaceTightPairs } from './lib/tight-pairs';

const NB = ' ';
const NB_HYPHEN = '‑';

// Тег начинается с «<» и буквы (или «/», «!», «?») — как в самом HTML: «< 5 минут» в тексте остаётся текстом.
const SKIP = /(<!--[\s\S]*?-->|<script\b[\s\S]*?<\/script>|<style\b[\s\S]*?<\/style>|<title\b[\s\S]*?<\/title>|<textarea\b[\s\S]*?<\/textarea>|<[a-z/!?](?:[^>"']|"[^"]*"|'[^']*')*>)/gi;

function typograph(text: string, verbatim: boolean): string {
  if (!text.trim()) return text;
  const out = text
    // неразрывный пробел перед тире
    .replace(/[ \t\n]+—(?=\s)/g, `${NB}—`)
    // число не отрывается от следующего слова: «73 клиента», «10 объектов»
    .replace(/(?<=^|[\s («„])(\d+)[ \t\n]+(?=[А-Яа-яЁё])/g, `$1${NB}`)
    // короткие слова (1–2 буквы) привязываются к следующему слову
    .replace(/(?<=^|[\s («„])([А-Яа-яЁё]{1,2})[ \t\n]+(?=\S)/g, `$1${NB}`);
  if (verbatim) return out;
  // короткая первая часть слова через дефис: РО-БОТ, IT-компания, Эко-Сити
  return out.replace(/(?<=^|[\s («„])([A-Za-zА-Яа-яЁё]{1,3})-(?=[A-Za-zА-Яа-яЁё])/g, `$1${NB_HYPHEN}`);
}

const VOID = /^(area|base|br|col|embed|hr|img|input|link|meta|source|track|wbr)$/i;

/** Типограф для частей страницы (чётные — текст, нечётные — теги) с учётом областей data-verbatim. */
function typographParts(parts: string[]): string[] {
  let tag = ''; // элемент, открывший область data-verbatim
  let depth = 0; // вложенность таких же элементов внутри неё
  return parts.map((part, i) => {
    if (i % 2 === 0) return typograph(part, depth > 0);
    const m = /^<(\/?)([a-z][\w-]*)/i.exec(part);
    if (!m) return part;
    const [, close, name] = m;
    if (VOID.test(name) || part.endsWith('/>')) return part;
    if (depth > 0) {
      if (name.toLowerCase() === tag) depth += close ? -1 : 1;
    } else if (!close && /\sdata-verbatim(?=[\s=>/])/i.test(part)) {
      tag = name.toLowerCase();
      depth = 1;
    }
    return part;
  });
}

export const onRequest = defineMiddleware(async (_ctx, next) => {
  const res = await next();
  if (!res.headers.get('content-type')?.includes('text/html')) return res;
  const html = await res.text();
  const out = spaceTightPairs(typographParts(html.split(SKIP))).join('');
  return new Response(out, { status: res.status, headers: res.headers });
});
