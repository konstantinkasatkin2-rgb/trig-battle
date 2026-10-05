# -*- coding: utf-8 -*-
"""
ТРИГОНОМЕТРИЧЕСКИЙ МОРСКОЙ БОЙ — версия на PYGAME (ПК + Android/APK)
====================================================================

Полный порт `trig_circle.py` (настольная версия на matplotlib) на pygame.
Логика игры, правила, отрисовка полей, прицел, ИИ и туториал перенесены 1:1.

Что изменено по сравнению с matplotlib-версией (это и есть адаптация
под pygame и APK):

  * Вместо фигур matplotlib (`Line2D`, `Text`, `Patch`) всё рисуется
    примитивами pygame на одной поверхности — полный контроль кадра,
    никаких перерисовок по частям.
  * Вместо `plt.pause()` — собственная очередь таймеров `after()`.
  * Вместо `numpy` — модуль `math` (меньше зависимостей, быстрее сборка
    APK).
  * Вместо виджетов matplotlib (`Slider`, `TextBox`, `Button`,
    `RadioButtons`) — свои виджеты: `Button`, `Slider`, `Field`,
    `CheckBox`. Все работают и мышью, и пальцем.
  * Вместо `TextBox` с физической клавиатурой — экранная цифровая
    клавиатура (`Keypad`), потому что на телефоне клавиатуры нет.
  * ПК-мышь: ЛКМ — построить/выбрать/угол 1, ПКМ — удалить/угол 2,
    колесо — поворот юнита. Телефон: тап — построить/выбрать,
    перетаскивание по полю — прицел (углы переключаются кнопками
    «Прицел: 1 / 2»), кнопки «Поворот» и «Удалить».
  * Раскладка полностью адаптивная: игра рисует прямо в окно (без
    масштабирования и чёрных полос), все размеры — панели, поля, кнопки,
    шрифты — пересчитываются в `layout()` под реальный размер окна и
    соотношение сторон. Одинаково работает в окне 1024x600, на телефоне
    2340x1080 и на планшете 2560x1600; при перетаскивании окна
    пересчитывается на лету (VIDEORESIZE), текст остаётся чётким.
  * Текст автоматически переносится по ширине, а если не помещается по
    высоте (например, длинная подсказка туториала в неполноэкранном
    режиме) — шрифт пропорционально уменьшается.
  * Маркеры юнитов, крестики попаданий и подписи точек P1/P2 стали
    мельче (примерно на 20%), подписи P1/P2 рисуются НАД точкой и не
    закрывают её.
  * Списки флота рисуются фигурами (квадраты/треугольники), а не
    символами ■/□/▲/△ — они есть в любом шрифте.
  * Удалён неиспользуемый импорт `auth_db` (в оригинале он был
    импортирован, но нигде не использовался; авторизация — только
    в kivy-версии android/main.py).

Новое (профили и игра по сети):
  * профили: регистрация по электронной почте, вход, смена никнейма,
    статистика. Кнопка профиля — в левом верхнем углу каждого экрана
    меню. База — SQLite в каталоге `dtb` (см. profiles.py).
  * игра по локальной сети: хост раздаёт код из пяти символов, второй
    игрок подключается либо по коду (широковещательный поиск), либо по
    IP. Транспорт и протокол — в netgame.py.

Запуск:
    pip install pygame
    python trig_battle_pygame.py

Сборка APK: см. buildozer.spec в каталоге ready_apk.
"""

import glob
import math
import os
import random
import sys

# pygame не должен печатать приветствие поверх игры; переменная
# читается при первом импорте pygame, поэтому ставим её до него
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')

import pygame

# Профили и сетевая игра — отдельные модули, чтобы их можно было
# положить в APK вместе с игрой. Импорт не должен ронять игру целиком:
# если модуля нет (например, старая копия файла), работаем без
# профилей и без сети, а не падаем на старте.
try:
    import profiles
except Exception:                       # noqa: BLE001 - играем и без профилей
    profiles = None
try:
    import netgame
except Exception:                       # noqa: BLE001 - сеть необязательна
    netgame = None

# ===================== КОНСТАНТЫ ИГРЫ =====================

STEP = 0.1
GRID = 0.1
LIMIT = 1.6
ANGLE1_0 = 50
ANGLE2_0 = 110
HIT_TOL = 0.05
FADE = 0.32          # прозрачность второстепенных линий (в matplotlib 0.1,
                     # на маленьком экране 0.1 нечитаемо, как в kivy-версии)
FLEET_SHIPS = {1: 4, 2: 4, 3: 3, 4: 2, 5: 1}
FLEET_PLANES = {1: 3, 2: 2, 3: 1}
MAX_SIZE = {'ship': 5, 'plane': 3}

DIRECTIONS = [(1, 0), (1, 1), (0, 1), (-1, 1),
              (-1, 0), (-1, -1), (0, -1), (1, -1)]

# ============ НОВЫЙ РЕЖИМ: МАШИНКИ И ПРЕПЯТСТВИЯ ============
# Игрок 1 (за ход) ставит МАШИНКИ — синие круги — за пределами
# окружности, но в пределах квадрата, и задаёт им направление кнопкой
# «Поворот» (шаг 45°, поэтому диагональ идёт снизу-слева наверх-направо).
# За ход машинка проезжает одну клетку. Столкнувшись с препятствием,
# машинка меняет направление на противоположное и сносит одну клетку
# препятствия (стена рассыпается).
# Игрок 2 (защита) ставит ПРЕПЯТСТВИЯ — чёрные квадраты, соединённые как
# корабли и самолёты, длина не больше 4.
# Цель защитника — маленький жёлтый круг [-0.2; 0.2] в центре.
# Машинка, коснувшаяся жёлтого круга, приносит победу атакующему.
# Если все машинки израсходовали запас ходов, побеждает защитник.
CAR_MODE = 'cars'
YELLOW_R = 0.2                  # жёлтый круг: координаты [-0.2; 0.2]
FLEET_CARS = {1: 4}             # 4 машинки (одна на 5 клеток препятствий)
FLEET_WALLS = {1: 4, 2: 3, 3: 2, 4: 1}      # 1:4, 2:3, 3:2, 4:1
CAR_MAX_LEN = 4                 # длина препятствия не больше 4
CAR_R = 0.015                  # радиус машинки в долях ширины поля.
# По требованию игрока машинка размером примерно в одну клетку:
# клетка — это GRID = 0.1 в координатах поля, то есть 0.015 от ширины
# поля в пикселях (0.5 клетки в радиусе, клетка в диаметре).
CAR_STEPS = 40                  # запас ходов у машинки
CAR_ANIM_MS = 320               # на сколько миллисекунд показываем ход:
# машинка крупная, а шаг — ровно клетка, поэтому без плавного
# сдвига движение совсем не заметно
CAR_DIR_NAMES = ['→', '↗', '↑', '↖', '←', '↙', '↓', '↘']

ALL_CELLS = [(round(i * GRID, 2), round(j * GRID, 2))
             for i in range(-16, 17) for j in range(-16, 17)]
SQ_CELLS = [c for c in ALL_CELLS if abs(c[0]) <= 1 and abs(c[1]) <= 1]

# ===================== ПРАВИЛА =====================

# Текст правил собирается из абзацев: пустая строка между абзацами даёт
# перевод строки. chr(10) вместо '\n' — чтобы в этом файле не было
# escape-последовательностей, которые легко испортить при правках.
PARA = chr(10) * 2

RULES = PARA.join([
    '1 - Точка, в которую вы стреляете, это точка пересечения tg и cos, '
    'либо ctg и sin.',
    '2 - Корабли и прочие юниты могут стоять как диагонально, так и '
    'вертикально/горизонтально',
    '3 - Корабли можно ставить лишь в пределах единичной окружности',
    '4 - Самолёты могут стоять лишь в пределах квадрата, но не в пределах '
    'единичной окружности.',
    '5 - Точка атаки может быть лишь в границах квадрата',
    '6 - При попадании по вражескому кораблю враг пропускает ход',
    'НОВЫЙ РЕЖИМ: МАШИНКИ ПРОТИВ ПРЕПЯТСТВИЯ',
    '1 - Машинки (синие круги) ставятся только ЗА пределами окружности, '
    'но внутри чёрного квадрата',
    '2 - Направление машинки задаётся кнопкой «Поворот» с шагом 45°, '
    'по диагонали она едет снизу-слева наверх-направо',
    '3 - За ход машинка проезжает ровно одну клетку',
    '4 - Столкнувшись с препятствием, машинка меняет курс на '
    'противоположный и сносит одну клетку стены',
    '5 - Препятствия (чёрные квадраты) строятся как корабли и самолёты, '
    'длина до 4; жёлтый круг закрывать нельзя',
    '6 - Машинка, коснувшаяся жёлтого круга [-0.2; 0.2], приносит победу '
    'атакующему; если все машинки израсходовали ходы — побеждает защитник',
])

# ===================== ЦВЕТА =====================

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
SMOKE = (245, 245, 245)
NAVY = (0, 0, 128)
TEAL = (0, 128, 128)
PURPLE = (140, 0, 170)
DKORANGE = (230, 120, 10)
ORANGE = (255, 150, 20)
BLUE = (20, 20, 200)
BLUE_L = (0, 0, 235)
RED = (215, 20, 20)
DKRED = (150, 0, 0)
DGREEN = (0, 110, 25)
GREEN = (0, 150, 60)
GRAY = (135, 135, 135)
DGRAY = (100, 100, 100)
SILVER = (195, 195, 195)
LIME = (0, 220, 0)
GOLD = (245, 200, 0)
LTBLUE = (173, 216, 230)
LTGREEN = (200, 235, 200)
LTRED = (250, 210, 210)
LAVENDER = (225, 210, 245)
LTSKY = (210, 235, 245)
PANEL_BG = (250, 250, 245)
BORDER = (90, 90, 90)

MODE_COLORS = {'angles': LTBLUE, 'ships': LTGREEN, 'planes': LAVENDER}
DIFF_COLORS = {'Низкий': (215, 245, 215), 'Средний': LTGREEN,
               'Высокий': LTRED}

# ===================== ГЕОМЕТРИЯ РАСКЛАДКИ =====================
# Никаких «магических» координат: все размеры вычисляются в
# TrigBattle.compute_layout() под реальный размер окна, поэтому раскладка
# одинаково корректна и на ПК (окно/полный экран), и на телефонах/планшетах
# с любым соотношением сторон. DESIGN_* — лишь опорные значения для u.

DESIGN_W, DESIGN_H = 1600, 900
MIN_W, MIN_H = 900, 480             # минимальный размер окна

BACKSPACE = '\b'

# ===================== ШРИФТЫ =====================
# Важно: НЕ используем Font.set_bold() — на некоторых шрифтах (например
# Arial Narrow) синтетическое «жирное» не расширяет межбуквенные интервалы и
# буквы наезжают друг на друга. Вместо этого подгружаем настоящий bold-файл.

_font_cache = {}
_font_paths = None

REG_NAMES = ('DejaVuSans.ttf', 'Roboto-Regular.ttf', 'NotoSans-Regular.ttf',
             'LiberationSans-Regular.ttf', 'FreeSans.ttf', 'arial.ttf',
             'verdana.ttf', 'tahoma.ttf', 'Arial.ttf')
BOLD_NAMES = ('DejaVuSans-Bold.ttf', 'Roboto-Bold.ttf', 'NotoSans-Bold.ttf',
              'LiberationSans-Bold.ttf', 'FreeSansBold.ttf', 'arialbd.ttf',
              'verdanab.ttf', 'tahomabd.ttf', 'Arialbd.ttf')


def _font_dirs():
    here = os.path.dirname(os.path.abspath(__file__))
    dirs = [os.path.join(here, 'assets'), here,
            os.path.join(os.environ.get('WINDIR', 'C:/Windows'), 'Fonts'),
            '/system/fonts', '/usr/share/fonts']
    for pat in ('/usr/share/fonts/**/DejaVuSans.ttf',
                '/usr/share/fonts/**/LiberationSans-Regular.ttf'):
        for p in glob.glob(pat, recursive=True):
            dirs.append(os.path.dirname(p))
    return dirs


def _find_face(names, dirs):
    for d in dirs:
        for n in names:
            p = os.path.join(d, n)
            if os.path.isfile(p):
                return p
    for n in names:                       # имена без пути — через match_font
        stem = os.path.splitext(n)[0].split('-')[0].lower()
        try:
            m = pygame.font.match_font(stem)
        except Exception:
            m = None
        if m:
            return m
    return None


def discover_font():
    """-> (путь к обычному начертанию, путь к жирному) либо (None, None)."""
    global _font_paths
    if _font_paths is None:
        dirs = _font_dirs()
        reg = _find_face(REG_NAMES, dirs)
        bold = _find_face(BOLD_NAMES, dirs)
        if not reg and not bold:           # последний шанс — любой системный
            for pat in ('/system/fonts/*.ttf', '/usr/share/fonts/**/*.ttf'):
                found = sorted(glob.glob(pat, recursive=True))
                if found:
                    reg = found[0]
                    break
        _font_paths = (reg, bold)
    return _font_paths


def font(size, bold=False):
    key = (int(size), bool(bold))
    if key not in _font_cache:
        reg, bold_path = discover_font()
        path = (bold_path if bold else None) or reg
        f = None
        if path:
            try:
                f = pygame.font.Font(path, int(size))
                f.set_bold(bool(bold) and not bold_path)
            except Exception:
                f = None
        if f is None:
            f = pygame.font.Font(None, int(size))
        _font_cache[key] = f
    return _font_cache[key]


# ===================== МЕЛКИЕ ХЕЛПЕРЫ =====================

def clamp(v, lo, hi):
    return lo if v < lo else (hi if v > hi else v)


def mix(c1, c2, a):
    """Смесь цветов: a=0 -> c1, a=1 -> c2."""
    return (int(c1[0] + (c2[0] - c1[0]) * a),
            int(c1[1] + (c2[1] - c1[1]) * a),
            int(c1[2] + (c2[2] - c1[2]) * a))


def faint(c, a=FADE):
    """Цвет с прозрачностью a относительно белого фона поля."""
    return mix(WHITE, c, a)


def text_size(s, size=14, bold=False):
    return font(size, bold).size(s)


def blit_text(surf, s, pos, size=14, color=BLACK, anchor='lt', bold=False,
              alpha=255):
    img = font(size, bold).render(s, True, color)
    if alpha < 255:
        img = img.copy()
        img.set_alpha(alpha)
    w, h = img.get_size()
    dx = {'l': 0, 'm': -w // 2, 'r': -w}[anchor[0]]
    dy = {'t': 0, 'm': -h // 2, 'b': -h}[anchor[1]]
    surf.blit(img, (int(pos[0] + dx), int(pos[1] + dy)))
    return (dx, dy, w, h)


def draw_dash(surf, color, p1, p2, width=1, dash=9, gap=6):
    x1, y1 = p1
    x2, y2 = p2
    ln = math.hypot(x2 - x1, y2 - y1)
    if ln < 1e-6:
        return
    ux, uy = (x2 - x1) / ln, (y2 - y1) / ln
    t = 0.0
    while t < ln:
        t2 = min(t + dash, ln)
        pygame.draw.line(surf, color, (x1 + ux * t, y1 + uy * t),
                         (x1 + ux * t2, y1 + uy * t2), width)
        t += dash + gap


def draw_dash_poly(surf, color, pts, width=1, dash=9, gap=6):
    n = len(pts)
    for i in range(n):
        draw_dash(surf, color, pts[i], pts[(i + 1) % n], width, dash, gap)


def draw_dash_rect(surf, color, rect, width=1, dash=9, gap=6):
    pts = [(rect.left, rect.top), (rect.right, rect.top),
           (rect.right, rect.bottom), (rect.left, rect.bottom)]
    draw_dash_poly(surf, color, pts, width, dash, gap)


def draw_cross(surf, color, x, y, r, width=2):
    pygame.draw.line(surf, color, (x - r, y - r), (x + r, y + r), width)
    pygame.draw.line(surf, color, (x - r, y + r), (x + r, y - r), width)


def draw_star(surf, color, x, y, r, width=2):
    for ang in (0, 60, 120):
        a = math.radians(ang)
        dx, dy = math.cos(a) * r, math.sin(a) * r
        pygame.draw.line(surf, color, (x - dx, y - dy), (x + dx, y + dy),
                         width)


def draw_triangle(surf, color, x, y, r, width=0):
    pts = [(x, y - r), (x - r * 0.9, y + r * 0.8), (x + r * 0.9, y + r * 0.8)]
    pygame.draw.polygon(surf, color, pts, width)


def draw_arrow(surf, color, p1, p2, width=1):
    pygame.draw.line(surf, color, p1, p2, width)
    ang = math.atan2(p2[1] - p1[1], p2[0] - p1[0])
    for da in (2.6, -2.6):
        pygame.draw.line(
            surf, color, p2,
            (p2[0] - 9 * math.cos(ang + da), p2[1] - 9 * math.sin(ang + da)),
            width)


def text_box(surf, lines, pos, size=12, fg=BLACK, bg=PANEL_BG,
             border=BORDER, anchor='lt', bold=False, lh=None, alpha=245,
             pad=6):
    """Панель с текстом (аналог matplotlib Text с bbox=round)."""
    f = font(size, bold)
    lh = lh or int(size * 1.35)
    w = max(f.size(s)[0] for s in lines) + pad * 2
    h = lh * len(lines) + pad * 2
    x, y = pos
    if 'r' in anchor:
        x -= w
    elif 'm' in anchor:
        x -= w // 2
    if 'm' in anchor:
        y -= h // 2
    elif 'b' in anchor:
        y -= h
    box = pygame.Surface((w, h), pygame.SRCALPHA)
    box.fill((*bg, alpha))
    pygame.draw.rect(box, border, box.get_rect(), 1)
    surf.blit(box, (x, y))
    for i, s in enumerate(lines):
        img = f.render(s, True, fg)
        surf.blit(img, (x + pad, y + pad + i * lh))
    return pygame.Rect(x, y, w, h)


def blit_lines(surf, text, pos, size=16, color=BLACK, anchor='lt', bold=False,
               lh=None, center=False):
    """Многострочный текст; при center=True строки центрируются по pos.x."""
    lh = lh or int(size * 1.45)
    f = font(size, bold)
    for i, ln in enumerate(text.split('\n')):
        y = pos[1] + i * lh
        if center:
            blit_text(surf, ln, (pos[0], y), size, color, 'mm', bold)
        else:
            blit_text(surf, ln, (pos[0], y), size, color, anchor, bold)


# ===================== ВИДЖЕТЫ =====================

class Widget:
    visible = True

    def hit(self, pos):
        return self.visible and self.rect.collidepoint(pos)

    def draw(self, surf):
        pass


class Button(Widget):
    def __init__(self, rect, label, cb, color=LTBLUE, size=15, bold=False,
                 text_color=BLACK, radius=7, toggle=False):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.cb = cb
        self.color = color
        self.size = size
        self.bold = bold
        self.text_color = text_color
        self.radius = radius
        self.toggle = toggle
        self.active = False
        self.pressed = False

    def draw(self, surf):
        if not self.visible:
            return
        col = self.color
        if self.toggle and self.active:
            col = GOLD
        if self.pressed:
            col = mix(col, (0, 0, 0), 0.22)
        pygame.draw.rect(surf, col, self.rect, border_radius=self.radius)
        pygame.draw.rect(surf, BORDER, self.rect, 1, border_radius=self.radius)
        blit_text(surf, self.label, self.rect.center, self.size,
                  self.text_color, 'mm', self.bold)

    def press(self):
        self.pressed = True

    def release(self, pos):
        was = self.pressed
        self.pressed = False
        if was and self.hit(pos):
            self.cb()
            return True
        return False


class CheckBox(Widget):
    def __init__(self, rect, label, getter, setter, size=16):
        self.rect = pygame.Rect(rect)
        self.size = size
        bs = int(size * 1.6)
        self.box = pygame.Rect(rect.x, rect.y + (rect.h - bs) // 2, bs, bs)
        self.label = label
        self.getter = getter
        self.setter = setter
        w, h = text_size(label, size)
        self.text_rect = pygame.Rect(self.box.right + int(10 * size / 16),
                                     rect.y, w, rect.h)

    def draw(self, surf):
        if not self.visible:
            return
        pygame.draw.rect(surf, WHITE, self.box)
        pygame.draw.rect(surf, BLACK, self.box, 2)
        if self.getter():
            cx, cy = self.box.center
            pygame.draw.lines(surf, DGREEN, False,
                              [(cx - self.box.w * 0.30, cy),
                               (cx - self.box.w * 0.05,
                                cy + self.box.h * 0.25),
                               (cx + self.box.w * 0.32,
                                cy - self.box.h * 0.28)],
                              max(2, self.box.w // 10))
        blit_text(surf, self.label, (self.text_rect.x, self.rect.centery),
                  self.size, BLACK, 'lm')

    def press(self):
        self.setter(not self.getter())


class Slider(Widget):
    def __init__(self, rect, value, vmin=0, vmax=360, step=1, on_change=None):
        self.rect = pygame.Rect(rect)
        self.value = float(value)
        self.vmin = vmin
        self.vmax = vmax
        self.step = step
        self.on_change = on_change
        self.grabbed = False

    def set(self, v, exact=False):
        """exact=True — не округлять до шага (ввод числа с клавиатуры)."""
        v = clamp(float(v), self.vmin, self.vmax)
        if self.step and not exact:
            v = round(v / self.step) * self.step
        if abs(v - self.value) < 1e-9:
            self.value = v
            return
        self.value = v
        if self.on_change:
            self.on_change()

    def bump(self, d):
        self.set(self.value + d)

    def _from_pos(self, x):
        t = (x - self.rect.left) / max(1, self.rect.width)
        self.set(self.vmin + t * (self.vmax - self.vmin))

    def draw(self, surf):
        if not self.visible:
            return
        cy = self.rect.centery
        pygame.draw.rect(surf, (205, 205, 200), self.rect, border_radius=4)
        pygame.draw.rect(surf, BORDER, self.rect, 1, border_radius=4)
        t = (self.value - self.vmin) / (self.vmax - self.vmin)
        kx = self.rect.left + t * self.rect.width
        ky = cy
        pygame.draw.line(surf, NAVY, (self.rect.left + 8, cy),
                         (kx, ky), 5)
        pygame.draw.circle(surf, NAVY, (int(kx), int(ky)), 13)
        pygame.draw.circle(surf, WHITE, (int(kx), int(ky)), 13, 2)

    def press(self, pos):
        self.grabbed = True
        self._from_pos(pos[0])

    def drag(self, pos):
        if self.grabbed:
            self._from_pos(pos[0])

    def release(self):
        self.grabbed = False


class Field(Widget):
    """Поле ввода. По умолчанию — число (аналог matplotlib TextBox).

    Для email/пароля/ника задаётся `charset`: он же определяет, что
    принимает экранная клавиатура.
    """

    NUMERIC = '0123456789.-'
    TEXT = ("abcdefghijklmnopqrstuvwxyz"
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789@._-")

    def __init__(self, rect, label, getter, on_submit, size=18,
                 charset=None, max_len=8, text_keypad=False, masked=False):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.size = size
        self.getter = getter          # -> текущий текст (из значения угла)
        self.on_submit = on_submit    # (строка) -> нормализованный текст
        self.charset = charset or self.NUMERIC
        self.max_len = max_len
        # текстовым полям нужна клавиатура с буквами и замаскированный ввод
        self.text_keypad = text_keypad
        self.masked = masked
        self.text = ''
        self.focused = False

    def display_text(self):
        """Что показать: у пароля вместо символов точки."""
        return '*' * len(self.text) if self.masked else self.text

    def draw(self, surf):
        if not self.visible:
            return
        ls = max(9, int(self.size * 0.72))
        w, _ = text_size(self.label, ls, True)
        blit_text(surf, self.label, (self.rect.x - w - int(8 * self.size / 18),
                                      self.rect.centery), ls, BLACK, 'lm', True)
        pygame.draw.rect(surf, GOLD if self.focused else WHITE, self.rect)
        pygame.draw.rect(surf, DKORANGE if self.focused else BORDER,
                         self.rect, 2 if self.focused else 1)
        shown = self.display_text() if self.focused else self.getter()
        blit_text(surf, shown, self.rect.center, self.size, BLACK, 'mm',
                  self.focused)
        if self.focused:
            blit_text(surf, '|', (self.rect.right - int(self.size * 0.6),
                                  self.rect.centery - self.size // 2),
                      self.size, DKORANGE, 'mt', True)

    def press(self):
        # Всегда начинаем с пустого поля: если подставить текущее
        # значение угла, то ввод «0.2» допишется к нему («450.2»).
        self.focused = True
        self.text = ''

    def key(self, ch):
        if ch == BACKSPACE:
            self.text = self.text[:-1]
            return
        if ch == '±' and '±' in self.charset:
            self.text = self.text[1:] if self.text.startswith('-') \
                else '-' + self.text
            return
        if ch not in self.charset:
            return
        if ch == '-' and self.text:
            self.text = '-' + self.text[1:]
            return
        # В числовом поле точка и минус могут встречаться только раз;
        # в текстовом (почта) это ломало бы адрес вида ivan@mail.ru
        if self.charset == self.NUMERIC and ch in '.-' and \
                any(c in self.text for c in '.-'):
            return
        if len(self.text) >= self.max_len:
            return
        self.text += ch

    def submit(self):
        self.text = self.on_submit(self.text)
        self.focused = False


class Keypad(Widget):
    """Экранная цифровая клавиатура (на телефоне физической нет)."""

    KEYS = [['1', '2', '3'], ['4', '5', '6'], ['7', '8', '9'],
            ['.', '0', '±']]

    def __init__(self, rect, u=1.0):
        self.rect = pygame.Rect(rect)
        self.u = u
        self.visible = False
        self.field = None
        self.keys = []
        self.actions = []
        self.disp = pygame.Rect(0, 0, 0, 0)
        self._build()

    def _build(self):
        u = self.u
        gap = max(6, int(10 * u))
        head = int(76 * u)
        kw = int((self.rect.width - 4 * gap) / 3)
        kh = int((self.rect.height - head - 2 * gap) / 5.6)
        kh = max(int(28 * u), kh)
        gx = self.rect.x + (self.rect.width - (3 * kw + 2 * gap)) // 2
        y0 = self.rect.y + head
        for r, row in enumerate(self.KEYS):
            for c, ch in enumerate(row):
                self.keys.append((ch, pygame.Rect(gx + c * (kw + gap),
                                                  y0 + r * (kh + gap),
                                                  kw, kh)))
        y = y0 + 4 * (kh + gap)
        x = self.rect.x + gap
        for lbl in ('C', BACKSPACE, 'OK'):
            self.actions.append((lbl, pygame.Rect(x, y, kw, kh)))
            x += kw + gap
        self.disp = pygame.Rect(int(self.rect.centerx -
                                    self.rect.width * 0.46),
                                self.rect.y + int(30 * u),
                                int(self.rect.width * 0.92),
                                int(42 * u))

    def open(self, field):
        self.field = field
        self.visible = True

    def close(self):
        self.field = None
        self.visible = False

    def _tap(self, pos):
        for ch, r in self.keys:
            if r.collidepoint(pos):
                self.field.key(ch)
                return
        for ch, r in self.actions:
            if r.collidepoint(pos):
                if ch == 'C':
                    self.field.text = ''
                elif ch == BACKSPACE:
                    self.field.key(BACKSPACE)
                else:
                    self.field.submit()
                    self.close()
                return

    def draw(self, surf):
        if not self.visible:
            return
        u = self.u
        shade = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 120))
        surf.blit(shade, (0, 0))
        rad = max(6, int(10 * u))
        pygame.draw.rect(surf, SMOKE, self.rect, border_radius=rad)
        pygame.draw.rect(surf, BORDER, self.rect, max(1, int(3 * u)),
                         border_radius=rad)
        blit_text(surf, 'Введите  ' + self.field.label,
                  (self.rect.x + int(14 * u), self.rect.y + int(8 * u)),
                  max(11, int(15 * u)), DKORANGE, 'lt', True)
        pygame.draw.rect(surf, WHITE, self.disp)
        pygame.draw.rect(surf, BORDER, self.disp, max(1, int(2 * u)))
        blit_text(surf, self.field.text or '—', self.disp.center,
                  max(16, int(30 * u)), BLACK, 'mm', True)
        for ch, r in self.keys:
            col = LTGREEN if ch == '±' else WHITE
            pygame.draw.rect(surf, col, r, border_radius=rad)
            pygame.draw.rect(surf, BORDER, r, 1, border_radius=rad)
            blit_text(surf, ch, r.center, max(14, int(26 * u)), BLACK, 'mm',
                      True)
        for ch, r in self.actions:
            col = LTGREEN if ch == 'OK' else (LTRED if ch == 'C' else WHITE)
            pygame.draw.rect(surf, col, r, border_radius=rad)
            pygame.draw.rect(surf, BORDER, r, 1, border_radius=rad)
            blit_text(surf, ch, r.center, max(12, int(22 * u)), BLACK, 'mm',
                      True)

    # --- события: окно модальное, наружу не пропускаем ---
    def down(self, pos):
        self._tap(pos)
        return True

    def drag(self, pos):
        return True

    def up(self, pos):
        return True


class TextKeypad(Widget):
    """Экранная клавиатура для текста: буквы, @ и точка нужны для почты.

    Три раскладки переключаются кнопкой `123 / abc / АБВ`; цифры,
    символы `@` и `_` есть в нижней строке всегда, чтобы не искать их
    в третьей раскладке.
    """

    LAYOUTS = {
        'abc': ['abcdefghij', 'klmnopqrst', 'uvwxyz._-@'],
        'ABC': ['ABCDEFGHIJ', 'KLMNOPQRS', 'TUVWXYZ._-@'],
        '123': ['123456789', '0.,!?-/\\', ' '],
    }
    ORDER = ['abc', 'ABC', '123']

    def __init__(self, rect, u=1.0):
        self.rect = pygame.Rect(rect)
        self.u = u
        self.visible = False
        self.field = None
        self.mode = 'abc'
        self.keys = []          # [(символ, rect)]
        self.actions = []       # [(метка, rect)]
        self.disp = pygame.Rect(0, 0, 0, 0)
        self._build()

    def _build(self):
        u = self.u
        gap = max(5, int(8 * u))
        head = int(70 * u)
        rows = self.LAYOUTS[self.mode]
        kw = int((self.rect.width - 11 * gap) / 10)
        kh = int((self.rect.height - head - 2 * gap) / 4.8)
        kh = max(int(26 * u), kh)
        gx = self.rect.x + gap
        y0 = self.rect.y + head
        self.keys = []
        for r, row in enumerate(rows):
            n = len(row)
            for c, ch in enumerate(row):
                self.keys.append((ch, pygame.Rect(gx + c * (kw + gap),
                                                  y0 + r * (kh + gap),
                                                  kw, kh)))
        y = y0 + 3 * (kh + gap)
        # нижний ряд: пробел, C, стирание, переключение раскладки, OK
        wide = int(kw * 2.6)
        x = self.rect.x + gap
        bottom = []
        bottom.append(('space', pygame.Rect(x, y, wide, kh)))
        x += wide + gap
        bottom.append(('C', pygame.Rect(x, y, kw, kh)))
        x += kw + gap
        bottom.append((BACKSPACE, pygame.Rect(x, y, kw, kh)))
        x += kw + gap
        bottom.append(('layout', pygame.Rect(x, y, int(kw * 2.2), kh)))
        x += int(kw * 2.2) + gap
        bottom.append(('OK', pygame.Rect(x, y, kw, kh)))
        self.actions = bottom
        self.disp = pygame.Rect(int(self.rect.centerx -
                                    self.rect.width * 0.46),
                                self.rect.y + int(26 * u),
                                int(self.rect.width * 0.92),
                                int(36 * u))

    def open(self, field):
        self.field = field
        self.visible = True

    def close(self):
        self.field = None
        self.visible = False

    def _tap(self, pos):
        for ch, r in self.keys:
            if r.collidepoint(pos):
                self.field.key(' ' if ch == ' ' else ch)
                return
        for ch, r in self.actions:
            if r.collidepoint(pos):
                if ch == 'C':
                    self.field.text = ''
                elif ch == BACKSPACE:
                    self.field.key(BACKSPACE)
                elif ch == 'space':
                    self.field.key(' ')
                elif ch == 'layout':
                    i = self.ORDER.index(self.mode)
                    self.mode = self.ORDER[(i + 1) % len(self.ORDER)]
                    self._build()
                else:
                    self.field.submit()
                    self.close()
                return

    def draw(self, surf):
        if not self.visible:
            return
        u = self.u
        shade = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 120))
        surf.blit(shade, (0, 0))
        rad = max(5, int(9 * u))
        pygame.draw.rect(surf, SMOKE, self.rect, border_radius=rad)
        pygame.draw.rect(surf, BORDER, self.rect, max(1, int(3 * u)),
                         border_radius=rad)
        blit_text(surf, 'Введите  ' + self.field.label,
                  (self.rect.x + int(12 * u), self.rect.y + int(6 * u)),
                  max(11, int(15 * u)), DKORANGE, 'lt', True)
        shown = self.field.display_text() or '—'
        pygame.draw.rect(surf, WHITE, self.disp)
        pygame.draw.rect(surf, BORDER, self.disp, max(1, int(2 * u)))
        blit_text(surf, shown[-40:], self.disp.center,
                  max(14, int(24 * u)), BLACK, 'mm', True)
        fs = max(11, int(21 * u))
        for ch, r in self.keys:
            pygame.draw.rect(surf, WHITE, r, border_radius=rad)
            pygame.draw.rect(surf, BORDER, r, 1, border_radius=rad)
            blit_text(surf, ch if ch != ' ' else 'пробел', r.center, fs,
                      BLACK, 'mm', True)
        for ch, r in self.actions:
            col = LTGREEN if ch == 'OK' else (LTRED if ch == 'C' else
                                              (LAVENDER if ch == 'layout'
                                               else WHITE))
            pygame.draw.rect(surf, col, r, border_radius=rad)
            pygame.draw.rect(surf, BORDER, r, 1, border_radius=rad)
            label = {'C': 'C', BACKSPACE: '<-', 'space': 'пробел',
                     'layout': 'abc / АБВ / 123', 'OK': 'OK'}[ch]
            blit_text(surf, label, r.center, max(10, int(16 * u)), BLACK,
                      'mm', True)

    def down(self, pos):
        self._tap(pos)
        return True

    def drag(self, pos):
        return True

    def up(self, pos):
        return True


# ===================== ПРИЛОЖЕНИЕ =====================

class TrigBattle:
    def __init__(self):
        pygame.display.set_caption('Тригонометрический морской бой')
        self.force_landscape()
        self.win = self.open_display()
        self.layout(self.win.get_width(), self.win.get_height())
        print('[trigbattle] окно %dx%d%s, холст %dx%d, u=%.2f, '
              'видеодрайвер: %s'
              % (self.win_size[0], self.win_size[1],
                 ' (повёрнуто)' if self.rotated else '',
                 self.W, self.H, self.u,
                 os.environ.get('SDL_VIDEODRIVER', 'по умолчанию')),
              flush=True)
        self.clock = pygame.time.Clock()
        self.running = True
        self.fullscreen = False

        self.settings = {'planes': True, 'music': False, 'hints': False,
                         'difficulty': 'Средний'}
        # состояние пользователя (профиль; раньше авторизация не
        # использовалась, в оригинале был неиспользуемый импорт auth_db)
        self.user_state = {'user_id': None, 'nickname': None,
                           'email': None, 'logged_in': False}

        # ---------------- ПРОФИЛИ ----------------
        # profiles.py кладёт базу в каталог `dtb` рядом с программой.
        # Если модуля нет или база не открылась — игра работает, просто
        # без профилей: профильная кнопка прячется.
        self.profile_db = None
        self.profile_error = ''
        if profiles is not None:
            try:
                self.profile_db = profiles.Profiles()
                saved = self.profile_db.restore_session()
                if saved:
                    self.set_user(saved)
            except Exception as e:            # noqa: BLE001 - не мешаем игре
                self.profile_db = None
                self.profile_error = 'Профили недоступны: %s' % e
        # содержимое полей форм (почта, пароль, ник, код, IP)
        self.form = {'email': '', 'password': '', 'password2': '',
                     'nick': '', 'code': '', 'ip': ''}
        self.form_focus = None

        # ---------------- ИГРА ПО СЕТИ ----------------
        self.net = None                 # HostServer | Client | None
        self.net_role = None            # 'host' | 'client'
        self.net_code = ''
        self.net_peer_nick = 'Соперник'
        self.net_state = 'idle'         # idle|waiting|connected|battle|over
        self.car_play = 'local'      # вид партии в новом режиме: ai|local|net
        self.net_ready_sent = False
        self.net_peer_ready = False
        self.net_shots = 0
        self.net_hits = 0

        self.FL = {'name': 'Игрок 1', 'units': [], 'misses': [], 'hints': set()}
        self.FR = {'name': 'Игрок 2', 'units': [], 'misses': [], 'hints': set()}
        self.state = {'P1': None, 'P2': None}

        self.game = {'mode': 'ai', 'phase': 'place1', 'turn': 'player1',
                     'my_moves': 0, 'enemy_moves': 0, 'last': '—',
                     'awaiting_tap': False,
                     'streak': {'player1': 0, 'player2': 0}}
        self.unit_state = {'size': 3, 'dir_idx': 0, 'selected': None,
                           'last': None}
        self.mode = {'name': 'angles'}
        self.enemy_ai = {'tried': set(), 'hunt': [], 'thits': []}
        self.shot_sel = {'p': 'P1'}
        self.aim_sel = 1

        self.s1, self.s2 = float(ANGLE1_0), float(ANGLE2_0)
        self.msg = ('Тригонометрический морской бой', BLACK)
        self.timers = []
        self.screen_name = 'menu'
        self.tutorial = {'active': False, 'step': -1, 'waiting': None,
                         'end': None, 'zones': False}
        self.drag_side = None
        self.drag_btn = 1
        self.pressed_btn = None
        self.pressed_slider = None

        self.screens = {}
        self.build_ui()
        self.update_angles()
        self.show_screen('menu')

    # =========================================================
    #  РАСКЛАДКА: пересчитывается под реальный размер окна
    # =========================================================
    def layout(self, win_w, win_h):
        """Пересчитать все прямоугольники под окно win_w x win_h.

        Игра альбомная. Если система всё же отдала книжное окно, холст
        строится в повёрнутых (переставленных) размерах и выводится
        повёрнутым на 90°, а касания пересчитываются обратно. Играть
        можно в любой ориентации — просто приложение само выбирает
        альбомную.
        """
        self.win_size = (int(win_w), int(win_h))
        self.rotated = win_h > win_w
        w, h = (win_h, win_w) if self.rotated else (win_w, win_h)
        w = max(MIN_W, int(w))
        h = max(MIN_H, int(h))
        u = clamp(h / float(DESIGN_H), 0.60, 3.0)   # масштаб элементов
        self.W, self.H, self.u = w, h, u

        # --- шапка, баннер туториала, блок управления ---
        self.HEADER_H = int(46 * u)
        self.TUT_H = int(78 * u)
        bh = int(42 * u)                            # высота кнопки
        r1h, r2h = int(66 * u), int(60 * u)
        r3h = r4h = bh + int(4 * u)
        hint_h = int(38 * u)
        self.CTRL_H = r1h + r2h + r3h + r4h + hint_h
        self.CTRL_TOP = h - self.CTRL_H
        self.R1 = (self.CTRL_TOP, r1h)               # углы
        self.R2 = (self.R1[0] + r1h, r2h)            # числовой ввод
        self.R3 = (self.R2[0] + r2h, r3h)            # стройка
        self.R4 = (self.R3[0] + r3h, r4h)            # бой
        self.HINT_Y = self.R4[0] + r4h

        # --- поля и боковые панели ---
        self.GAP = max(5, int(12 * u))
        self.M = max(8, int(40 * u))                 # боковое поле
        mid_top = self.HEADER_H + self.TUT_H
        mid_h = max(120, h - mid_top - self.CTRL_H)
        panel_w = int(clamp(250 * u, 120, 460))
        board = int(min(mid_h - self.GAP,
                        (w - 2 * panel_w - 3 * self.GAP) / 2.0))
        board = max(150, board)
        self.PANEL_W, self.BOARD = panel_w, board
        total = 2 * panel_w + 2 * board + 3 * self.GAP
        x0 = max(self.GAP, (w - total) // 2)
        by = mid_top + (mid_h - board) // 2
        # порядок слева направо: панель 1 | поле L | поле R | панель 2
        self.pr = [pygame.Rect(x0, by, panel_w, board)]
        self.br = {'L': pygame.Rect(self.pr[0].right + self.GAP, by,
                                    board, board)}
        self.br['R'] = pygame.Rect(self.br['L'].right + self.GAP, by,
                                   board, board)
        self.pr.append(pygame.Rect(self.br['R'].right + self.GAP, by,
                                   panel_w, board))

        # --- экранная клавиатура ---
        kw = int(clamp(0.42 * w, 340, 700))
        kh = int(clamp(0.47 * h, 260, 430))
        self.KP = pygame.Rect((w - kw) // 2, (h - kh) // 2, kw, kh)

        # холст = размер окна (без масштабирования — текст всегда чёткий)
        self.base = pygame.Surface((w, h)).convert()
        self.base.fill(SMOKE)

    def resize(self, w, h):
        w = max(MIN_W, int(w))
        h = max(MIN_H, int(h))
        self.win = pygame.display.set_mode((w, h), pygame.RESIZABLE)
        self.layout(w, h)
        self.build_ui()          # виджеты пересоздаются под новый размер
        self.update_angles()

    def force_landscape(self):
        """Просит Android поставить окно в альбомную ориентацию.

        Манифест уже содержит screenOrientation=landscape, но некоторые
        прошивки и планшеты всё равно отдают книжное окно. Здесь мы
        обращаемся к активности напрямую. На ПК модуля jnius нет — это
        не ошибка, там ориентацию задаёт окно.
        """
        if os.environ.get('SDL_VIDEODRIVER') == 'dummy':
            return
        try:
            from jnius import autoclass
        except ImportError:
            return
        try:
            activity = autoclass('org.kivy.android.PythonActivity').mActivity
            # ActivityInfo.SCREEN_ORIENTATION_LANDSCAPE
            activity.setRequestedOrientation(0)
            print('[trigbattle] ориентация запрошена альбомная', flush=True)
        except Exception as e:            # noqa: BLE001
            print('[trigbattle] не удалось задать ориентацию: %r' % (e,),
                  flush=True)

    # =========================================================
    #  СОЗДАНИЕ ОКНА (с подстраховкой для телефонов)
    # =========================================================
    def open_display(self):
        """Создать окно. Если видеодрайвер Android не даёт окно —
        пробуем пустой драйвер: игра не запустится красиво, но не упадёт
        молча, и в logcat будет видно причину."""
        pygame.init()
        try:
            return pygame.display.set_mode((DESIGN_W, DESIGN_H),
                                           pygame.RESIZABLE)
        except pygame.error as exc:
            print('[trigbattle] set_mode не удался: %s; пробуем драйвер '
                  'dummy' % exc, flush=True)
            os.environ['SDL_VIDEODRIVER'] = 'dummy'
            return pygame.display.set_mode((DESIGN_W, DESIGN_H))

    # ---------------- таймеры (замена plt.pause) ----------------
    def after(self, ms, fn):
        self.timers.append([pygame.time.get_ticks() + ms, fn])

    def pump_timers(self):
        if not self.timers:
            return
        now = pygame.time.get_ticks()
        due = [t for t in self.timers if t[0] <= now]
        self.timers = [t for t in self.timers if t[0] > now]
        for _, fn in due:
            fn()

    # =========================================================
    #  ЭКРАН И КАРКАС
    # =========================================================
    def show_screen(self, name):
        self.screen_name = name
        self.keypad.close()
        self.textpad.close()
        self.pressed_btn = None
        self.pressed_slider = None
        if name not in ('game', 'victory'):
            # уходя с игрового экрана, гасим последнее действие и
            # подсказку: в меню они висели как чужой текст. На экране
            # победы текст нужен, поэтому его не трогаем.
            self.set_msg('', BLACK)
            self.game['last'] = '—'
            self.unit_state['last'] = None

    def set_msg(self, text, color=BLACK):
        self.msg = (text, color)

    # ---------------- main loop ----------------
    def run(self):
        while self.running:
            for ev in pygame.event.get():
                self.handle_event(ev)
            if self.net is not None:
                self._net_poll()
            self.pump_timers()
            self.draw()
            self.present()
            self.clock.tick(60)
        if self.net is not None:
            self.net.send({'t': 'bye'})
            self.net.close()
            self.net = None
        pygame.quit()

    def present(self):
        # холст рисуется в размер окна, поэтому просто копируем без
        # масштабирования (текст остаётся чётким на любом DPI/экране).
        # В книжном окне холст повёрнут: rotate(90) даёт ровно размер окна.
        ww, wh = self.win.get_size()
        if (ww, wh) != self.win_size:
            self.resize(ww, wh)
            self.draw()
        if self.rotated:
            self.win.blit(pygame.transform.rotate(self.base, 90), (0, 0))
        else:
            self.win.blit(self.base, (0, 0))
        pygame.display.flip()

    def to_design(self, pos):
        """Экранные координаты -> координаты холста.

        При повёрнутом выводе холст шириной W и высотой H показан на
        окне W'=H, H'=W: точка холста (cx, cy) оказывается в окне в
        точке (cy, W - 1 - cx). Отсюда обратное преобразование.
        """
        if not self.rotated:
            return pos                # холст == окно, координаты совпадают
        return (self.W - 1 - pos[1], pos[0])

    # =========================================================
    #  СОБЫТИЯ
    # =========================================================
    def handle_event(self, ev):
        if ev.type == pygame.QUIT:
            self.running = False
        elif ev.type == pygame.VIDEORESIZE:
            self.resize(ev.w, ev.h)
        elif ev.type == pygame.KEYDOWN:
            self.on_key(ev)
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button in (1, 2, 3):
            self.on_down(self.to_design(ev.pos), ev.button)
        elif ev.type == pygame.MOUSEBUTTONUP and ev.button in (1, 2, 3):
            self.on_up(self.to_design(ev.pos), ev.button)
        elif ev.type == pygame.MOUSEMOTION:
            self.on_move(self.to_design(ev.pos),
                         3 if ev.buttons[1] or ev.buttons[2] else 1)

    def widgets(self):
        return self.screens.get(self.screen_name, [])

    def on_down(self, pos, btn=1):
        if self.textpad.visible:
            self.textpad.down(pos)
            return
        if self.keypad.visible:
            self.keypad.down(pos)
            return
        # сначала виджеты экрана
        for wdg in reversed(self.widgets()):
            if not wdg.hit(pos):
                continue
            if isinstance(wdg, Button):
                self.pressed_btn = wdg
                wdg.press()
                return
            if isinstance(wdg, CheckBox):
                wdg.press()
                return
            if isinstance(wdg, Slider):
                self.pressed_slider = wdg
                wdg.press(pos)
                return
            if isinstance(wdg, Field):
                # текстовые поля (почта/пароль/код) открывают клавиатуру
                # с буквами, числовые — цифровую
                wdg.press()
                if wdg.text_keypad:
                    self.textpad.open(wdg)
                else:
                    self.keypad.open(wdg)
                return
        if self.screen_name == 'game':
            for side in ('L', 'R'):
                if self.br[side].collidepoint(pos):
                    self.board_touch(side, pos, 'down', btn)
                    return

    def on_move(self, pos, btn=1):
        if self.textpad.visible:
            self.textpad.drag(pos)
            return
        if self.keypad.visible:
            self.keypad.drag(pos)
            return
        if self.pressed_slider is not None:
            self.pressed_slider.drag(pos)
            return
        if self.screen_name == 'game' and self.drag_side:
            self.board_touch(self.drag_side, pos, 'move', btn)

    def on_up(self, pos, btn=1):
        if self.textpad.visible:
            self.textpad.up(pos)
            return
        if self.keypad.visible:
            self.keypad.up(pos)
            return
        if self.pressed_btn is not None:
            b = self.pressed_btn
            self.pressed_btn = None
            b.release(pos)
            return
        if self.pressed_slider is not None:
            self.pressed_slider.release()
            self.pressed_slider = None
            return
        if self.drag_side:
            self.drag_side = None

    def on_key(self, ev):
        k = ev.key
        if k == pygame.K_F11:
            self.toggle_fullscreen()
            return
        if k == pygame.K_ESCAPE:
            if self.textpad.visible:
                self.textpad.close()
                return
            if self.keypad.visible:
                self.keypad.close()
                return
            if self.screen_name == 'game':
                for wdg in self.game_widgets:
                    if isinstance(wdg, Field) and wdg.focused:
                        wdg.focused = False
                self.deselect()
            return
        # ввод в сфокусированное поле (на ПК — физическая клавиатура)
        # поля ищем на текущем экране: игровые числа и текстовые поля
        # входа/сети живут в разных списках виджетов
        focused = [w for w in (self.game_widgets if self.screen_name == 'game'
                               else self.widgets())
                   if isinstance(w, Field) and w.focused]
        if not focused and self.textpad.visible:
            focused = [self.textpad.field]
        for wdg in focused:
            if k == pygame.K_BACKSPACE:
                wdg.key(BACKSPACE)
            elif k in (pygame.K_PERIOD, pygame.K_COMMA):
                wdg.key('.')
            elif k in (pygame.K_MINUS, pygame.K_PLUS, pygame.K_EQUALS):
                wdg.key('±')
            elif k == pygame.K_at:
                wdg.key('@')
            elif pygame.K_0 <= k <= pygame.K_9:
                wdg.key(chr(k))
            elif 32 <= k <= 126:
                wdg.key(chr(k))          # латиница, '@', '.', '_', '-'
            elif k in (pygame.K_RETURN, pygame.K_KP_ENTER):
                wdg.submit()
                self.keypad.close()
                self.textpad.close()
            return
        if self.screen_name != 'game':
            return
        # горячие клавиши стройки
        if self.build_fld() is not None and \
                self.mode['name'] in ('ships', 'planes'):
            mx = MAX_SIZE[self.cur_type()]
            if pygame.K_1 <= k <= pygame.K_5 and k - pygame.K_0 <= mx:
                self.set_size(k - pygame.K_0)
            elif k == pygame.K_r:
                self.rotate(1)
            elif k == pygame.K_z:
                fld = self.build_fld()
                if fld['units']:
                    self.remove_unit(fld['units'][-1])
            elif k == pygame.K_c:
                self.clear_field()
            elif k == pygame.K_DELETE:
                self.delete_selected()
        # точная подстройка углов
        if k == pygame.K_LEFT:
            self.sliders[self.aim_sel - 1].bump(-1)
        elif k == pygame.K_RIGHT:
            self.sliders[self.aim_sel - 1].bump(1)

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        if self.fullscreen:
            self.force_landscape()
            info = pygame.display.Info()
            self.win = pygame.display.set_mode((info.current_w, info.current_h),
                                              pygame.FULLSCREEN)
            self.resize(info.current_w, info.current_h)
        else:
            self.resize(DESIGN_W, DESIGN_H)

    # =========================================================
    #  ПОЛЯ: координаты, геометрия юнитов
    # =========================================================
    def to_px(self, side, x, y):
        r = self.br[side]
        s = r.width * 0.96 / (2 * LIMIT)
        return (r.centerx + x * s, r.centery - y * s)

    def to_data(self, side, pos):
        r = self.br[side]
        s = r.width * 0.96 / (2 * LIMIT)
        return ((pos[0] - r.centerx) / s, (r.centery - pos[1]) / s)

    def snap(self, v):
        return round(round(v / GRID) * GRID, 2)

    def unit_points(self, x0, y0, size, dir_idx):
        dx, dy = DIRECTIONS[dir_idx]
        return [(round(x0 + k * dx * GRID, 2), round(y0 + k * dy * GRID, 2))
                for k in range(size)]

    def no_touch(self, pts, units, ignore=None):
        for un in units:
            if un is ignore:
                continue
            for p in pts:
                for q in un['pts']:
                    if max(abs(p[0] - q[0]), abs(p[1] - q[1])) <= GRID + 1e-9:
                        return False
        return True

    def points_ok(self, pts, utype, units, ignore=None):
        if utype == 'ship':
            for p in pts:
                if p[0] ** 2 + p[1] ** 2 > 1 + 1e-9:
                    return False
        else:
            for p in pts:
                if not (-1 - 1e-9 <= p[0] <= 1 + 1e-9 and
                        -1 - 1e-9 <= p[1] <= 1 + 1e-9):
                    return False
                if p[0] ** 2 + p[1] ** 2 < 1 - 1e-9:
                    return False
        return self.no_touch(pts, units, ignore)

    def fleets(self):
        return dict(FLEET_SHIPS), \
            (dict(FLEET_PLANES) if self.settings['planes'] else {})

    def remaining(self, units):
        fsh, fpl = self.fleets()
        rem = {'ship': fsh, 'plane': fpl}
        for un in units:
            rem[un['type']][un['size']] -= 1
        return rem

    def unit_at(self, units, x, y, tol=0.055):
        for un in reversed(units):
            for px, py in un['pts']:
                if abs(px - x) <= tol and abs(py - y) <= tol:
                    return un
        return None

    @staticmethod
    def is_sunk(un):
        return len(un['pts']) > 0 and len(un['hits']) == len(un['pts'])

    @staticmethod
    def all_sunk(units):
        return len(units) > 0 and all(TrigBattle.is_sunk(un) for un in units)

    def unit_visible(self, un, fld):
        """Классические правила скрытия: чужие юниты не видны (кроме потопленных)."""
        if self.car_mode():
            # в новом режиме своих фигур видно всегда, а чужие
            # проявляются только после столкновения (см. car_seen)
            return (self.car_owner(un) ==
                    self.car_side_of_fld(fld) or
                    bool(un.get('revealed')) or
                    self.game['phase'] == 'over')
        if self.game['phase'] == 'over' or self.is_sunk(un):
            return True
        if self.game.get('awaiting_tap') and self.game['phase'] == 'battle':
            return False
        if self.game['mode'] == 'ai':
            return fld is self.FL
        if self.game['mode'] == 'net':
            # по сети у каждого одно своё поле: свой флот виден всегда,
            # чужой — только потопленные корабли (и всё поле в конце боя,
            # см. первую строку). Иначе соперник видел бы наш флот целиком
            # в чужий ход, а мы — его.
            return fld is self.FL
        if self.game['phase'] == 'place1':
            return fld is self.FL
        if self.game['phase'] == 'place2':
            return fld is self.FR
        own = (fld is self.FL) == (self.game['turn'] == 'player1')
        return own

    def halo_points(self, un, units):
        halo = set()
        occupied = {q for o in units for q in o['pts']}
        for px, py in un['pts']:
            for dx in (-GRID, 0.0, GRID):
                for dy in (-GRID, 0.0, GRID):
                    if dx == 0 and dy == 0:
                        continue
                    q = (round(px + dx, 2), round(py + dy, 2))
                    if not (-LIMIT <= q[0] <= LIMIT and
                            -LIMIT <= q[1] <= LIMIT):
                        continue
                    if q in occupied:
                        continue
                    halo.add(q)
        return halo

    def fire_at(self, fld, px, py):
        for un in fld['units']:
            for p in un['pts']:
                if p not in un['hits'] and \
                        abs(px - p[0]) <= HIT_TOL and abs(py - p[1]) <= HIT_TOL:
                    un['hits'].add(p)
                    return 'sunk' if self.is_sunk(un) else 'hit'
        fld['misses'].append((round(px, 3), round(py, 3)))
        return 'miss'

    # =========================================================
    #  ПРИЦЕЛ
    # =========================================================
    def set_angle1(self, v, exact=False):
        self.sliders[0].set(v, exact)

    def set_angle2(self, v, exact=False):
        self.sliders[1].set(v, exact)

    def set_angle_slot(self, slot, v, exact=False):
        """Ставим угол по номеру ползунка (1 — «Угол 1», 2 — «Угол 2»).

        Оба угла принадлежат тому, кто играет: у каждого игрока свой угол
        для синусов/косинусов и свой угол для тангенсов/котангенсов.
        По сети соперник присылает нам только координаты выстрела, так
        что его углы на нашем экране не появляются вовсе.
        """
        if slot == 1:
            self.set_angle1(v, exact)
        else:
            self.set_angle2(v, exact)

    def on_slider(self, which):
        """Ползунок изменился -> обновляем углы и точки P1/P2."""
        if which == 1:
            self.s1 = self.sliders[0].value
        else:
            self.s2 = self.sliders[1].value
        self.update_angles()
        # По сети углы НЕ отправляются: у соперника своя пара углов, и
        # его значения не должны двигать наш прицел. Сопернику мы тоже
        # шлём только точку выстрела.

    def update_angles(self):
        a1, a2 = math.radians(self.s1), math.radians(self.s2)
        c1, s1 = math.cos(a1), math.sin(a1)
        c2, s2 = math.cos(a2), math.sin(a2)
        tg2 = s2 / c2 if abs(c2) > 1e-9 else None
        ctg2 = c2 / s2 if abs(s2) > 1e-9 else None
        self.state['P1'] = (c1, clamp(tg2 * c1, -1.0, 1.0)) \
            if tg2 is not None else None
        self.state['P2'] = (clamp(ctg2 * s1, -1.0, 1.0), s1) \
            if ctg2 is not None else None
        return c1, s1, c2, s2, tg2, ctg2

    @staticmethod
    def nearest_angle(cands, ref):
        return min(cands, key=lambda a: abs((a - ref + 180) % 360 - 180))

    @staticmethod
    def sin_angles(v):
        """Все углы в [0, 360) с sin = v."""
        a = math.degrees(math.asin(clamp(v, -1.0, 1.0)))
        return sorted({a % 360, (180 - a) % 360, (180 + a) % 360,
                       (360 - a) % 360})

    @staticmethod
    def cos_angles(v):
        """Все углы в [0, 360) с cos = v."""
        b = math.degrees(math.acos(clamp(v, -1.0, 1.0)))
        return sorted({b % 360, (-b) % 360, (180 + b) % 360, (180 - b) % 360})

    def sin_txt(self):
        return '%.2f' % math.sin(math.radians(self.s1))

    def cos_txt(self):
        return '%.2f' % math.cos(math.radians(self.s1))

    def tg_txt(self):
        a = math.radians(self.s2)
        c = math.cos(a)
        return '%.2f' % (math.sin(a) / c) if abs(c) > 1e-9 else '—'

    def ctg_txt(self):
        a = math.radians(self.s2)
        s = math.sin(a)
        return '%.2f' % (math.cos(a) / s) if abs(s) > 1e-9 else '—'

    @staticmethod
    def parse_num(txt):
        try:
            return float(txt.replace(',', '.').strip())
        except ValueError:
            return None

    def submit_sin(self, txt):
        v = self.parse_num(txt)
        if v is None or abs(v) > 1:
            return self.sin_txt()
        self.set_angle_slot(1, self.nearest_angle(self.sin_angles(v),
                                                  self.s1), True)
        return self.sin_txt()

    def submit_cos(self, txt):
        v = self.parse_num(txt)
        if v is None or abs(v) > 1:
            return self.cos_txt()
        self.set_angle_slot(1, self.nearest_angle(self.cos_angles(v),
                                                  self.s1), True)
        return self.cos_txt()

    def submit_tg(self, txt):
        v = self.parse_num(txt)
        if v is None:
            return self.tg_txt()
        base = math.degrees(math.atan(v)) % 360
        self.set_angle_slot(2, self.nearest_angle([base, (base + 180) % 360],
                                               self.s2), True)
        return self.tg_txt()

    def submit_ctg(self, txt):
        v = self.parse_num(txt)
        if v is None:
            return self.ctg_txt()
        if abs(v) < 1e-12:
            self.set_angle_slot(2, self.nearest_angle([90.0, 270.0], self.s2))
        else:
            base = math.degrees(math.atan(1.0 / v)) % 360
            self.set_angle_slot(2, self.nearest_angle(
                [base, (base + 180) % 360], self.s2), True)
        return self.ctg_txt()

    # =========================================================
    #  СТРОЙКА
    # =========================================================
    def build_fld(self):
        """Поле, на котором сейчас идёт стройка."""
        if self.car_mode():
            # расстановка одна: свои машинки ставим на поле СОПЕРНИКА
            return (self.car_foe_fld()
                    if self.game['phase'] == 'place' else None)
        if self.game['phase'] == 'place1':
            return self.FL
        if self.game['phase'] == 'place2':
            return self.FR
        return None

    def target_fld(self):
        """Поле, по которому стреляет текущий игрок."""
        if self.game['mode'] == 'net':
            # по сети всегда стреляем в флот соперника (FR)
            return self.FR
        if self.game['mode'] == 'ai' or self.game['turn'] == 'player1':
            return self.FR
        return self.FL

    def active_side(self):
        """Поле с активным прицелом (или None)."""
        if self.car_mode():
            # в новом режиме прицела нет: ход делается кнопкой
            return None
        if self.game['phase'] != 'battle' or self.game.get('awaiting_tap'):
            return None
        if self.game['mode'] == 'ai':
            return 'R'
        if self.game['mode'] == 'net':
            # прицел живой только в свой ход и всегда на сопернике
            mine = self._net_my_turn()
            return 'R' if self.game['turn'] == mine else None
        return 'R' if self.game['turn'] == 'player1' else 'L'

    def cur_type(self):
        if self.car_mode():
            fld = self.build_fld()
            return self.car_kind(fld) if fld is not None else 'car'
        return 'plane' if self.mode['name'] == 'planes' else 'ship'

    def place_size(self, utype):
        """Длина, с которой ставим фигуру (в новом режиме — по виду)."""
        if self.car_mode():
            return 1 if utype == 'car' else \
                min(self.unit_state['size'], CAR_MAX_LEN)
        return min(self.unit_state['size'], MAX_SIZE[utype])

    def can_place(self, fld, utype, pts, ignore=None):
        """Можно ли поставить фигуру: есть место и хватает фигур флота."""
        if self.car_mode():
            return (self.car_remaining(fld)[utype].get(len(pts), 0) > 0 and
                    self.car_points_ok(pts, utype, fld['units'], ignore))
        return (self.remaining(fld['units'])[utype].get(len(pts), 0) > 0 and
                self.points_ok(pts, utype, fld['units'], ignore))

    def on_rotate(self, step=1):
        """Кнопка «Поворот»: в новом режиме — свои правила."""
        if self.car_mode():
            self.car_rotate(step)
        else:
            self.rotate(step)

    def unit_color(self, un):
        if self.car_mode() and self.unit_state.get('sel_cars'):
            if un in self.unit_state['sel_cars']:
                return GOLD
            return self.unit_color_plain(un)
        if un is self.unit_state['selected']:
            return GOLD
        if self.is_sunk(un):
            return RED
        return NAVY if un['type'] == 'ship' else TEAL

    def unit_color_plain(self, un):
        """Обычный цвет фигуры (в новом режиме — свой)."""
        if self.is_sunk(un):
            return RED
        if un['type'] == 'ship':
            return NAVY
        if un['type'] == 'plane':
            return TEAL
        if un['type'] == 'wall':
            return (25, 25, 30)
        return (30, 90, 210)

    def select(self, un):
        self.unit_state['selected'] = un
        if un is not None and self.tutorial['active'] and \
                self.tutorial['waiting'] == 'select':
            self.tut_next()

    def deselect(self):
        self.unit_state['selected'] = None

    def place_unit(self, fld, pts, dir_idx, size, utype, visible=True):
        fld['units'].append({'type': utype, 'pts': pts, 'dir': dir_idx,
                             'size': size, 'hits': set(), 'fld': fld,
                             'visible': visible})
        if self.tutorial['active'] and self.tutorial['waiting'] == 'place' \
                and fld is self.FL and size == 2:
            self.tut_next()

    def remove_unit(self, un):
        fld = un['fld']
        if self.unit_state['selected'] is un:
            self.unit_state['selected'] = None
        if un in fld['units']:
            fld['units'].remove(un)

    def rotate(self, step):
        un = self.unit_state['selected']
        if un is None:
            self.unit_state['dir_idx'] = \
                (self.unit_state['dir_idx'] + step) % 8
        else:
            x0, y0 = un['pts'][0]
            new_dir = (un['dir'] + step) % 8
            new_pts = self.unit_points(x0, y0, un['size'], new_dir)
            if self.points_ok(new_pts, un['type'], un['fld']['units'],
                              ignore=un):
                un['pts'] = new_pts
                un['dir'] = new_dir
        if self.tutorial['active'] and self.tutorial['waiting'] == 'rotate':
            self.tut_next()

    def ghost_pts(self):
        """Призрак юнита, который поставится по последней точке касания."""
        fld = self.build_fld()
        if fld is None or self.mode['name'] not in ('ships', 'planes') or \
                self.unit_state['last'] is None:
            return None, False
        gx, gy = self.unit_state['last']
        utype = self.cur_type()
        size = min(self.unit_state['size'], MAX_SIZE[utype])
        rem = self.remaining(fld['units'])[utype].get(size, 0)
        pts = self.unit_points(gx, gy, size, self.unit_state['dir_idx'])
        ok = self.points_ok(pts, utype, fld['units']) and rem > 0
        return pts, ok

    def status_line(self):
        if self.mode['name'] not in ('ships', 'planes'):
            return ''
        utype = self.cur_type()
        size = min(self.unit_state['size'], MAX_SIZE[utype])
        fld = self.build_fld()
        rem = self.remaining(fld['units'])[utype].get(size, 0) if fld else 0
        dx, dy = DIRECTIONS[self.unit_state['dir_idx']]
        deg = int(math.degrees(math.atan2(dy, dx)) % 360)
        return 'размер %d (ост. %d), %d°' % (size, rem, deg)

    # =========================================================
    #  ИИ
    # =========================================================
    def enemy_place(self):
        fsh, fpl = self.fleets()
        for utype, fleet in (('ship', fsh), ('plane', fpl)):
            for size in sorted(fleet, reverse=True):
                for _ in range(fleet[size]):
                    for _try in range(600):
                        x0 = random.randint(-10, 10) / 10
                        y0 = random.randint(-10, 10) / 10
                        d = random.randrange(8)
                        pts = self.unit_points(round(x0, 2), round(y0, 2),
                                               size, d)
                        if self.points_ok(pts, utype, self.FR['units']):
                            self.place_unit(self.FR, pts, d, size, utype,
                                            visible=False)
                            break

    def enemy_pick_cell(self):
        diff = self.settings['difficulty']
        while self.enemy_ai['hunt']:
            p = self.enemy_ai['hunt'].pop(0)
            if p not in self.enemy_ai['tried']:
                return p
        untried = [c for c in SQ_CELLS if c not in self.enemy_ai['tried']]
        if diff != 'Низкий':
            cb = [c for c in untried
                  if (round(c[0] / GRID) + round(c[1] / GRID)) % 2 == 0]
            if cb:
                untried = cb
        return random.choice(untried) if untried else None

    def enemy_turn(self):
        cell = self.enemy_pick_cell()
        if cell is None:
            return
        self.enemy_ai['tried'].add(cell)
        self.game['enemy_moves'] += 1
        result = self.fire_at(self.FL, cell[0], cell[1])
        diff = self.settings['difficulty']
        if result in ('hit', 'sunk') and diff != 'Низкий':
            self.enemy_ai['thits'].append(cell)
            for dx, dy in ((GRID, 0), (-GRID, 0), (0, GRID), (0, -GRID)):
                q = (round(cell[0] + dx, 2), round(cell[1] + dy, 2))
                if q in SQ_CELLS and q not in self.enemy_ai['tried']:
                    self.enemy_ai['hunt'].append(q)
            if diff == 'Высокий' and len(self.enemy_ai['thits']) >= 2:
                dx = round(self.enemy_ai['thits'][-1][0] -
                           self.enemy_ai['thits'][-2][0], 2)
                dy = round(self.enemy_ai['thits'][-1][1] -
                           self.enemy_ai['thits'][-2][1], 2)
                q = (round(cell[0] + dx, 2), round(cell[1] + dy, 2))
                if q in SQ_CELLS and q not in self.enemy_ai['tried']:
                    self.enemy_ai['hunt'].insert(0, q)
        if result == 'sunk':
            self.enemy_ai['thits'] = []
        txt = {'hit': 'ПОПАДАНИЕ!', 'sunk': 'ПОТОПЛЕН ВАШ ЮНИТ!',
               'miss': 'мимо'}[result]
        self.set_msg('Противник стреляет (%.1f, %.1f) — %s'
                     % (cell[0], cell[1], txt),
                     DKRED if result != 'miss' else BLACK)
        self.after(700, lambda: self.enemy_continue(cell, result))

    def enemy_continue(self, cell, result):
        if self.all_sunk(self.FL['units']):
            self.game['phase'] = 'over'
            self.set_msg('ПРОТИВНИК ПОБЕДИЛ. Все ваши юниты потоплены.',
                         DKRED)
            self.show_victory('Победил противник (ИИ)!')
            return
        if result in ('hit', 'sunk'):
            # ПРАВИЛО 6 (для ИИ): попадание -> игрок пропускает ход
            self.set_msg('Противник попал (%.1f, %.1f) — вы пропускаете '
                         'ход!' % (cell[0], cell[1]), DKRED)
            self.after(700, self.enemy_turn)

    # =========================================================
    #  ХОД ИГРЫ
    # =========================================================
    def stat_shot(self, hit):
        """Записать выстрел игрока в статистику."""
        self.stat_add('hits' if hit else 'misses')

    def make_move(self):
        if self.tutorial['active']:
            if self.game['phase'] == 'battle':
                self.tutorial_fire()
            return
        if self.game['mode'] == 'net':
            self._net_fire()
            return
        if self.game['phase'] != 'battle':
            self.set_msg('Сначала завершите расстановку юнитов!')
            return
        if self.game['mode'] == 'ai' and self.game['turn'] != 'player1':
            return

        P = self.state['P1'] if self.shot_sel['p'] == 'P1' else self.state['P2']
        if P is None:
            self.set_msg('точка %s не определена' % self.shot_sel['p'])
            return

        target = self.target_fld()
        shooter = 'Вы' if self.game['mode'] == 'ai' else \
            ('Игрок 1' if self.game['turn'] == 'player1' else 'Игрок 2')

        if abs(P[0]) > 1 or abs(P[1]) > 1:
            result = 'miss'
            res_txt = 'МИМО (вне квадрата)'
            target['misses'].append((round(P[0], 3), round(P[1], 3)))
        else:
            result = self.fire_at(target, P[0], P[1])
            res_txt = {'hit': 'ПОПАДАНИЕ!', 'sunk': 'ПОТОПЛЕН!',
                       'miss': 'МИМО'}[result]

        self.game['my_moves'] += 1
        self.stat_shot(result != 'miss')        # попадание или промах
        self.stat_add('moves')                  # ход игрока

        # подсказка: 15 промахов подряд -> раскрыть одну вражескую клетку
        if self.settings['hints']:
            key = 'player1' if (self.game['mode'] == 'ai' or
                                self.game['turn'] == 'player1') else 'player2'
            if result == 'miss':
                self.game['streak'][key] += 1
                if self.game['streak'][key] >= 15:
                    self.game['streak'][key] = 0
                    if self.reveal_hint(target):
                        res_txt += ' подсказка!'
            else:
                self.game['streak'][key] = 0
        self.game['last'] = res_txt

        if self.all_sunk(target['units']):
            self.game['phase'] = 'over'
            if self.game['mode'] == 'ai':
                self.set_msg('ПОБЕДА! Флот противника уничтожен за %d ходов!'
                             % self.game['my_moves'], DGREEN)
                self.show_victory('Победил Игрок 1!')
            else:
                self.set_msg('%s ПОБЕДИЛ! Все юниты соперника потоплены.'
                             % shooter.upper(), DGREEN)
                self.show_victory('Победил %s!' % shooter)
            return

        extra_turn = result in ('hit', 'sunk')

        if self.game['mode'] == 'ai':
            if extra_turn:
                self.set_msg('%s Противник пропускает ход — стреляйте ещё '
                             'раз!' % res_txt, DGREEN)
            else:
                self.set_msg('Ваш ход (%s): %s  Теперь ход противника...'
                             % (self.shot_sel['p'], res_txt))
                self.game['turn'] = 'enemy'
                self.after(500, self.after_enemy)
        else:
            if extra_turn:
                self.set_msg('%s: %s Соперник пропускает ход — %s ходит '
                             'снова!' % (shooter, res_txt, shooter), DGREEN)
            else:
                self.game['turn'] = 'player2' if self.game['turn'] == \
                    'player1' else 'player1'
                self.game['awaiting_tap'] = True
                n = '2' if self.game['turn'] == 'player2' else '1'
                self.set_msg('Игрок %s коснитесь экрана' % n, NAVY)
        self.update_angles()

    def after_enemy(self):
        self.enemy_turn()
        self.after(60, self.back_to_player)

    def back_to_player(self):
        if self.game['phase'] == 'battle':
            self.game['turn'] = 'player1'
            self.set_msg('ВАШ ХОД (%s). Последний выстрел: %s'
                         % (self.shot_sel['p'], self.game['last']), DGREEN)

    def reveal_hint(self, fld):
        cands = [p for un in fld['units'] for p in un['pts']
                 if p not in un['hits']]
        if cands:
            fld['hints'].add(random.choice(cands))
            self.stat_add('hints')
            return True
        return False

    def advance(self):
        """Кнопка 'Начать бой' / 'Готово'."""
        if self.car_mode():
            self.car_advance()
            return
        if self.tutorial['active'] and self.game['phase'] == 'place1':
            if not self.FL['units']:
                self.set_msg('Сначала поставьте корабль!', DKRED)
                return
            self.place_unit(self.FR, [(0.3, 0.2), (0.4, 0.2)], 0, 2, 'ship',
                            visible=False)
            self.game['phase'] = 'battle'
            self.game['turn'] = 'player1'
            self.btn_start.label = 'Бой идёт'
            self.update_angles()
            if self.tutorial['waiting'] == 'start':
                self.tut_next()
            return
        if self.game['mode'] == 'net' and self.game['phase'] == 'place1':
            self.net_send_ready()
            return
        if self.game['phase'] == 'place1':
            if not self.FL['units']:
                self.set_msg('Игрок 1: постройте хотя бы один юнит!', DKRED)
                return
            if self.game['mode'] == 'ai':
                self.enemy_place()
                self.game['phase'] = 'battle'
                self.game['turn'] = 'player1'
                self.btn_start.label = 'Бой идёт'
                self.set_msg('ВАШ ХОД: выберите P1 или P2, наведите прицел '
                             'и нажмите "Совершить ход"', DGREEN)
            else:
                self.game['phase'] = 'place2'
                self.btn_start.label = 'Готово (Игрок 2)'
                self.set_msg('Игрок 2 расставляет юниты на ПРАВОМ поле. '
                             'Поле игрока 1 скрыто.', NAVY)
        elif self.game['phase'] == 'place2':
            if not self.FR['units']:
                self.set_msg('Игрок 2: постройте хотя бы один юнит!', DKRED)
                return
            self.game['phase'] = 'battle'
            self.game['turn'] = 'player1'
            self.btn_start.label = 'Бой идёт'
            self.set_msg('ХОД ИГРОКА 1 (прицел на правом поле)', DGREEN)
        else:
            return
        self.deselect()
        self.unit_state['last'] = None
        self.update_angles()

    def reset_game(self):
        for fld in (self.FL, self.FR):
            fld['units'].clear()
            fld['misses'].clear()
            fld['hints'].clear()
        self.enemy_ai['tried'].clear()
        self.enemy_ai['hunt'].clear()
        self.enemy_ai['thits'].clear()
        phase = 'place' if self.car_mode() else 'place1'
        turn = 'player1'
        if self.car_mode() and self.play_mode() == 'ai':
            turn = getattr(self, 'car_human', 'player1')
        self.game.update(phase=phase, turn=turn, my_moves=0,
                         enemy_moves=0, last='—', awaiting_tap=False,
                         stats_saved=False,
                         streak={'player1': 0, 'player2': 0})
        self.unit_state.update(selected=None, last=None, sel_cars=[],
                               car_kind_btn='car')
        if self.car_mode():
            # в новом режиме расстановка одна: свои машинки на поле
            # соперника, дальше бой
            self.btn_start.label = 'Готово'
        elif self.game['mode'] == 'ai':
            self.btn_start.label = 'Начать бой'
        elif self.game['mode'] == 'net':
            self.btn_start.label = 'Готово'
        else:
            self.btn_start.label = 'Готово (Игрок 1)'
        self.timers.clear()
        # reset_angles знает про сеть: по сети сбрасывается только свой угол,
        # иначе угол соперника уехал бы у нас без его ведома
        self.reset_angles()
        self.update_angles()

    # =========================================================
    #  ТУТОРИАЛ
    # =========================================================
    TUT_STEPS = [
        {'key': 'intro', 'wait': None,
         'text': 'ДОБРО ПОЖАЛОВАТЬ В ТУТОРИАЛ!\n'
                 'Научимся играть за пару минут.\nНажмите «Далее»'},
        {'key': 'zones', 'wait': None, 'zones': True,
         'text': 'Синяя окружность — это ОКЕАН: в нём могут быть '
                 'ТОЛЬКО КОРАБЛИ.\nУголки чёрного квадрата — ВОЗДУХ: '
                 'там ТОЛЬКО САМОЛЁТЫ.\nСегодня тренируемся с кораблями.'},
        {'key': 'mode', 'wait': None, 'hl': 'mode',
         'text': 'Уже выбран режим «Корабли» и размер 2.\n'
                 'Нажмите «Далее»'},
        {'key': 'place', 'wait': 'place', 'hl': 'boardL',
         'text': 'ПОСТАВЬТЕ КОРАБЛЬ: коснитесь точки ВНУТРИ окружности '
                 'на левом поле.\nПолупрозрачный «призрак» показывает, '
                 'где встанет корабль.'},
        {'key': 'select', 'wait': 'select', 'hl': 'boardL',
         'text': 'Отлично! Теперь ВЫБЕРИТЕ корабль — коснитесь его.\n'
                 'Он подсветится золотым.'},
        {'key': 'rotate', 'wait': 'rotate', 'hl': 'rotate',
         'text': 'Теперь РАЗВЕРНИТЕ корабль:\nнажмите «Поворот» '
                 '(на ПК — клавиша R или колесо мыши).'},
        {'key': 'start', 'wait': 'start', 'hl': 'start',
         'text': 'Корабль готов! Нажмите «Начать бой».\n'
                 'У противника — один такой же 2-точечный корабль.'},
        {'key': 'aim', 'wait': None,
         'text': 'ПРИЦЕЛИВАНИЕ. Попробуйте:\n'
                 '• тянуть пальцем по полю (кнопка «Прицел: 1 / 2» '
                 'выбирает угол)\n'
                 '• двигать ползунки «Угол 1/2» или кнопки −/+\n'
                 '• переключать «Огонь P1/P2»\n'
                 'Когда наиграетесь — «Далее»'},
        {'key': 'fire1', 'wait': 'fire', 'hl': 'fire',
         'text': 'ТОЧНЫЙ ВЫСТРЕЛ. Выберите огонь P2 и введите:\n'
                 'sin1 = 0.2  и  ctg2 = 1.5\n'
                 '— P2 окажется точно в (0.3, 0.2). «Совершить ход»!'},
        {'key': 'fire2', 'wait': 'fire', 'hl': 'fire',
         'text': 'ПОПАДАНИЕ! Теперь добьём: введите ctg2 = 2.0\n'
                 '— P2 попадёт в (0.4, 0.2). «Совершить ход»!'},
    ]

    def tut_hl_rect(self, key):
        if key == 'boardL':
            return self.br['L']
        if key == 'start':
            return self.btn_start.rect if self.btn_start else None
        if key == 'fire':
            return self.btn_move.rect if self.btn_move else None
        if key == 'mode':
            if self.btn_mode_ships and self.btn_mode_planes:
                return self.btn_mode_ships.rect.union(
                    self.btn_mode_planes.rect)
            return None
        if key == 'rotate':
            return self.btn_rotate.rect if self.btn_rotate else None
        return None

    def tut_next(self):
        self.tutorial['step'] += 1
        if self.tutorial['step'] >= len(self.TUT_STEPS):
            return
        st = self.TUT_STEPS[self.tutorial['step']]
        self.tutorial['waiting'] = st.get('wait')
        self.tut_say(st['text'],
                     'Далее' if st.get('wait') is None else None)
        self.tut_hl = self.tut_hl_rect(st.get('hl'))
        self.tutorial['zones'] = bool(st.get('zones'))
        if st['key'] == 'mode':
            self.set_mode('ships')
            self.unit_state['size'] = 2

    def tut_say(self, text, next_label=None):
        self.tut_text = text
        self.btn_tut_next.visible = bool(next_label)
        if next_label:
            self.btn_tut_next.label = next_label

    def on_tut_next(self):
        if self.tutorial.get('end'):
            if self.tutorial['end'] == 'lose':
                self.tutorial['end'] = None
                self.start_tutorial()
            else:
                self.tut_exit()
            return
        if self.tutorial['waiting'] is None:
            self.tut_next()

    def tut_exit(self):
        self.tutorial.update(active=False, waiting=None, end=None,
                             zones=False)
        self.tut_text = ''
        self.tut_hl = None
        self.btn_tut_next.visible = False
        self.btn_tut_skip.visible = False
        self.timers.clear()
        self.show_screen('menu')

    def start_tutorial(self):
        self.tutorial.update(active=True, step=-1, waiting=None, end=None,
                             zones=False)
        self.game['mode'] = 'ai'
        self.settings['difficulty'] = 'Низкий'
        self.start_trig_ui()
        self.reset_game()
        self.show_screen('game')
        self.btn_tut_skip.visible = True
        self.set_msg('ТУТОРИАЛ — следуйте подсказкам', DKORANGE)
        self.tut_next()

    def tutorial_enemy_fire(self):
        """Скриптованный враг: бьёт по первой неподбитой точке игрока."""
        for un in self.FL['units']:
            for p in un['pts']:
                if p not in un['hits']:
                    self.fire_at(self.FL, p[0], p[1])
                    return p
        return None

    def tutorial_fire(self):
        """Ход игрока в туториале (скриптованный бой)."""
        P = self.state['P1'] if self.shot_sel['p'] == 'P1' else self.state['P2']
        if P is None:
            self.set_msg('Точка не определена — поверните углы')
            return
        result = self.fire_at(self.FR, P[0], P[1])
        self.game['my_moves'] += 1
        if self.all_sunk(self.FR['units']):
            self.game['phase'] = 'over'
            self.tut_end(True)
            return
        if result == 'miss':
            self.set_msg('МИМО! Противник стреляет в ответ...', DKRED)
            self.after(600, self.tutorial_enemy_reply)
        else:
            self.set_msg('ПОПАДАНИЕ!' if result == 'hit' else 'ПОТОПЛЕН!',
                         DGREEN)
            if self.tutorial['waiting'] == 'fire':
                self.tut_next()

    def tutorial_enemy_reply(self):
        hp = self.tutorial_enemy_fire()
        if self.all_sunk(self.FL['units']):
            self.game['phase'] = 'over'
            self.tut_end(False)
            return
        self.set_msg('Противник попал в (%.1f, %.1f)! Ваша очередь — '
                     'следуйте подсказке.' % (hp[0], hp[1]), DKRED)
        self.tut_say('МИМО — враг попал по вашему кораблю!\n'
                     'Введите ТОЧНО: огонь P2, sin1 = 0.2, ctg2 = 1.5\n'
                     'и нажмите «Совершить ход».')

    def tut_end(self, win):
        self.tutorial['waiting'] = None
        self.tutorial['step'] = len(self.TUT_STEPS)
        self.tut_hl = None
        if win:
            self.tutorial['end'] = 'win'
            self.set_msg('ПОБЕДА в туториале!', DGREEN)
            self.tut_say('ПОБЕДА! Вражеский корабль потоплен.\n'
                         'ТУТОРИАЛ ПРОЙДЕН! Нажмите «Завершить».',
                         'Завершить')
        else:
            self.tutorial['end'] = 'lose'
            self.set_msg('Поражение в туториале.', DKRED)
            self.tut_say('ПОРАЖЕНИЕ... Но это была тренировка!\n'
                         '«Заново» — пройти ещё раз, «Завершить» — выйти.',
                         'Заново')

    # =========================================================
    #  ДЕЙСТВИЯ ЭКРАНОВ
    # =========================================================
    def start_trig_ui(self):
        """Интерфейс тригонометрического режима.

        Вызывается при каждом старте классической игры: после нового
        режима вид фигур оставался «cars», и все тригонометрические
        элементы (ползунки углов 1 и 2, поля sin/cos/tg/ctg, точка
        пересечения, кнопки режимов) оставались скрытыми — игра была
        неиграбельной.
        """
        self.set_mode('cars' if self.car_mode() else self.trig_mode())
        self.cars_widgets_apply()

    def trig_mode(self):
        """Вид фигур тригонометрического режима (по умолчанию корабли)."""
        name = getattr(self, 'last_trig_mode', None) or 'ships'
        return name if name in MODE_COLORS else 'ships'

    def choose_diff(self, diff):
        self.settings['difficulty'] = diff
        self.game['mode'] = 'ai'
        self.start_trig_ui()
        self.reset_game()
        self.show_screen('game')
        self.set_msg('Сложность: %s. Расставьте флот на ЛЕВОМ поле и '
                     'нажмите "Начать бой"' % diff, NAVY)

    def start_local(self):
        self.game['mode'] = 'local'
        self.start_trig_ui()
        self.reset_game()
        self.show_screen('game')
        self.set_msg('ЛОКАЛЬНАЯ ИГРА. Игрок 1 расставляет юниты на ЛЕВОМ '
                     'поле, затем — "Готово (Игрок 1)"', NAVY)

    def show_victory(self, text):
        """Экран победы и запись результата в статистику игрока.

        Раньше результат писался только в сетевых партиях, поэтому
        игры против ИИ и локальные в статистике не учитывались.
        """
        self.victory_title = text
        if not self.game.get('stats_saved'):
            self.game['stats_saved'] = True
            self._save_game_result()
        self.show_screen('victory')

    def _save_game_result(self):
        """Сохранить итог партии: победа/поражение и выстрелы."""
        if self.profile_db is None or not self.user_state['logged_in']:
            return
        won = str(self.victory_title or '').startswith('Победил') or \
            'победил!' in str(self.victory_title or '').lower() or \
            'прорвались' in str(self.victory_title or '').lower()
        if not won and 'вы' in str(self.victory_title or '').lower():
            won = True
        try:
            self.profile_db.record_game(self.user_state['user_id'], won,
                                        self.net_shots, self.net_hits)
        except Exception:                     # noqa: BLE001
            pass

    def set_mode(self, name):
        self.mode['name'] = name
        if name in MODE_COLORS:
            self.last_trig_mode = name
        if name == 'cars':
            # в новом режиме нет ни углов, ни кораблей с самолётами
            return
        if name == 'planes':
            self.unit_state['size'] = min(self.unit_state['size'],
                                          MAX_SIZE['plane'])
        if name == 'angles':
            self.unit_state['last'] = None
            self.deselect()
        for btn, mn in ((self.btn_mode_angles, 'angles'),
                        (self.btn_mode_ships, 'ships'),
                        (self.btn_mode_planes, 'planes')):
            if btn is not None:
                btn.active = (mn == name)

    def set_shot(self, p):
        self.shot_sel['p'] = p
        if self.btn_shot1:
            self.btn_shot1.active = (p == 'P1')
        if self.btn_shot2:
            self.btn_shot2.active = (p == 'P2')

    def set_aim_sel(self, n):
        self.aim_sel = n
        if self.btn_aim1:
            self.btn_aim1.active = (n == 1)
        if self.btn_aim2:
            self.btn_aim2.active = (n == 2)

    def set_size(self, s):
        self.unit_state['size'] = s
        for i, b in enumerate(self.size_buttons, start=1):
            b.active = (i == s)

    def delete_selected(self):
        un = self.unit_state['selected']
        if un is not None:
            self.remove_unit(un)

    def clear_field(self):
        fld = self.build_fld()
        if fld is None:
            return
        for un in fld['units'][:]:
            self.remove_unit(un)
        self.unit_state['last'] = None

    # =========================================================
    #  КАСАНИЯ ПО ПОЛЮ
    # =========================================================
    def board_touch(self, side, pos, phase, btn=1):
        dx, dy = self.to_data(side, pos)

        # локальная игра: экран ожидания — тап следующего игрока
        if self.game.get('awaiting_tap') and self.game['phase'] == 'battle':
            if phase == 'down':
                self.game['awaiting_tap'] = False
                nxt = 'ИГРОКА 1' if self.game['turn'] == 'player1' \
                    else 'ИГРОКА 2'
                sd = 'правом' if self.game['turn'] == 'player1' else 'левом'
                self.set_msg('ХОД %s (прицел на %s поле)' % (nxt, sd),
                             DGREEN)
                self.update_angles()
            return

        if self.game['phase'] == 'battle' and side == self.active_side():
            if phase == 'down':
                self.drag_side = side
                self.drag_btn = btn
            if self.drag_btn == 3 or self.aim_sel == 2:
                self.set_angle2(math.degrees(math.atan2(dy, dx)) % 360)
            else:
                self.set_angle1(math.degrees(math.atan2(dy, dx)) % 360)
            return

        if self.car_mode() and self.game['phase'] == 'battle':
            # в бою тап по полю: выбрать свою фигуру или поставить стену
            if phase != 'move':
                self.car_tap(side, dx, dy, btn)
            return

        fld = self.build_fld()
        if fld is None:
            return
        side_name = 'L' if fld is self.FL else 'R'
        kinds = ('ships', 'planes', 'cars')
        if side != side_name or self.mode['name'] not in kinds:
            return
        gx, gy = self.snap(dx), self.snap(dy)
        if phase == 'move':
            self.unit_state['last'] = (gx, gy)
            return
        hit = self.unit_at(fld['units'], dx, dy)
        utype = self.cur_type()
        if btn == 3:
            if hit is not None:
                self.remove_unit(hit)
            return
        if hit is not None:
            self.select(hit)
        else:
            self.deselect()
            size = self.place_size(utype)
            pts = self.unit_points(gx, gy, size, self.unit_state['dir_idx'])
            if self.can_place(fld, utype, pts):
                self.place_unit(fld, pts, self.unit_state['dir_idx'], size,
                                utype)
                if self.car_mode() and utype == 'car':
                    fld['units'][-1]['left'] = CAR_STEPS
                self.unit_state['last'] = (gx, gy)
                if self.car_mode():
                    self.cars_tutorial_hit(
                        'place' if utype == 'car' else 'wall')

    # =========================================================
    #  НОВЫЙ РЕЖИМ: МАШИНКИ И ПРЕПЯТСТВИЯ
    def car_side_of_fld(self, fld):
        """Чья сторона это поле: левое — машинки, правое — защита."""
        return 'player1' if fld is self.FL else 'player2'

    def car_tap(self, side, dx, dy, btn=1):
        """Тап по полю в новом режиме.

        Расстановка (фаза 'place'): ставим СВОИ машинки на поле
        СОПЕРНИКА — там, куда мы собираемся ехать.

        Бой: тап по своей фигуре выбирает её, тап по пустой клетке
        СВОЕГО поля ставит стену. Стены до боя ставить нельзя, за ход
        ставится ровно одна, и только в свой ход.
        """
        fld = self.FL if side == 'L' else self.FR
        hit = self.unit_at(fld['units'], dx, dy)
        placing = self.game['phase'] == 'place'
        mine = self.car_my_side()
        your_turn = (self.game['turn'] == mine if mine is not None else
                     self.game['turn'] == self.car_owner(hit)
                     if hit is not None else True)

        if hit is not None:
            if btn == 3 and not placing and self.car_owner(hit) == \
                    (mine or self.car_side_of_fld(fld)):
                self.remove_unit(hit)
                self.car_clear_sel()
                self.set_msg('Фигура убрана', NAVY)
                return
            if placing:
                self.select(hit)
                self.unit_state['sel_cars'] = [hit]
            else:
                self.car_select(hit)
            return

        self.car_clear_sel()
        gx, gy = self.snap(dx), self.snap(dy)

        # --- расстановка: только машинки, только на поле соперника
        if placing:
            if fld is not self.car_foe_fld():
                self.set_msg('Машинки ставятся на поле СОПЕРНИКА: '
                             'вот здесь — его сторона', DKRED)
                return
            pts = self.unit_points(gx, gy, 1, self.unit_state['dir_idx'])
            if not self.can_place(fld, 'car', pts):
                self.set_msg('Здесь машинка не встанет: нужно свободное '
                             'место ЗА пределами окружности, внутри '
                             'квадрата', DKRED)
                return
            self.place_unit(fld, pts, self.unit_state['dir_idx'], 1, 'car')
            fld['units'][-1]['left'] = CAR_STEPS
            self.unit_state['last'] = (gx, gy)
            self.cars_tutorial_hit('place')
            self.cars_after_change()
            return

        # --- бой: стена на своём поле, одна за ход
        if fld is not self.car_my_fld():
            self.set_msg('Стены строятся только на своём поле: тут мы '
                         'защищаем жёлтый круг', DKRED)
            return
        if not your_turn:
            self.set_msg('Стены ставятся в свой ход, и только одна за ход '
                         '(сейчас ход соперника)', DKRED)
            return
        size = self.place_size('wall')
        d = self.unit_state['dir_idx']
        pts = self.unit_points(gx, gy, size, d)
        if not self.can_place(fld, 'wall', pts):
            self.set_msg('Здесь стена не встанет: нужно свободное место '
                         'и длина 1–4, жёлтый круг трогать нельзя',
                         DKRED)
            return
        self.place_unit(fld, pts, d, size, 'wall')
        if self.net is not None and self.play_mode() == 'net':
            self.car_send_build(fld['units'][-1])
        self.game['last'] = 'Поставлено препятствие'
        self.game['my_moves'] += 1
        self.stat_add('moves')
        self.set_msg('Стена поставлена: за ход ставится одна стена, ход '
                     'переходит сопернику', DGREEN)
        self.cars_tutorial_hit('wall')
        self.cars_after_change()
        self.car_next_turn()

    def car_next_turn(self):
        """Ход закончен: переходим к другому игроку."""
        self.game['turn'] = ('player2' if self.game['turn'] == 'player1'
                             else 'player1')
        self.cars_turn_feedback()

    # =========================================================
    def car_advance(self):
        """«Готово» в новом режиме.

        Расстановка одна: свои машинки на поле соперника. Потом бою,
        в котором каждый игрок в свой ход либо двигает свою фигуру,
        либо ставит одну стену на своём поле.
        """
        if self.game['phase'] != 'place':
            return
        if not self.car_my_cars():
            self.set_msg('Поставьте хотя бы одну машинку на поле '
                         'соперника!', DKRED)
            return
        self.deselect()
        self.unit_state['size'] = 2
        mode = self.play_mode()
        if mode == 'local':
            if self.game['turn'] == 'player1':
                self.game['turn'] = 'player2'
                self.btn_start.label = 'Готово'
                if self.cars_tut_active():
                    # в туториале за второго игрока играет компьютер
                    self.car_auto_place(self.car_foe_fld(), 'car')
                    self.game['phase'] = 'battle'
                    self.btn_start.label = 'Бой идёт'
                    self.cars_begin()
                    return
                self.set_msg('Игрок 2: поставьте машинки на ЛЕВОМ поле '
                             'и нажмите «Готово» — они поедут вправо, '
                             'на территорию игрока 1', NAVY)
                return
            self.game['phase'] = 'battle'
            self.btn_start.label = 'Бой идёт'
            self.cars_begin()
            return
        if mode == 'ai':
            self.car_place_ai()
            self.game['phase'] = 'battle'
            self.btn_start.label = 'Бой идёт'
            self.cars_begin()
            return
        # по сети: отправляем свои машинки и ждём машинки соперника
        self.net_send_ready()

    def cars_begin(self):
        """Бой начался."""
        self.game['phase'] = 'battle'
        self.game['turn'] = 'player1'
        self.game['my_moves'] = 0
        self.game['enemy_moves'] = 0
        self.unit_state['size'] = 2
        self.deselect()
        self.cars_tutorial_hit('start')
        self.set_msg('БОЙ. В свой ход: двигаем свою машинку или стену '
                     'либо ставим одну стену на своём поле', DGREEN)
        self.cars_maybe_ai()

    def car_start(self, mode, human='player1'):
        """Запуск нового режима.

        mode: 'local' — оба за одним экраном, 'ai' — против машины,
        'net' — по сети. Ни в одном случае нет отдельной роли
        «нападающий» или «защитник»: каждый игрок и едет на чужое
        поле машинками, и строит стены на своём.
        human: за какого игрока играет человек против ИИ.
        """
        self.game['mode'] = CAR_MODE
        self.car_play = mode
        self.car_human = human
        self.unit_state['selected'] = None
        self.unit_state['size'] = 1
        self.set_mode('cars')
        self.cars_widgets_apply()
        self.FL['name'] = self.car_fld_name('player1')
        self.FR['name'] = self.car_fld_name('player2')
        self.reset_game()
        self.show_screen('game')
        who = self.car_now()
        side = 'ЛЕВОМ' if self.car_foe_fld() is self.FL else 'ПРАВОМ'
        self.set_msg('Расстановка машинок: %s, игрок %s ставит свои '
                     'машинки на %s поле — это поле СОПЕРНИКА. '
                     'Стены ставятся только в бою, в свой ход.'
                     % (side, who[-1], side), NAVY)

    def car_fld_name(self, player):
        """Подпись поля: в локальной игре — по игроку, иначе — '
        'ваше/поле соперника'."""
        if self.play_mode() == 'local':
            return 'ПОЛЕ ИГРОКА %s' % player[-1]
        if self.play_mode() == 'net':
            mine = self._net_my_turn()
        else:
            mine = getattr(self, 'car_human', 'player1')
        return 'ВАШЕ ПОЛЕ' if player == mine else 'ПОЛЕ СОПЕРНИКА'

    def car_ai_side(self):
        """Сторона компьютера: та, что не человек."""
        if self.play_mode() != 'ai':
            return None
        human = getattr(self, 'car_human', 'player1')
        return 'player2' if human == 'player1' else 'player1'

    def car_place_ai(self):
        """ИИ расставляет свои машинки сразу: ехать ему на наше поле."""
        ai = self.car_ai_side()
        self.car_auto_place(self.car_fld_of('player2' if ai == 'player1'
                                            else 'player1'), 'car')
        self.unit_state['selected'] = None

    def car_auto_place(self, fld, kind):
        """Расстановка фигур по полю. kind: 'car' или 'wall'.

        Ставим по порядку: сначала самые длинные препятствия — так стена
        получается ровнее и закрывает центр лучше.
        """
        rem = self.car_fleet_of(kind)
        grid = self.car_grid()
        for size in sorted(rem, reverse=True):
            for _ in range(max(0, rem[size])):
                if self.car_try_place(fld, kind, size, grid):
                    continue
                # длинное препятствие не влезло — ставим более короткое,
                # чтобы поле не осталось пустым
                for shorter in range(size - 1, 0, -1):
                    if self.car_try_place(fld, kind, shorter, grid):
                        break

    def car_try_place(self, fld, kind, size, grid):
        """Ищет свободное место для фигуры длиной size. -> bool"""
        for dir_idx in range(8):
            for gx in grid:
                for gy in grid:
                    pts = self.unit_points(gx, gy, size, dir_idx)
                    if not self.car_points_ok(pts, kind, fld['units']):
                        continue
                    self.place_unit(fld, pts, dir_idx, size, kind)
                    if kind == 'car':
                        fld['units'][-1]['left'] = CAR_STEPS
                    return True
        return False

    def car_grid(self):
        """Координаты клеток поля — для расстановки машиной."""
        n = int(1 / GRID)
        return [round(i * GRID, 2) for i in range(-n, n + 1)]

    def car_mode(self):
        """Идёт ли новый режим (машинки против препятствий)."""
        return self.game['mode'] == CAR_MODE

    def play_mode(self):
        """Тип партии: 'ai', 'local' или 'net'.

        В новом режиме game['mode'] занят словом 'cars', поэтому
        вид игры хранится отдельно — иначе игра с ИИ выглядела бы
        как локальная, а по сети никто бы не ходил.
        """
        return self.car_play if self.car_mode() else self.game['mode']

    def car_kind(self, fld=None):
        """Что ставим на расстановке: только машинки.

        Стены до боя ставить нельзя — они строятся в своём ходу.
        """
        return 'car'

    def car_fld_of(self, player):
        """Поле игрока: левое — player1, правое — player2."""
        return self.FL if player == 'player1' else self.FR

    def car_now(self):
        """Чей сейчас ход (и чья идёт расстановка).

        В локальной игре ход переходит между игроками, по сети и против
        ИИ ход всегда за тем, за кем этот экран.
        """
        mode = self.play_mode()
        if mode == 'local':
            return self.game.get('turn', 'player1')
        if mode == 'net':
            return self._net_my_turn()
        return getattr(self, 'car_human', 'player1')

    def car_my_fld(self):
        """Моё поле: тут стоят МОИ стены и ездят чужие машинки."""
        return self.car_fld_of(self.car_now())

    def car_foe_fld(self):
        """Поле соперника: тут стоят ЕГО стены и ездят МОИ машинки."""
        mine = self.car_my_fld()
        return self.FR if mine is self.FL else self.FL

    def car_owner(self, un):
        """Чья это фигура.

        Стены принадлежат тому, чьё поле, машинки — тому, чьё поле
        ИМЕННО ОНИ АТАКУЮТ, то есть сопернику владельца поля.
        """
        who = self.car_side_of_fld(un['fld'])
        if un['type'] == 'wall':
            return who
        return 'player2' if who == 'player1' else 'player1'

    def car_owner_cars(self, who):
        """Машинки игрока: они стоят на поле его соперника."""
        fld = self.car_fld_of('player2' if who == 'player1' else 'player1')
        return [u for u in fld['units']
                if u['type'] == 'car' and u.get('left', 1) > 0]

    def car_my_cars(self):
        """Мои машинки — они на поле соперника."""
        return [u for u in self.car_foe_fld()['units'] if u['type'] == 'car']

    def car_my_walls(self):
        """Мои стены — они на моём поле."""
        return [u for u in self.car_my_fld()['units'] if u['type'] == 'wall']

    def car_units(self, kind):
        """Флот указанного вида со всех полей (у каждого свой)."""
        out = []
        for fld in (self.FL, self.FR):
            out += [un for un in fld['units'] if un['type'] == kind]
        return out

    def car_fleet_of(self, kind):
        return dict(FLEET_CARS) if kind == 'car' else dict(FLEET_WALLS)

    def car_remaining(self, fld):
        """Сколько фигур каждого вида ещё надо поставить на это поле.

        Своё место у каждого поля: стены можно ставить и на поле
        машинок (правило «стены ставятся прямо во время игры»), поэтому
        считаем оба вида раздельно.
        """
        rem = {'car': dict(FLEET_CARS), 'wall': dict(FLEET_WALLS)}
        for un in fld['units']:
            kind = un['type']
            if kind in rem:
                rem[kind][un['size']] = rem[kind].get(un['size'], 0) - 1
        return rem

    def car_panel_kinds(self, fld):
        """Какие виды фигур показывать в панели этого поля."""
        kinds = set(un['type'] for un in fld['units'])
        if self.build_fld() is fld:
            kinds.add('car')
        if self.game['phase'] == 'battle':
            kinds.add('wall')
        return [k for k in ('car', 'wall') if k in kinds] or ['car']

    def car_can_build(self, fld):
        """Можно ли строить стену на этом поле.

        Стены строятся только на СВОЁМ поле: там, где мы защищаем
        жёлтый круг. На поле соперника мы ставим машинки (и только до
        начала боя).
        """
        return fld is self.car_my_fld()

    @staticmethod
    def car_in_square(p):
        """Точка внутри чёрного квадрата [-1; 1]² — поля боя."""
        return -1 - 1e-9 <= p[0] <= 1 + 1e-9 and -1 - 1e-9 <= p[1] <= 1 + 1e-9

    @staticmethod
    def car_dist(p):
        return (p[0] ** 2 + p[1] ** 2) ** 0.5

    def car_points_ok(self, pts, kind, units, ignore=None):
        """Можно ли поставить фигуру.

        Машинки — за пределами окружности, но внутри квадрата.
        Препятствия — только ВНУТРИ единичной окружности и не на
        самом жёлтом круге: круг защитник обязан оставить
        открытым, иначе игра теряет смысл.
        """
        for p in pts:
            if not self.car_in_square(p):
                return False
            d = self.car_dist(p)
            if kind == 'car' and d < 1 - 1e-9:
                return False
            if kind == 'wall':
                if d > 1 + 1e-9:
                    return False
                if d < YELLOW_R - 1e-9:
                    return False
        return self.no_touch(pts, units, ignore)

    def car_rotate(self, step=1):
        """Поворачивает выбранную фигуру на 45°×step.

        Препятствие перебираем несколько способов, потому что клетки
        должны лежать строго на сетке, а после поворота на 45° половина
        вариантов сдвигается на полклетки:

          1) вокруг своего центра — стена остаётся на месте;
          2) от каждого из двух концов в новую сторону и в противоположную;
          3) то же, но со сдвигом на клетку в сторону.

        Первое подходящее место и берём, иначе честно говорим, что здесь
        не поместится. Раньше пробовалось только первое, поэтому стены
        казались невращаемыми.
        """
        un = self.unit_state['selected']
        if un is None:
            self.unit_state['dir_idx'] = \
                (self.unit_state['dir_idx'] + step) % 8
            return
        new_dir = (un['dir'] + step) % 8
        if un['type'] == 'car':
            # машинке не нужны клетки под курс: меняем только направление
            un['dir'] = new_dir
            self.cars_after_change()
            self.cars_tutorial_hit('rotate')
            return
        size, units = un['size'], un['fld']['units']
        cx = round(sum(p[0] for p in un['pts']) / len(un['pts']), 2)
        cy = round(sum(p[1] for p in un['pts']) / len(un['pts']), 2)
        cands = []
        for d in (new_dir, (new_dir + 4) % 8):
            pts = self.car_line_points(cx, cy, size, d)
            if pts:
                cands.append((d, pts))
            for x0, y0 in (un['pts'][0], un['pts'][-1]):
                cands.append((d, self.unit_points(x0, y0, size, d)))
                for dx, dy in DIRECTIONS:
                    cands.append((d, self.unit_points(
                        round(x0 + dx * GRID, 2), round(y0 + dy * GRID, 2),
                        size, d)))
        for d, pts in cands:
            if self.car_points_ok(pts, 'wall', units, ignore=un):
                un['pts'] = pts
                # направление обязано совпадать с клетками: по нему
                # стена потом сдвигается на клетку
                un['dir'] = d
                self.cars_after_change()
                self.cars_tutorial_hit('rotate')
                return
        self.set_msg('Здесь стена не поместится в другую сторону: '
                     'не хватает места внутри круга', DKRED)

    @staticmethod
    def car_line_points(cx, cy, size, dir_idx):
        """Клетки препятствия вдоль направления, центрированные по (cx, cy).

        Возвращает None, если центр не попадает на сетку клеток: ставить
        стену с половинным сдвигом нельзя, всё должно быть в клетках.
        """
        k = (size - 1) / 2.0
        x0 = round(cx - k * DIRECTIONS[dir_idx][0] * GRID, 2)
        y0 = round(cy - k * DIRECTIONS[dir_idx][1] * GRID, 2)
        if (abs(round(x0 / GRID) - x0 / GRID) > 1e-6 or
                abs(round(y0 / GRID) - y0 / GRID) > 1e-6):
            return None
        return [(round(x0 + j * DIRECTIONS[dir_idx][0] * GRID, 2),
                 round(y0 + j * DIRECTIONS[dir_idx][1] * GRID, 2))
                for j in range(size)]


    def car_reverse(self, un):
        """Разворот на 180° — так машинка отскакивает от препятствия."""
        un.pop('anim', None)
        un['dir'] = (un['dir'] + 4) % 8
        if un['type'] == 'wall':
            un['pts'] = self.unit_points(un['pts'][0][0], un['pts'][0][1],
                                         un['size'], un['dir'])

    @staticmethod
    def car_delta(dx, dy):
        """Смещение на одну клетку по направлению DIRECTIONS.

        Диагональ — это тоже клетка: по обеим осям сразу на
        GRID, ровно как у диагональных кораблей и самолётов.
        """
        return dx * GRID, dy * GRID

    def car_step_vector(self, un):
        """Куда поедет фигура за один ход (одна клетка)."""
        sx, sy = self.car_delta(*DIRECTIONS[un['dir']])
        return (round(un['pts'][0][0] + sx, 3),
                round(un['pts'][0][1] + sy, 3))

    def car_cell_taken(self, p, ignore=None):
        """Кто стоит в клетке: препятствие, машинка или никто."""
        wall = car = None
        for fld in (self.FL, self.FR):
            for un in fld['units']:
                if un is ignore or not un['pts']:
                    continue
                for q in un['pts']:
                    if max(abs(p[0] - q[0]), abs(p[1] - q[1])) <= GRID * 0.9:
                        if un['type'] == 'wall':
                            wall = (un, q)
                        else:
                            car = (un, q)
        if wall:
            return 'wall', wall
        if car:
            return 'car', car
        return None, None

    def car_hit_yellow(self, p):
        """Коснулась ли машинка жёлтого круга."""
        return self.car_dist(p) <= YELLOW_R + 1e-9

    def car_break_wall(self, un, cell):
        """Препятствие сносит одну клетку: таран разрушает стену."""
        if cell in un['pts']:
            un['pts'].remove(cell)
        if not un['pts']:
            self.remove_unit(un)
        elif len(un['pts']) == 1:
            un['size'] = 1

    def car_move_unit(self, un):
        """Ход одной фигуры на одну клетку. -> текст результата.

        Порядок проверок важен и одинаков на всех устройствах: иначе по
        сети стороны посчитают результат по-разному.
        """
        p = un['pts'][0]
        if un['type'] == 'wall':
            return self.car_move_wall(un)
        nxt = self.car_step_vector(un)
        if not self.car_in_square(nxt):
            self.car_reverse(un)
            return 'Машинка упёрлась в границу поля — разворот'
        kind, hit = self.car_cell_taken(nxt, ignore=un)
        if kind == 'wall':
            self.car_reverse(un)
            # Столкновение раскрывает обе стороны: соперник видит,
            # где стоит стена, а владелец стены видит машинку.
            # До этого момента чужие фигуры не видны.
            hit[0]['revealed'] = True
            un['revealed'] = True
            self.car_break_wall(*hit)
            return 'Машинка врезалась в препятствие: разворот, стена слаба'
        if kind == 'car':
            self.car_reverse(un)
            return 'Машинка упёрлась в другую машинку — разворот'
        un['anim'] = ([tuple(un['pts'][0])], pygame.time.get_ticks())
        un['pts'] = [nxt]
        un['left'] = max(0, int(un.get('left', CAR_STEPS)) - 1)
        if self.car_hit_yellow(nxt):
            return 'МАШИНКА ДОШЛА ДО ЖЁЛТОГО КРУГА!'
        if un['left'] == 0:
            return 'Машинка израсходовала все ходы и снята с поля'
        return 'Машинка проехала на клетку'

    def car_move_wall(self, un):
        """Защитник двигает своё препятствие на клетку.

        Проверяем занятость по СВОЕМУ полю фигуры, а не по левому:
        стена может лежать на любом поле (защитник строит и на поле
        соперника, по сети поля вообще нумеруются по-разному), и с
        проверкой по FL соперник посчитал бы ход иначе.
        """
        nxt = self.car_step_vector(un)
        if not self.car_points_ok([nxt], 'wall', un['fld']['units'],
                                  ignore=un):
            return 'Препятствие туда не встанет'
        sx, sy = self.car_delta(*DIRECTIONS[un['dir']])
        un['anim'] = ([tuple(p) for p in un['pts']],
                      pygame.time.get_ticks())
        un['pts'] = [(round(p[0] + sx, 3), round(p[1] + sy, 3))
                     for p in un['pts']]
        return 'Препятствие сдвинуто на клетку'

    def car_turn_of(self):
        """Чей ход: 'player1' — машинки, 'player2' — защита."""
        return self.game.get('turn', 'player1')

    CAR_SELECT_MAX = 3         # выбрать можно не больше трёх машинок

    def car_selected(self):
        """Выбранные фигуры нового режима (список, до трёх машинок)."""
        out = [un for un in self.unit_state.get('sel_cars', [])
               if un.get('fld') is not None and
               un in un['fld']['units']]
        return out

    def car_select(self, un):
        """Выбирает или снимает выбор фигуры.

        Машинок четыре, а ходнуть можно максимум три: четвёртая не
        добавляется, о ней честно сообщаем.
        """
        if un is None:
            return
        sel = list(self.unit_state.get('sel_cars') or [])
        if un in sel:
            sel.remove(un)
            self.unit_state['sel_cars'] = sel
            self.unit_state['selected'] = sel[0] if sel else None
            return
        if un['type'] == 'car' and \
                len([u for u in sel if u['type'] == 'car']) >= \
                self.CAR_SELECT_MAX:
            self.set_msg('Выбрать можно только %d машинки из четырёх'
                         % self.CAR_SELECT_MAX, DKRED)
            return
        sel.append(un)
        self.unit_state['sel_cars'] = sel
        self.unit_state['selected'] = sel[0]
        self.set_msg('Выбрано фигур: %d. «Совершить ход» — двинуть '
                     'их на клетку' % len(sel), NAVY)

    def car_clear_sel(self):
        self.unit_state['sel_cars'] = []
        self.unit_state['selected'] = None

    def car_set_kind(self, kind):
        """Что сейчас ставим: машинки (только на расстановке) или стены."""
        self.unit_state['car_kind_btn'] = kind
        if kind == 'car' and self.game['phase'] != 'place':
            self.set_msg('Машинки ставятся только ДО боя, на поле '
                         'соперника. В бою строите стены.', NAVY)
        else:
            self.set_msg('Ставим: %s' % ('МАШИНКИ' if kind == 'car'
                                         else 'СТЕНЫ'), NAVY)

    def car_after_move(self, moved=None):
        """Проверки после хода: конец партии и передача хода.

        moved — фигуры, которыми ходили (все выбранные). Раньше здесь
        бралась одна фигура из выбора, но после мультивыбора выбор
        очищается раньше, и машинка с исчерпанными ходами оставалась
        на поле, а проигравший не объявлялся.
        """
        if moved is None:
            un = self.unit_state.get('selected')
            moved = [un] if un is not None else []
        for un in list(moved):
            if un.get('left', 1) <= 0 and un.get('fld') is not None:
                self.remove_unit(un)
        # проиграл тот, у кого не осталось машинок: своих машинок он
        # ставил на поле соперника, и ездили они тоже за него
        if self.game['phase'] == 'battle' and moved:
            who = self.car_owner(moved[-1])
            left = [u for u in self.car_units('car')
                    if u.get('left', 1) > 0 and self.car_owner(u) == who]
            if not left:
                self.game['turn'] = who
                self.car_end(win=False, who=who)
                return True
        self.car_next_turn()
        return False

    def car_my_side(self):
        """Сторона, за которую играет этот экран (None — ходят оба)."""
        if self.play_mode() == 'local':
            return None
        if self.play_mode() == 'ai':
            return getattr(self, 'car_human', 'player1')
        return self._net_my_turn()

    def car_make_move(self):
        """«Совершить ход»: каждая выбранная фигура едет на клетку.

        Выбрать можно до трёх машинок, и за ход они все сдвигаются на
        одну клетку в своих направлениях. Ход тратится один: после
        ходит соперник.
        """
        if not self.car_mode() or self.game['phase'] != 'battle':
            self.set_msg('Сначала расставьте машинки и начните бой', DKRED)
            return
        sel = self.car_selected()
        if not sel:
            self.set_msg('Коснитесь машинок — выбрать можно до трёх',
                         DKRED)
            return
        mine = self.car_my_side()
        if mine is not None and self.game['turn'] != mine:
            self.set_msg('Сейчас ход соперника', NAVY)
            return
        mine = self.car_my_side()
        texts = []
        for un in sel:
            if mine is not None and self.car_owner(un) != mine:
                self.set_msg('Это фигура соперника', DKRED)
                return
        for un in sel:
            txt = self.car_move_unit(un)
            texts.append(txt)
            if self.net is not None and self.play_mode() == 'net':
                # каждую сдвинувшуюся фигуру отправляем своим ходом
                self.car_send_move(un)
            if 'ЖЁЛТОГО' in txt:
                self.car_clear_sel()
                self.car_end(win=True, who=self.car_owner(un))
                return
            if 'БОЙ' in txt and 'окон' in txt:
                pass
        self.car_clear_sel()
        self.game['my_moves'] += 1
        self.stat_add('moves')
        self.game['last'] = '; '.join(texts)
        self.set_msg('Ход сделан: %s' % '; '.join(texts), NAVY)
        self.cars_tutorial_hit('move')
        self.cars_after_change()
        if not self.car_after_move(sel):
            self.cars_turn_feedback()

    def car_wait(self):
        """Кнопка «Ждать»: пропустить свой ход."""
        if not self.car_mode() or self.game['phase'] != 'battle':
            return
        mine = self.car_my_side()
        if mine is not None and self.game['turn'] != mine:
            self.set_msg('Сейчас ход соперника', NAVY)
            return
        self.game['turn'] = 'player2' if self.game['turn'] == 'player1' \
            else 'player1'
        self.set_msg('Ход пропущен', NAVY)
        self.cars_turn_feedback()

    # ---------------- ИИ в новом режиме ----------------
    def cars_maybe_ai(self):
        """Если сейчас ход компьютера — пусть он и ходит (с задержкой)."""
        if self.play_mode() != 'ai' or self.game['phase'] != 'battle':
            return
        if self.game['turn'] != self.car_ai_side():
            return
        self.after(450, self.car_ai_turn)

    def car_ai_turn(self):
        """Ход компьютера в новом режиме."""
        if self.play_mode() != 'ai' or self.game['phase'] != 'battle':
            return
        if self.game['turn'] != self.car_ai_side():
            return
        if self.game['turn'] == 'player1':
            txt = self.car_ai_drive()
        elif self.car_ai_build():
            txt = 'компьютер построил ещё стену'
        else:
            txt = self.car_ai_wall()
        self.set_msg('Компьютер: %s' % txt, DKORANGE)
        self.cars_after_change()
        if self.car_after_move():
            return
        self.cars_turn_feedback()

    def car_ai_fld(self):
        """Поле компьютера: там его стены."""
        ai = self.car_ai_side()
        return self.car_fld_of(ai) if ai else self.car_my_fld()

    def car_ai_cars(self):
        """Машинки компьютера: они ездят по НАШЕМУ полю."""
        fld = self.FL if self.car_ai_fld() is self.FR else self.FR
        return [u for u in fld['units']
                if u['type'] == 'car' and u.get('left', 1) > 0]

    def car_ai_drive(self):
        """Машинка компьютера: едет к жёлтому кругу, обходя стены."""
        cars = self.car_ai_cars()
        if not cars:
            return 'машинок не осталось'
        # сперва ищем тот ход, который приближает к центру
        best, best_txt = None, None
        for un in cars:
            here = self.car_dist(un['pts'][0])
            for step in (0, 1, -1, 2, -2, 3, -3, 4):
                save_dir = un['dir']
                un['dir'] = (save_dir + step) % 8
                nxt = self.car_step_vector(un)
                if not self.car_in_square(nxt):
                    un['dir'] = save_dir
                    continue
                kind, hit = self.car_cell_taken(nxt, ignore=un)
                if kind == 'car':
                    un['dir'] = save_dir
                    continue
                d = self.car_dist(nxt)
                if best is None or d < best[0]:
                    best = (d, un, kind, hit)
                un['dir'] = save_dir
        if best is None:
            return 'машинки зажаты между стенами'
        _, un, kind, hit = best
        txt = self.car_move_unit(un)
        if 'ЖЁЛТОГО' in txt:
            self.car_end(win=False, who=self.car_owner(un))
        return txt

    def car_ai_build(self):
        """Компьютер строит стену на своём поле, если они остались.

        Правило то же, что у человека: одна стена за ход, только внутри
        круга и не на жёлтом круге. Ставим на свободную клетку как можно
        ближе к центру — так защита получается плотнее.
        """
        fld = self.car_ai_fld()
        free = [w for w, n in self.car_remaining(fld)['wall'].items() if n > 0]
        if not free:
            return False
        size = max(free)                      # сперва длинные стены
        best = None
        for i in range(-10, 11):
            for j in range(-10, 11):
                x, y = round(i * GRID, 2), round(j * GRID, 2)
                if self.car_dist((x, y)) > 1 - 1e-9:
                    continue
                for d in range(8):
                    pts = self.unit_points(x, y, size, d)
                    if not self.can_place(fld, 'wall', pts):
                        continue
                    # не прижимаем к самому центру: жёлтый круг должен
                    # оставаться достижимым для машинок
                    dist = min(self.car_dist(p) for p in pts)
                    if dist < YELLOW_R + GRID:
                        continue
                    if best is None or dist < best[0]:
                        best = (dist, pts, d)
        if best is None:
            return False
        _, pts, d = best
        self.place_unit(fld, pts, d, size, 'wall')
        return True

    def car_ai_wall(self):
        """Компьютер двигает свою стену к центру."""
        walls = [u for u in self.car_ai_fld()['units']
                 if u['type'] == 'wall']
        if not walls:
            return 'стены разрушены'
        # ближайшая к центру стена едет к центру
        walls.sort(key=lambda u: self.car_dist(u['pts'][0]))
        un = walls[0]
        cx, cy = un['pts'][0]
        best_dir, best_d = None, self.car_dist((cx, cy))
        for dir_idx in range(8):
            un['dir'] = dir_idx
            sx, sy = self.car_delta(*DIRECTIONS[dir_idx])
            nxt = (round(cx + sx, 3), round(cy + sy, 3))
            if not self.car_points_ok([nxt], 'wall', un['fld']['units'],
                                      ignore=un):
                continue
            d = self.car_dist(nxt)
            if d < best_d:
                best_d, best_dir = d, dir_idx
        un['dir'] = best_dir if best_dir is not None else un['dir']
        if best_dir is None:
            return 'стену некуда сдвинуть'
        return self.car_move_unit(un)

    # ---------------- по сети ----------------
    def car_send_move(self, un):
        """Отправляем ход: обе стороны применяют одно и то же правило.

        Фигура адресуется полем, видом и номером среди фигур того же
        вида на этом поле: пока стены можно ставить прямо в бою, на поле
        могут лежать и машинки, и стены, и обычный номер в списке уже не
        однозначен.
        """
        if self.net is None:
            return
        same = [u for u in un['fld']['units'] if u['type'] == un['type']]
        self.net.send({'t': 'car_move',
                       'f': 'L' if un['fld'] is self.FL else 'R',
                       'k': un['type'],
                       'i': same.index(un),
                       'd': un['dir']})

    def car_peer_fld(self, side):
        """Поле соперника по букве, которую прислал он.

        По сети у каждой стороны своя нумерация: свой флот лежит на поле
        своей роли, а флот соперника — на противоположном. Поэтому левое
        поле соперника это наше правое и наоборот.
        """
        if self.play_mode() != 'net':
            return self.FL if side == 'L' else self.FR
        return self.FR if self.car_my_fld() is self.FL else self.FL

    def car_send_build(self, un):
        """Отправляем новую фигуру (стена, поставленная в бою)."""
        if self.net is None:
            return
        self.net.send({'t': 'car_build',
                       'f': 'L' if un['fld'] is self.FL else 'R',
                       'k': un['type'],
                       'pts': [[p[0], p[1]] for p in un['pts']],
                       'd': un['dir']})

    def car_apply_build(self, msg):
        """Чужая стена, поставленная прямо во время боя.

        Ставим ровно то же, что прислали, но проверяем всё заново: клетки
        должны быть на сетке, стена — внутри единичной окружности и не
        на жёлтом круге, Supply тоже должен остаться.
        """
        side, kind = msg.get('f'), msg.get('k')
        pts, d = msg.get('pts'), msg.get('d')
        if (side not in ('L', 'R') or kind not in ('car', 'wall') \
                or not isinstance(pts, list) or \
                not isinstance(d, int)):
            return
        fld = self.car_peer_fld(side)
        if not pts or len(pts) > CAR_MAX_LEN:
            return
        clean = []
        for q in pts:
            if (not isinstance(q, list) or len(q) != 2 or
                    not all(isinstance(v, (int, float)) for v in q)):
                return
            x, y = round(float(q[0]), 2), round(float(q[1]), 2)
            if (abs(round(x / GRID) - x / GRID) > 1e-6 or \
                    abs(round(y / GRID) - y / GRID) > 1e-6):
                return
            clean.append((x, y))
        if len(set(clean)) != len(clean):
            return
        if self.car_remaining(fld)[kind].get(len(clean), 0) <= 0:
            return
        if not self.car_points_ok(clean, kind, fld['units']):
            return
        self.place_unit(fld, clean, d % 8, len(clean), kind)
        self.set_msg('Соперник поставил стену в бою', DKORANGE)
        self.cars_after_change()

    def car_apply_move(self, msg):
        """Применяем чужой ход ровно так же, как свой."""
        kind, idx, d = msg.get('k'), msg.get('i'), msg.get('d')
        side = msg.get('f')
        if (kind not in ('car', 'wall') or side not in ('L', 'R') or
                not isinstance(idx, int) or not isinstance(d, int) or
                idx < 0 or d < 0 or d > 7):
            return
        fld = self.car_peer_fld(side)
        cands = [un for un in fld['units'] if un['type'] == kind]
        if idx >= len(cands):
            return
        un = cands[idx]
        un['dir'] = d % 8
        if un['type'] == 'wall':
            un['pts'] = self.unit_points(un['pts'][0][0], un['pts'][0][1],
                                         un['size'], un['dir'])
        txt = self.car_move_unit(un)
        self.game['last'] = txt
        if 'ЖЁЛТОГО' in txt:
            self.set_msg('Машинка соперника дошла до жёлтого круга — '
                         'вы проиграли!', DKRED)
            self.car_end(win=False, who=self.car_owner(un))
            return
        self.set_msg('Ход соперника: %s' % txt, DKORANGE)
        self.cars_after_change()
        if not self.car_after_move():
            self.cars_turn_feedback()

    # ---------------- ОТРИСОВКА НОВОГО РЕЖИМА ----------------
    def cars_widgets_apply(self):
        """Показывает элементы управления нового режима и прячет углы.

        В этом режиме тригонометрии нет: ползунков, полей sin/cos/tg/ctg
        и выбора точки огня на экране быть не должно.
        """
        cars = self.car_mode()
        for w in self.row_angles:
            w.visible = not cars
        for w in (self.btn_aim1, self.btn_aim2, self.btn_shot1,
                  self.btn_shot2, self.btn_mode_angles, self.btn_mode_ships,
                  self.btn_mode_planes):
            if w is not None:
                w.visible = not cars
        for i, b in enumerate(self.size_buttons):
            # длину в новом режиме рисует своя панель (draw_cars_controls)
            b.visible = not cars
        for w in self.row_cars:
            w.visible = cars
        if self.btn_wait is not None:
            self.btn_wait.visible = cars
        # весь третий ряд в новом режиме заменён своей панелью: ни
        # режимов фигур, ни размеров, ни «Поворота» тут не нужно
        for w in self.row_build:
            if w is not None:
                w.visible = False
        # «Сброс углов» в новом режиме бессмыслен — углов тут нет
        if self.btn_reset_ang is not None:
            self.btn_reset_ang.visible = not cars
        if cars:
            self.btn_move.label = 'Ход'
            self.btn_del.label = 'Убрать'
            # «Готово» нужно только на расстановке, в бою эта кнопка
            # лишняя, а длинная подпись налезала бы на соседние кнопки
            if self.btn_start is not None:
                self.btn_start.visible = self.game['phase'] == 'place'
        else:
            self.btn_move.label = 'Совершить ход'
            self.btn_del.label = 'Удалить'
            if self.btn_start is not None:
                self.btn_start.visible = True

    def car_yellow_circle(self, s, side):
        """Жёлтый круг — цель атакующего."""
        u = self.u
        px = lambda x, y: self.to_px(side, x, y)
        cx, cy = px(0, 0)
        r = abs(px(YELLOW_R, 0)[0] - cx)
        lay = pygame.Surface((int(r * 2) + 2, int(r * 2) + 2),
                             pygame.SRCALPHA)
        pygame.draw.circle(lay, (255, 214, 40, 210),
                           (int(r), int(r)), int(r))
        s.blit(lay, (int(cx - r), int(cy - r)))
        pygame.draw.circle(s, DKORANGE, (int(cx), int(cy)), int(r),
                           max(2, int(3 * u)))
        blit_text(s, 'ЦЕЛЬ', (int(cx), int(cy)), max(9, int(11 * u)),
                  (90, 60, 0), 'mm', True)

    def car_anim_pos(self, un, idx=0):
        """Клетка фигуры для отрисовки с учётом плавного хода.

        Ход — ровно на клетку, а машинка теперь крупная (её диаметр
        больше клетки в несколько раз), поэтому мгновенный сдвиг
        не виден совсем. Пока идёт анимация, рисуем фигуру между
        старой и новой клеткой — так движение сразу заметно.
        """
        pts = un.get('pts') or []
        if idx >= len(pts):
            return None
        a = un.get('anim')
        if not a:
            return pts[idx]
        old, t0 = a
        k = (pygame.time.get_ticks() - t0) / float(CAR_ANIM_MS)
        if k >= 1.0:
            un.pop('anim', None)
            return pts[idx]
        e = k * k * (3 - 2 * k)          # плавный разгон и торможение
        j = idx + len(old) - len(pts)
        if not 0 <= j < len(old):
            return pts[idx]
        fx, fy = old[j]
        tx, ty = pts[idx]
        return (fx + (tx - fx) * e, fy + (ty - fy) * e)

    def car_draw_car(self, s, un, side):
        """Машинка: круг в клетку, стрелка курса, след при ходе.

        Размер ровно клетка (по требованию игрока), но рисуется целиком
        и с толстой обводкой, иначе на телефоне её почти не видно.
        """
        u = self.u
        px = lambda x, y: self.to_px(side, x, y)
        x, y = px(*self.car_anim_pos(un))
        cell = GRID * self.br[side].width * 0.96 / (2 * LIMIT)
        r = max(4, int(cell * 0.5))
        sel = un is self.unit_state.get('selected') or \
            un in (self.unit_state.get('sel_cars') or [])
        body = GOLD if sel else (25, 85, 200)
        edge = NAVY if sel else (10, 40, 110)

        # 1) след отхода — ПОД кузовом, иначе он выбеливал машинку
        a = un.get('anim')
        if a:
            ox, oy = px(*a[0][0])
            rr = max(3, int(cell * 0.44))
            for i in range(4):
                f = (i + 1) / 5.0
                tx, ty = int(ox + (x - ox) * f), int(oy + (y - oy) * f)
                lay = pygame.Surface((rr * 2, rr * 2), pygame.SRCALPHA)
                pygame.draw.circle(lay, (60, 90, 200, int(150 * (1 - f))),
                                   (rr, rr), rr)
                s.blit(lay, (tx - rr, ty - rr))

        # 2) кузов
        pygame.draw.circle(s, body, (int(x), int(y)), r)
        pygame.draw.circle(s, edge, (int(x), int(y)), r,
                           max(1, int(2 * u)))
        # 3) стрелка курса — выходит за клетку, направление видно сразу
        dx, dy = DIRECTIONS[un['dir']]
        tip = (int(x + dx * cell * 0.85), int(y - dy * cell * 0.85))
        pygame.draw.line(s, (255, 255, 255), (int(x), int(y)), tip,
                         max(2, int(3 * u)))
        # 4) счётчик ходов
        left = un.get('left', CAR_STEPS)
        blit_text(s, str(left), (int(x), int(y + r + 10 * u)),
                  max(7, int(9 * u)), NAVY, 'mm', True)

    def car_draw_wall(self, s, un, side):
        """Препятствие: чёрные квадраты, соединённые в стену."""
        u = self.u
        R = self.br[side]
        sc = R.width * 0.96 / (2 * LIMIT)
        half = GRID * sc * 0.46
        sel = un is self.unit_state.get('selected') or \
            un in (self.unit_state.get('sel_cars') or [])
        for i in range(len(un['pts'])):
            p = self.car_anim_pos(un, i)
            if p is None:
                continue
            fx, fy = self.to_px(side, *p)
            pygame.draw.rect(s, (25, 25, 30),
                             (int(fx - half), int(fy - half),
                              int(half * 2), int(half * 2)))
            pygame.draw.rect(s, GOLD if sel else (90, 90, 100),
                             (int(fx - half), int(fy - half),
                              int(half * 2), int(half * 2)),
                             max(1, int(2 * u)))

    def car_seen(self, un, side):
        """Видна ли фигура на этом поле.

        Свои фигуры видны всегда. Чужие — только после
        столкновения: пока машинка не врезалась в стену, стены
        соперника не видно, и наоборот — чужая машинка становится
        видимой, когда ломает препятствие.
        """
        return self.car_owner(un) == self.car_side_of_fld(
            self.FL if side == 'L' else self.FR) or \
            bool(un.get('revealed'))

    def car_draw_field_units(self, s, side):
        """Фигуры этого поля: свои и раскрытые чужие."""
        fld = self.FL if side == 'L' else self.FR
        for un in fld['units']:
            if un['type'] == 'car':
                self.car_draw_car(s, un, side)
            else:
                self.car_draw_wall(s, un, side)
        other = self.FR if fld is self.FL else self.FL
        for un in other['units']:
            # чужие фигуры видны только после столкновения (car_seen)
            if not self.car_seen(un, side):
                continue
            if un['type'] == 'car':
                self.car_draw_car(s, un, side)
            else:
                self.car_draw_wall(s, un, side)

    def car_draw_fleet(self, s, x, y, fld):
        """Панель флота: сколько машинок и стен осталось поставить."""
        u = self.u
        fs = max(10, int(14 * u))
        sq = int(13 * u)
        step = sq + int(4 * u)
        rem = self.car_remaining(fld)
        for kind in self.car_panel_kinds(fld):
            for size in sorted(rem[kind]):
                n = max(0, rem[kind][size])
                if n <= 0:
                    continue
                blit_text(s, '%d:' % size, (x, y + sq // 2), fs, BLACK,
                          'lm')
                cx = x + int(24 * u)
                for _ in range(n):
                    if kind == 'wall':
                        for k in range(size):
                            r = (int(cx + k * step), int(y), sq, sq)
                            pygame.draw.rect(s, (25, 25, 30), r)
                            pygame.draw.rect(s, (110, 110, 120), r, 1)
                    else:
                        pygame.draw.circle(
                            s, (30, 90, 210),
                            (int(cx + sq // 2), int(y + sq // 2)), sq // 2)
                    cx += step * (size if kind == 'wall' else 1)
                y += sq + int(10 * u)
        return y

    def car_net_open(self):
        """Новый режим по сети: обычное подключение, но играть будем
        в машино-защитный вариант."""
        self.pending_mode = CAR_MODE
        self.show_screen('net')

    def start_cars_tutorial(self):
        """Короткий туториал нового режима."""
        self.game['mode'] = CAR_MODE
        self.car_play = 'local'
        self.car_human = 'player1'
        self.unit_state['selected'] = None
        self.unit_state['size'] = 2
        self.set_mode('cars')
        self.cars_widgets_apply()
        self.FL['name'] = 'МАШИНКИ'
        self.FR['name'] = 'ПРЕПЯТСТВИЯ'
        self.reset_game()
        self.cars_tut = {'step': 0}
        self.cars_tutorial_place()
        self.show_screen('game')

    # ---------------- туториал нового режима ----------------
    CAR_TUT = [
        {'key': 'place',
         'text': 'НОВЫЙ РЕЖИМ: МАШИНКИ И ПРЕПЯТСТВИЯ.\n\n'
                 'Отдельного «нападающего» и «защитника» нет: вы и '
                 'защитник, и нападающий.\n\n'
                 'Жёлтый круг в центре поля — цель: машинка, '
                 'коснувшаяся его, приносит победу тому, кто её '
                 'поставил.\n\n'
                 'Свои машинки ставим на поле СОПЕРНИКА ({CAR}) — '
                 'за пределами окружности, внутри чёрного квадрата.'},
        {'key': 'rotate',
         'text': 'Кнопка «Поворот» меняет курс машинки на 45°, '
                 'кнопки 1-4 — это длина стены.\n'
                 'Машинка размером примерно в клетку.'},
        {'key': 'start',
         'text': 'Жмите «Готово» — и бой начинается.\n\n'
                 'Дальше в свой ход вы делаете РОВНО ОДНО действие:\n'
                 '  • двигаете свою машинку или свою стену;\n'
                 '  • либо ставите одну новую стену на своём поле '
                 '({WALL}).\n\n'
                 'Стены до боя ставить нельзя — только во время '
                 'игры, и только в свой ход.'},
        {'key': 'wall',
         'text': 'Поставьте стену: тап по свободной клетке своего '
                 'поля вокруг жёлтого круга, длина 1-4, кнопка '
                 '«Поворот» меняет направление.\n'
                 'Сам круг закрывать нельзя!'},
        {'key': 'move',
         'text': 'Нажмите «Ход» — машинка проедет ровно одну '
                 'клетку.\n'
                 'У границы квадрата и при таране машинка '
                 'разворачивается на 180°.\n'
                 'Чужие фигуры не видны, пока не было столкновения.'},
    ]

    def cars_tutorial_place(self):
        """Туториал идёт по обычным фазам: машинка -> поворот -> бой ->
        стена -> ход. Второй игрок в туториале компьютерный, чтобы
        игрок не переключался сам с собой.
        """
        for fld in (self.FL, self.FR):
            fld['units'].clear()
        self.game['phase'] = 'place'
        self.game['turn'] = 'player1'
        self.unit_state['selected'] = None
        self.unit_state['size'] = 1
        self.btn_start.label = 'Готово'
        self.cars_tut = {'step': 0}
        self.cars_tut_text()

    def cars_tut_active(self):
        """Идёт ли туториал нового режима."""
        return (self.car_mode() and \
                getattr(self, 'cars_tut', None) is not None and \
                self.cars_tut.get('step', 0) < len(self.CAR_TUT))

    def car_side_word(self, fld):
        """«ЛЕВОМ» или «ПРАВОМ» — про указанное поле."""
        return 'ЛЕВОМ' if fld is self.FL else 'ПРАВОМ'

    def cars_tut_text(self):
        if not self.cars_tut_active():
            return
        text = self.CAR_TUT[self.cars_tut['step']]['text']
        text = text.replace('{CAR}', self.car_side_word(self.car_foe_fld()))
        text = text.replace('{WALL}', self.car_side_word(self.car_my_fld()))
        self.set_msg(text, DKORANGE)

    def cars_tut_advance(self):
        """Следующий шаг туториала."""
        if not self.cars_tut_active():
            return
        self.cars_tut['step'] += 1
        if not self.cars_tut_active():
            self.cars_tut = None
            self.set_msg('Туториал пройден! Играйте: «Новый режим» в '
                         'главном меню.', DGREEN)
            return
        self.cars_tut_text()

    def cars_tutorial_hit(self, key):
        """Отмечает выполненное действие туториала."""
        if not self.cars_tut_active():
            return
        if self.CAR_TUT[self.cars_tut['step']]['key'] == key:
            self.cars_tut_advance()


    def car_end(self, win, who=None):
        """Партия закончена.

        win=True — машинка дорвалась до жёлтого круга на чужом поле
        (победа атаковавшего), win=False — у кого-то не осталось
        машинок.
        """
        if self.game['phase'] == 'over':
            return
        self.game['phase'] = 'over'
        if self.play_mode() == 'net' and self.net is not None:
            self.net.send({'t': 'over', 'winner': 'me' if win else 'you'})
        if who is None:
            who = self.game.get('turn', 'player1')
        name = self.car_player_name(who)
        text = ('Машинки прорвались — %s победил!' % name if win else
                'Машинки кончились — %s проиграл!' % name)
        self.set_msg(text, DGREEN if win else DKRED)
        self.show_victory(text)
        # результат запишется в show_victory() — для любого режима

    def cars_after_change(self):
        """Пересчитать то, что зависит от положения фигур."""
        self.unit_state['last'] = None
        self.update_angles()

    def car_player_name(self, who):
        """Как назвать игрока: в локальной игре — по номеру, иначе — '
        'вы/соперник'."""
        if self.play_mode() == 'local':
            return 'ИГРОК %s' % who[-1]
        me = self.car_now()
        return 'ВЫ' if who == me else 'СОПЕРНИК'

    def cars_turn_feedback(self):
        """Подсказка, чей ход и что делать."""
        if self.game['phase'] != 'battle':
            return
        who = self.game['turn']
        left = len([u for u in self.car_units('car')
                    if u.get('left', 1) > 0 and self.car_owner(u) == who])
        self.set_msg('Ход: %s. В свой ход: двигаем свою машинку или стену '
                     'либо ставим одну стену на своём поле. '
                     'Машинок в игре: %d'
                     % (self.car_player_name(who), left), NAVY)

    # =========================================================
    #  ОТРИСОВКА
    # =========================================================
    def draw(self):
        s = self.base
        s.fill(SMOKE)
        if self.screen_name == 'game':
            self.draw_game(s)
            # подсветка элемента туториала — поверх всего
            if self.tutorial['active'] and self.tut_hl:
                r = self.tut_hl.inflate(int(10 * self.u), int(10 * self.u))
                hl = pygame.Surface(r.size, pygame.SRCALPHA)
                pygame.draw.rect(hl, (255, 0, 0), hl.get_rect(),
                                 max(2, int(4 * self.u)))
                s.blit(hl, r.topleft)
            self.keypad.draw(s)
        else:
            self.draw_menu_screen(s)
            self.textpad.draw(s)

    def draw_game(self, s):
        u = self.u
        # --- шапка ---
        pygame.draw.rect(s, WHITE, (0, 0, self.W, self.HEADER_H))
        pygame.draw.line(s, BORDER, (0, self.HEADER_H),
                         (self.W, self.HEADER_H), 1)
        blit_text(s, self.msg[0], (self.W // 2, self.HEADER_H // 2),
                  int(17 * u), self.msg[1], 'mm', True)

        # --- баннер туториала: текст переносится по ширине, при нехватке
        #     высоты шрифт уменьшается, поэтому помещается на любом экране ---
        if self.tutorial['active'] and getattr(self, 'tut_text', ''):
            r = pygame.Rect(self.M, self.HEADER_H + int(2 * u),
                            self.W - 2 * self.M, self.TUT_H - int(4 * u))
            pygame.draw.rect(s, (255, 250, 225), r, border_radius=int(8 * u))
            pygame.draw.rect(s, DKORANGE, r, max(1, int(2 * u)),
                             border_radius=int(8 * u))
            size, lines = self.fit_lines(self.tut_text, r.w - int(16 * u),
                                         int(14 * u), r.h - int(6 * u))
            lh = int(size * 1.3)
            y0 = r.centery - (len(lines) * lh) // 2
            for i, ln in enumerate(lines):
                blit_text(s, ln, (r.centerx, y0 + i * lh), size,
                          (110, 70, 0), 'mm')

        self.draw_board(s, 'L')
        self.draw_board(s, 'R')
        self.draw_panel(s, self.pr[0], self.FL, 0)
        self.draw_panel(s, self.pr[1], self.FR, 1)

        # подписи «ПОЛЕ ИГРОКА N» внутри полей
        if self.car_mode():
            for side, cap in (('L', self.FL['name'] or 'ВЫ'),
                                ('R', self.FR['name'] or 'СОПЕРНИК')):
                blit_text(s, cap,
                          (self.br[side].x + int(8 * u),
                           self.br[side].y + int(6 * u)),
                          int(13 * u), NAVY, 'lt', True)
        else:
            blit_text(s, 'ПОЛЕ ИГРОКА 1',
                      (self.br['L'].x + int(8 * u),
                       self.br['L'].y + int(6 * u)),
                      int(13 * u), NAVY, 'lt', True)
            blit_text(s, 'ПОЛЕ ИГРОКА 2',
                      (self.br['R'].x + int(8 * u),
                       self.br['R'].y + int(6 * u)),
                      int(13 * u), NAVY, 'lt', True)

        # --- нижняя подсказка: тоже с переносом по ширине окна ---
        if self.car_mode():
            hint = ('Расстановка: свои машинки ставим на поле СОПЕРНИКА '
                    '(за пределами окружности), «Поворот» — курс на 45°, '
                    '«Готов» — передать ход   •   Бой: коснитесь своих '
                    'машинок, чтобы выбрать их (не больше трёх из '
                    'четырёх), «Совершить ход» — каждая едет на клетку '
                    'в своём направлении; тап по пустой клетке СВОЕГО '
                    'поля — поставить стену (1–4, круг не закрывать); '
                    'стены до боя ставить нельзя; у границы квадрата и '
                    'при таране машинка разворачивается, чужие фигуры '
                    'видны только после столкновения')
        else:
            hint = ('Стройка: тап по полю — поставить/выбрать, '
                    '«Поворот» — развернуть, 1–5 — размер, «Удалить» — '
                    'убрать   •   Бой: тап и ведение пальцем по полю — '
                    'прицел («Прицел: 1 / 2»), поля sin1 cos1 tg2 ctg2 — '
                    'ввод с клавиатуры, «Огонь P1/P2» → «Совершить ход»')
        size, lines = self.fit_lines(hint, self.W - 2 * self.M,
                                     int(12 * u), int(34 * u))
        lh = int(size * 1.3)
        y0 = max(self.HINT_Y, self.H - len(lines) * lh - int(4 * u))
        for i, ln in enumerate(lines):
            blit_text(s, ln, (self.W // 2, y0 + i * lh), size, DGRAY, 'mm')

        # --- кнопки строк управления ---
        self.draw_controls(s)

    @staticmethod
    def fit_lines(text, width, size, max_h):
        """Перенос строк по ширине (с реальным измерением шрифта);
        если не влезает по высоте — шрифт делается мельче."""
        size = max(9, int(size))
        while True:
            f = font(size)
            lines = []
            for para in text.split('\n'):
                cur = ''
                for word in para.split(' '):
                    trial = (cur + ' ' + word).strip()
                    if cur and f.size(trial)[0] > width:
                        lines.append(cur)
                        cur = word
                    else:
                        cur = trial
                lines.append(cur)
            if len(lines) * size * 1.3 <= max_h or size <= 9:
                return size, lines
            size -= 1

    def row4_fit(self):
        """Пересобирает ряд 4 под текущие подписи кнопок.

        Подписи меняются по ходу игры («Совершить ход» → «Ход»,
        «Начать бой» → «Готово (Игрок 2)»), а ширина кнопки задана один
        раз при построении экрана. Из-за этого длинная подпись вылезала
        за кнопку и наезжала на соседнюю. Поэтому как только набор
        подписей изменился, раскладываем ряд заново.
        """
        btns = [b for b in (self.btn_shot1, self.btn_shot2, self.btn_move,
                            self.btn_start, self.btn_menu, self.btn_tut_next,
                            self.btn_tut_skip, self.btn_reset_ang,
                            self.btn_wait) if b is not None]
        key = tuple(b.label for b in btns)
        if key == getattr(self, '_row4_key', None):
            return
        self._row4_key = key
        u = self.u
        gap = int(8 * u)
        y4, h4 = self.R4
        h = min(int(clamp(32 * u, 24, 48)), h4 - int(4 * u))
        lab = 'Ход:' if self.car_mode() else 'Огонь:'
        x = self.M + font(max(9, int(14 * u)), True).size(lab)[0] + gap
        for b in btns:
            w = font(b.size, b.bold).size(b.label)[0] + int(24 * u)
            b.rect = pygame.Rect(int(x), int(y4 + (h4 - h) // 2), int(w), h)
            x += w + gap

    def draw_controls(self, s):
        u = self.u
        y1, h1 = self.R1
        y2, h2 = self.R2
        y3, h3 = self.R3
        y4, h4 = self.R4
        self.row4_fit()
        if self.car_mode():
            # в новом режиме тригонометрии нет вообще: рисуем свою
            # панель — что ставим, длина, готовность, ход и выход
            self.draw_cars_controls(s)
            return

        # --- ряд 1: углы и выбор прицела ---
        # Оба угла свои — в том числе по сети, поэтому подписи и
        # значения выглядят как обычно.
        for i, gx in enumerate(self.ang_x):
            blit_text(s, 'Угол %d, °' % (i + 1),
                      (gx, y1 + int(2 * u)), int(14 * u), BLACK,
                      'lt', True)
        blit_text(s, '%.1f°' % self.s1,
                  (self.ang_val[0], y1 + h1 // 2), int(17 * u), PURPLE,
                  'mm', True)
        blit_text(s, '%.1f°' % self.s2,
                  (self.ang_val[1], y1 + h1 // 2), int(17 * u), DKORANGE,
                  'mm', True)
        blit_text(s, 'Прицел:', (self.aim_x, y1 + h1 // 2),
                  int(14 * u), BLACK, 'lm', True)
        hint1 = 'тяните пальцем по полю'
        if self.hint1_x + text_size(hint1, int(13 * u))[0] < self.W - self.M:
            blit_text(s, hint1, (self.hint1_x, y1 + h1 // 2),
                      int(13 * u), DGRAY, 'lm')
        # --- ряд 2: числовой ввод ---
        if self.car_mode():
            hint2 = 'стена ставится в свой ход, одна за ход'
        else:
            hint2 = 'коснитесь поля — ввод с экранной клавиатуры'
        if self.hint2_x + text_size(hint2, int(13 * u))[0] < self.W - self.M:
            blit_text(s, hint2, (self.hint2_x, y2 + h2 // 2), int(13 * u),
                      DGRAY, 'lm')
        # --- ряд 3 и 4 ---
        if self.car_mode():
            # ни «Режим», ни «Размер», ни «Огонь» здесь ни при чём
            blit_text(s, 'Длина стены:', (self.M, y3 + h3 // 2),
                      int(14 * u), BLACK, 'lm', True)
            blit_text(s, 'Ход:', (self.M, y4 + h4 // 2), int(14 * u), BLACK,
                      'lm', True)
        else:
            blit_text(s, 'Режим:', (self.M, y3 + h3 // 2), int(14 * u), BLACK,
                      'lm', True)
            blit_text(s, 'Размер:', (self.size_lab_x, y3 + h3 // 2),
                      int(14 * u), BLACK, 'lm', True)
            blit_text(s, 'Огонь:', (self.M, y4 + h4 // 2), int(14 * u), BLACK,
                      'lm', True)
        for row in (self.row_angles, self.row_build, self.row_battle):
            for wdg in row:
                wdg.draw(s)

    def draw_cars_controls(self, s):
        """Панель нового режима: два ряда вместо четырёх.

        Верхний ряд — что ставим (машинки или стены) и длина 1–4,
        нижний — «Готов», «Совершить ход» и «Выход». Тригонометрических
        ползунков, полей sin/cos/tg/ctg и точек прицела здесь нет.
        """
        u = self.u
        M = self.M
        gap = int(10 * u)
        y1, h1 = self.R1
        y2, h2 = self.R2
        h = min(int(clamp(34 * u, 22, 48)), h1 - int(4 * u),
                h2 - int(4 * u))
        cy1 = y1 + (h1 - h) // 2
        cy2 = y2 + (h2 - h) // 2
        placing = self.game['phase'] == 'place'
        battle = self.game['phase'] == 'battle'

        # --- верхний ряд: машинки/стены и длина ---
        self.btn_car_cars.visible = placing
        self.btn_car_walls.visible = True
        kind = self.unit_state.get('car_kind_btn', 'car')
        self.btn_car_cars.active = kind == 'car'
        self.btn_car_walls.active = kind == 'wall'
        x = M
        for b in (self.btn_car_cars, self.btn_car_walls):
            w = font(b.size, b.bold).size(b.label)[0] + int(26 * u)
            b.rect = pygame.Rect(int(x), int(cy1), int(w), h)
            x += w + gap
        blit_text(s, 'Длина:', (int(x + 2 * u), cy1 + h // 2),
                  max(9, int(13 * u)), BLACK, 'lm', True)
        x += font(max(9, int(13 * u)), True).size('Длина:')[0] + gap
        for i, b in enumerate(self.size_buttons[:CAR_MAX_LEN]):
            w = int(h)
            b.visible = True
            b.rect = pygame.Rect(int(x), int(cy1), w, h)
            b.active = self.unit_state['size'] == i + 1
            x += w + gap
        for b in self.size_buttons[CAR_MAX_LEN:]:
            b.visible = False

        # --- нижний ряд: готовность, ход и выход ---
        xr = M
        for b, label in ((self.btn_ready, 'Готов'),
                         (self.btn_commit, 'Совершить ход'),
                         (self.btn_exit, 'Выход')):
            b.label = label
            w = font(b.size, b.bold).size(label)[0] + int(26 * u)
            b.rect = pygame.Rect(int(xr), int(cy2), int(w), h)
            xr += w + gap
        self.btn_ready.visible = placing
        self.btn_commit.visible = battle
        self.btn_exit.visible = True
        sel = self.car_selected()
        if battle:
            n_cars = len([u for u in sel if u['type'] == 'car'])
            blit_text(s, 'Выбрано машинок: %d из %d   (максимум %d)'
                      % (n_cars, sum(FLEET_CARS.values()),
                         self.CAR_SELECT_MAX),
                      (xr + gap, cy2 + h // 2),
                      max(9, int(13 * u)), DGRAY, 'lm')
        else:
            who = self.car_now()
            blit_text(s, 'Ставит машинки: %s (поле соперника — %s)'
                      % (self.car_player_name(who),
                         'ЛЕВОЕ' if self.car_foe_fld() is self.FL
                         else 'ПРАВОЕ'),
                      (xr + gap, cy2 + h // 2),
                      max(9, int(13 * u)), DGRAY, 'lm')
        for b in (self.btn_car_cars, self.btn_car_walls, self.btn_ready,
                  self.btn_commit, self.btn_exit):
            b.draw(s)
        for b in self.size_buttons[:CAR_MAX_LEN]:
            b.draw(s)

    def car_panel_title(self, idx, phase):
        """Заголовок боковой панели в новом режиме.

        Отдельных «нападающего» и «защитника» нет, поэтому подпись
        называет владельца поля, а не вид фигуры.
        """
        fld = self.FL if idx == 0 else self.FR
        who = self.car_side_of_fld(fld)
        if phase == 'place' and fld is self.car_foe_fld() and \
                who == self.car_now():
            return 'ИГРОК %s — МАШИНКИ:' % who[-1]
        return ('ИГРОК %s:' % who[-1] if self.play_mode() == 'local'
                else ('ВЫ:' if who == self.car_now() else 'СОПЕРНИК:'))

    def draw_panel(self, s, r, fld, idx):
        u = self.u
        pad = int(10 * u)
        pygame.draw.rect(s, PANEL_BG, r)
        pygame.draw.rect(s, BORDER, r, 1)
        md, ph = self.game['mode'], self.game['phase']
        if self.car_mode():
            title = self.car_panel_title(idx, ph)
        elif idx == 0:
            title = 'ИГРОК 1 — СТРОЙКА:' if ph == 'place1' else \
                ('ИГРОК 1 (в живых):' if md == 'local'
                 else 'МОИ ЮНИТЫ (в живых):')
        elif md == 'ai':
            title = 'ПРОТИВНИК:' if ph == 'place1' else 'ПРОТИВНИК (в живых):'
        elif ph == 'place2':
            title = 'ИГРОК 2 — СТРОЙКА:'
        elif ph == 'place1':
            title = 'Игрок 2:'
        else:
            title = 'ИГРОК 2 (в живых):'
        blit_text(s, title, (r.x + pad, r.y + pad), max(11, int(14 * u)),
                  BLACK, 'lt', True)
        y = r.y + pad + int(24 * u)
        building = (idx == 0 and ph == 'place1') or \
                   (idx == 1 and ph == 'place2' and md == 'local')
        if not fld['units'] and ph == 'place1' and idx == 1 and md == 'ai':
            blit_text(s, 'расставляет флот...', (r.x + pad, y),
                      max(11, int(13 * u)), DGRAY, 'lt')
        elif md == 'net' and idx == 1:
            # состав флота соперника скрыт: видно только то, что уже
            # нашли по подбитым и потопленным кораблям
            blit_text(s, 'флот соперника скрыт', (r.x + pad, y),
                      max(11, int(13 * u)), DGRAY, 'lt')
            y += int(18 * u)
        else:
            if self.car_mode():
                y = self.car_draw_fleet(s, r.x + pad, y, fld)
            else:
                y = self.draw_fleet(s, r.x + pad, y, fld, building)
        if building:
            st = self.status_line()
            if st:
                blit_text(s, st, (r.x + pad, y + int(6 * u)),
                          max(11, int(13 * u)), DGREEN, 'lt', True)
        elif fld['units']:
            hits = sum(len(u['hits']) for u in fld['units'])
            sunks = sum(1 for u in fld['units'] if self.is_sunk(u))
            blit_text(s, 'подбито: %d   потоплено: %d' % (hits, sunks),
                      (r.x + pad, y + int(6 * u)), max(11, int(13 * u)),
                      DGRAY, 'lt')
        if (idx == 1 and md == 'ai' and not self.car_mode() and
                ph not in ('place1', 'place2')):
            blit_text(s, 'мои ходы: %d' % self.game['my_moves'],
                      (r.x + pad, r.bottom - int(46 * u)),
                      max(11, int(13 * u)), BLACK, 'lt')
            blit_text(s, 'его ходы: %d' % self.game['enemy_moves'],
                      (r.x + pad, r.bottom - int(28 * u)),
                      max(11, int(13 * u)), BLACK, 'lt')
        if idx == 0 and not self.car_mode():
            blit_text(s, 'сложность: %s' % self.settings['difficulty'],
                      (r.x + pad, r.bottom - int(24 * u)),
                      max(10, int(12 * u)), DGRAY, 'lt')
        if self.car_mode():
            # ходы и «сложность» здесь ни при чём: показываем, сколько
            # стен ещё можно построить на этом поле и сколько машинок
            # ездит по нему
            who = self.car_side_of_fld(fld)
            left = sum(max(0, v) for v in
                       self.car_remaining(fld)['wall'].values())
            cars = len(self.car_owner_cars(who))
            blit_text(s, 'стен осталось: %d   машинок: %d' % (left, cars),
                      (r.x + pad, r.bottom - int(28 * u)),
                      max(10, int(12 * u)), DGRAY, 'lt')

    def draw_fleet(self, s, x, y, fld, building):
        u = self.u
        fsh, fpl = self.fleets()
        if building:
            rem = self.remaining(fld['units'])
        else:
            rem = {'ship': dict.fromkeys(fsh, 0),
                   'plane': dict.fromkeys(fpl, 0)}
            for un in fld['units']:
                if not self.is_sunk(un):
                    rem[un['type']][un['size']] += 1
        fs = max(10, int(14 * u))
        sq = int(13 * u)                     # сторона квадратика корабля
        st = max(int(17 * u), sq + int(4 * u))
        tri = int(8 * u)
        row_h = st + int(9 * u)
        for sz in sorted(fsh):
            blit_text(s, '%d:' % sz, (x, y + st // 2), fs, BLACK, 'lm')
            cx = x + int(24 * u)
            for i in range(fsh[sz]):
                col = NAVY if i < rem['ship'][sz] else (205, 205, 205)
                pygame.draw.rect(s, col, (cx, y, sq, sq))
                pygame.draw.rect(s, BORDER, (cx, y, sq, sq), 1)
                cx += st
            if fpl and sz in fpl:
                cx += int(6 * u)
                for i in range(fpl[sz]):
                    filled = i < rem['plane'][sz]
                    col = TEAL if filled else (205, 205, 205)
                    draw_triangle(s, col, cx + sq // 2, y + sq // 2, tri, 0)
                    if not filled:
                        pygame.draw.polygon(s, BORDER, [
                            (cx + sq // 2, y),
                            (cx, y + sq),
                            (cx + sq, y + sq)], 1)
                    cx += st
            y += row_h
        if not fpl:
            blit_text(s, 'самолёты выкл.', (x + int(24 * u), y + int(6 * u)),
                      max(10, int(12 * u)), DGRAY, 'lt')
            y += int(18 * u)
        return y

    # ---------------- игровое поле ----------------
    def draw_board(self, s, side):
        u = self.u
        fld = self.FL if side == 'L' else self.FR
        R = self.br[side]
        px = lambda x, y: self.to_px(side, x, y)
        pygame.draw.rect(s, WHITE, R)
        sc = R.width * 0.96 / (2 * LIMIT)
        fs = max(9, int(11 * u))            # мелкий текст поля

        # сетка
        gc = faint(GRAY, 0.45)
        for i in range(-16, 17):
            v = i * GRID
            pygame.draw.line(s, gc, px(v, -LIMIT), px(v, LIMIT))
            pygame.draw.line(s, gc, px(-LIMIT, v), px(LIMIT, v))

        # оси
        draw_arrow(s, faint(BLACK, FADE + 0.1), px(-LIMIT, 0), px(LIMIT, 0))
        draw_arrow(s, faint(BLACK, FADE + 0.1), px(0, -LIMIT), px(0, LIMIT))
        blit_text(s, 'x', (px(LIMIT - 0.05, 0)[0] + 10 * u,
                           px(0, 0)[1] + 14 * u), fs,
                  faint(BLACK, FADE + 0.1), 'mm', True)
        blit_text(s, 'y', (px(0, 0)[0] + 14 * u,
                           px(0, LIMIT - 0.05)[1] - 10 * u), fs,
                  faint(BLACK, FADE + 0.1), 'mm', True)

        # в новом режиме тригонометрии на поле нет: ни осей tg/ctg,
        # ни подписей делений — только клетки, круг и цель
        if not self.car_mode():
            draw_dash(s, faint(RED, 0.5), px(1, -LIMIT), px(1, LIMIT),
                      max(1, int(2 * u)), int(12 * u), int(8 * u))
            draw_dash(s, faint(GREEN, 0.6), px(-LIMIT, 1), px(LIMIT, 1),
                      max(1, int(2 * u)), int(12 * u), int(8 * u))
            blit_text(s, 'ось tg', (px(1, -LIMIT + 0.03)[0],
                                    px(0, -LIMIT)[1] + 12 * u), fs,
                      faint(RED, 0.7), 'mm')
            blit_text(s, 'ось ctg', (px(-LIMIT + 0.03, 0)[0],
                                     px(0, 1)[1] - 12 * u), fs,
                      faint(GREEN, 0.7), 'mm')
            # подписи делений: шаг подбирается так, чтобы не слипались
            tstep = 0.2
            min_px = text_size('0.0', fs)[0] + 8
            while tstep * sc < min_px and tstep < 1.0:
                tstep += 0.2
            for i in range(-10, 11, max(1, int(tstep * 10))):
                v = round(i / 10, 1)
                fx, fy = px(v, 0)
                blit_text(s, '%.1f' % v, (fx, fy + 7 * u), fs,
                          faint(BLACK, FADE), 'mm')
                fx, fy = px(0, v)
                blit_text(s, '%.1f' % v, (fx - 8 * u, fy), fs,
                          faint(BLACK, FADE), 'rm')

        # окружность, квадраты
        cx, cy = px(0, 0)
        r = abs(px(1, 0)[0] - cx)
        lw = max(1, int(3 * u))
        pygame.draw.circle(s, BLUE_L, (int(cx), int(cy)), int(r), lw)
        pygame.draw.polygon(s, BLACK, [px(-1, -1), px(1, -1), px(1, 1),
                                       px(-1, 1)], lw)
        draw_dash_poly(s, DGRAY, [px(0, 0), px(1, 0), px(1, 1), px(0, 1)],
                       max(1, int(2 * u)), int(10 * u), int(6 * u))

        # зоны (подсказка туториала)
        if self.tutorial['active'] and self.tutorial.get('zones') and \
                side == 'L':
            blit_text(s, 'ОКЕАН', (cx, cy - 0.12 * sc), int(22 * u),
                      (0, 0, 130), 'mm', True)
            blit_text(s, 'только корабли', (cx, cy - 0.22 * sc), int(14 * u),
                      (0, 0, 130), 'mm')
            for zx in (0.9, -0.9):
                for zy in (0.9, -0.9):
                    blit_text(s, 'ВОЗДУХ', px(zx, zy), int(13 * u),
                              (0, 120, 120), 'mm', True)

        if self.car_mode():
            # новый режим: без tg/ctg, зато жёлтый круг-цель и
            # собственные фигуры (машинки — круги, стены — квадраты)
            self.car_yellow_circle(s, side)
            self.car_draw_field_units(s, side)
            return

        # --- размеры маркеров (точки юнитов и крестики — уменьшены на 20%) ---
        ship_r = max(3, int(0.052 * sc))       # было 0.065
        plane_r = max(4, int(0.062 * sc))      # было 0.065 + 3px
        unit_line = max(2, int(4 * u))
        hit_r = max(3, int(0.056 * sc))         # было 0.070
        hit_w = max(2, int(3 * u))
        halo_r = max(3, int(4 * u))             # серые кресты вокруг потопленных
        miss_r = max(2, int(0.032 * sc))       # было 0.040

        # призрак постройки
        if side == ('L' if self.build_fld() is self.FL else 'R'):
            gh, ok = self.ghost_pts()
            if gh:
                col = (0, 200, 0, 150) if ok else (220, 30, 30, 150)
                pts = [px(*q) for q in gh]
                if len(pts) > 1:
                    pygame.draw.lines(s, col[:3], False, pts,
                                      max(2, int(4 * u)))
                rr = max(3, int(0.042 * sc))
                for fx, fy in pts:
                    layer = pygame.Surface((rr * 2 + 2, rr * 2 + 2),
                                           pygame.SRCALPHA)
                    pygame.draw.circle(layer, col, (rr + 1, rr + 1), rr)
                    s.blit(layer, (int(fx - rr - 1), int(fy - rr - 1)))

        # юниты
        for un in fld['units']:
            if not self.unit_visible(un, fld):
                continue
            col = self.unit_color(un)
            pts = [px(*q) for q in un['pts']]
            if len(pts) > 1:
                pygame.draw.lines(s, col, False, pts, unit_line)
            for fx, fy in pts:
                if un['type'] == 'ship':
                    pygame.draw.circle(s, col, (int(fx), int(fy)), ship_r)
                else:
                    draw_triangle(s, col, fx, fy, plane_r, 0)

        # серые кресты вокруг потопленных
        drawn = set()
        for un in fld['units']:
            if self.is_sunk(un):
                for q in self.halo_points(un, fld['units']):
                    if q in drawn:
                        continue
                    drawn.add(q)
                    fx, fy = px(*q)
                    draw_cross(s, (160, 160, 160), fx, fy, halo_r,
                               max(1, int(2 * u)))

        # промахи
        for m in fld['misses']:
            fx, fy = px(*m)
            pygame.draw.circle(s, SILVER, (int(fx), int(fy)), miss_r)
            pygame.draw.circle(s, GRAY, (int(fx), int(fy)), miss_r, 1)

        # попадания
        for un in fld['units']:
            for q in un['hits']:
                fx, fy = px(*q)
                draw_cross(s, RED, fx, fy, hit_r, hit_w)

        # подсказки
        if not self.game.get('awaiting_tap'):
            hit_pts = {p for un in fld['units'] for p in un['hits']}
            for q in fld['hints']:
                if q in hit_pts:
                    continue
                fx, fy = px(*q)
                pygame.draw.circle(s, ORANGE, (int(fx), int(fy)),
                                   int(0.11 * sc), max(2, int(3 * u)))

        # прицел: луч и точки пересечения показываем всегда, когда
        # вид фигур — «Углы». Раньше они появлялись только в бою, и в
        # расстановке игрок не видел, куда вообще целиться.
        if self.mode['name'] == 'angles' and \
                (self.game['phase'] != 'battle' or
                 self.active_side() == side):
            self.draw_aim(s, side, px)


    def draw_aim(self, s, side, px):
        u = self.u
        c1, s1, c2, s2, tg2, ctg2 = self.update_angles()
        R = self.br[side]
        sc = R.width * 0.96 / (2 * LIMIT)
        lw = max(2, int(3 * u))

        # Оба угла и обе точки считаются из НАШИХ углов, поэтому и луч угла 1,
        # и луч угла 2, и подписи sin/cos/tg/ctg — свои. Точки P1 и P2
        # тоже обе свои и независимые: по сети соперник присылает только
        # координаты выстрела, поэтому его точек на нашем экране нет.
        on1 = self.shot_sel['p'] == 'P1'
        # Какие точки реально нарисованы — для проверок и отладки.
        self.aim_points_drawn = []

        # --- угол 1 ---
        pygame.draw.line(s, PURPLE, px(0, 0), px(c1, s1), lw)
        pygame.draw.circle(s, PURPLE, (int(px(c1, s1)[0]), int(px(c1, s1)[1])),
                           max(4, int(6 * u)))
        pc = faint(BLUE, FADE + 0.15)
        pygame.draw.line(s, pc, px(c1, 0), px(c1, s1), max(1, int(2 * u)))
        pygame.draw.line(s, pc, px(0, s1), px(c1, s1), max(1, int(2 * u)))
        blit_text(s, 'cos = %.2f' % c1,
                  (px(c1, 0)[0] - 6 * u, px(0, 0)[1] + 14 * u),
                  max(9, int(11 * u)), pc, 'rm')
        blit_text(s, 'sin = %.2f' % s1,
                  (px(0, 0)[0] - 10 * u, px(0, s1)[1]),
                  max(9, int(11 * u)), pc, 'rm')

        # --- угол 2 ---
        pygame.draw.line(s, DKORANGE, px(0, 0), px(c2, s2), lw)
        p2 = px(c2, s2)
        d = max(5, int(7 * u))
        pygame.draw.polygon(s, DKORANGE, [(p2[0], p2[1] - d), (p2[0] + d, p2[1]),
                                          (p2[0], p2[1] + d), (p2[0] - d, p2[1])],
                            max(1, int(2 * u)))
        pc2 = faint(DGRAY, FADE + 0.15)
        pygame.draw.line(s, pc2, px(c2, 0), px(c2, s2), max(1, int(2 * u)))
        pygame.draw.line(s, pc2, px(0, s2), px(c2, s2), max(1, int(2 * u)))

        # --- лучи tg/ctg до границы квадрата ---
        for c, sn in ((c1, s1), (c2, s2)):
            m = max(abs(c), abs(sn))
            if m > 0:
                bx, by = c / m, sn / m
                pygame.draw.line(s, faint(RED, FADE), px(0, 0), px(bx, by),
                                 max(1, int(2 * u)))
                pygame.draw.line(s, faint(GREEN, FADE), px(0, 0), px(bx, by),
                                 max(1, int(2 * u)))

        # --- маркеры на осях tg/ctg ---
        if tg2 is not None:
            fx, fy = px(1, clamp(tg2, -LIMIT, LIMIT))
            q = max(3, int(4 * u))
            pygame.draw.rect(s, faint(RED, FADE),
                             (int(fx) - q, int(fy) - q, 2 * q, 2 * q),
                             max(1, int(2 * u)))
        if ctg2 is not None:
            fx, fy = px(clamp(ctg2, -LIMIT, LIMIT), 1)
            draw_triangle(s, faint(GREEN, FADE), fx, fy, max(4, int(6 * u)),
                          max(1, int(2 * u)))

        # --- точки пересечения P1 / P2 ---
        # Подпись ставится НАД точкой и мелким шрифтом, чтобы не закрывать её.
        lbl_size = max(8, int(10 * u))
        star_r = max(7, int(10 * u))
        if self.state['P1'] is not None:
            self.aim_points_drawn.append('P1')
            Px, Py = self.state['P1']
            fx, fy = px(Px, Py)
            col = BLACK if on1 else mix(WHITE, BLACK, 0.25)
            draw_star(s, col, fx, fy, star_r, max(2, int(2 * u)))
            self.aim_label(s, 'P1 = (%.2f, %.2f)' % (Px, Py), fx, fy, R,
                           col, lbl_size)
        if self.state['P2'] is not None:
            self.aim_points_drawn.append('P2')
            Qx, Qy = self.state['P2']
            fx, fy = px(Qx, Qy)
            col = DGREEN if not on1 else mix(WHITE, DGREEN, 0.25)
            draw_star(s, col, fx, fy, star_r, max(2, int(2 * u)))
            self.aim_label(s, 'P2 = (%.2f, %.2f)' % (Qx, Qy), fx, fy, R,
                           col, lbl_size)

        # --- соединительные проекции ---
        if tg2 is not None:
            Py = clamp(tg2 * c1, -1.0, 1.0)
            pygame.draw.line(s, faint(PURPLE, FADE), px(c1, s1), px(c1, Py),
                             max(1, int(2 * u)))
        if ctg2 is not None:
            Qx = clamp(ctg2 * s1, -1.0, 1.0)
            pygame.draw.line(s, faint(DKORANGE, FADE), px(c1, s1), px(Qx, s1),
                             max(1, int(2 * u)))

        # --- информационная панель ---
        f = lambda v: '% .2f' % v if v is not None else '   —'
        p1s = ('(%.2f, %.2f)' % self.state['P1']) if self.state['P1'] \
            else 'нет'
        p2s = ('(%.2f, %.2f)' % self.state['P2']) if self.state['P2'] \
            else 'нет'
        # Оба угла и обе точки — свои, показываем и те и другие. Точек
        # соперника на экране нет: он шлёт нам только координаты.
        lines = ['угол 1 = %5.1f°' % self.s1,
                 '  sin=%s cos=%s' % (f(s1), f(c1)),
                 'угол 2 = %5.1f°' % self.s2,
                 '  tg =%s ctg=%s' % (f(tg2), f(ctg2)),
                 'P1 = ' + p1s,
                 'P2 = ' + p2s]
        text_box(s, lines, (R.right - 6 * self.u, R.y + 6 * self.u),
                 max(9, int(12 * u)), BLACK, WHITE,
                 BORDER, 'rt', False, None, 235, int(5 * self.u))

        # подсветка выбранной точки огня
        blit_text(s, 'огонь: %s' % self.shot_sel['p'],
                  (R.centerx, R.bottom - 14 * u), max(10, int(13 * u)),
                  BLACK if on1 else DGREEN, 'mm', True)

    def aim_label(self, s, text, fx, fy, R, col, size):
        """Подпись точки пересечения — НАД точкой, всегда внутри поля."""
        w = text_size(text, size)[0]
        pad = max(2, int(4 * self.u))
        h = size + 2 * pad
        # центрируем над точкой и прижимаем к верхней границе поля
        x = clamp(fx - w / 2 - pad, R.x + 2, R.right - w - 2 * pad - 2)
        y = fy - h - max(6, int(12 * self.u))
        if y < R.y + 2:                       # точка слишком высоко — снизу
            y = fy + max(6, int(12 * self.u))
        box = pygame.Surface((int(w) + 2 * pad, h), pygame.SRCALPHA)
        box.fill((*PANEL_BG, 225))
        pygame.draw.rect(box, BORDER, box.get_rect(), 1)
        img = font(size).render(text, True, col)
        box.blit(img, (pad, pad))

    def draw_menu_screen(self, s):
        """Заголовки/тексты экрана; сами кнопки уже собраны в build_menu_ui()."""
        name = self.screen_name
        u, W, H = self.u, self.W, self.H
        cx = W // 2
        bh = int(clamp(0.075 * H, 38, 78))
        if name == 'menu':
            t = int(clamp(0.045 * H, 22, 42))
            blit_text(s, 'Тригонометрический', (cx, int(0.15 * H)), t,
                      NAVY, 'mm', True)
            blit_text(s, 'морской бой', (cx, int(0.15 * H) + int(t * 1.2)),
                      t, NAVY, 'mm', True)
            size, lines = self.fit_lines(
                'выстрел — точка пересечения tg и cos (P1) либо ctg и sin (P2)',
                W - 2 * self.M, int(16 * u), int(40 * u))
            blit_text(s, lines[0] if lines else '', (cx, int(0.245 * H)),
                      size, DGRAY, 'mm')
        elif name == 'difficulty':
            # надписей над кнопками режимов больше нет: текст
            # «С компьютером» / «Вдвоём на экране» относился к старому
            # меню и только путал — выбирать надо самими кнопками
            t = int(clamp(0.028 * H, 15, 26))
            blit_text(s, 'Выберите режим игры', (cx, int(0.14 * H)),
                      t, DGRAY, 'mm')
        elif name == 'rules':
            blit_text(s, 'Правила', (cx, int(0.11 * H)),
                      int(clamp(0.034 * H, 18, 32)), NAVY, 'mm', True)
            back_y = H - bh - int(0.05 * H)
            size, lines = self.fit_lines(RULES, W - 2 * self.M,
                                         int(clamp(0.024 * H, 12, 22)),
                                         back_y - int(0.17 * H))
            lh = int(size * 1.45)
            y0 = int(0.17 * H)
            for i, ln in enumerate(lines):
                blit_text(s, ln, (cx, y0 + i * lh), size, BLACK, 'mm')
        elif name == 'settings':
            blit_text(s, 'Настройки', (cx, int(0.11 * H)),
                      int(clamp(0.034 * H, 18, 32)), NAVY, 'mm', True)
        elif name == 'feedback':
            blit_text(s, 'Обратная связь:', (cx, int(0.28 * H)),
                      int(clamp(0.03 * H, 16, 28)), BLACK, 'mm', True)
            blit_text(s, 'konstantinkasatkin2@gmail.com',
                      (cx, int(0.28 * H) + int(0.09 * H)),
                      int(clamp(0.026 * H, 14, 24)), NAVY, 'mm', True)
        elif name == 'victory':
            blit_text(s, getattr(self, 'victory_title', ''), (cx, int(0.28 * H)),
                      int(clamp(0.04 * H, 20, 38)), DGREEN, 'mm', True)
        elif name in ('login', 'register'):
            t = int(clamp(0.034 * H, 18, 32))
            blit_text(s, 'Вход' if name == 'login' else 'Регистрация',
                      (cx, int(0.13 * H)), t, NAVY, 'mm', True)
            hint = ('Один адрес почты — один аккаунт.'
                    if name == 'register'
                    else 'Введите почту и пароль, созданные при регистрации.')
            size, lines = self.fit_lines(hint, W - 2 * self.M,
                                         int(clamp(0.022 * H, 11, 19)),
                                         int(0.24 * H))
            blit_text(s, lines[0] if lines else '', (cx, int(0.205 * H)),
                      size, DGRAY, 'mm')
        elif name == 'profile':
            t = int(clamp(0.034 * H, 18, 32))
            blit_text(s, 'Профиль', (cx, int(0.13 * H)), t, NAVY, 'mm', True)
            st = self.profile_stats()
            if st is not None:
                acc = 100.0 * st['hits'] / st['shots'] if st['shots'] else 0.0
                size, lines = self.fit_lines(
                    '%s\nИгр: %d   Побед: %d   Поражений: %d\n'
                    'Выстрелов: %d   Попаданий: %d   Точность: %.0f%%'
                    % (self.user_state['email'], st['games'], st['wins'],
                       st['losses'], st['shots'], st['hits'], acc),
                    W - 2 * self.M, int(clamp(0.024 * H, 12, 21)),
                    int(0.22 * H))
                for i, ln in enumerate(lines):
                    blit_text(s, ln, (cx, int(0.20 * H) + i *
                                      int(clamp(0.030 * H, 15, 26))),
                              size, BLACK, 'mm', i == 0)
        elif name == 'stats':
            t2 = int(clamp(0.026 * H, 13, 24))
            y = int(0.10 * H)
            for line in self.stats_text():
                head = bool(line) and line.isupper()
                blit_text(s, line, (cx, y), t2,
                          NAVY if head else BLACK, 'mm', head)
                y += int(t2 * 1.5)
        elif name == 'net':
            blit_text(s, 'Игра по сети', (cx, int(0.13 * H)),
                      int(clamp(0.034 * H, 18, 32)), NAVY, 'mm', True)
            size, lines = self.fit_lines(
                'Оба устройства должны быть в одной Wi-Fi или проводной сети.',
                W - 2 * self.M, int(clamp(0.024 * H, 12, 21)),
                int(0.24 * H))
            blit_text(s, lines[0] if lines else '', (cx, int(0.21 * H)),
                      size, DGRAY, 'mm')
        elif name == 'net_host':
            blit_text(s, 'Ваш код игры', (cx, int(0.16 * H)),
                      int(clamp(0.028 * H, 15, 26)), NAVY, 'mm', True)
            code = self.net_code or '—'
            big = int(clamp(0.11 * H, 40, 104))
            box = pygame.Rect(0, 0, int(0.62 * W), int(big * 1.9))
            box.center = (cx, self._net_code_y + int(big))
            pygame.draw.rect(s, WHITE, box, border_radius=10)
            pygame.draw.rect(s, BORDER, box, 2, border_radius=10)
            blit_text(s, code, box.center, big, BLACK, 'mm', True)
            size, lines = self.fit_lines(
                'Пока соперник не подключился. Передайте ему этот код — '
                'он введёт его в пункте «Подключиться по коду».',
                W - 2 * self.M, int(clamp(0.022 * H, 11, 19)),
                int(0.62 * H) - int(0.02 * H))
            for i, ln in enumerate(lines):
                blit_text(s, ln, (cx, int(0.66 * H) + i * int(size * 1.4)),
                          size, DGRAY, 'mm')
            size, lines = self.fit_lines(
                'Ваш IP в этой сети: %s' % (
                    netgame.local_ip() if netgame else '—'),
                W - 2 * self.M, int(clamp(0.022 * H, 11, 19)),
                int(0.86 * H))
            for i, ln in enumerate(lines):
                blit_text(s, ln, (cx, int(0.86 * H) + i * int(size * 1.4)),
                          size, DGRAY, 'mm')
        elif name in ('net_join', 'net_ip'):
            blit_text(s, 'Подключение' if name == 'net_join'
                      else 'Подключение по IP', (cx, int(0.13 * H)),
                      int(clamp(0.034 * H, 18, 32)), NAVY, 'mm', True)
            if self.net is not None and \
                    getattr(self.net, 'status_text', ''):
                size, lines = self.fit_lines(self.net.status_text,
                                             W - 2 * self.M,
                                             int(clamp(0.024 * H, 12, 21)),
                                             int(0.24 * H))
                blit_text(s, lines[0] if lines else '', (cx, int(0.21 * H)),
                          size, NAVY, 'mm')
        for wdg in self.widgets():
            wdg.draw(s)
        self.draw_menu_msg(s)

    def draw_menu_msg(self, s):
        """Показывает последнее сообщение и на экранах меню.

        Без этого ошибка на экране входа или сети была не видна нигде:
        раньше сообщение рисовалось только в шапке игрового экрана, и
        «кнопка не работает» выглядело как молчание.
        """
        text, color = self.msg
        if not text:
            return
        size, lines = self.fit_lines(text, self.W - 2 * self.M,
                                     int(clamp(0.024 * self.H, 11, 20)),
                                     int(0.10 * self.H))
        y = int(0.90 * self.H)
        lh = int(size * 1.35)
        for i, ln in enumerate(lines[-3:]):
            blit_text(s, ln, (self.W // 2, y + i * lh), size, color, 'mm')

    # =========================================================
    #  ПРОФИЛИ: регистрация по почте, вход, ник, статистика
    # =========================================================
    def set_user(self, data):
        """Запомнить вошедшего пользователя."""
        self.user_state.update(user_id=data['id'], nickname=data['nickname'],
                               email=data['email'], logged_in=True)
        self.refresh_menu_ui()
        return self.user_state

    def refresh_menu_ui(self):
        """Пересобрать меню: «Статистика» есть только у вошедших.

        Кнопки меню создаются один раз при запуске, поэтому после входа
        их надо собрать заново — иначе статистика недоступна.
        """
        if not getattr(self, 'screens', None):
            return
        current = self.screen_name
        try:
            self.build_menu_ui()
            self.show_screen(current if current in self.screens else 'menu')
        except Exception:                     # noqa: BLE001
            pass

    def profile_label(self):
        if self.user_state['logged_in']:
            nick = self.user_state['nickname']
            return nick if len(nick) <= 14 else nick[:13] + '…'
        return 'Профиль'

    def open_profile(self):
        """Кнопка в левом верхнем углу: вход, если гость."""
        if self.profile_db is None:
            self.set_msg('Профили недоступны: %s' % self.profile_error, DKRED)
            return
        self.form['password'] = ''
        self.form['password2'] = ''
        if self.user_state['logged_in']:
            self.form['nick'] = self.user_state['nickname']
            self.show_screen('profile')
        else:
            self.show_screen('login')

    def do_login(self):
        try:
            data = self.profile_db.login(self.form['email'],
                                         self.form['password'])
        except Exception as e:                # noqa: BLE001
            self.set_msg(str(e), DKRED)
            return
        self.set_user(data)
        self.form['password'] = ''
        self.set_msg('Здравствуйте, %s!' % data['nickname'], DGREEN)
        self.show_screen('menu')

    def do_register(self):
        if self.form['password'] != self.form['password2']:
            self.set_msg('Пароли не совпадают', DKRED)
            return
        try:
            data = self.profile_db.register(self.form['email'],
                                            self.form['password'],
                                            self.form['nick'])
        except Exception as e:                # noqa: BLE001
            self.set_msg(str(e), DKRED)
            return
        self.set_user(data)
        self.form['password'] = self.form['password2'] = ''
        self.set_msg('Профиль создан. Приятной игры, %s!'
                     % data['nickname'], DGREEN)
        self.show_screen('menu')

    def open_stats(self):
        """Экран статистики игрока."""
        if self.profile_db is None or not self.user_state['logged_in']:
            self.show_screen('login')
            return
        self.show_screen('stats')

    def stats_text(self):
        """Сводка: ходы, попадания, промахи, подсказки, игры, победы."""
        uid = self.user_state.get('user_id')
        if self.profile_db is None or not uid:
            return ('Войдите в профиль, чтобы вести статистику.',)
        st = self.profile_db.get_stats(uid)
        acc = (100.0 * st['hits'] / st['shots']) if st['shots'] else 0.0
        return (
            'ИГРОК: %s' % (self.user_state.get('nickname') or '—'),
            '',
            'Сыграно игр:      %d' % st['games'],
            'Побед:            %d' % st['wins'],
            'Поражений:        %d' % st['losses'],
            '',
            'Ходов сделано:    %d' % st['moves'],
            'Попаданий:        %d' % st['hits'],
            'Промахов:          %d' % st['misses'],
            'Точность:         %.0f%%' % acc,
            'Подсказок взято:  %d' % st['hints'],
        )

    def stat_add(self, key, n=1):
        """Записать действие игрока в статистику."""
        if self.profile_db is None or not self.user_state['logged_in']:
            return
        try:
            self.profile_db.add_stat(self.user_state['user_id'], key, n)
        except Exception:                     # noqa: BLE001
            pass

    def do_rename(self):
        try:
            nick = self.profile_db.change_nickname(
                self.user_state['user_id'], self.form['nick'])
        except Exception as e:                # noqa: BLE001
            self.set_msg(str(e), DKRED)
            return
        self.user_state['nickname'] = nick
        self.set_msg('Никнейм изменён: %s' % nick, DGREEN)
        self.show_screen('profile')

    def do_logout(self):
        try:
            if self.profile_db is not None:
                self.profile_db.logout()
        except Exception:                     # noqa: BLE001
            pass
        self.user_state.update(user_id=None, nickname=None, email=None,
                               logged_in=False)
        self.form['password'] = self.form['password2'] = ''
        self.set_msg('Вы вышли из профиля', NAVY)
        self.refresh_menu_ui()
        self.show_screen('menu')

    def profile_stats(self):
        if self.profile_db is None or not self.user_state['logged_in']:
            return None
        try:
            return self.profile_db.get_stats(self.user_state['user_id'])
        except Exception:                     # noqa: BLE001
            return None

    def _form_submit(self, key, text):
        """Подтверждение поля формы: чистим пробелы, но пароль не трогаем."""
        if key in ('password', 'password2'):
            self.form[key] = text
        else:
            self.form[key] = text.strip()
        if key == 'code' and netgame is not None:
            self.form['code'] = netgame.normalize_code(self.form['code'])
        return self.form[key]

    # =========================================================
    #  ИГРА ПО ЛОКАЛЬНОЙ СЕТИ
    # =========================================================
    def my_nick(self):
        return (self.user_state['nickname']
                or (self.profile_label() if self.user_state['logged_in']
                    else 'Игрок'))

    def net_close(self):
        if self.net is not None:
            self.net.close()
        self.net = None
        self.net_role = None
        self.net_state = 'idle'
        self.net_ready_sent = False
        self.net_peer_ready = False
        self.net_code = ''

    def net_active(self):
        """Идёт ли игра по сети: режим net и назначенная роль."""
        return self.game['mode'] == 'net' and self.net_role is not None

    def net_start_host(self):
        """Создать игру: получаем код, ждём соперника."""
        if netgame is None:
            self.set_msg('Сеть недоступна в этой сборке', DKRED)
            return
        self.net_close()
        try:
            host = netgame.HostServer(self.my_nick())
            host.start_beacon()
        except Exception as e:                # noqa: BLE001
            self.set_msg(str(e), DKRED)
            return
        self.net = host
        self.net_role = 'host'
        self.net_code = host.code
        self.net_state = 'waiting'
        self.show_screen('net_host')
        self.set_msg('Код игры: %s. Передайте его сопернику.' % host.code,
                     NAVY)

    def net_start_client_code(self):
        code = netgame.normalize_code(self.form['code'])
        if len(code) != netgame.CODE_LENGTH:
            self.set_msg('Код состоит из %d символов'
                         % netgame.CODE_LENGTH, DKRED)
            return
        self.net_close()
        try:
            cli = netgame.Client(self.my_nick())
            cli.search_code(code)
        except Exception as e:                # noqa: BLE001
            self.set_msg(str(e), DKRED)
            return
        self.net = cli
        self.net_role = 'client'
        self.net_code = code
        self.net_state = 'waiting'
        self.show_screen('net_join')
        self.set_msg('Ищу соперника с кодом %s...' % code, NAVY)

    def net_start_client_ip(self, port=None):
        """Подключение по IP.

        Порт по умолчанию читается в момент вызова, а не при определении
        функции: иначе его нельзя переопределить, а для проверок и
        нестандартных сетей порт задавать нужно.
        """
        ip = (self.form['ip'] or '').strip()
        if not ip:
            self.set_msg('Введите IP-адрес соперника', DKRED)
            return
        self.net_close()
        try:
            cli = netgame.Client(self.my_nick())
            cli.connect_ip(ip, port or netgame.DEFAULT_TCP_PORT)
        except Exception as e:                # noqa: BLE001
            self.set_msg(str(e), DKRED)
            return
        self.net = cli
        self.net_role = 'client'
        # остаёмся в waiting: переход к расстановке делает _net_poll,
        # и если выставить connected здесь, он не сработает и клиент
        # останется на экране ввода кода
        self.net_state = 'waiting'
        self.show_screen('net_ip')
        self.set_msg('Подключение к %s установлено, ждём соперника...'
                     % ip, DGREEN)

    def net_begin_placement(self):
        """Соединение есть: начинаем расставлять свой флот.

        По сети у каждого игрока ровно одно поле — своё. Левое помечено
        «Вы», правое — ник соперника; флот соперника придёт сразу после
        его подтверждения о готовности.
        """
        # в новом режиме game['mode'] остаётся 'cars', а вид игры
        # (по сети) хранится отдельно — иначе игра перестала бы
        # считаться сетевой и никто бы не ходил
        if getattr(self, 'pending_mode', None) == CAR_MODE:
            # новый режим запускаем через car_start: он ставит фазу
            # 'place', выбирает вид фигур и подписи полей
            self.pending_mode = None
            self.car_start('net', 'player1')
            self.FL['name'] = 'ВАШЕ ПОЛЕ (%s)' % self.my_nick()
            self.FR['name'] = 'ПОЛЕ СОПЕРНИКА: %s' % self.net_peer_nick
        else:
            self.game['mode'] = 'net'
            self.start_trig_ui()
            self.FL['name'] = 'Вы (%s)' % self.my_nick()
            self.FR['name'] = self.net_peer_nick
        # Оба угла и обе точки — свои, поэтому выбор угла и точки
        # остаётся за игроком: хоста — первый, клиента — второй, но
        # выбрать можно любой из двух точек
        self.set_aim_sel(1 if self._net_my_turn() == 'player1' else 2)
        self.set_shot(self._net_my_turn())
        self.reset_game()
        self.show_screen('game')
        self.set_msg('Расставьте флот на ЛЕВОМ поле и нажмите «Готово». '
                     'Соперник делает то же самое.', NAVY)

    def net_cancel(self):
        self.net_close()
        self.set_msg('Соединение закрыто', NAVY)
        self.show_screen('net')

    def _net_poll(self):
        """Разбор входящих сообщений. Вызывается каждый кадр."""
        if self.net is None:
            return
        # хост в ожидании: проверяем, не подключился ли соперник
        if self.net_role == 'host' and self.net_state == 'waiting':
            try:
                if self.net.try_accept():
                    self.net_state = 'connected'
                    self.set_msg('Соперник подключился!', DGREEN)
                    self.net_begin_placement()
            except Exception as e:            # noqa: BLE001
                self.set_msg(str(e), DKRED)
                self.net_close()
                return
        # клиент ищет хост по коду: следим за состоянием поиска
        if self.net_role == 'client' and \
                getattr(self.net, 'status', '') == 'searching' and \
                self.screen_name == 'net_join':
            self.set_msg(self.net.status_text or 'Ищу соперника...', NAVY)
        if getattr(self.net, 'status', '') == 'ready' and \
                self.net_state == 'waiting':
            self.net_state = 'connected'
            self.set_msg('Соперник найден!', DGREEN)
            self.net_begin_placement()

        for msg in self.net.poll():
            # чужие или испорченные данные не должны убивать игру: на
            # устройстве с другой версией протокола формат может отличаться
            try:
                self._net_handle(msg)
            except Exception as e:            # noqa: BLE001
                print('[trigbattle] не понял сообщение %r: %s'
                      % (msg.get('t'), e), flush=True)
                self.set_msg('Сообщение от соперника не распознано, '
                             'пропущено. Возможно, у вас разные версии '
                             'игры.', DKRED)

    def _net_handle(self, msg):
        kind = msg.get('t')
        if kind == 'hello':
            nick = str(msg.get('nick') or 'Соперник')[:16]
            self.net_peer_nick = nick
            self.FR['name'] = nick
            peer_proto = msg.get('proto')
            if (isinstance(peer_proto, int) and \
                    peer_proto != netgame.PROTOCOL_VERSION):
                self.set_msg('Соперник: %s. ВНИМАНИЕ: версии игры '
                             'различаются, игра может идти неправильно — '
                             'обновите оба устройства.' % nick, DKRED)
            else:
                self.set_msg('Соперник: %s' % nick, DGREEN)
        elif kind == 'angles':
            # Углы больше не синхронизируются: у каждого игрока своя
            # пара углов. Сообщение приходит только от старой версии
            # игры — принимать его нельзя, иначе чужой угол утащит наш
            # прицел (такое и было причиной жалоб).
            print('[trigbattle] соперник прислал углы — игнорирую, '
                  'у нас свои', flush=True)
        elif kind == 'ready':
            # флот приходит одним сообщением; в новом режиме это
            # машинки соперника, и едут они по НАШЕМУ полю
            self.net_peer_ready = True
            fld = self.car_my_fld() if self.car_mode() else self.FR
            fld['units'] = []
            for un in netgame.decode_fleet(msg.get('units')):
                # fld — ссылка на наше поле: без неё отрисовка
                # и подсчёт оставшихся кораблей не работают
                un['fld'] = fld
                fld['units'].append(un)
            fld['misses'].clear()
            fld['hints'].clear()
            self._net_maybe_start()
        elif kind == 'car_move':
            self.car_apply_move(msg)
        elif kind == 'car_build':
            self.car_apply_build(msg)
        elif kind == 'shot':
            self._net_incoming(msg)
        elif kind == 'disconnect':
            self.set_msg('Соперник отключился', DKRED)
            self.net_state = 'idle'
            if self.game['phase'] != 'over':
                self.show_screen('net')
        elif kind == 'over':
            if self.game['phase'] != 'over':
                self._net_lose()
        elif kind == 'bye':
            self.net_close()
            self.show_screen('net')

    def net_send_ready(self, again=False, stage=None):
        """Отправляем свой флот и ждём флот соперника.

        В новом режиме передаём только машинки: стены до боя ставить
        нельзя, их соперник увидит сообщениями car_build по ходу игры.
        Свои машинки стоят на поле соперника — отправляем именно их.
        """
        if self.net is None or (self.net_ready_sent and not again):
            return
        fld = self.car_foe_fld() if self.car_mode() else self.FL
        units = [u for u in fld['units']
                 if not self.car_mode() or u['type'] == 'car']
        if not units:
            self.set_msg('Сначала поставьте машинки на поле соперника!',
                         DKRED)
            return
        self.net.send({'t': 'ready',
                       'units': netgame.encode_fleet(units)})
        self.net_ready_sent = True
        self.set_msg('Машинки отправлены. Ждём машинки соперника...', NAVY)
        self._net_maybe_start()

    def _net_maybe_start(self):
        """Оба флота получены — начинаем бой. Ход первого — у хоста."""
        if not (self.net_ready_sent and self.net_peer_ready):
            return
        if self.game['phase'] == 'battle':
            return
        self.net_state = 'battle'
        if self.car_mode():
            self.cars_begin()
            self.show_screen('game')
            return
        self.game['phase'] = 'battle'
        # ходит тот, кто играет за Игрока 1: хост — за первого,
        # клиент — за второго
        first = 'player1' if self.net_role == 'host' else 'player2'
        self.game['turn'] = first
        self.btn_start.label = 'Бой идёт'
        self.game['my_moves'] = 0
        self.game['enemy_moves'] = 0
        self.set_msg('Оба флота на месте. %s'
                     % ('ВАШ ХОД: наведите прицел и «Совершить ход».'
                        if first == 'player1'
                        else 'Ход соперника. Ждём...'), DGREEN)
        self.show_screen('game')
        self.update_angles()

    def _net_fire(self):
        """Выстрел по сети: считаем точку, шлём её, применяем у себя."""
        if self.game['phase'] != 'battle':
            self.set_msg('Сначала расставьте флот и нажмите «Готово»')
            return
        if self.game['turn'] != self._net_my_turn():
            self.set_msg('Сейчас ход соперника', NAVY)
            return
        who = self._net_my_turn()
        # Обе точки (P1 и P2) — наши и независимые, стреляем по той,
        # которую выбрали кнопками «Огонь P1/P2»
        P = self.state[self.shot_sel['p']]
        if P is None:
            self.set_msg('Угол не определён (проверьте tg/ctg)', DKRED)
            return
        target = self.FR              # стреляем по флоту соперника
        px, py = P
        self.net_shots += 1
        if abs(px) > 1 or abs(py) > 1:
            result = 'miss'
            target['misses'].append((round(px, 3), round(py, 3)))
        else:
            result = self.fire_at(target, px, py)
            if result in ('hit', 'sunk'):
                self.net_hits += 1
        res_txt = {'hit': 'ПОПАДАНИЕ!', 'sunk': 'ПОТОПЛЕН!',
                   'miss': 'МИМО'}[result]
        self.game['last'] = res_txt
        self.net.send({'t': 'shot', 'x': px, 'y': py})
        if self.all_sunk(target['units']):
            self._net_win()
            return
        if result in ('hit', 'sunk'):
            self.set_msg('%s Соперник пропускает ход — ходите снова!'
                         % res_txt, DGREEN)
        else:
            self.game['turn'] = 'player2' if who == 'player1' else 'player1'
            self.set_msg('МИМО. Ход соперника...', NAVY)
        self.update_angles()

    def _net_my_turn(self):
        """За какого игрока играем: хост — за первого, клиент — за второго."""
        return 'player1' if self.net_role == 'host' else 'player2'

    def _net_incoming(self, msg):
        """Выстрел соперника по нашему флоту."""
        if self.game['phase'] != 'battle':
            return
        try:
            px = float(msg.get('x', 0.0))
            py = float(msg.get('y', 0.0))
        except (TypeError, ValueError):
            return                       # битые координаты — просто игнор
        result = 'miss'
        if abs(px) <= 1 and abs(py) <= 1:
            result = self.fire_at(self.FL, px, py)
        res_txt = {'hit': 'ПОПАДАНИЕ!', 'sunk': 'ПОТОПЛЕН!',
                   'miss': 'МИМО'}[result]
        if self.all_sunk(self.FL['units']):
            self._net_lose()
            return
        if result == 'miss':
            # промах — ход переходит к нам
            self.game['turn'] = self._net_my_turn()
            self.set_msg('МИМО. %s' % ('ВАШ ХОД.' if self.game['turn'] ==
                                        self._net_my_turn()
                                        else 'Ход соперника...'), NAVY)
        else:
            self.game['turn'] = 'player2' if self._net_my_turn() == \
                'player1' else 'player1'
            self.set_msg('%s Ваш корабль поражён!' % res_txt, DKRED)

    def _net_win(self):
        if self.game['phase'] == 'over':
            return
        self.game['phase'] = 'over'
        self.net_state = 'over'
        won = True
        # сообщаем сопернику явно: он и сам обнаружит потопление по
        # своему флоту, но полагаться на порядок сообщений не нужно
        if self.net is not None:
            self.net.send({'t': 'over', 'winner': 'me'})
        self.set_msg('ПОБЕДА! Флот соперника уничтожен.', DGREEN)
        self.show_victory('Победил %s!' % self.my_nick())

    def _net_lose(self):
        if self.game['phase'] == 'over':
            return
        self.game['phase'] = 'over'
        self.net_state = 'over'
        won = False
        self.set_msg('Ваш флот уничтожен.', DKRED)
        self.show_victory('Победил %s!' % self.net_peer_nick)

    def _net_save_stats(self, won):
        if self.profile_db is None or not self.user_state['logged_in']:
            return
        try:
            self.profile_db.record_game(self.user_state['user_id'], won,
                                        self.net_shots, self.net_hits)
        except Exception:                     # noqa: BLE001
            pass

    # =========================================================
    #  ПОСТРОЕНИЕ ИНТЕРФЕЙСА (адаптивное)
    # =========================================================
    def build_ui(self):
        self.screens = {}
        self.build_menu_ui()
        self.build_game_ui()

    def build_menu_ui(self):
        u, W, H = self.u, self.W, self.H
        bw = int(clamp(0.26 * W, 230, 470))       # ширина кнопок меню
        bh = int(clamp(0.075 * H, 38, 78))        # высота кнопок меню
        bw2 = int(clamp(0.21 * W, 190, 380))      # кнопки выбора режима
        cx, cy = W // 2, H // 2
        back_y = H - bh - int(0.05 * H)

        def btn(lst, x, y, w, h, label, cb, color, size=22, bold=True):
            lst.append(Button(pygame.Rect(int(x), int(y), int(w), int(h)),
                              label, cb, color, int(size * u), bold))
            return lst[-1]

        # Кнопка профиля — только в ГЛАВНОМ меню (левый верхний угол):
        # по ней вход/регистрация, ник и статистика. На остальных
        # экранах её нет, чтобы не мешала.
        def add_profile(lst):
            if self.profile_db is None:
                return
            pw = int(clamp(0.20 * W, 120, 260))
            ph = int(clamp(0.072 * H, 34, 68))
            logged = self.user_state['logged_in']
            lst.insert(0, Button(pygame.Rect(self.M // 2, int(0.035 * H),
                                             pw, ph),
                                 self.profile_label(),
                                 self.open_profile,
                                 LTGREEN if logged else LTSKY,
                                 max(12, int(17 * u)), True))
            if logged:
                # вошедшему игроку — кнопка статистики под профилем
                lst.insert(0, Button(pygame.Rect(
                    self.M // 2, int(0.035 * H) + ph + int(6 * u), pw, ph),
                    'Статистика', self.open_stats, LAVENDER,
                    max(12, int(17 * u))))

        def form_field(lst, key, label, x, y, w, h, masked=False,
                       max_len=40):
            fld = Field(pygame.Rect(x, y, w, h), label,
                        lambda: self.form[key],
                        lambda t: self._form_submit(key, t),
                        size=max(12, int(19 * u)),
                        charset=Field.TEXT, max_len=max_len,
                        text_keypad=True, masked=masked)
            lst.append(fld)
            return fld

        # «Назад» по умолчанию идёт в главное меню; на экранах
        # выбора типа игры — на предыдущий экран
        def back(lst, to=None):
            return btn(lst, cx - bw / 2, back_y, bw, bh, 'Назад',
                        to or (lambda: self.show_screen('menu')),
                        (210, 210, 210), 20)

        # --- главное меню ---
        menu = []
        y = int(0.31 * H)
        for label, cb, col in (
                ('Начать игру', lambda: self.show_screen('difficulty'),
                 LTBLUE),
                ('Правила', lambda: self.show_screen('rules'), LTGREEN),
                ('Настройки', lambda: self.show_screen('settings'), LAVENDER),
                ('Обратная связь', lambda: self.show_screen('feedback'),
                 LTSKY),
                ('Выход', self.quit, (210, 210, 210))):
            btn(menu, cx - bw / 2, y, bw, bh, label, cb, col)
            y += bh + int(0.014 * H)
        self.screens['menu'] = menu
        add_profile(menu)

        # --- выбор режима: сначала игра, потом её вид ---
        diff = []
        bw3 = int(clamp(0.34 * W, 260, 620))
        bh3 = int(clamp(0.14 * H, 60, 130))
        y = int(0.30 * H)
        btn(diff, cx - bw3 / 2, y, bw3, bh3, 'Тригонометрический морской бой',
            lambda: self.show_screen('play_trig'), LTBLUE, 26)
        y += bh3 + int(0.03 * H)
        btn(diff, cx - bw3 / 2, y, bw3, bh3, 'Новый режим',
            lambda: self.show_screen('play_cars'), LTGREEN, 26)
        back(diff)
        self.screens['difficulty'] = diff

        # --- тип игры: одинаковые кнопки у обоих режимов ---
        # «Игра против ИИ», «Игра против игрока», «Туториал»,
        # «Игра по сети» находятся прямо на экране режима, а выбор
        # сложности и роли вынесен на свои экраны.
        trig = []
        y = int(0.22 * H)
        for label, cb, col in (
                ('Игра против ИИ', lambda: self.show_screen('ai_diff'),
                 LTBLUE),
                ('Игра против игрока', self.start_local, LAVENDER),
                ('Туториал', self.start_tutorial, LTSKY),
                ('Игра по сети', lambda: self.show_screen('net'), LTGREEN)):
            btn(trig, cx - bw2 / 2, y, bw2, bh, label, cb, col)
            y += bh + int(0.018 * H)
        back(trig, lambda: self.show_screen('difficulty'))
        self.screens['play_trig'] = trig

        # --- сложность компьютера в тригонометрическом режиме ---
        aidiff = []
        y = int(0.26 * H)
        for label, col in (('Низкий', DIFF_COLORS['Низкий']),
                           ('Средний', DIFF_COLORS['Средний']),
                           ('Высокий', DIFF_COLORS['Высокий'])):
            btn(aidiff, cx - bw2 / 2, y, bw2, bh, label,
                (lambda d=label: self.choose_diff(d)), col)
            y += bh + int(0.018 * H)
        back(aidiff, lambda: self.show_screen('play_trig'))
        self.screens['ai_diff'] = aidiff

        # --- тип игры для нового режима ---
        cars = []
        y = int(0.22 * H)
        for label, cb, col in (
                ('Игра против ИИ', lambda: self.show_screen('cars_role'),
                 LTBLUE),
                ('Игра против игрока', lambda: self.car_start('local'),
                 LAVENDER),
                ('Туториал', self.start_cars_tutorial, LTSKY),
                ('Игра по сети', lambda: self.car_net_open(), LTGREEN)):
            btn(cars, cx - bw2 / 2, y, bw2, bh, label, cb, col)
            y += bh + int(0.018 * H)
        back(cars, lambda: self.show_screen('difficulty'))
        self.screens['play_cars'] = cars

        # --- за кого играем в новом режиме против ИИ ---
        role = []
        y = int(0.26 * H)
        for label, cb, col in (
                ('Я — МАШИНКИ', lambda: self.car_start('ai', 'player1'),
                 LTBLUE),
                ('Я — ПРЕПЯТСТВИЯ', lambda: self.car_start('ai', 'player2'),
                 LAVENDER)):
            btn(role, cx - bw2 / 2, y, bw2, bh, label, cb, col)
            y += bh + int(0.018 * H)
        back(role, lambda: self.show_screen('play_cars'))
        self.screens['cars_role'] = role

        # --- правила / обратная связь ---
        self.screens['rules'] = []
        back(self.screens['rules'])
        self.screens['feedback'] = []
        back(self.screens['feedback'])

        # --- настройки ---
        ch = int(clamp(0.06 * H, 30, 46))
        cbx = int(clamp(0.30 * W, 120, 620))
        step = ch + int(0.018 * H)
        sett = [
            CheckBox(pygame.Rect(cbx, int(0.22 * H), int(30 * u), ch),
                     'Включить самолёты',
                     lambda: self.settings['planes'],
                     lambda v: self.settings.__setitem__('planes', v),
                     int(16 * u)),
            CheckBox(pygame.Rect(cbx, int(0.22 * H) + step, int(30 * u), ch),
                     'Включить музыка' if False else
                     'Включить музыку (будет потом)',
                     lambda: self.settings['music'],
                     lambda v: self.settings.__setitem__('music', v),
                     int(16 * u)),
            CheckBox(pygame.Rect(cbx, int(0.22 * H) + 2 * step, int(30 * u), ch),
                     'Включить подсказки',
                     lambda: self.settings['hints'],
                     lambda v: self.settings.__setitem__('hints', v),
                     int(16 * u)),
        ]
        back(sett)
        self.screens['settings'] = sett

        # --- победа ---
        vic = []
        y = int(0.42 * H)
        btn(vic, cx - bw / 2, y, bw, bh, 'Показать раскладку',
            lambda: self.show_screen('game'), LTGREEN, 22)
        btn(vic, cx - bw / 2, y + bh + int(0.02 * H), bw, bh, 'В меню',
            lambda: self.show_screen('menu'), (210, 210, 210), 22)
        self.screens['victory'] = vic

        self.build_profile_ui(btn, form_field, back, cx, bw, bh)

    # ---------------- ЭКРАНЫ ПРОФИЛЕЙ И СЕТИ ----------------
    def build_profile_ui(self, btn, form_field, back, cx, bw, bh):
        u, W, H = self.u, self.W, self.H
        fw = int(clamp(0.46 * W, 260, 620))       # ширина полей формы
        fh = int(clamp(0.072 * H, 34, 66))
        fx = (W - fw) // 2
        gap = int(0.018 * H)
        y = int(0.29 * H)

        # --- вход ---
        lg = []
        form_field(lg, 'email', 'почта', fx, y, fw, fh, max_len=120)
        y2 = y + fh + gap
        form_field(lg, 'password', 'пароль', fx, y2, fw, fh, masked=True,
                   max_len=64)
        y3 = y2 + fh + gap
        btn(lg, fx, y3, fw // 2 - gap // 2, fh, 'Войти', self.do_login,
            LTGREEN, 20)
        btn(lg, fx + fw // 2 + gap // 2, y3, fw // 2 - gap // 2, fh,
            'Регистрация', lambda: self.show_screen('register'), LTSKY, 20)
        back(lg)
        self.screens['login'] = lg

        # --- регистрация ---
        rg = []
        form_field(rg, 'email', 'почта', fx, y, fw, fh, max_len=120)
        y2 = y + fh + gap
        form_field(rg, 'password', 'пароль', fx, y2, fw, fh, masked=True,
                   max_len=64)
        y3 = y2 + fh + gap
        form_field(rg, 'password2', 'пароль ещё раз', fx, y3, fw, fh,
                   masked=True, max_len=64)
        y4 = y3 + fh + gap
        form_field(rg, 'nick', 'никнейм', fx, y4, fw, fh, max_len=16)
        y5 = y4 + fh + gap
        btn(rg, fx, y5, fw, fh, 'Создать профиль', self.do_register,
            LTBLUE, 20)
        y6 = y5 + fh + gap
        btn(rg, fx, y6, fw, fh, 'Я уже зарегистрирован',
            lambda: self.show_screen('login'), (215, 215, 215), 17)
        back(rg)
        self.screens['register'] = rg

        # --- статистика игрока ---
        stt = []
        yst = int(0.20 * H)
        btn(stt, fx, yst, fw, fh, 'Обновить', self.open_stats, LTBLUE, 19)
        yst += fh + gap
        btn(stt, fx, yst, fw, fh, 'В меню',
            lambda: self.show_screen('menu'), (215, 215, 215), 19)
        self.screens['stats'] = stt

        # --- профиль (вошедший) ---
        pf = []
        y7 = int(0.34 * H)
        form_field(pf, 'nick', 'никнейм', fx, y7, fw, fh, max_len=16)
        y8 = y7 + fh + gap
        btn(pf, fx, y8, fw, fh, 'Сохранить никнейм', self.do_rename,
            LTBLUE, 20)
        y9 = y8 + fh + gap
        btn(pf, fx, y9, fw, fh, 'Выйти из профиля', self.do_logout,
            LTRED, 20)
        back(pf)
        self.screens['profile'] = pf

        # --- сеть: что делать ---
        nt = []
        yn = int(0.28 * H)
        btn(nt, fx, yn, fw, bh, 'Создать игру (получить код)',
            self.net_start_host, LTGREEN, 20)
        yn += bh + gap
        btn(nt, fx, yn, fw, bh, 'Подключиться по коду',
            lambda: self.show_screen('net_join'), LTSKY, 20)
        yn += bh + gap
        btn(nt, fx, yn, fw, bh, 'Подключиться по IP',
            lambda: self.show_screen('net_ip'), LAVENDER, 20)
        back(nt)
        self.screens['net'] = nt

        # --- хост: показ кода ---
        nh = []
        self._net_code_y = int(0.30 * H)
        btn(nh, fx, int(0.62 * H), fw, bh, 'Отмена', self.net_cancel,
            LTRED, 20)
        self.screens['net_host'] = nh

        # --- клиент: ввод кода ---
        nj = []
        form_field(nj, 'code', 'код (5 символов)', fx, y, fw, fh,
                   max_len=5)
        yj = y + fh + gap
        btn(nj, fx, yj, fw, bh, 'Искать соперника',
            self.net_start_client_code, LTGREEN, 20)
        yj += bh + gap
        btn(nj, fx, yj, fw, bh, 'Отмена', self.net_cancel, LTRED, 20)
        back(nj)
        self.screens['net_join'] = nj

        # --- клиент: ввод IP ---
        ni = []
        form_field(ni, 'ip', 'IP соперника', fx, y, fw, fh, max_len=45)
        yi = y + fh + gap
        btn(ni, fx, yi, fw, bh, 'Подключиться', self.net_start_client_ip,
            LTGREEN, 20)
        yi += bh + gap
        btn(ni, fx, yi, fw, bh, 'Отмена', self.net_cancel, LTRED, 20)
        back(ni)
        self.screens['net_ip'] = ni

    def make_buttons(self, y, h, specs, x0, gap, limit):
        """Кнопки в ряд с авто-шириной по тексту; optional-кнопки отбрасываются,
        если до правого края не хватает места (узкие экраны)."""
        out, x = [], x0
        for label, cb, color, size, bold, toggle, optional in specs:
            wpx = font(size, bold).size(label)[0] + int(24 * self.u)
            if optional and x + wpx > limit:
                continue
            out.append(Button(pygame.Rect(int(x), int(y), int(wpx), int(h)),
                              label, cb, color, size, bold, toggle=toggle))
            x += wpx + gap
        return out, x

    def build_game_ui(self):
        u = self.u
        M, GAP = self.M, self.GAP
        y1, h1 = self.R1
        y2, h2 = self.R2
        y3, h3 = self.R3
        y4, h4 = self.R4
        f14, f16, f17 = max(9, int(14 * u)), max(10, int(16 * u)), \
            max(11, int(17 * u))
        gap = int(8 * u)
        # ---------------- ряд 1: углы и прицел ----------------
        small = int(clamp(32 * u, 24, 48))
        val_w = int(76 * u)
        aim_lbl = font(f14, True).size('Прицел:')[0]
        aim_bw = int(clamp(56 * u, 40, 90))
        aim_w = aim_lbl + aim_bw * 2 + gap * 2
        gw = min((self.W - 2 * M - aim_w - 3 * GAP) / 2.0, 470.0 * u)
        gw = max(120.0, gw)
        sw = max(60, int(gw - small * 2 - val_w - 3 * gap))
        sh = min(small, h1 - int(22 * u))
        sy = y1 + int(22 * u) + max(0, (sh - small) // 2)
        self.ang_x, self.ang_val = [], []
        self.sliders = []
        self.row_angles = []
        for i in range(2):
            gx = M + i * (gw + GAP)
            sl = Slider(pygame.Rect(int(gx + small + gap), sy, sw, sh),
                        ANGLE1_0 if i == 0 else ANGLE2_0,
                        on_change=lambda k=i + 1: self.on_slider(k))
            self.sliders.append(sl)
            self.row_angles += [
                Button(pygame.Rect(int(gx), sy, small, small), '−',
                       (lambda s=sl: s.bump(-1))),
                sl,
                Button(pygame.Rect(int(gx + small + gap + sw), sy, small,
                                   small), '+', (lambda s=sl: s.bump(1))),
            ]
            self.ang_x.append(int(gx))
            self.ang_val.append(int(gx + small * 2 + gap * 2 + sw + val_w / 2))
        self.aim_x = int(M + 2 * (gw + GAP))
        self.btn_aim1 = Button(pygame.Rect(self.aim_x + aim_lbl + gap, sy,
                                           aim_bw, small), '1',
                               lambda: self.set_aim_sel(1), LTSKY, f16,
                               True, toggle=True)
        self.btn_aim2 = Button(pygame.Rect(self.btn_aim1.rect.right + gap, sy,
                                           aim_bw, small), '2',
                               lambda: self.set_aim_sel(2), LTSKY, f16,
                               True, toggle=True)
        self.row_angles += [self.btn_aim1, self.btn_aim2]
        self.hint1_x = self.btn_aim2.rect.right + gap

        # ---------------- ряд 2: числовой ввод ----------------
        lab_w = font(f14, True).size('ctg2')[0] + gap
        block = int((self.W - 2 * M) * 0.72) // 4
        box_w = max(70, block - lab_w)
        fh = min(int(46 * u), h2 - int(4 * u))
        fy = y2 + (h2 - fh) // 2
        self.f_sin = Field(pygame.Rect(M + lab_w, fy, box_w, fh), 'sin1',
                           self.sin_txt, self.submit_sin, f17)
        self.f_cos = Field(pygame.Rect(M + block + lab_w, fy, box_w, fh),
                           'cos1', self.cos_txt, self.submit_cos, f17)
        self.f_tg = Field(pygame.Rect(M + 2 * block + lab_w, fy, box_w, fh),
                          'tg2', self.tg_txt, self.submit_tg, f17)
        self.f_ctg = Field(pygame.Rect(M + 3 * block + lab_w, fy, box_w, fh),
                           'ctg2', self.ctg_txt, self.submit_ctg, f17)
        self.keypad = Keypad(self.KP, u)
        self.textpad = TextKeypad(self.KP, u)
        self.hint2_x = M + 4 * block + gap
        self.row_angles += [self.f_sin, self.f_cos, self.f_tg, self.f_ctg]

        # ---------------- ряд 3: стройка ----------------
        reg_lbl = font(f14, True).size('Режим:')[0] + gap
        x = M + reg_lbl
        mode_specs = [('Углы', lambda: self.set_mode('angles'),
                       MODE_COLORS['angles'], f16, True, True, False),
                      ('Корабли', lambda: self.set_mode('ships'),
                       MODE_COLORS['ships'], f16, True, True, False),
                      ('Самолёты', lambda: self.set_mode('planes'),
                       MODE_COLORS['planes'], f16, True, True, False)]
        modes, _ = self.make_buttons(y3 + (h3 - small) // 2, small,
                                     mode_specs, x, gap, self.W - M)
        # на узком экране кнопок режима может не хватить — разбор без
        # падения (см. ряд 4)
        modes = list(modes) + [None] * (3 - len(modes))
        (self.btn_mode_angles, self.btn_mode_ships,
         self.btn_mode_planes) = modes
        x = (self.btn_mode_planes.rect.right if self.btn_mode_planes
             else x) + gap
        self.size_lab_x = x
        x += font(f14, True).size('Размер:')[0] + gap
        self.size_buttons = []
        for i in range(5):
            bw_ = max(int(small), font(f17, True).size(str(i + 1))[0] +
                      int(14 * u))
            self.size_buttons.append(
                Button(pygame.Rect(int(x), y3 + (h3 - small) // 2, bw_, small),
                       str(i + 1), (lambda s=i + 1: self.set_size(s)),
                       WHITE, f17, True, toggle=True))
            x += bw_ + gap
        rest, _ = self.make_buttons(y3 + (h3 - small) // 2, small, [
            ('Поворот', lambda: self.rotate(1), LTGREEN, f16, True, False,
             False),
            ('Удалить', self.delete_selected, LTRED, f16, True, False, False),
            ('Очистить всё', self.clear_field, (215, 215, 215), f16, False,
             False, True)], x, gap, self.W - M)
        # «Очистить всё» необязательная и на узком экране исчезает — разбор без
        # падения (см. ряд 4)
        rest = list(rest) + [None] * (3 - len(rest))
        self.btn_rotate, self.btn_del, self.btn_clear = rest
        self.row_build = [b for b in (self.btn_mode_angles, self.btn_mode_ships,
                                     self.btn_mode_planes) if b is not None]
        self.row_build += self.size_buttons + [b for b in rest
                                               if b is not None]

        # ---------------- ряд 4: бой ----------------
        fire_lbl = font(f14, True).size('Огонь:')[0] + gap
        x = M + fire_lbl
        specs = [('Огонь P1', lambda: self.set_shot('P1'), LTSKY, f16, True,
                  True, False),
                 ('Огонь P2', lambda: self.set_shot('P2'), LTSKY, f16, True,
                  True, False),
                 ('Совершить ход', self.make_move, (255, 232, 150), f17, True,
                  False, False),
                 ('Начать бой', self.advance, LTGREEN, f17, True, False,
                  False),
                 ('Меню', lambda: self.show_screen('menu'), (215, 215, 215),
                  f16, False, False, False),
                 ('Далее', self.on_tut_next, (255, 232, 150), f16, True, False,
                  False),
                 ('Пропустить', self.tut_exit, (215, 215, 215), f16, False,
                  False, True),
                 ('Сброс углов', self.reset_angles, (215, 215, 215), f16,
                  False, False, True),
                  # «Ждать» нужно только новому режиму, поэтому кнопка
                  # необязательная и стоит последней: её отбрасывание на
                  # узком экране не должно сдвигать разбор остальных
                  # (иначе «Начать бой» получал чужую подпись)
                 ('Ждать', self.car_wait, (255, 232, 150), f17, True,
                  False, True)]
        btns, _ = self.make_buttons(y4 + (h4 - small) // 2, small, specs, x,
                                    gap, self.W - M)
        # Кнопки-«необязательные» отбрасываются на узких экранах, поэтому
        # список может оказаться короче: недостающие заменяем пустышками,
        # иначе приложение падает с ValueError при разборе (в книжной
        # ориентации это и происходило).
        btns = list(btns) + [None] * (9 - len(btns))
        (self.btn_shot1, self.btn_shot2, self.btn_move, self.btn_start,
         self.btn_menu, self.btn_tut_next, self.btn_tut_skip,
         self.btn_reset_ang, self.btn_wait) = btns
        for b in (self.btn_tut_next, self.btn_tut_skip):
            if b is not None:
                b.visible = False
        if self.tutorial['active']:         # кнопки туториала на месте
            for b in (self.btn_tut_next, self.btn_tut_skip):
                if b is not None:
                    b.visible = True
        self.row_battle = [b for b in btns if b is not None]

        # ---------------- панель нового режима ----------------
        # Живёт в двух верхних рядах и показывается только в нём:
        # выбор, что ставим (машинки или стены), длина, готовность,
        # «Совершить ход» и выход. Тригонометрии здесь нет вовсе.
        cy3 = y3 + (h3 - small) // 2
        self.btn_car_cars = Button(
            pygame.Rect(0, cy3, max(int(small), 120), small), 'Машинки',
            lambda: self.car_set_kind('car'), LTBLUE, f16, True, toggle=True)
        self.btn_car_walls = Button(
            pygame.Rect(0, cy3, max(int(small), 120), small), 'Стены',
            lambda: self.car_set_kind('wall'), LAVENDER, f16, True,
            toggle=True)
        self.btn_ready = Button(
            pygame.Rect(0, cy3, max(int(small), 150), small), 'Готов',
            self.car_advance, LTGREEN, f16, True)
        self.btn_commit = Button(
            pygame.Rect(0, cy3, max(int(small), 190), small),
            'Совершить ход', self.car_make_move, (255, 232, 150), f16, True)
        self.btn_exit = Button(
            pygame.Rect(0, cy3, max(int(small), 120), small), 'Выход',
            lambda: self.show_screen('menu'), (215, 215, 215), f16)
        self.row_cars = [self.btn_car_cars, self.btn_car_walls,
                         self.btn_ready, self.btn_commit, self.btn_exit]
        for b in self.row_cars:
            b.visible = False

        self.game_widgets = (self.row_angles + self.row_build +
                             self.row_battle)
        self.screens['game'] = self.game_widgets

        self.set_mode(self.mode['name'])
        self.set_size(self.unit_state['size'])
        self.set_shot(self.shot_sel['p'])
        self.set_aim_sel(self.aim_sel)
        self.tut_text = getattr(self, 'tut_text', '')
        self.tut_hl = getattr(self, 'tut_hl', None)

    def reset_angles(self):
        # Оба угла свои — в том числе по сети: соперник присылает только
        # точку выстрела, углы у каждого свои.
        self.sliders[0].set(ANGLE1_0)
        self.sliders[1].set(ANGLE2_0)

    def quit(self):
        self.running = False


# ===================== ТОЧКА ВХОДА =====================

def main():
    app = TrigBattle()
    app.run()


if __name__ == '__main__':
    main()