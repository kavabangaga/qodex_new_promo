// Клиенты и партнёры QODEX: плитки «Нам доверяют» на главной и на страницах продуктов.
// Логотипы — public/clients/<logo>; их готовит tools/client-logos.py из исходников заказчика
// в папке Logos (фон становится прозрачным, пустые поля обрезаются). Без логотипа плитка
// показывает название.
export interface Client {
  name: string;
  /** Файл логотипа в public/clients/ (PNG). */
  logo?: string;
  /** Партнёр, а не клиент: на плитке метка «партнёр». */
  partner?: boolean;
}

export const CLIENTS: Client[] = [
  { name: 'РО «Эко-Сити»', logo: 'eko-siti.png' },
  { name: 'Башкирская содовая компания', logo: 'bsk.png' },
  { name: 'ООО «НУР»', logo: 'nur.png' },
  { name: 'ЭкоВторИндустрия', logo: 'ekovtorindustriya.png' },
  { name: 'Управление отходами Мелеуз', logo: 'uo-meleuz.png' },
  { name: 'ЭКОИндустрия', logo: 'ekoindustriya.png' },
  { name: 'Альянс групп', logo: 'alyans-grupp.png' },
  { name: 'Экотех Мелеуз', logo: 'ekoteh-meleuz.png' },
  { name: 'Грин Сити', logo: 'grin-siti.png' },
  { name: 'Ростелеком', logo: 'rostelekom.png', partner: true },
];
