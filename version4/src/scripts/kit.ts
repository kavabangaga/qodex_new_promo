// Поведение общих приёмов v4: аккордеон с автопереключением и цепочка карточек.
import { reducedMotion } from './motion';

/** Таймер, который можно ставить на паузу и продолжать с того же места. */
function pausableTimer(onDone: () => void) {
  let timer = 0;
  let startedAt = 0;
  let elapsed = 0;
  let duration = 0;
  let running = false;
  return {
    start(ms: number) {
      clearTimeout(timer);
      duration = ms;
      elapsed = 0;
      startedAt = performance.now();
      running = true;
      timer = window.setTimeout(onDone, ms);
    },
    pause() {
      if (!running) return;
      clearTimeout(timer);
      elapsed += performance.now() - startedAt;
      running = false;
    },
    resume() {
      if (running || duration === 0) return;
      startedAt = performance.now();
      running = true;
      timer = window.setTimeout(onDone, Math.max(0, duration - elapsed));
    },
    stop() {
      clearTimeout(timer);
      running = false;
      duration = 0;
    },
  };
}

/** Следит, виден ли элемент на экране. */
function watchInView(el: Element, cb: (inView: boolean) => void, threshold = 0.3) {
  if (!('IntersectionObserver' in window)) {
    cb(true);
    return;
  }
  new IntersectionObserver(([entry]) => cb(entry.isIntersecting), { threshold }).observe(el);
}

/**
 * Аккордеон: [data-acc] > .acc__item[data-acc-item] > button.acc__head + .acc__body + .acc__progress.
 * Открытый пункт рисует полосу прогресса; через data-acc-ms (6000) мс открывается следующий —
 * только пока блок на экране и курсор не над ним. data-acc-auto="false" — без автопереключения.
 * Вместе с пунктами переключаются панели [data-panes] > [data-pane] внутри ближайшего [data-acc-scope]
 * (иначе — внутри родителя аккордеона); активная панель получает класс .is-active.
 */
export function initAccordions(): void {
  document.querySelectorAll<HTMLElement>('[data-acc]').forEach((acc) => {
    const items = [...acc.querySelectorAll<HTMLElement>(':scope > [data-acc-item]')];
    if (!items.length) return;
    const scope = acc.closest<HTMLElement>('[data-acc-scope]') ?? acc.parentElement;
    const panes = scope ? [...scope.querySelectorAll<HTMLElement>('[data-panes] > [data-pane]')] : [];
    const ms = Number(acc.dataset.accMs ?? 6000);
    const auto = acc.dataset.accAuto !== 'false' && !reducedMotion();
    acc.style.setProperty('--acc-ms', `${ms}ms`);

    let index = Math.max(0, items.findIndex((it) => it.classList.contains('is-open')));
    let inView = false;
    let hover = false;
    let focus = false;
    const timer = pausableTimer(() => open(index + 1));

    const restartBar = (item: HTMLElement) => {
      const bar = item.querySelector<HTMLElement>('.acc__progress');
      if (!bar) return;
      bar.style.animation = 'none';
      void bar.offsetWidth;
      bar.style.animation = '';
    };

    const sync = () => {
      if (!auto) return;
      if (inView && !hover && !focus) {
        delete acc.dataset.paused;
        timer.resume();
      } else {
        acc.dataset.paused = '';
        timer.pause();
      }
    };

    function open(i: number) {
      index = (i + items.length) % items.length;
      items.forEach((item, k) => {
        const isOpen = k === index;
        item.classList.toggle('is-open', isOpen);
        item.querySelector('.acc__head')?.setAttribute('aria-expanded', String(isOpen));
        if (isOpen) restartBar(item);
      });
      panes.forEach((pane, k) => {
        pane.classList.toggle('is-active', k === index);
        pane.setAttribute('aria-hidden', String(k !== index));
      });
      scope?.setAttribute('data-active', String(index));
      if (auto) {
        timer.start(ms);
        sync();
      }
    }

    items.forEach((item, k) => {
      item.querySelector('.acc__head')?.addEventListener('click', () => open(k));
    });
    acc.addEventListener('pointerenter', (e) => {
      if ((e as PointerEvent).pointerType !== 'mouse') return;
      hover = true;
      sync();
    });
    acc.addEventListener('pointerleave', () => {
      hover = false;
      sync();
    });
    // пока фокус клавиатуры внутри — тоже пауза, иначе пункт закроется сам
    acc.addEventListener('focusin', () => {
      focus = true;
      sync();
    });
    acc.addEventListener('focusout', (e) => {
      if (acc.contains(e.relatedTarget as Node | null)) return;
      focus = false;
      sync();
    });
    watchInView(acc, (v) => {
      inView = v;
      sync();
    });
    open(index);
  });
}

/**
 * Цепочка карточек: [data-chain] > .chain__card. Одна карточка открыта (.is-open, шире остальных),
 * открытая переключается сама каждые data-chain-ms (5000) мс, пока цепочка на экране;
 * наведение, фокус или клик открывают карточку и ставят автопереключение на паузу.
 * На узком экране (до data-chain-narrow, по умолчанию 960 px) карточки идут столбиком —
 * там все открыты, автопереключения нет.
 */
export function initChains(): void {
  document.querySelectorAll<HTMLElement>('[data-chain]').forEach((chain) => {
    const cards = [...chain.querySelectorAll<HTMLElement>(':scope > .chain__card')];
    if (!cards.length) return;
    const ms = Number(chain.dataset.chainMs ?? 5000);
    // .98 — чтобы при дробной ширине окна (масштаб системы 125–150 %) не было «щели» между
    // этим условием и соседним min-width
    const narrow = window.matchMedia(`(max-width: ${Number(chain.dataset.chainNarrow ?? 960) + 0.98}px)`);
    let index = Math.max(0, cards.findIndex((c) => c.classList.contains('is-open')));
    let inView = false;
    let hover = false;
    let focus = false;
    const timer = pausableTimer(() => open(index + 1));
    const canAuto = () => !reducedMotion() && !narrow.matches;

    const sync = () => {
      if (!canAuto()) return timer.pause();
      if (inView && !hover && !focus) timer.resume();
      else timer.pause();
    };

    function open(i: number) {
      index = (i + cards.length) % cards.length;
      cards.forEach((card, k) => {
        card.classList.toggle('is-open', narrow.matches || k === index);
        card.setAttribute('data-open', String(k === index));
      });
      chain.setAttribute('data-active', String(index));
      if (canAuto()) {
        timer.start(ms);
        sync();
      }
    }

    cards.forEach((card, k) => {
      card.addEventListener('pointerenter', (e) => {
        if ((e as PointerEvent).pointerType !== 'mouse' || narrow.matches) return;
        hover = true;
        if (k !== index) open(k);
        sync();
      });
      card.addEventListener('focusin', () => {
        focus = true;
        if (!narrow.matches && k !== index) open(k);
        sync();
      });
      card.addEventListener('click', () => {
        if (!narrow.matches && k !== index) open(k);
      });
    });
    chain.addEventListener('pointerleave', () => {
      hover = false;
      sync();
    });
    chain.addEventListener('focusout', (e) => {
      if (chain.contains(e.relatedTarget as Node | null)) return;
      focus = false;
      sync();
    });
    narrow.addEventListener('change', () => open(index));
    watchInView(chain, (v) => {
      inView = v;
      sync();
    });
    open(index);
  });
}
