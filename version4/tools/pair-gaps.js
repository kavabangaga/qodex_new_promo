// Таблица зазоров и кернинга между соседними буквами шрифта Geist — её читает src/lib/tight-pairs.ts.
//
// Пересчитывать нужно только при смене шрифта или его начертаний:
//   1. запустить сайт (npm run dev) и открыть его в Chrome;
//   2. вставить содержимое этого файла в консоль разработчика;
//   3. скачанный pair-gaps.json положить в src/data/.
//
// Каждая буква рисуется крупно (200 px), по каждой строке пикселей запоминаются левый и правый
// края. Зазор пары — наименьшее расстояние по горизонтали между правым краем первой буквы
// и левым краем второй; соседние по высоте строки (±3 px) тоже считаются, чтобы поймать
// касание по диагонали. Из двух начертаний заголовков (600 и 560) берётся меньший зазор,
// кернинг — средний. Меряется всё с ненулевым letter-spacing, как в заголовках: при нём браузер
// не собирает лигатуры («ff», «tt»), и их ширина не попадает в кернинг.
//
// Формат (всё в тысячных долях кегля):
//   gap  — { "ги": 46 }: зазор пары с учётом кернинга шрифта; только пары, которые могут
//          слипнуться при самом тесном трекинге сайта;
//   kern — { "ги": -33 }: кернинг пары, если он не нулевой.
// Цифры — обычные (пропорциональные). Табличные цифры (font-variant-numeric: tabular-nums)
// в Geist — отдельные знаки одной ширины с большими полями: они не слипаются, сайт их не трогает.
(async () => {
  const CHARS = 'абвгдеёжзийклмнопрстуфхцчшщъыьэюяАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ.,:;!?—–-−«»()%+≈=₽/№…·×';
  const WEIGHTS = [600, 560];
  // самый тесный трекинг сайта −0.065em + наименьший зазор 0.022em + то, на что расчёт
  // может сдвинуть пару, которую сам не раздвигает (сжатие слова 0.006em и мелкий кернинг 0.012em)
  const KEEP_BELOW = 0.105;
  const SPACING = 1; // px
  const SIZE = 200, W = 700, H = 360, OX = 220, BASE = 250, TOL = 3;

  const gaps = {};
  const kerns = {};
  for (const weight of WEIGHTS) {
    const font = `${weight} ${SIZE}px "Geist Variable"`;
    await document.fonts.load(font, CHARS);
    // без этой проверки на странице с ошибкой сборки молча измерился бы запасной шрифт
    if (![...document.fonts].some((face) => face.family.includes('Geist') && face.status === 'loaded')) throw new Error('Шрифт Geist на странице не загружен');
    const canvas = document.createElement('canvas');
    canvas.width = W;
    canvas.height = H;
    const g = canvas.getContext('2d', { willReadFrequently: true });
    g.font = font;
    g.textBaseline = 'alphabetic';
    g.fillStyle = '#000';
    g.letterSpacing = `${SPACING}px`;
    if (g.letterSpacing !== `${SPACING}px`) throw new Error('Браузер не умеет letterSpacing на холсте — нужен Chrome 99 или новее');
    // ширина без добавленного интервала: он прибавляется после каждого знака
    const width = (text) => g.measureText(text).width - SPACING * [...text].length;

    const profile = {};
    for (const ch of CHARS) {
      g.clearRect(0, 0, W, H);
      g.fillText(ch, OX, BASE);
      const d = g.getImageData(0, 0, W, H).data;
      const L = new Float32Array(H).fill(Infinity);
      const R = new Float32Array(H).fill(-Infinity);
      for (let y = 0; y < H; y++)
        for (let x = 0; x < W; x++)
          if (d[(y * W + x) * 4 + 3] > 100) {
            if (x < L[y]) L[y] = x;
            if (x > R[y]) R[y] = x;
          }
      const L2 = new Float32Array(H).fill(Infinity);
      const R2 = new Float32Array(H).fill(-Infinity);
      for (let y = 0; y < H; y++)
        for (let k = -TOL; k <= TOL; k++) {
          const yy = y + k;
          if (yy < 0 || yy >= H) continue;
          if (L[yy] < L2[y]) L2[y] = L[yy];
          if (R[yy] > R2[y]) R2[y] = R[yy];
        }
      profile[ch] = { L: L2, R: R2, adv: width(ch) };
    }

    for (const a of CHARS)
      for (const b of CHARS) {
        const A = profile[a];
        const B = profile[b];
        const kern = width(a + b) - A.adv - B.adv;
        kerns[a + b] = (kerns[a + b] ?? 0) + kern / SIZE / WEIGHTS.length;
        let bare = Infinity;
        for (let y = 0; y < H; y++) {
          if (A.R[y] === -Infinity || B.L[y] === Infinity) continue;
          const v = A.adv + (B.L[y] - OX) - (A.R[y] - OX + 1);
          if (v < bare) bare = v;
        }
        if (bare !== Infinity) gaps[a + b] = Math.min(gaps[a + b] ?? Infinity, (bare + kern) / SIZE);
      }
  }

  const gap = {};
  const kern = {};
  for (const [pair, value] of Object.entries(gaps)) if (value < KEEP_BELOW) gap[pair] = Math.round(value * 1000);
  for (const [pair, value] of Object.entries(kerns)) if (Math.round(value * 1000)) kern[pair] = Math.round(value * 1000);

  // по строке на первую букву пары — чтобы файл можно было сравнивать построчно
  const lines = (map) => {
    const byFirst = {};
    for (const [pair, value] of Object.entries(map)) (byFirst[[...pair][0]] ??= []).push(`${JSON.stringify(pair)}:${value}`);
    return '{\n' + Object.values(byFirst).map((row) => row.join(',')).join(',\n') + '\n}';
  };
  const json = `{"gap":${lines(gap)},\n"kern":${lines(kern)}}\n`;
  JSON.parse(json);
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([json], { type: 'application/json' }));
  a.download = 'pair-gaps.json';
  document.body.appendChild(a);
  a.click();
  a.remove();
  return `${Object.keys(gap).length} зазоров, ${Object.keys(kern).length} кернингов`;
})();
