// Мусоровоз QODEX — один рисунок для всех сцен сайта (эталон — «Как это работает» на странице QODEX TONN).
// Плоская иллюстрация в серо-голубой гамме сцены: белый кузов с бирюзовой полосой, серый задний борт
// с подъёмником, кабина с голубым стеклом, тёмная рама и колёса. Строки — содержимое <svg>/<g> (set:html).
// Кто рисует сцену с мусоровозом — берёт его отсюда, а не рисует свой.

/** Сбоку, кабиной вправо, без колёс. Свои координаты: задний борт — x 0, крыша кузова — y 0,
 *  перед бампера — x 364, низ колёс — y 172. Колёса — TRUCK_WHEELS + TRUCK_WHEEL (крутятся отдельно). */
export const TRUCK =
  // задний борт со скошенной стенкой, бункер внизу, гидроцилиндр
  `<path d="M60 2H38q-8 0-11 7L4 90q-3 8 0 15l3 10q2 5 8 5h45Z" fill="#8f9ca7"/>` +
  `<path d="M33 16 12 88" stroke="#7f8c97" stroke-width="2"/>` +
  `<path d="M45 24 39 80" stroke="#6f7c88" stroke-width="4" stroke-linecap="round"/>` +
  `<path d="M6 98h24v22H14q-4 0-5-4l-4-11q-1-4 1-7Z" fill="#76838e"/>` +
  `<rect x="11" y="72" width="5" height="11" rx="1.5" fill="#e5484d"/>` +
  // кузов
  `<rect x="58" width="196" height="126" rx="12" fill="#eef2f5" stroke="#cdd5de" stroke-width="2"/>` +
  `<path d="M104 10v106M150 10v106M196 10v106" stroke="#dce3e9" stroke-width="3"/>` +
  `<rect x="59" y="78" width="194" height="13" fill="#a8ddd7"/>` +
  // кабина
  `<path d="M254 128V42q0-16 16-16h48q9 0 13 7l21 37q4 7 4 15v43Z" fill="#f4f6f9" stroke="#cdd5de" stroke-width="2"/>` +
  `<path d="M268 38h46q5 0 8 5l17 28q2 4-3 4h-68q-3 0-3-3V41q0-3 3-3Z" fill="#9fb3c6"/>` +
  `<path d="M282 72 302 40h12l-20 32Z" fill="#fff" fill-opacity=".3"/>` +
  `<path d="M300 84v38" stroke="#dbe2e8" stroke-width="2"/><rect x="306" y="90" width="12" height="3.5" rx="1.75" fill="#b9c4cc"/>` +
  `<path d="M347 58h11" stroke="#6f7c88" stroke-width="3"/><rect x="356" y="46" width="5" height="24" rx="2" fill="#6f7c88"/>` +
  `<rect x="350" y="98" width="8" height="12" rx="2" fill="#fff3c4"/>` +
  // рама, бак, арки колёс, ступенька, бампер
  `<rect x="6" y="122" width="350" height="14" rx="4" fill="#45505b"/>` +
  `<rect x="186" y="128" width="46" height="18" rx="5" fill="#6f7c88"/>` +
  `<path d="M67 150a27 27 0 0 1 54 0ZM119 150a27 27 0 0 1 54 0ZM279 150a27 27 0 0 1 54 0Z" fill="#45505b"/>` +
  `<rect x="250" y="132" width="24" height="6" rx="2" fill="#6f7c88"/>` +
  `<rect x="336" y="118" width="28" height="18" rx="4" fill="#57636e"/>`;

/** Центры колёс по x (y центра — 150, радиус 22, низ — 172) */
export const TRUCK_WHEELS = [94, 146, 306];
export const TRUCK_WHEEL_Y = 150;

/** Колесо с центром в (0, 0): шина, диск, крестовина — видно, как оно крутится */
export const TRUCK_WHEEL =
  `<circle r="22" fill="#222a31"/><circle r="10" fill="#8b97a2"/>` +
  `<path d="M0-6v12M-6 0h12" stroke="#5d6873" stroke-width="2.6" stroke-linecap="round"/>`;

/** Морда машины крупно — кадр камеры номеров 240×96 (номер — отдельной табличкой поверх) */
export const TRUCK_FRONT =
  `<rect width="240" height="96" fill="#dfe6ec"/>` +
  `<rect x="22" y="-10" width="196" height="56" rx="8" fill="#f4f6f9" stroke="#cdd5de" stroke-width="2"/>` +
  `<rect x="72" y="2" width="96" height="30" rx="5" fill="#57636e"/><path d="M80 10h80M80 17h80M80 24h80" stroke="#76838e" stroke-width="2"/>` +
  `<rect x="32" y="12" width="28" height="15" rx="5" fill="#fff3c4"/><rect x="180" y="12" width="28" height="15" rx="5" fill="#fff3c4"/>` +
  `<rect x="10" y="48" width="220" height="30" rx="7" fill="#45505b"/>` +
  `<rect y="84" width="240" height="12" fill="#c3ccd4"/>`;

/** Кузов сверху — «фото кузова» с обзорной камеры, 120×80 */
export const TRUCK_BODY_TOP =
  `<rect width="120" height="80" fill="#9aa6b0"/><rect x="14" y="10" width="92" height="60" rx="6" fill="#55708a"/>` +
  `<rect x="20" y="16" width="80" height="48" rx="4" fill="#6c7f74"/>` +
  `<ellipse cx="40" cy="34" rx="16" ry="10" fill="#8a8f6e"/><ellipse cx="70" cy="44" rx="18" ry="11" fill="#a29373"/>` +
  `<ellipse cx="62" cy="28" rx="11" ry="7" fill="#7f8c96"/><ellipse cx="86" cy="30" rx="9" ry="7" fill="#c2b28f"/>` +
  `<ellipse cx="34" cy="52" rx="10" ry="6" fill="#5f6b5a"/>`;

/** Сверху, кабиной вверх (вперёд — к y 0), колёса нарисованы и не крутятся. Свои координаты: ось машины —
 *  x 0, перед бампера — y 0, задний борт — y 364 (длина как у TRUCK: y = 364 − x бокового вида, поэтому
 *  колёса стоят на тех же местах: передние — y 58, задние — 218 и 270). Ширина кузова — ±62, кабины — ±58,
 *  с зеркалами — ±74. Камеры на схемах: спереди — (0, 12), по бортам — (±62, y кузова 112…302), сзади — (0, 356). */
export const TRUCK_TOP =
  // мягкая тень на дороге
  `<rect x="-56" y="6" width="126" height="362" rx="14" fill="#45505b" fill-opacity=".14"/>` +
  // шины выглядывают из-под кабины и кузова
  [58, 218, 270]
    .map((y) => `<rect x="-70" y="${y - 22}" width="14" height="44" rx="5" fill="#222a31"/><rect x="56" y="${y - 22}" width="14" height="44" rx="5" fill="#222a31"/>`)
    .join('') +
  // рама в просвете между кабиной и кузовом, бампер с фарами
  `<rect x="-40" y="98" width="80" height="22" fill="#45505b"/>` +
  `<rect x="-56" y="0" width="112" height="14" rx="4" fill="#57636e"/>` +
  `<rect x="-50" y="2" width="14" height="5" rx="2" fill="#fff3c4"/><rect x="36" y="2" width="14" height="5" rx="2" fill="#fff3c4"/>` +
  // задний борт с подъёмником: край бункера, гидроцилиндры по бокам, ступенька, красные фонари
  `<rect x="-60" y="296" width="120" height="62" rx="8" fill="#8f9ca7"/>` +
  `<path d="M-48 320H48" stroke="#7f8c97" stroke-width="2"/>` +
  `<path d="M-50 304v34M50 304v34" stroke="#6f7c88" stroke-width="5" stroke-linecap="round"/>` +
  `<rect x="-56" y="348" width="112" height="16" rx="4" fill="#76838e"/>` +
  `<rect x="-56" y="356" width="11" height="5" rx="1.5" fill="#e5484d"/><rect x="45" y="356" width="11" height="5" rx="1.5" fill="#e5484d"/>` +
  // кузов: белая крыша с рёбрами, бирюзовые полосы вдоль бортов
  `<rect x="-62" y="112" width="124" height="190" rx="10" fill="#eef2f5" stroke="#cdd5de" stroke-width="2"/>` +
  `<path d="M-52 160H52M-52 206H52M-52 252H52" stroke="#dce3e9" stroke-width="3"/>` +
  `<rect x="-55" y="120" width="9" height="174" rx="2" fill="#a8ddd7"/><rect x="46" y="120" width="9" height="174" rx="2" fill="#a8ddd7"/>` +
  // кабина: крыша, лобовое стекло с бликом, зеркала
  `<path d="M-58 104V24q0-16 16-16h84q16 0 16 16v80Z" fill="#f4f6f9" stroke="#cdd5de" stroke-width="2"/>` +
  `<path d="M-48 22q0-5 5-5h86q5 0 5 5v18q0 3-3 3h-90q-3 0-3-3Z" fill="#9fb3c6"/>` +
  `<path d="M-30 43-14 17h11L-19 43Z" fill="#fff" fill-opacity=".3"/>` +
  `<rect x="-42" y="54" width="84" height="40" rx="7" fill="#e9eef2"/>` +
  `<path d="M-58 30h-11M58 30h11" stroke="#6f7c88" stroke-width="3"/>` +
  `<rect x="-75" y="20" width="7" height="18" rx="2" fill="#6f7c88"/><rect x="68" y="20" width="7" height="18" rx="2" fill="#6f7c88"/>`;
