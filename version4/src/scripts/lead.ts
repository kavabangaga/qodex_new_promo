// Заявка с формы → запрос к прежнему отправщику писем qodex.tech (служба mail-sender на сервере, POST /api/request;
// решение заказчика 2026-10-09 — заявки шлёт тот же отправщик, что и у прежнего сайта). Он принимает пять строк —
// name, phone, email, company, comment — и отправляет их одним письмом на info@qodex.tech. Всё остальное, что форма
// знает о заявке (продукты, откуда отправлена, метки, согласие, время), складывается в comment читаемым текстом,
// по строке на сведение: в письме это блок после «Комментарий:».

import { PRODUCTS, PRODUCT_ORDER, type ProductId } from '../config/site';

/** Ответ отправщика, когда почтовый сервер принял письмо. Любой другой ответ — заявка не ушла. */
export const SENT_OK = 'Письмо успешно отправлено';

/**
 * Длина полей в символах — maxlength полей формы (LeadForm.astro) и обрезка в toRequest: вся заявка
 * с comment остаётся далеко внутри предела тела запроса на сервере (16 КБ, deploy/nginx/qodex.tech.conf).
 */
export const NAME_MAX = 120;
export const PHONE_MAX = 40;

// ── Маска телефона «+7 (999) 999 99 99» (решение заказчика 09.10.2026) ──────────────────────────────────────
// Посетитель вводит только 10 цифр номера; «+7 (», скобки и пробелы ставятся сами. Набранные по привычке
// «8 917…» / «7 917…», вставка и автозаполнение («89173500000», «+7 917 350-00-00») приводятся к маске:
// одиннадцатая цифра с 7 или 8 в начале — код страны, он отбрасывается. Иностранные номера маска не принимает.

const PHONE_PREFIX = '+7 (';

/** 10 цифр номера без кода страны из любого написания. */
export function phoneDigits(value: string): string {
  let v = value.trim();
  if (v.startsWith('+7')) v = v.slice(2);
  let d = v.replace(/\D/g, '');
  if (d.length > 10 && /^[78]/.test(d)) d = d.slice(1);
  return d.slice(0, 10);
}

/** «9173500000» → «+7 (917) 350 00 00»; неполный номер — сколько набрано. */
export function formatPhone(d: string): string {
  if (!d) return '';
  let s = PHONE_PREFIX + d.slice(0, 3);
  if (d.length > 3) s += ') ' + d.slice(3, 6);
  if (d.length > 6) s += ' ' + d.slice(6, 8);
  if (d.length > 8) s += ' ' + d.slice(8, 10);
  return s;
}

/** Позиция в отформатированном номере сразу после n-й цифры (код страны «7» не считается). */
function caretAfter(formatted: string, n: number): number {
  if (n <= 0) return Math.min(PHONE_PREFIX.length, formatted.length);
  let seen = 0;
  for (let i = PHONE_PREFIX.length; i < formatted.length; i++) {
    if (/\d/.test(formatted[i]) && ++seen === n) return i + 1;
  }
  return formatted.length;
}

export function attachPhoneMask(input: HTMLInputElement): void {
  input.placeholder = '+7 (999) 999 99 99';

  const render = (digitsBeforeCaret: number | null) => {
    const formatted = formatPhone(phoneDigits(input.value));
    const shown = formatted || (document.activeElement === input ? PHONE_PREFIX : '');
    if (input.value !== shown) input.value = shown;
    if (digitsBeforeCaret !== null && document.activeElement === input) {
      const pos = caretAfter(shown, digitsBeforeCaret);
      input.setSelectionRange(pos, pos);
    }
  };

  // сколько цифр номера стоит до курсора в текущем (ещё не отформатированном) значении
  const digitsBefore = (): number => {
    const caret = input.selectionStart ?? input.value.length;
    const all = phoneDigits(input.value).length;
    const before = phoneDigits(input.value.slice(0, caret)).length;
    // отброшенная восьмёрка/семёрка в начале была до курсора — курсор не должен уехать на цифру вперёд
    const raw = input.value.trim().startsWith('+7') ? input.value.trim().slice(2) : input.value;
    const dropped = raw.replace(/\D/g, '').length > 10 && all === 10 ? 1 : 0;
    return Math.max(0, Math.min(all, before - (before > 0 ? dropped : 0)));
  };

  input.addEventListener('focus', () => {
    if (!input.value) {
      input.value = PHONE_PREFIX;
      requestAnimationFrame(() => input.setSelectionRange(input.value.length, input.value.length));
    }
  });
  input.addEventListener('blur', () => {
    if (!phoneDigits(input.value)) input.value = '';
  });
  input.addEventListener('input', () => render(digitsBefore()));

  // Backspace по скобке или пробелу стирает цифру перед ними, а не упирается в знак маски
  input.addEventListener('beforeinput', (e) => {
    if (e.inputType !== 'deleteContentBackward') return;
    const start = input.selectionStart ?? 0;
    if (start !== input.selectionEnd || start === 0 || /\d/.test(input.value[start - 1] ?? '')) return;
    if (start <= PHONE_PREFIX.length) {
      e.preventDefault();
      return;
    }
    let i = start - 1;
    while (i >= PHONE_PREFIX.length && !/\d/.test(input.value[i])) i--;
    if (i < PHONE_PREFIX.length) {
      e.preventDefault();
      return;
    }
    e.preventDefault();
    const keep = phoneDigits(input.value.slice(0, i)).length;
    input.value = input.value.slice(0, i) + input.value.slice(i + 1);
    render(keep);
    input.dispatchEvent(new Event('input', { bubbles: true }));
  });

  render(null);
}

/**
 * Телефон похож на настоящий: российский — 10 цифр или 11 с 7/8 в начале; иностранный (с «+», код не 7) —
 * от 10 до 15 цифр (международный предел). Иначе в заявку уходили номера вроде 79173500000000000.
 */
export function phoneOk(value: string): boolean {
  const raw = value.trim();
  const digits = raw.replace(/\D/g, '');
  if (raw.startsWith('+') && !raw.startsWith('+7')) return digits.length >= 10 && digits.length <= 15;
  return digits.length === 10 || (digits.length === 11 && /^[78]/.test(digits));
}

/**
 * Сколько ждать ответа на заявку, мс. nginx сам отвечает 504, если отправщик молчит дольше 30 с (+5 с
 * на соединение), — этот предел на случай, когда до сервера не доходит сама связь: без него запрос
 * висел бы минутами, а окно заявки, пока заявка уходит, не закрывается (LeadModal.astro).
 */
const SEND_TIMEOUT = 45_000;

/** Событие на форме (всплывает), когда отправка закончилась — успехом или ошибкой (LeadForm → LeadModal). */
export const LEAD_SETTLED_EVENT = 'qodex:lead-settled';

export interface Lead {
  name: string;
  phone: string;
  /** Отмеченные продукты, в порядке PRODUCT_ORDER. */
  interest: ProductId[];
  /** Где на странице форма: «окно заявки, открыто кнопкой …» или «форма в разделе …». */
  place: string;
  /** Полный адрес страницы, с которой отправили заявку. */
  page: string;
  utm: Record<string, string>;
  sentAt: Date;
  /** Доказательство согласия (ч. 3 ст. 9 152-ФЗ): какая редакция текста и где он лежит. */
  consent: { edition: string; text: string };
}

/** Тело запроса прежнего отправщика: ровно эти пять полей, все — строки. */
export interface LeadRequest {
  name: string;
  phone: string;
  email: string;
  company: string;
  comment: string;
}

const clean = (s: string) => s.replace(/\s+/g, ' ').trim();
const clip = (s: string, max = 90) => (s.length > max ? `${s.slice(0, max - 1).trimEnd()}…` : s);

/** Время с часовым поясом посетителя, ISO 8601: 2026-10-09T17:04:05+05:00. */
export function isoLocal(d: Date): string {
  const p = (n: number) => String(Math.abs(n)).padStart(2, '0');
  const off = -d.getTimezoneOffset();
  const date = `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
  const time = `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
  return `${date}T${time}${off < 0 ? '-' : '+'}${p(Math.trunc(off / 60))}:${p(off % 60)}`;
}

/** Где на странице элемент: шапка, подвал или раздел с его заголовком. Пустая строка — не определить. */
export function sectionOf(el: Element): string {
  // по классам шапки и подвала сайта (Header.astro, Footer.astro): <header> есть и во вводной части раздела
  if (el.closest('.hdr')) return 'шапка сайта';
  if (el.closest('.ftr')) return 'подвал';
  const sec = el.closest<HTMLElement>('section');
  if (!sec) return '';
  const labelId = sec.getAttribute('aria-labelledby')?.split(/\s+/)[0];
  const heading = (labelId && document.getElementById(labelId)) || sec.querySelector('h1, h2');
  const title = clean(heading?.textContent ?? '') || clean(sec.getAttribute('aria-label') ?? '');
  if (title) return `раздел «${clip(title)}»`;
  return sec.id ? `раздел #${sec.id}` : '';
}

/** Кнопка, которой открыли окно заявки: «кнопка «Запустить пилот», раздел «…»». */
export function describeOpener(link: HTMLElement): string {
  // innerText — только видимая надпись (у кнопки в шапке есть полная и короткая, видна одна)
  const label = clip(clean(link.innerText || link.textContent || ''), 60);
  const where = sectionOf(link);
  return [label && `кнопка «${label}»`, where].filter(Boolean).join(', ');
}

/**
 * Собирает comment: по строке на сведение, без пустых строк. Первый символ — перевод строки: отправщик пишет
 * comment сразу после «Комментарий: », и без него первая строка слиплась бы с подписью.
 */
export function leadComment(lead: Lead): string {
  const names = lead.interest.map((id) => PRODUCTS[id].name).join(', ');
  const all = PRODUCT_ORDER.every((id) => lead.interest.includes(id));
  const utm = Object.entries(lead.utm)
    .map(([k, v]) => `${k}=${v}`)
    .join(', ');
  const lines = [
    `Что интересно: ${names ? (all ? `всё вместе — ${names}` : names) : 'не отмечено'}`,
    // заявку с отмеченным Tracker обрабатываем как запрос демо, пилот по нему не обещаем
    lead.interest.includes('tracker') && 'QODEX Tracker: запрос демо (пилот по Tracker не обещаем)',
    `Откуда: ${lead.place}`,
    `Страница: ${lead.page}`,
    utm && `Метки UTM: ${utm}`,
    `Согласие на обработку персональных данных: дано, редакция от ${lead.consent.edition}, текст: ${lead.consent.text}`,
    `Отправлено: ${isoLocal(lead.sentAt)} (часы посетителя)`,
  ];
  return '\n' + lines.filter(Boolean).join('\n');
}

/** Без пробелов по краям и не длиннее max символов (по символам, а не по половинкам эмодзи). */
const field = (s: string, max: number) => [...s.trim()].slice(0, max).join('').trimEnd();

/**
 * Пять полей прежнего отправщика. Почты и компании форма не спрашивает — пустые строки, а не пропуск:
 * пропущенное поле отправщик печатает в письме словом «None».
 */
export function toRequest(lead: Lead): LeadRequest {
  return {
    name: field(lead.name, NAME_MAX),
    phone: field(lead.phone, PHONE_MAX),
    email: '',
    company: '',
    comment: leadComment(lead),
  };
}

/**
 * Отправляет заявку. Отправщик отвечает 200 и тогда, когда письмо не ушло, — поэтому успех только один:
 * ответ 200 с JSON {"status": SENT_OK}. Другой статус, другой текст, не JSON, обрыв связи, нет ответа
 * за SEND_TIMEOUT — ошибка (исключение).
 */
export async function sendLead(endpoint: string, body: LeadRequest): Promise<void> {
  const ctl = new AbortController();
  const timer = window.setTimeout(() => ctl.abort(), SEND_TIMEOUT);
  try {
    const res = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: ctl.signal,
    });
    const answer: unknown = await res.json().catch(() => null);
    const status = answer && typeof answer === 'object' ? (answer as { status?: unknown }).status : undefined;
    if (res.status !== 200 || status !== SENT_OK) throw new Error(`${res.status} ${String(status)}`);
  } finally {
    window.clearTimeout(timer);
  }
}
