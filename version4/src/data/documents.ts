// Документы на странице «Документы» (/documents/). Файлы лежат в public/files/ под теми же именами,
// что и на прежнем сайте qodex.tech/files/…: старые ссылки (в письмах, заявках, реестрах) продолжают работать.
// Порядок групп: сначала общие документы компании, затем документы по продуктам. Когда страница продукта
// переезжает с лендинга на сайт, документы с лендинга добавляются в группу этого продукта — и файлы,
// и названия переносятся без изменений.
import { METRIKA_ID, type ProductId } from '../config/site';

export interface Doc {
  /** Название — как на прежнем сайте. */
  title: string;
  /** Имя файла в public/files/ — или page, если документ — страница сайта. */
  file?: string;
  /** Адрес страницы сайта (без подпапки), например '/consent/'. */
  page?: string;
  /** Вид материала, если это не документ. */
  kind?: 'Презентация';
}

export interface ProductDocs {
  product: ProductId;
  /** Якорь группы на странице. */
  id: string;
  docs: Doc[];
}

/**
 * Общие документы компании (на прежнем сайте — «иные документы» и презентация из подвала).
 * «Пользовательское соглашение» — соглашение системы QODEX TONN (ранее QODEX ECO: Gravity и Signall),
 * поэтому оно в документах QODEX TONN; ссылка «Пользовательское соглашение» в подвале ведёт на ту же страницу.
 * Политика и соглашение — страницы сайта (pages/privacy.astro, pages/documents/user_agreement.astro).
 */
export const GENERAL_DOCS: Doc[] = [
  { title: 'Политика в отношении обработки персональных данных (Политика конфиденциальности)', page: '/privacy/' },
  { title: 'Согласие на обработку персональных данных', page: '/consent/' },
  // согласие на cookie — только когда включена Яндекс Метрика (без неё сайт cookie не ставит)
  ...(METRIKA_ID ? [{ title: 'Согласие на использование файлов cookie и Яндекс Метрики', page: '/cookies/' }] : []),
  { title: 'Карта партнёра', file: 'partners_map.pdf' },
  { title: 'Для представителей власти', file: 'gov.pdf', kind: 'Презентация' },
];

/** Документы по продуктам (на прежнем сайте — «документы по системе QODEX TONN» и презентации из подвала). */
export const PRODUCT_DOCS: ProductDocs[] = [
  {
    product: 'tonn',
    id: 'dokumenty-tonn',
    docs: [
      { title: 'Описание функциональных характеристик ПО QODEX TONN', file: 'tonn_functions.pdf' },
      { title: 'Руководство пользователя QODEX TONN', file: 'tonn_user_guide.pdf' },
      { title: 'Руководство администратора QODEX TONN (установка и эксплуатация)', file: 'tonn_admin_guide.pdf' },
      { title: 'Описание процессов поддержания жизненного цикла QODEX TONN', file: 'tonn_lifecycle.pdf' },
      { title: 'Технические требования', file: 'requirements.pdf' },
      { title: 'Инструкция Gravity', file: 'gravity_manual.pdf' },
      { title: 'Информационно-техническое сопровождение', file: 'support.pdf' },
      { title: 'Пользовательское соглашение', page: '/documents/user_agreement/' },
      { title: 'О системе', file: 'system.pdf', kind: 'Презентация' },
    ],
  },
  {
    product: 'tracker',
    id: 'dokumenty-tracker',
    docs: [{ title: 'Tracker', file: 'tracker.pdf', kind: 'Презентация' }],
  },
];
