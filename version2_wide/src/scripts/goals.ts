import { METRIKA_ID } from '../config/site';

type Ym = (id: number, action: 'reachGoal', goal: string, params?: Record<string, unknown>) => void;

/** Отправляет цель в Яндекс Метрику, если счётчик подключён. */
export function goal(name: string, params?: Record<string, unknown>): void {
  const ym = (window as unknown as { ym?: Ym }).ym;
  if (METRIKA_ID && typeof ym === 'function') ym(METRIKA_ID, 'reachGoal', name, params);
}

/** Клики по элементам с data-goal="имя_цели" отправляются автоматически. */
export function initGoals(): void {
  document.addEventListener('click', (e) => {
    const el = (e.target as Element | null)?.closest<HTMLElement>('[data-goal]');
    if (!el?.dataset.goal) return;
    goal(el.dataset.goal, el.dataset.goalProduct ? { product: el.dataset.goalProduct } : undefined);
  });
}
