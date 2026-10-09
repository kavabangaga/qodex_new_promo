// Общее состояние поля «Что интересно» в форме заявки.
// Пишут в него: самопроверка (блок 3), «Подобрать решение для объекта» (блок 5), кнопки с data-interest,
// страница продукта (её продукт отмечен в формах этой страницы). Читает форма.
// Живёт только на текущей странице: между страницами не переносится (решение заказчика 09.10.2026 —
// посмотрел страницу Tracker, вернулся на главную, открыл заявку — ничего не отмечено, выбирает сам).

import type { ProductId } from '../config/site';

export const INTEREST_EVENT = 'qodex:interest';

// прежние версии сайта хранили выбор в sessionStorage — убираем, чтобы он не всплыл у вернувшихся посетителей
try {
  sessionStorage.removeItem('qodex:interest');
} catch {
  /* приватный режим */
}

let state = new Set<ProductId>();

function commit(): void {
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
