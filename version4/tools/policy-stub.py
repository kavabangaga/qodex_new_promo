# Заглушка public/files/policy.pdf: Политика теперь страница сайта (/privacy/), а по старому адресу файла
# (ссылки из писем и прежнего сайта) открывается одна страница со ссылкой на актуальную редакцию.
# Прежняя редакция (01.05.2025) хранится в истории git. Запуск: python tools/policy-stub.py
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'public' / 'files' / 'policy.pdf'
URL = 'https://qodex.tech/privacy/'
FONT = 'C:/Windows/Fonts/arial.ttf'
FONT_BOLD = 'C:/Windows/Fonts/arialbd.ttf'

doc = pymupdf.open()
page = doc.new_page(width=595, height=842)  # A4
page.insert_font(fontname='ar', fontfile=FONT)
page.insert_font(fontname='arb', fontfile=FONT_BOLD)

x, y = 72, 110
page.insert_text((x, y), 'ООО «КОДЕКС ТЕХНОЛОГИИ»', fontname='ar', fontsize=11, color=(0.35, 0.35, 0.38))
y += 40
for line in ['Политика в отношении обработки', 'персональных данных']:
    page.insert_text((x, y), line, fontname='arb', fontsize=22, color=(0.11, 0.11, 0.12))
    y += 28
page.insert_text((x, y), '(Политика конфиденциальности)', fontname='ar', fontsize=13, color=(0.35, 0.35, 0.38))
y += 50
for line in ['Политика опубликована на сайте компании как страница.', 'Актуальная редакция — по адресу:']:
    page.insert_text((x, y), line, fontname='ar', fontsize=13, color=(0.11, 0.11, 0.12))
    y += 20
y += 12
page.insert_text((x, y), URL, fontname='arb', fontsize=15, color=(0.0, 0.42, 1.0))
width = pymupdf.Font(fontfile=FONT_BOLD).text_length(URL, fontsize=15)
page.insert_link({'kind': pymupdf.LINK_URI, 'from': pymupdf.Rect(x, y - 15, x + width, y + 4), 'uri': URL})

doc.set_metadata({'title': 'Политика в отношении обработки персональных данных — ООО «КОДЕКС ТЕХНОЛОГИИ»', 'author': 'ООО «КОДЕКС ТЕХНОЛОГИИ»'})
doc.subset_fonts()  # только нужные буквы шрифта — файл в десятки килобайт, а не мегабайт
doc.save(OUT, garbage=4, deflate=True)
print('saved', OUT, OUT.stat().st_size, 'bytes')
