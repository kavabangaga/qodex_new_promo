// Денежный поток на первом экране: частицы идут через четыре шлюза
// (база начислений → маршрут → весы → ФГИС).
//
// Выключенный шлюз — тусклый пунктирный круг: часть денег серыми каплями утекает вниз.
// Включённый шлюз окрашивает поток в цвет продукта, поток плавно обтекает круг,
// а от круга с ровным интервалом спокойно расходятся волны.

interface Ripple {
  r: number;
  a: number;
}

interface Gate {
  x: number;
  color: string;
  active: boolean;
  core: number; // радиус круга с иконкой (HTML), px
  lens: number; // 0..1 — насколько поток обтекает круг, плавно растёт при включении
  hover: number; // 0..1 — курсор рядом
  pulse: number; // 0..1 — ударная волна при включении
  ripples: Ripple[];
  clock: number; // кадры до следующей волны
}

type State = 'flow' | 'leak';

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  base: number;
  side: number;
  len: number;
  color: string;
  alpha: number;
  state: State;
  next: number;
}

export interface FlowOptions {
  canvas: HTMLCanvasElement;
  /** Центры шлюзов (невидимые якоря внутри кнопок-вкладок). */
  gateEls: HTMLElement[];
  colors: string[];
  reduced: boolean;
}

export interface Flow {
  activate(i: number): void;
  activateAll(): void;
  highlight(i: number): void;
  destroy(): void;
}

const WHITE = 'rgba(236, 238, 242, ALPHA)';
const LOSS = 'rgba(122, 128, 140, ALPHA)';
const LEAK_P = 0.34;
const TAU = Math.PI * 2;
// поток на 10% медленнее прежнего
const FLOW_SPEED = 0.9;
// волна раз в ~2,5 с (в кадрах по 60 fps), расходится медленно
const RIPPLE_EVERY = 150;
const RIPPLE_SPEED = 0.26;

export function createFlow({ canvas, gateEls, colors, reduced }: FlowOptions): Flow {
  const ctx = canvas.getContext('2d')!;
  let W = 0;
  let H = 0;
  let dpr = 1;
  let pipeY = 0;
  let scale = 1;
  const gates: Gate[] = colors.map((c, i) => ({
    x: 0,
    color: c,
    active: false,
    core: 23,
    lens: 0,
    hover: 0,
    pulse: 0,
    ripples: [],
    // сдвиг по фазе, чтобы шлюзы не пульсировали одновременно
    clock: RIPPLE_EVERY * (0.35 + i * 0.22),
  }));
  let highlighted = -1;
  let particles: Particle[] = [];
  let raf = 0;
  let running = false;
  let visible = true;
  let last = 0;
  let spawnAcc = 0;
  const pointer = { x: -9999, y: -9999 };

  const rand = (a: number, b: number) => a + Math.random() * (b - a);
  const gauss = () => (Math.random() + Math.random() + Math.random() - 1.5) / 1.5;
  const clamp = (v: number, a: number, b: number) => Math.min(b, Math.max(a, v));

  function measure() {
    const rect = canvas.getBoundingClientRect();
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    W = rect.width;
    H = rect.height;
    canvas.width = Math.round(W * dpr);
    canvas.height = Math.round(H * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    pipeY = H * 0.5;
    // на узком экране шлюзы стоят теснее — волны расходятся не так далеко
    scale = clamp((W - 360) / 840, 0, 1) * 0.5 + 0.5;
    gateEls.forEach((el, i) => {
      const r = el.getBoundingClientRect();
      gates[i].x = r.left + r.width / 2 - rect.left;
      const icon = el.parentElement?.querySelector<HTMLElement>('.gate__icon');
      if (icon) gates[i].core = icon.offsetWidth / 2;
    });
  }

  const lensR = (g: Gate) => g.core + 5;
  const speedScale = () => Math.min(1, Math.max(0.55, W / 1200));

  function spawn(x = -20): Particle {
    const vx = rand(2.1, 3.6) * speedScale() * FLOW_SPEED;
    const base = gauss() * (H < 240 ? 7 : 10);
    const p: Particle = {
      x,
      y: 0,
      vx,
      vy: 0,
      base,
      side: base === 0 ? (Math.random() < 0.5 ? -1 : 1) : Math.sign(base),
      len: 3 + vx * rand(1.6, 3.4),
      color: WHITE,
      alpha: rand(0.35, 0.8),
      state: 'flow',
      next: 0,
    };
    p.y = pipeY + base;
    while (p.next < gates.length && gates[p.next].x < p.x) p.next++;
    for (let i = p.next - 1; i >= 0; i--) {
      if (gates[i].active) {
        p.color = gates[i].color;
        break;
      }
    }
    return p;
  }

  // поток плавно обтекает круг сверху и снизу
  function lensOffset(p: Particle) {
    let off = 0;
    for (const g of gates) {
      if (g.lens < 0.01) continue;
      const L = lensR(g) * 2.4;
      const dx = p.x - g.x;
      if (Math.abs(dx) >= L) continue;
      const bump = (Math.cos((Math.PI * dx) / L) + 1) / 2;
      off += p.side * lensR(g) * 1.05 * bump * g.lens;
    }
    return off;
  }

  function emitRipple(g: Gate) {
    g.ripples.push({ r: g.core + 1, a: 0.7 });
  }

  function step(dt: number) {
    spawnAcc += dt * Math.max(0.6, W / 1400) * 0.95 * FLOW_SPEED;
    while (spawnAcc >= 1) {
      particles.push(spawn());
      spawnAcc -= 1;
    }

    const maxR = 70 * scale;
    gates.forEach((g) => {
      g.lens += ((g.active ? 1 : 0) - g.lens) * Math.min(1, 0.05 * dt);
      const d = Math.hypot(pointer.x - g.x, pointer.y - pipeY);
      g.hover += ((d < 110 && g.active ? 1 : 0) - g.hover) * Math.min(1, 0.08 * dt);
      if (g.pulse > 0) g.pulse = Math.max(0, g.pulse - 0.012 * dt);
      // волны — строго по таймеру, пока не отыграла ударная волна включения
      if (g.active && g.pulse === 0) {
        g.clock -= dt;
        if (g.clock <= 0) {
          emitRipple(g);
          g.clock += RIPPLE_EVERY;
        }
      }
      for (const r of g.ripples) {
        r.r += RIPPLE_SPEED * dt;
        // волна гаснет по мере удаления от круга
        r.a = 0.7 * Math.max(0, 1 - (r.r - g.core) / maxR);
      }
      g.ripples = g.ripples.filter((r) => r.a > 0.01);
    });

    for (const p of particles) {
      if (p.state === 'flow') {
        p.x += p.vx * dt;
        const dx = p.x - pointer.x;
        const dy = p.y - pointer.y;
        const d2 = dx * dx + dy * dy;
        let push = 0;
        if (d2 < 90 * 90) {
          const f = 1 - Math.sqrt(d2) / 90;
          push = (dy >= 0 ? 1 : -1) * f * 22;
        }
        const target = pipeY + p.base + push + lensOffset(p);
        p.y += (target - p.y) * Math.min(1, 0.16 * dt);

        const gi = p.next;
        const g = gates[gi];
        if (g && p.x >= g.x) {
          if (g.active) {
            p.color = g.color;
          } else if (Math.random() < LEAK_P) {
            p.state = 'leak';
            p.color = LOSS;
            p.vy = rand(0.3, 1.1);
            p.vx *= 0.55;
          }
          p.next++;
        }
      } else {
        p.vy += 0.07 * dt;
        p.vx *= Math.pow(0.985, dt);
        p.x += p.vx * dt;
        p.y += p.vy * dt;
        p.alpha -= 0.006 * dt;
      }
    }
    particles = particles.filter((p) => p.x < W + 40 && p.y < H + 20 && p.alpha > 0.02);
  }

  function rgba(c: string, a: number) {
    const al = Math.max(0, Math.min(1, a)).toFixed(3);
    if (c.includes('ALPHA')) return c.replace('ALPHA', al);
    const n = parseInt(c.slice(1), 16);
    return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${al})`;
  }

  function draw() {
    ctx.clearRect(0, 0, W, H);

    // русло
    const grad = ctx.createLinearGradient(0, 0, W, 0);
    grad.addColorStop(0, 'rgba(255,255,255,0)');
    grad.addColorStop(0.08, 'rgba(255,255,255,0.07)');
    grad.addColorStop(0.92, 'rgba(255,255,255,0.07)');
    grad.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.fillStyle = grad;
    ctx.fillRect(0, pipeY - 0.5, W, 1);

    // мягкое свечение включённого шлюза — под частицами
    gates.forEach((g, i) => {
      if (g.lens < 0.01) return;
      const hi = i === highlighted && g.active;
      const R = g.core * (hi ? 3.6 : 3);
      const halo = ctx.createRadialGradient(g.x, pipeY, g.core, g.x, pipeY, R);
      halo.addColorStop(0, rgba(g.color, (hi ? 0.26 : 0.15) * g.lens));
      halo.addColorStop(1, rgba(g.color, 0));
      ctx.fillStyle = halo;
      ctx.fillRect(g.x - R, pipeY - R, R * 2, R * 2);
    });

    // частицы
    for (const p of particles) {
      ctx.fillStyle = rgba(p.color, p.alpha);
      if (p.state === 'leak') ctx.fillRect(p.x - 1, p.y - 1, 2.2, 2.2 + p.vy * 1.5);
      else ctx.fillRect(p.x - p.len, p.y - 0.8, p.len, 1.6);
    }

    // шлюзы: пунктир у выключенных, волны у включённых
    gates.forEach((g, i) => {
      const hi = i === highlighted && g.active;
      if (g.lens < 0.02) {
        ctx.setLineDash([3, 5]);
        ctx.strokeStyle = 'rgba(255,255,255,0.22)';
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        ctx.arc(g.x, pipeY, lensR(g) + 1, 0, TAU);
        ctx.stroke();
        ctx.setLineDash([]);
      }

      for (const r of g.ripples) {
        ctx.strokeStyle = rgba(g.color, r.a * g.lens * (hi ? 1 : 0.8));
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.arc(g.x, pipeY, r.r, 0, TAU);
        ctx.stroke();
      }

      if (g.pulse > 0) {
        const r = g.core + (1 - g.pulse) * 90 * scale;
        ctx.strokeStyle = rgba(g.color, g.pulse);
        ctx.lineWidth = 2.5 * g.pulse + 0.5;
        ctx.beginPath();
        ctx.arc(g.x, pipeY, r, 0, TAU);
        ctx.stroke();
      }
    });
  }

  function frame(now: number) {
    const dt = Math.min(3, (now - last) / 16.667 || 1);
    last = now;
    step(dt);
    draw();
    raf = requestAnimationFrame(frame);
  }

  function start() {
    if (running || reduced || !visible || document.hidden) return;
    running = true;
    last = performance.now();
    raf = requestAnimationFrame(frame);
  }

  function stop() {
    running = false;
    cancelAnimationFrame(raf);
  }

  function prewarm(frames: number) {
    for (let i = 0; i < frames; i++) step(1);
  }

  measure();
  prewarm(reduced ? 520 : 420);
  draw();

  const ro = new ResizeObserver(() => {
    measure();
    particles.forEach((p) => {
      p.next = 0;
      while (p.next < gates.length && gates[p.next].x < p.x) p.next++;
    });
    if (!running) draw();
  });
  ro.observe(canvas);

  const io = new IntersectionObserver(([e]) => {
    visible = e.isIntersecting;
    visible ? start() : stop();
  });
  io.observe(canvas);

  const onVis = () => (document.hidden ? stop() : start());
  document.addEventListener('visibilitychange', onVis);

  const host = canvas.parentElement!;
  const onMove = (e: PointerEvent) => {
    const r = canvas.getBoundingClientRect();
    pointer.x = e.clientX - r.left;
    pointer.y = e.clientY - r.top;
  };
  const onLeave = () => {
    pointer.x = pointer.y = -9999;
  };
  host.addEventListener('pointermove', onMove);
  host.addEventListener('pointerleave', onLeave);

  start();

  // без анимации: сразу конечное состояние, без волн
  const redrawStatic = () => {
    if (!reduced) return;
    gates.forEach((g) => (g.lens = g.active ? 1 : 0));
    particles = [];
    prewarm(520);
    gates.forEach((g) => {
      g.ripples = [];
      g.pulse = 0;
    });
    draw();
  };

  return {
    activate(i) {
      const g = gates[i];
      if (!g || g.active) return;
      g.active = true;
      g.pulse = 1;
      // первая обычная волна — через паузу после ударной
      g.clock = RIPPLE_EVERY * 0.5;
      redrawStatic();
    },
    activateAll() {
      gates.forEach((g) => (g.active = true));
      redrawStatic();
    },
    highlight(i) {
      highlighted = i;
      if (reduced) draw();
    },
    destroy() {
      stop();
      ro.disconnect();
      io.disconnect();
      document.removeEventListener('visibilitychange', onVis);
      host.removeEventListener('pointermove', onMove);
      host.removeEventListener('pointerleave', onLeave);
    },
  };
}
