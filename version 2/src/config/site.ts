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
  /** Будущий адрес страницы продукта (этап 2). */
  stage2Path: string;
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
    color: '#FF8A00',
    glow: '#FFB055',
  },
};

export const PRODUCT_ORDER: ProductId[] = ['robot', 'tracker', 'tonn', 'kodeks'];

/** Ссылка на лендинг продукта с UTM-метками; content — блок, из которого переход. */
export function productHref(id: ProductId, content: string): string {
  const params = new URLSearchParams({
    utm_source: 'qodex.tech',
    utm_medium: 'referral',
    utm_campaign: 'home',
    utm_content: content,
  });
  return `${PRODUCTS[id].url}/?${params}`;
}

/** Номер счётчика Яндекс Метрики. Пока не задан — цели не отправляются. */
export const METRIKA_ID: number | null = null;

/** Адрес, куда форма отправляет заявку (POST, JSON). Пока пустой — отправка имитируется. */
export const FORM_ENDPOINT = '';

export const SKOLKOVO_URL = 'https://navigator.sk.ru/orn/1125740';
