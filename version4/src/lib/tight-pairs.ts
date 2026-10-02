// Буквы, которые слипаются в заголовках.
//
// Крупный текст набран с отрицательным letter-spacing (−0.02…−0.065em), а у Geist ещё и свой
// кернинг: «ги», «го», «ку», «УТ», «7%» стоят почти вплотную уже без трекинга и в заголовке
// сливаются. Трекинг и кернинг остаются как есть — при генерации HTML первая буква такой пары
// получает свой интервал, и зазор пары становится ровно MIN. Пары, которым места хватает,
// не трогаются; ширина слова остаётся прежней с точностью до долей пикселя (кроме редких слов,
// где слиплось сразу несколько пар), поэтому в Chrome и Safari строки переносятся там же, где
// и раньше (Firefox иногда иначе уравновешивает строки заголовка). Как именно — в spaceWord().
//
// Где набор тесный, берётся из самих стилей: правила с letter-spacing читаются из исходников,
// так что новый заголовок или другой трекинг подхватываются сами. Так же читаются
// font-variant-numeric (табличные цифры не трогаем: свой интервал у одной цифры сломал бы их равную ширину),
// font-size (трекинг наследуется в пикселях: при другом кегле он в долях кегля уже не тот)
// и display (внутри flex и grid лишний элемент стал бы отдельной ячейкой и разорвал строку).
// Зазоры и кернинг пар лежат в src/data/pair-gaps.json (как пересчитать — tools/pair-gaps.js).
import GAPS from '../data/pair-gaps.json';

/** Наименьший зазор между буквами, в долях кегля. Меньше — буквы выглядят слипшимися. */
const MIN = 0.022;
/** Трекинг, с которого набор считается тесным. Обычный текст не трогаем. */
const TIGHT = -0.02;

/** Тысячные доли кегля: зазор пары с учётом кернинга (только у тесных пар) и сам кернинг (если он не нулевой). */
const GAP = GAPS.gap as unknown as Record<string, number>;
const KERN = GAPS.kern as unknown as Record<string, number>;

// ───────────────────────── что написано в стилях ─────────────────────────

interface Compound {
  tag: string;
  classes: string[];
}
interface Rule<T> {
  chain: Compound[];
  value: T;
  weight: number;
  /** Правило лежит внутри @media или @container — действует не при любой ширине окна. */
  conditional: boolean;
}
type Rules<T> = Map<string, Rule<T>[]>;

const SOURCES = import.meta.glob<string>(['../**/*.astro', '../**/*.css'], {
  query: '?raw',
  import: 'default',
  eager: true,
});

/** Простые правила CSS: селектор, тело и признак «внутри @media». @media, @supports и подобные раскрываются. */
function* eachRule(css: string, conditional = false): Generator<[selector: string, body: string, conditional: boolean]> {
  let i = 0;
  for (;;) {
    const open = css.indexOf('{', i);
    if (open < 0) return;
    const head = css.slice(i, open);
    const selector = head.slice(Math.max(head.lastIndexOf(';'), head.lastIndexOf('}')) + 1).trim();
    let depth = 1;
    let p = open + 1;
    while (p < css.length && depth) {
      if (css[p] === '{') depth++;
      else if (css[p] === '}') depth--;
      p++;
    }
    const body = css.slice(open + 1, p - 1);
    if (/^@(media|supports|layer|container)\b/.test(selector)) yield* eachRule(body, conditional || !selector.startsWith('@layer'));
    else if (!selector.startsWith('@')) yield [selector, body, conditional];
    i = p;
  }
}

/** Таблицы стилей сайта: общие идут первыми — при равном весе правило компонента сильнее. */
const SHEETS = Object.keys(SOURCES)
  .sort((a, b) => Number(b.endsWith('.css')) - Number(a.endsWith('.css')) || a.localeCompare(b))
  .flatMap((path) => {
    const src = SOURCES[path];
    const blocks = path.endsWith('.css')
      ? [{ css: src, scoped: false }]
      : [...src.matchAll(/<style\b([^>]*)>([\s\S]*?)<\/style>/g)].map((m) => ({ css: m[2], scoped: !m[1].includes('is:global') }));
    return blocks.map(({ css, scoped }) => ({ path, scoped, rules: [...eachRule(css.replace(/\/\*[\s\S]*?\*\//g, ''))] }));
  });

const COMPOUND = /^([a-z][\w-]*)?((?:\.[\w-]+)*)$/i;

/**
 * Цепочка «предок … элемент» из селектора. Понимает теги, классы и вложенность.
 * loose — всё остальное (:hover, [hidden], #id, сосед через «+») отбрасывается, и правило
 * подходит большему числу элементов, чем на самом деле: годится там, где лучше перестраховаться.
 */
function parseSelector(selector: string, loose: boolean): Compound[] | null {
  let s = selector;
  if (loose)
    s = s
      .replace(/\[[^\]]*\]/g, '')
      .replace(/:[\w-]+/g, '')
      .replace(/#[\w-]+/g, '')
      .replace(/[&*]/g, '')
      .replace(/[^\s>+~]*\s*[+~]\s*/g, '');
  const chain: Compound[] = [];
  for (const part of s.split(/\s*>\s*|\s+/).filter(Boolean)) {
    const m = COMPOUND.exec(part);
    if (!m) return null;
    chain.push({ tag: (m[1] ?? '').toLowerCase(), classes: m[2] ? m[2].slice(1).split('.') : [] });
  }
  return chain.length ? chain : null;
}

/** Все правила, где задано свойство: ключ — последний класс селектора, тег или «*». */
function readRules<T>(property: string, parse: (value: string) => T, mode: 'strict' | 'quiet' | 'loose' = 'strict'): Rules<T> {
  const loose = mode === 'loose';
  const byKey: Rules<T> = new Map();
  const declaration = new RegExp(`(?:^|[;\\s])${property}\\s*:\\s*([^;]+)`, 'g');
  let order = 0;
  for (const { path, scoped, rules } of SHEETS) {
    for (const [selectors, body, conditional] of rules) {
      const decl = [...body.matchAll(declaration)].pop();
      if (!decl) continue;
      const value = parse(decl[1].replace('!important', '').trim());
      // скобки вместе с содержимым: :global(.a) раскрывается, :not(.a, .b) и подобные убираются
      const list = selectors.replace(/:global\(([^()]*)\)/g, '$1').replace(loose ? /:[\w-]+\((?:[^()]|\([^()]*\))*\)/g : /$^/, '');
      for (const raw of list.split(',')) {
        const selector = raw.trim();
        if (selector.includes('::')) continue; // псевдоэлементы: текста страницы там нет
        const chain = parseSelector(selector, loose);
        if (!chain) {
          if (mode === 'strict') console.warn(`[tight-pairs] селектор «${selector}» (${path}) слишком сложный — ${property} этого правила не учитывается`);
          continue;
        }
        const last = chain[chain.length - 1];
        const key = last.classes.length ? `.${last.classes[last.classes.length - 1]}` : last.tag || '*';
        const classes = chain.reduce((n, c) => n + c.classes.length, 0);
        const tags = chain.filter((c) => c.tag).length;
        // Astro дописывает к каждому звену своего селектора атрибут области видимости
        const weight = ((classes + (scoped ? chain.length : 0)) * 1000 + tags * 10) * 10000 + order++;
        const bucket = byKey.get(key) ?? [];
        bucket.push({ chain, value, weight, conditional });
        byKey.set(key, bucket);
      }
    }
  }
  return byKey;
}

const TRACKING = readRules('letter-spacing', (value) => {
  const em = /^(-?\d*\.?\d+)em$/.exec(value);
  return em ? Number(em[1]) : 0;
});
const NUMERIC = readRules('font-variant-numeric', (value) => value.includes('tabular-nums'));
const RESIZED = readRules('font(?:-size)?', () => true, 'loose');
const BOXES = readRules('display', (value) => /flex|grid|contents/.test(value), 'loose');
/** Элемент — блок: текст после него начинается с новой строки. Сложные селекторы здесь просто не учитываются. */
const BLOCKS = readRules('display', (value) => /^(block|flex|grid|list-item|table|flow-root)/.test(value), 'quiet');

// ───────────────────────── разбор HTML ─────────────────────────

interface Open {
  tag: string;
  classes: string[];
  /** Трекинг текста внутри, в em. NaN — неизвестен. */
  tracking: number;
  /** Цифры внутри табличные. */
  tabular: boolean;
  /** Текст прямо в этом элементе не трогаем: это flex или grid. */
  box: boolean;
  /** По стилям это блок, хотя тег строчный (span с display: block). */
  block: boolean;
  /** Внутри текст не трогаем совсем: SVG, списки выбора и т. п. */
  skip: boolean;
}

const VOID = new Set(['area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'source', 'track', 'wbr']);
const RAW = /^<(?:script|style|title|textarea)\b/i;
const NO_TEXT = new Set(['svg', 'math', 'select', 'datalist', 'template', 'noscript', 'head', 'canvas', 'iframe', 'object', 'video', 'audio']);
/** У этих тегов свой кегль от браузера. */
const RESIZING = new Set(['small', 'big', 'sub', 'sup', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'code', 'kbd', 'samp', 'pre', 'button', 'input']);

const matches = (c: Compound, el: Open): boolean => (!c.tag || c.tag === el.tag) && c.classes.every((name) => el.classes.includes(name));

/** Правила, которые подходят элементу (stack — его предки). */
function* applied<T>(rules: Rules<T>, el: Open, stack: Open[]): Generator<Rule<T>> {
  for (const key of ['*', el.tag, ...el.classes.map((name) => `.${name}`)]) {
    for (const rule of rules.get(key) ?? []) {
      const { chain } = rule;
      if (!matches(chain[chain.length - 1], el)) continue;
      let depth = stack.length - 1;
      let ok = true;
      for (let i = chain.length - 2; i >= 0 && ok; i--) {
        while (depth >= 0 && !matches(chain[i], stack[depth])) depth--;
        ok = depth >= 0;
        depth--;
      }
      if (ok) yield rule;
    }
  }
}

/**
 * Значение, заданное элементу напрямую, — от самого сильного из подходящих правил.
 * Если какое-то правило из @media даёт другое значение, верного ответа на все ширины окна нет:
 * возвращается unknown.
 */
function own<T>(rules: Rules<T>, el: Open, stack: Open[], unknown: T): T | undefined {
  let base: Rule<T> | undefined; // самое сильное из правил вне @media
  const conditional: Rule<T>[] = [];
  for (const rule of applied(rules, el, stack)) {
    if (rule.conditional) conditional.push(rule);
    else if (!base || rule.weight > base.weight) base = rule;
  }
  // правило из @media, которое при своей ширине окна перебивает обычное и даёт другое значение
  if (conditional.some((rule) => (!base || rule.weight > base.weight) && rule.value !== base?.value)) return unknown;
  return base?.value;
}

/** Хотя бы одно подходящее правило (в любом @media) даёт true. */
function any(rules: Rules<boolean>, el: Open, stack: Open[]): boolean {
  for (const rule of applied(rules, el, stack)) if (rule.value) return true;
  return false;
}

// Сущность — один знак. Точка с запятой необязательна: «&nbsp» и «&amp» браузер тоже понимает.
const ENTITY = /(&(?:#\d+|#x[\da-f]+|[a-z][a-z\d]*);?)/i;
const SPACE_ENTITY = /^&(?:nbsp|ensp|emsp|thinsp|#160|#xa0);?$/i;
const DIGIT = /\d/;
/** Пропавший кернинг меньше этого не возвращаем: сдвиг на сотую кегля не виден. */
const SMALL = 0.012;
/** Запас к зазору на разницу кернинга между начертаниями — чтобы он не вышел меньше MIN. */
const PAD = 0.001;
/** Запас на ту же разницу — чтобы слово не вышло шире прежнего. */
const SLACK = 0.002;
/** Сильнее этого остальные интервалы слова не сжимаем — дальше сужается пробел после слова. */
const SQUEEZE_MAX = 0.006;
/** И пробел после слова сужаем не больше, чем на столько. */
const TAIL_MAX = 0.05;

/** Число для CSS: до четырёх знаков, без лишних нулей. */
const css = (value: number): string => (Number(value.toFixed(4)) || 0).toString().replace(/^(-?)0\./, '$1.');
/** Округление вверх до четырёх знаков. */
const up = (value: number): number => Math.ceil(value * 1e4 - 1e-7) / 1e4;

/**
 * Свой интервал после буквы: число — точный, под зазор MIN; 'kern' — повторяет пропавший
 * кернинг; 'tail' — последняя буква слова, после неё сужается пробел.
 */
type Own = number | 'kern' | 'tail' | undefined;

/**
 * Слово (знаки без пробелов; сущность вроде &amp; — один знак), в котором есть слипшиеся пары.
 *
 * Первая буква такой пары заворачивается в <span class="kg"> со своим letter-spacing — ровно
 * таким, чтобы зазор стал MIN. У буквы в обёртке нет кернинга с соседями (см. .kg в global.css),
 * поэтому интервал считается от зазора без кернинга. По той же причине пропадает кернинг
 * у пары слева от обёртки: если он заметный, предыдущая буква тоже получает обёртку
 * с интервалом, который его повторяет.
 *
 * Чтобы слово не стало шире и заголовок не перенёсся по-другому, оно целиком лежит
 * в <span class="kw"> с чуть более тесным трекингом: на сколько раздвинуты пары, на столько
 * в сумме сжаты остальные интервалы — на x каждый. Если пар в слове много и x вышел бы
 * заметным, остаток забирает интервал после последней буквы, то есть пробел за словом
 * (spaced: он там действительно есть — иначе к слову притянулся бы следующий знак).
 * И у него есть предел: слово, где слиплось сразу несколько пар, становится чуть шире.
 */
function spaceWord(units: string[], ctx: Open, spaced: boolean): string | null {
  const n = units.length;
  const ls = ctx.tracking;
  const gap: (number | undefined)[] = [];
  const kern: number[] = [];
  let glued = false;
  for (let i = 0; i < n - 1; i++) {
    const pair = units[i] + units[i + 1];
    // табличные цифры — другие знаки, без кернинга; точечный интервал сломал бы их равную ширину,
    // поэтому их не трогаем (если слипаются — элементу нужен трекинг не теснее −0.025em)
    const tabular = ctx.tabular && DIGIT.test(pair);
    const g = tabular ? undefined : GAP[pair];
    gap.push(g === undefined ? undefined : g / 1000);
    kern.push(tabular ? 0 : (KERN[pair] ?? 0) / 1000);
    if (g !== undefined && g / 1000 + ls < MIN) glued = true;
  }
  if (!glued) return null;

  // Пары, которым уже выдан точный интервал. Список только растёт: иначе пара на границе
  // (зазор чуть больше MIN) то попадала бы в него, то выпадала, и расчёт не сходился бы.
  let exact: boolean[] = new Array(n).fill(false);

  /** Расстановка обёрток при сжатии x: справа налево, потому что обёртка лишает кернинга пару слева. */
  const plan = (x: number, tail: boolean) => {
    const own: Own[] = new Array(n).fill(undefined);
    let wider = 0; // на сколько слово стало бы шире, не сожми мы остальные интервалы
    let squeezed = n; // сколько интервалов сжимается на x
    let grew = false; // появились новые пары с точным интервалом
    if (tail) {
      own[n - 1] = 'tail';
      squeezed--;
    }
    for (let i = n - 2; i >= 0; i--) {
      const g = gap[i];
      // следующая буква в обёртке — кернинга у пары уже нет: заметный вернём, мелкий оставим как есть
      const split = own[i + 1] !== undefined;
      const restore = split && Math.abs(kern[i]) > SMALL;
      const lost = split && !restore ? kern[i] : 0;
      if (g !== undefined && (exact[i] || g - lost + ls - x < MIN)) {
        grew ||= !exact[i];
        exact[i] = true;
        const spacing = up(MIN + PAD - (g - kern[i]));
        own[i] = spacing;
        wider += spacing - ls - kern[i] + SLACK;
        squeezed--;
      } else if (restore) {
        own[i] = 'kern';
        wider += SLACK;
      } else if (lost) {
        wider += SLACK - lost;
      }
    }
    return { own, wider, squeezed, grew };
  };

  let x = 0;
  let { own, wider, squeezed, grew } = plan(x, false);
  // список пар растёт не больше n раз, после этого x перестаёт меняться
  for (let round = 0; round < 2 * n + 4; round++) {
    const next = up(wider / squeezed);
    if (next === x && !grew) break;
    x = next;
    ({ own, wider, squeezed, grew } = plan(x, false));
  }
  let tail = 0;
  if (x > SQUEEZE_MAX) {
    // сжатие ограничено: считаем заново при x = SQUEEZE_MAX, один проход
    x = SQUEEZE_MAX;
    exact = new Array(n).fill(false);
    ({ own, wider, squeezed } = plan(x, spaced));
    if (spaced) tail = Math.min(TAIL_MAX, Math.max(x, up(wider - x * squeezed)));
  }

  let out = `<span class="kw" style="letter-spacing:${css(ls - x)}em">`;
  units.forEach((unit, i) => {
    const o = own[i];
    const spacing = o === 'kern' ? ls - x + kern[i] : o === 'tail' ? ls - tail : o;
    out += spacing === undefined ? unit : `<span class="kg" style="letter-spacing:${css(spacing)}em">${unit}</span>`;
  });
  return `${out}</span>`;
}

/** spaceAfter — за текстом на той же строке идёт пробел или блок закончился (а не знак из соседнего тега). */
function spaceText(text: string, ctx: Open, spaceAfter: boolean): string {
  let out = '';
  let word: string[] = [];
  const flush = (spaced: boolean) => {
    out += (word.length > 1 && spaceWord(word, ctx, spaced)) || word.join('');
    word = [];
  };
  for (const chunk of text.split(ENTITY)) {
    if (ENTITY.test(chunk)) {
      if (SPACE_ENTITY.test(chunk)) {
        flush(true);
        out += chunk;
      } else word.push(chunk);
      continue;
    }
    // знак — буква вместе со своими надстрочными (диакритикой), чтобы обёртка их не разлучила
    for (const ch of chunk.match(/[\s\S]\p{M}*/gu) ?? []) {
      if (/^\s/.test(ch)) {
        flush(true);
        out += ch;
      } else word.push(ch);
    }
  }
  flush(spaceAfter);
  return out;
}

const TAG_HEAD = /^<(\/?)([a-z][\w:-]*)/i;
/** Строчные теги: текст до и после них стоит на одной строке вплотную. */
const INLINE = new Set(['a', 'abbr', 'b', 'bdi', 'bdo', 'cite', 'code', 'data', 'del', 'dfn', 'em', 'font', 'i', 'ins', 'kbd', 'label', 'mark', 'q', 's', 'samp', 'small', 'span', 'strong', 'sub', 'sup', 'time', 'u', 'var', 'wbr']);
const STARTS_WITH_SPACE = /^(?:\s|&(?:nbsp|ensp|emsp|thinsp|#160|#xa0);?)/i;

/**
 * За куском текста parts[i] идёт пробел или конец блока — а не знак вплотную, из соседнего
 * строчного тега («17</span>%»). stack — элементы, открытые в этом месте.
 */
function spaceFollows(parts: string[], i: number, stack: Open[]): boolean {
  let depth = stack.length;
  let opened = 0; // строчные теги, открытые уже после текста
  for (let k = i + 1; k < parts.length; k++) {
    const part = parts[k];
    if (k % 2 === 0) {
      if (part) return STARTS_WITH_SPACE.test(part);
      continue;
    }
    const head = TAG_HEAD.exec(part);
    if (!head) continue; // комментарий
    const tag = head[2].toLowerCase();
    if (!INLINE.has(tag)) return true; // блок, <br>, картинка
    if (!head[1]) {
      // строчный тег, который по стилям блок (span с display: block), начинает новую строку
      const next: Open = { tag, classes: attr(part, 'class').split(/\s+/).filter(Boolean), tracking: 0, tabular: false, box: false, block: false, skip: false };
      if (own(BLOCKS, next, stack.slice(0, depth), false)) return true;
      opened++;
    } else if (opened) opened--;
    // вышли из своего элемента: он сам блок, или вокруг flex/grid, где сосед — отдельная ячейка
    else if (--depth >= 0 && (stack[depth].block || (depth > 0 && stack[depth - 1].box))) return true;
  }
  return true;
}
const attr = (tag: string, name: string): string => {
  const m = new RegExp(`\\s${name}\\s*=\\s*(?:"([^"]*)"|'([^']*)'|([^\\s>]+))`, 'i').exec(tag);
  return m?.[1] ?? m?.[2] ?? m?.[3] ?? '';
};

/**
 * parts — HTML, разрезанный на куски: на чётных местах текст, на нечётных теги
 * (а также целиком <script>, <style>, <title>, <textarea> и комментарии).
 * Пары на стыке двух тегов («7</span>%») не обрабатываются.
 */
export function spaceTightPairs(parts: string[]): string[] {
  const stack: Open[] = [];
  return parts.map((part, i) => {
    const top = stack[stack.length - 1];
    if (i % 2 === 0) {
      if (!top || top.skip || top.box || !(top.tracking <= TIGHT) || !part.trim()) return part;
      // «<» в тексте — признак разметки, которую разбор не понял: такой кусок лучше не трогать
      return part.includes('<') ? part : spaceText(part, top, spaceFollows(parts, i, stack));
    }
    const head = TAG_HEAD.exec(part);
    if (!head || RAW.test(part)) return part; // комментарий, <!doctype>, <script>…</script> целиком
    const tag = head[2].toLowerCase();
    if (head[1]) {
      const at = stack.map((el) => el.tag).lastIndexOf(tag);
      if (at >= 0) stack.length = at;
      return part;
    }
    if (VOID.has(tag) || part.endsWith('/>')) return part;
    const style = attr(part, 'style');
    const el: Open = {
      tag,
      classes: attr(part, 'class').split(/\s+/).filter(Boolean),
      tracking: top?.tracking ?? 0,
      tabular: top?.tabular ?? false,
      box: false,
      block: false,
      skip: (top?.skip ?? false) || NO_TEXT.has(tag),
    };
    const tracking = own(TRACKING, el, stack, NaN);
    const resized = RESIZING.has(tag) || /font(-size)?\s*:/.test(style) || any(RESIZED, el, stack);
    // унаследованный трекинг задан в пикселях родителя: при своём кегле в em он уже другой
    el.tracking = tracking ?? (resized && el.tracking !== 0 ? NaN : el.tracking);
    el.tabular = own(NUMERIC, el, stack, true) ?? el.tabular;
    el.box = /display\s*:\s*[\w-]*(flex|grid|contents)/.test(style) || any(BOXES, el, stack);
    el.block = own(BLOCKS, el, stack, false) === true;
    if (/letter-spacing|font-variant/.test(style)) el.tracking = NaN;
    stack.push(el);
    return part;
  });
}
