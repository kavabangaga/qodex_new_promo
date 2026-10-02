// Появление блоков при прокрутке, «in view» для схем и счётчики цифр.

export const reducedMotion = (): boolean =>
  window.matchMedia('(prefers-reduced-motion: reduce)').matches;

export function initReveal(): void {
  const items = document.querySelectorAll<HTMLElement>('[data-reveal], [data-inview]');
  if (!('IntersectionObserver' in window)) {
    items.forEach((el) => el.classList.add('is-in'));
    return;
  }
  const io = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        entry.target.classList.add('is-in');
        io.unobserve(entry.target);
      }
    },
    { rootMargin: '0px 0px -8% 0px', threshold: 0.12 },
  );
  items.forEach((el) => io.observe(el));
}

const fmt = (value: number, decimals: number): string =>
  value
    .toLocaleString('ru-RU', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
    .replace(/ /g, ' ');

/** <span data-count="7.5" data-decimals="1">7,5</span> — число досчитывается от нуля. */
export function initCounters(): void {
  const nodes = document.querySelectorAll<HTMLElement>('[data-count]');
  if (!nodes.length) return;
  if (reducedMotion() || !('IntersectionObserver' in window)) return;

  const run = (el: HTMLElement) => {
    // внутри могут быть обёртки раздвинутых цифр (lib/tight-pairs.ts) — в конце возвращаем разметку как была
    const final = el.innerHTML;
    const target = Number(el.dataset.count);
    const decimals = Number(el.dataset.decimals ?? 0);
    const duration = 1400;
    const start = performance.now();
    const tick = (now: number) => {
      // метка кадра бывает чуть раньше start — без нижней границы число уходит в минус
      const t = Math.min(1, Math.max(0, (now - start) / duration));
      const eased = 1 - Math.pow(1 - t, 4);
      el.textContent = fmt(target * eased, decimals);
      if (t < 1) requestAnimationFrame(tick);
      else el.innerHTML = final;
    };
    el.textContent = fmt(0, decimals);
    requestAnimationFrame(tick);
  };

  const io = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        run(entry.target as HTMLElement);
        io.unobserve(entry.target);
      }
    },
    { threshold: 0.6 },
  );
  nodes.forEach((el) => io.observe(el));
}
