// Единое место для контактов, адресов продуктов и интеграций.
// На этапе 2 адреса продуктов меняются на /ro-bot, /tracker, /tonn, /kodeks-tko — только здесь.

const NB = ' ';

/** Путь с учётом подпапки сайта (на GitHub Pages сайт живёт в /имя-репозитория/). */
export function withBase(path: string): string {
  const base = import.meta.env.BASE_URL.replace(/\/$/, '');
  return `${base}${path}`;
}

export const SITE = {
  url: 'https://qodex.tech',
  title: 'QODEX — находим деньги регионального оператора ТКО',
  description:
    'Сверка базы начислений с ГИС ЖКХ, фотофиксация вывоза, честный вес на полигоне и передача данных во ФГИС УТКО. 73 клиента. Бесплатный пилот РО-БОТа.',
  ogImage: '/og-image.png',
};

/**
 * Сведения об организации — для подвала и страницы «Документы». По приказу Минцифры № 511
 * (ИТ-аккредитация) полное наименование, адрес, ИНН, основной ОКВЭД и код ИТ-деятельности
 * обязаны быть на сайте; источник — выписка из ЕГРЮЛ, подвал и «Карта партнёра» прежнего сайта qodex.tech.
 */
export const COMPANY = {
  fullName: 'Общество с ограниченной ответственностью «КОДЕКС ТЕХНОЛОГИИ»',
  shortName: 'ООО «КОДЕКС ТЕХНОЛОГИИ»',
  inn: '0278962265',
  kpp: '027801001',
  ogrn: '1200200055791',
  /** Адрес юридического лица — как в выписке из ЕГРЮЛ от 05.10.2026 (регистр букв обычный). */
  address: `450009, Республика Башкортостан, г.о.${NB}город Уфа, г.${NB}Уфа, ул.${NB}Братьев Кадомцевых, д.${NB}12/2, кв.${NB}1, ком.${NB}7`,
  /** Тот же адрес по частям — для микроразметки schema.org. */
  addressParts: {
    postalCode: '450009',
    region: 'Республика Башкортостан',
    locality: 'Уфа',
    street: 'ул. Братьев Кадомцевых, д. 12/2, кв. 1, ком. 7',
  },
  okved: '62.01',
  okvedName: 'Разработка компьютерного программного обеспечения',
  itCode: '2.01',
  /** Документ, по которому присвоен код вида ИТ-деятельности. */
  itCodeOrder: `Приказ Минцифры №${NB}449 от 11.05.2023`,
  /** Регистрационный номер в реестре операторов персональных данных Роскомнадзора — для текстов согласий. */
  pdRegistry: '2-26-060104',
};

/** Наименование с неразрывными пробелами: «ООО» не отрывается от названия, «КОДЕКС ТЕХНОЛОГИИ» не рвётся. */
export function nbName(s: string): string {
  const nb = String.fromCharCode(160);
  return s.replace('ООО «', `ООО${nb}«`).replace('КОДЕКС ТЕХНОЛОГИИ', `КОДЕКС${nb}ТЕХНОЛОГИИ`);
}

export const CONTACTS = {
  phone: `+7${NB}996${NB}293${NB}03${NB}80`,
  phoneHref: 'tel:+79962930380',
  email: 'info@qodex.tech',
  emailHref: 'mailto:info@qodex.tech',
  telegram: '@qodex_t',
  telegramHref: 'https://t.me/qodex_t',
  pilotContact: `Данил${NB}Максадов`,
};

export type ProductId = 'robot' | 'tracker' | 'tonn' | 'kodeks';

export interface Product {
  id: ProductId;
  name: string;
  /** Текущий лендинг (этап 1). */
  url: string;
  /** Адрес страницы продукта на этом сайте (этап 2). */
  stage2Path: string;
  /** Страница продукта на этом сайте уже есть: ссылки ведут на неё, а не на старый лендинг. */
  onSite?: boolean;
  /** Цвет продукта (заливки); CSS-классы .p-robot и т. п. задают ещё текстовый и «светящийся» варианты. */
  color: string;
  /** Вариант для тёмного фона. */
  glow: string;
}

export const PRODUCTS: Record<ProductId, Product> = {
  robot: {
    id: 'robot',
    name: 'РО-БОТ',
    url: 'https://romoney.qodex.tech',
    stage2Path: '/ro-bot',
    color: '#6B4DFF',
    glow: '#A594FF',
  },
  tracker: {
    id: 'tracker',
    name: 'QODEX Tracker',
    url: 'https://tracker.qodex.tech',
    stage2Path: '/tracker',
    color: '#1669F0',
    glow: '#6FB0FF',
  },
  tonn: {
    id: 'tonn',
    name: 'QODEX TONN',
    url: 'https://tonn.qodex.tech',
    stage2Path: '/tonn',
    color: '#12B886',
    glow: '#45E0AE',
  },
  kodeks: {
    id: 'kodeks',
    name: 'Кодекс ТКО',
    url: 'https://fgis.qodex.tech',
    stage2Path: '/kodeks-tko',
    onSite: true,
    color: '#FF8A00',
    glow: '#FFB055',
  },
};

export const PRODUCT_ORDER: ProductId[] = ['robot', 'tracker', 'tonn', 'kodeks'];

/** Ссылка на главную или её раздел с любой страницы сайта: homeHref('#pilot'). */
export function homeHref(hash = ''): string {
  return `${withBase('/')}${hash}`;
}

/** Продукт ведёт на свою страницу этого сайта (а не на отдельный лендинг). */
export function isOnSite(id: ProductId): boolean {
  return PRODUCTS[id].onSite === true;
}

/** Адрес продукта для подписи в меню: «qodex.tech/kodeks-tko» или домен лендинга. */
export function productHost(id: ProductId): string {
  const p = PRODUCTS[id];
  return p.onSite ? `${new URL(SITE.url).host}${p.stage2Path}` : p.url.replace('https://', '');
}

/**
 * Ссылка на продукт: страница на этом сайте, если она уже есть, иначе лендинг с UTM-метками;
 * content — блок, из которого переход.
 */
export function productHref(id: ProductId, content: string): string {
  if (PRODUCTS[id].onSite) return withBase(`${PRODUCTS[id].stage2Path}/`);
  const params = new URLSearchParams({
    utm_source: 'qodex.tech',
    utm_medium: 'referral',
    utm_campaign: 'home',
    utm_content: content,
  });
  return `${PRODUCTS[id].url}/?${params}`;
}

/**
 * Номер счётчика Яндекс Метрики. Пока не задан — счётчика нет, плашки о cookie и страницы /cookies/ нет,
 * цели не отправляются. Задаётся здесь (число вместо null) или при сборке переменной PUBLIC_METRIKA_ID —
 * так проверяют плашку. Счётчик запускается только после согласия посетителя (components/Floating.astro).
 * Согласие на cookie (pages/[cookies].astro) обещает посетителям, поэтому при создании счётчика:
 * — включить «Ограниченный режим»;
 * — выключить «Автоматические цели» (п. 4.3.5 условий Метрики): у нового счётчика они включены по умолчанию
 *   и собирают для Директа дополнительные данные, в том числе ввод контактов в форму;
 * — не связывать счётчик с Директом и другими сервисами Яндекса, не включать передачу данных третьим
 *   лицам, опросы, публичный доступ и «Средние показатели по рынку» (пп. 4.3.2–4.3.10 условий Метрики);
 * — Вебвизор не включать (в «Ограниченном режиме» его нет; в Base.astro он выключен);
 * — сведения храним не дольше шести месяцев (так требует ч. 6 ст. 21 152-ФЗ при отзыве согласия, а удалить
 *   сведения одного посетителя Метрика не умеет): не реже раза в пять месяцев удалять счётчик (Яндекс ещё
 *   14 дней держит удалённый) и ставить новый, номер — сюда; сводные отчёты без персональных данных
 *   выгружать заранее.
 */
export const METRIKA_ID: number | null = Number(import.meta.env.PUBLIC_METRIKA_ID) || null;

/**
 * Адрес, куда форма отправляет заявку (POST, JSON). Пока пустой — отправка имитируется.
 * Прежде чем задать адрес: CRM и приём заявок — с хранением данных в России; приёмник сохраняет блок
 * consent из заявки и время получения по часам сервера; обработчиков (хостинг, почта, CRM, SMS) назвать
 * в согласии (pages/consent.astro, раздел 4) и поменять дату в CONSENT_EDITION.form; в договорах поручения
 * запретить привлекать других лиц, кроме центров обработки данных в России. Телефония: разговоры
 * не записывать, а если запись нужна — хранить записи в России, предупреждать о записи в начале звонка
 * и дописать записи разговоров в раздел 2 согласия. Демонстрации — только в российских сервисах видеосвязи
 * (согласие это обещает).
 */
export const FORM_ENDPOINT = '';

export const SKOLKOVO_URL = 'https://navigator.sk.ru/orn/1125740';

/**
 * Ссылки на документы для подвала, формы заявки и плашки cookie. Политика, соглашение и согласия — страницы
 * сайта (pages/privacy.astro, pages/documents/user_agreement.astro, pages/consent.astro, pages/[cookies].astro);
 * адреса /privacy/ и /documents/user_agreement/ напечатаны в прежних редакциях самих документов.
 */
export const DOC_LINKS = {
  /** Политика в отношении обработки персональных данных (Политика конфиденциальности). */
  policy: withBase('/privacy/'),
  /** Пользовательское соглашение системы QODEX TONN (ранее QODEX ECO). */
  agreement: withBase('/documents/user_agreement/'),
  /** Предыдущая редакция соглашения (от 25.05.2023) — PDF прежнего сайта, действует до вступления в силу новой. */
  agreementPrev: withBase('/files/user_agreement.pdf'),
  /** Согласие на обработку персональных данных — для формы заявки. */
  consent: withBase('/consent/'),
  /** Согласие на использование файлов cookie и Яндекс Метрики — для плашки cookie (когда Метрика включена). */
  cookies: withBase('/cookies/'),
  page: withBase('/documents/'),
};

/**
 * Редакции текстов согласий (дата). Поменялся текст согласия — поменяйте и дату: она показана на странице
 * согласия и уходит вместе с заявкой (форма) или хранится в браузере вместе с выбором и уходит в Метрику
 * параметром визита (cookie). Прежние тексты согласия обещают хранить — их хранит история git.
 */
export const CONSENT_EDITION = {
  form: '05.10.2026',
  cookies: '05.10.2026',
};

/**
 * Редакции Политики и Пользовательского соглашения (даты). Редакция соглашения от 06.10.2026 вступает в силу
 * 09.10.2026 — в день запуска сайта на qodex.tech (решение заказчика); основание — п. 7.2 прежней редакции
 * («если иной срок вступления в силу не определён при размещении»). Её же п. 4.2.2 требует уведомить
 * Пользователей за 30 дней — уведомление разослать как можно раньше. Будущие изменения — по п. 4.2.2 и 7.2
 * новой редакции (не раньше чем через 30 дней). agreementPrevUntil — день перед agreementFrom.
 * Текст Политики зависит от METRIKA_ID — включили Метрику, поменяйте DOC_EDITION.policy; проверить и CONSENT_EDITION.
 */
export const DOC_EDITION = {
  policy: '06.10.2026',
  agreement: '06.10.2026',
  agreementFrom: '09.10.2026',
  agreementPrev: '25.05.2023',
  agreementPrevUntil: '08.10.2026',
};

/** Подпись у галочки согласия в форме — дословно так же она названа в тексте согласия. */
export const CONSENT_LABEL = 'Даю согласие на обработку персональных данных';
