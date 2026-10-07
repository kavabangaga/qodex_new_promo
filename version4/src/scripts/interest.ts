// Общее состояние поля «Что интересно» в форме заявки.
// Пишут в него: самопроверка (блок 3), «Подобрать решение для объекта» (блок 5),
// кнопки «Подробнее» у продуктов. Читает форма. Хранится, пока посетитель на сайте.

import type { ProductId } from '../config/site';

const KEY = 'qodex:interest';
export const INTEREST_EVENT = 'qodex:interest';

function read(): Set<ProductId> {
  try {
    const raw = sessionStorage.getItem(KEY);
    return new Set(raw ? (JSON.parse(raw) as ProductId[]) : []);
  } catch {
    return new Set();
  }
}

let state = read();

function commit(): void {
  try {
    sessionStorage.setItem(KEY, JSON.stringify([...state]));
  } catch {
    /* приватный режим — состояние живёт только в памяти */
  }
  document.dispatchEvent(new CustomEvent(INTEREST_EVENT, { detail: [...state] }));
}

export function getInterest(): ProductId[] {
  return [...state];
}

export function addInterest(ids: ProductId[]): void {
  ids.forEach((id) => state.add(id));
  commit();
}

export function removeInterest(ids: ProductId[]): void {
  ids.forEach((id) => state.delete(id));
  commit();
}

export function setInterest(ids: ProductId[]): void {
  state = new Set(ids);
  commit();
}

/**
 * Клик по [data-interest="robot tonn"] отмечает в форме ровно эти продукты: окно заявки открывается
 * с продуктом той кнопки, которую нажали, а не со всем, что посетитель смотрел раньше.
 */
export function initInterestLinks(): void {
  document.addEventListener('click', (e) => {
    const el = (e.target as Element | null)?.closest<HTMLElement>('[data-interest]');
    if (!el?.dataset.interest) return;
    setInterest(el.dataset.interest.split(' ') as ProductId[]);
  });
}
