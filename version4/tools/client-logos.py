# Логотипы клиентов для сайта: из папки Logos в корне репозитория (исходники заказчика)
# → version4/public/clients/<slug>.png. Запуск из любой папки: python version4/tools/client-logos.py
# Новый клиент: положить исходник в Logos, добавить строку в FILES ниже и запись в src/data/clients.ts.
# 1) Белая подложка, запечённая в файл (прямоугольник, карточка с тенью), становится прозрачной:
#    заливка от краёв картинки по почти белым и почти прозрачным точкам. Белое внутри знака, отделённое
#    от краёв (буква «H» в синем квадрате и т. п.), не трогается.
# 2) Точки на границе заливки получают прозрачность по своей «белизне» (как «цвет в альфу» в редакторах):
#    без светлой каймы на бежевом фоне.
# 3) Пустые поля по краям обрезаются (остаётся 1 px), чтобы размер логотипа на сайте считался по самому знаку.
import io
import os
import sys
from collections import deque

from PIL import Image

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
# корень репозитория: version4/tools/ → два уровня вверх
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, 'Logos')
OUT = os.path.join(ROOT, 'version4', 'public', 'clients')

FILES = {
    'eko-siti.png': 'Group.png',  # «ЭКО-СИТИ региональный оператор» — РО «Эко-Сити»
    'bsk.png': 'Group 2774.png',  # «БСК содовая компания»
    'nur.png': 'image 38.png',  # ООО «НУР»
    'ekovtorindustriya.png': 'Frame 270989154.png',  # «ЭкоВторИндустрия»
    'uo-meleuz.png': 'image 39.png',  # «Управление отходами Мелеуз»
    'ekoindustriya.png': 'image 40.png',  # «ЭКОИндустрия»
    'alyans-grupp.png': 'image 41.png',  # «Альянс групп»
    'ekoteh-meleuz.png': 'image 42.png',  # «ЭКОТЕХ Мелеуз»
    'grin-siti.png': 'гринсити 1.png',  # «Грин Сити»
    'rostelekom.png': 'image 27.png',  # «Ростелеком»
}

WHITE = 238  # точка «почти белая», если все каналы не ниже
CLEAR = 40  # точка «почти прозрачная», если альфа ниже


def is_bg(p):
    r, g, b, a = p
    return a < CLEAR or (r >= WHITE and g >= WHITE and b >= WHITE)


def process(im):
    im = im.convert('RGBA')
    w, h = im.size
    px = im.load()
    bg = [[False] * w for _ in range(h)]
    q = deque()
    for x in range(w):
        for y in (0, h - 1):
            if is_bg(px[x, y]) and not bg[y][x]:
                bg[y][x] = True
                q.append((x, y))
    for y in range(h):
        for x in (0, w - 1):
            if is_bg(px[x, y]) and not bg[y][x]:
                bg[y][x] = True
                q.append((x, y))
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and not bg[ny][nx] and is_bg(px[nx, ny]):
                bg[ny][nx] = True
                q.append((nx, ny))
    out = im.copy()
    op = out.load()
    for y in range(h):
        for x in range(w):
            if bg[y][x]:
                op[x, y] = (255, 255, 255, 0)
                continue
            # граница знака с заливкой: «цвет в альфу» относительно белого
            near = any(0 <= x + dx < w and 0 <= y + dy < h and bg[y + dy][x + dx]
                       for dx in (-1, 0, 1) for dy in (-1, 0, 1))
            if not near:
                continue
            r, g, b, a = px[x, y]
            k = max(255 - r, 255 - g, 255 - b) / 255  # насколько точка темнее белого
            if k <= 0:
                op[x, y] = (255, 255, 255, 0)
                continue
            na = k * a / 255
            # исходный цвет, если бы точка была смесью этого цвета с белым
            nr, ng, nb = (round(255 - (255 - c) / k) for c in (r, g, b))
            op[x, y] = (max(0, nr), max(0, ng), max(0, nb), round(na * 255))
    # обрезка пустых полей
    box = out.getchannel('A').point(lambda v: 255 if v > 8 else 0).getbbox()
    if box:
        l, t, r, b = box
        out = out.crop((max(0, l - 1), max(0, t - 1), min(w, r + 1), min(h, b + 1)))
    return out


os.makedirs(OUT, exist_ok=True)
for slug, src in FILES.items():
    im = Image.open(os.path.join(SRC, src))
    res = process(im)
    res.save(os.path.join(OUT, slug), optimize=True)
    print(f'{slug:<24} {src:<22} {im.size} → {res.size}, {os.path.getsize(os.path.join(OUT, slug)) // 1024} КБ')
