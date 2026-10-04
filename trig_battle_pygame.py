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

ALL_CELLS = [(round(i * GRID, 2), round(j * GRID, 2))
             for i in range(-16, 17) for j in range(-16, 17)]
SQ_CELLS = [c for c in ALL_CELLS if abs(c[0]) <= 1 and abs(c[1]) <= 1]

RULES = ('1 - Точка в которую вы стреляете, это точка пересечения tg и cos, '
         'либо ctg и sin.\n\n'
         '2 - Корабли и прочие юниты могут стоять как диагонально, так и '
         'вертикально/горизонтально\n\n'
         '3 - Корабли можно ставить лишь в пределах единичной окружности\n\n'
         '4 - Самолеты могут стоять лишь в пределах квадрата, но не в '
         'пределах единичной окружности.\n\n'
         '5 - Точка атаки может быть лишь в границах квадрата\n\n'
         '6 - При попадании по вражескому кораблю враг пропускает ход')

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
        self.win = self.open_display()
        self.layout(self.win.get_width(), self.win.get_height())
        print('[trigbattle] окно %dx%d, u=%.2f, видеодрайвер: %s'
              % (self.W, self.H, self.u,
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
    def layout(self, w, h):
        """Пересчитать все прямоугольники под окно w x h."""
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
        # масштабирования (текст остаётся чётким на любом DPI/экране)
        ww, wh = self.win.get_size()
        if (ww, wh) != (self.W, self.H):
            self.resize(ww, wh)
            self.draw()
        self.win.blit(self.base, (0, 0))
        pygame.display.flip()

    def to_design(self, pos):
        return pos                    # холст == окно, координаты совпадают

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
        if self.game['phase'] == 'over' or self.is_sunk(un):
            return True
        if self.game.get('awaiting_tap') and self.game['phase'] == 'battle':
            return False
        if self.game['mode'] == 'ai':
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

    def on_slider(self, which):
        """Ползунок изменился -> обновляем углы и точки P1/P2."""
        if which == 1:
            self.s1 = self.sliders[0].value
        else:
            self.s2 = self.sliders[1].value
        self.update_angles()
        if self.game['mode'] == 'net' and self.net is not None:
            # формулы P1 и P2 считаются от обоих углов, значит соперник
            # должен знать оба — иначе точки выстрела разойдутся
            self.net.send({'t': 'angles',
                           'a1': round(self.s1, 4),
                           'a2': round(self.s2, 4)})

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
        self.set_angle1(self.nearest_angle(self.sin_angles(v), self.s1), True)
        return self.sin_txt()

    def submit_cos(self, txt):
        v = self.parse_num(txt)
        if v is None or abs(v) > 1:
            return self.cos_txt()
        self.set_angle1(self.nearest_angle(self.cos_angles(v), self.s1), True)
        return self.cos_txt()

    def submit_tg(self, txt):
        v = self.parse_num(txt)
        if v is None:
            return self.tg_txt()
        base = math.degrees(math.atan(v)) % 360
        self.set_angle2(self.nearest_angle([base, (base + 180) % 360],
                                           self.s2), True)
        return self.tg_txt()

    def submit_ctg(self, txt):
        v = self.parse_num(txt)
        if v is None:
            return self.ctg_txt()
        if abs(v) < 1e-12:
            self.set_angle2(self.nearest_angle([90.0, 270.0], self.s2))
        else:
            base = math.degrees(math.atan(1.0 / v)) % 360
            self.set_angle2(self.nearest_angle([base, (base + 180) % 360],
                                              self.s2), True)
        return self.ctg_txt()

    # =========================================================
    #  СТРОЙКА
    # =========================================================
    def build_fld(self):
        """Поле, на котором сейчас идёт стройка."""
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
        return 'plane' if self.mode['name'] == 'planes' else 'ship'

    def unit_color(self, un):
        if un is self.unit_state['selected']:
            return GOLD
        if self.is_sunk(un):
            return RED
        return NAVY if un['type'] == 'ship' else TEAL

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
            return True
        return False

    def advance(self):
        """Кнопка 'Начать бой' / 'Готово'."""
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
        self.game.update(phase='place1', turn='player1', my_moves=0,
                         enemy_moves=0, last='—', awaiting_tap=False,
                         streak={'player1': 0, 'player2': 0})
        self.unit_state.update(selected=None, last=None)
        if self.game['mode'] == 'ai':
            self.btn_start.label = 'Начать бой'
        elif self.game['mode'] == 'net':
            self.btn_start.label = 'Готово'
        else:
            self.btn_start.label = 'Готово (Игрок 1)'
        self.timers.clear()
        self.sliders[0].set(ANGLE1_0)
        self.sliders[1].set(ANGLE2_0)
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
            return self.btn_start.rect
        if key == 'fire':
            return self.btn_move.rect
        if key == 'mode':
            return self.btn_mode_ships.rect.union(self.btn_mode_planes.rect)
        if key == 'rotate':
            return self.btn_rotate.rect
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
    def choose_diff(self, diff):
        self.settings['difficulty'] = diff
        self.game['mode'] = 'ai'
        self.reset_game()
        self.show_screen('game')
        self.set_msg('Сложность: %s. Расставьте флот на ЛЕВОМ поле и '
                     'нажмите "Начать бой"' % diff, NAVY)

    def start_local(self):
        self.game['mode'] = 'local'
        self.reset_game()
        self.show_screen('game')
        self.set_msg('ЛОКАЛЬНАЯ ИГРА. Игрок 1 расставляет юниты на ЛЕВОМ '
                     'поле, затем — "Готово (Игрок 1)"', NAVY)

    def show_victory(self, text):
        self.victory_title = text
        self.show_screen('victory')

    def set_mode(self, name):
        self.mode['name'] = name
        if name == 'planes':
            self.unit_state['size'] = min(self.unit_state['size'],
                                          MAX_SIZE['plane'])
        if name == 'angles':
            self.unit_state['last'] = None
            self.deselect()
        for btn, mn in ((self.btn_mode_angles, 'angles'),
                        (self.btn_mode_ships, 'ships'),
                        (self.btn_mode_planes, 'planes')):
            btn.active = (mn == name)

    def set_shot(self, p):
        self.shot_sel['p'] = p
        self.btn_shot1.active = (p == 'P1')
        self.btn_shot2.active = (p == 'P2')

    def set_aim_sel(self, n):
        self.aim_sel = n
        self.btn_aim1.active = (n == 1)
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

        fld = self.build_fld()
        if fld is None:
            return
        side_name = 'L' if fld is self.FL else 'R'
        if side != side_name or self.mode['name'] not in ('ships', 'planes'):
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
            size = min(self.unit_state['size'], MAX_SIZE[utype])
            pts = self.unit_points(gx, gy, size, self.unit_state['dir_idx'])
            if self.remaining(fld['units'])[utype].get(size, 0) > 0 and \
                    self.points_ok(pts, utype, fld['units']):
                self.place_unit(fld, pts, self.unit_state['dir_idx'], size,
                                utype)
                self.unit_state['last'] = (gx, gy)

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
        blit_text(s, 'ПОЛЕ ИГРОКА 1',
                  (self.br['L'].x + int(8 * u), self.br['L'].y + int(6 * u)),
                  int(13 * u), NAVY, 'lt', True)
        blit_text(s, 'ПОЛЕ ИГРОКА 2',
                  (self.br['R'].x + int(8 * u), self.br['R'].y + int(6 * u)),
                  int(13 * u), NAVY, 'lt', True)

        # --- нижняя подсказка: тоже с переносом по ширине окна ---
        hint = ('Стройка: тап по полю — поставить/выбрать, «Поворот» — '
                'развернуть, 1–5 — размер, «Удалить» — убрать   •   '
                'Бой: тап и ведение пальцем по полю — прицел '
                '(«Прицел: 1 / 2»), поля sin1 cos1 tg2 ctg2 — ввод '
                'с клавиатуры, «Огонь P1/P2» → «Совершить ход»')
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

    def draw_controls(self, s):
        u = self.u
        y1, h1 = self.R1
        y2, h2 = self.R2
        y3, h3 = self.R3
        y4, h4 = self.R4
        # --- ряд 1: углы и выбор прицела ---
        for i, gx in enumerate(self.ang_x):
            blit_text(s, 'Угол %d, °' % (i + 1), (gx, y1 + int(2 * u)),
                      int(14 * u), BLACK, 'lt', True)
        blit_text(s, '%.1f°' % self.s1, (self.ang_val[0], y1 + h1 // 2),
                  int(17 * u), PURPLE, 'mm', True)
        blit_text(s, '%.1f°' % self.s2, (self.ang_val[1], y1 + h1 // 2),
                  int(17 * u), DKORANGE, 'mm', True)
        blit_text(s, 'Прицел:', (self.aim_x, y1 + h1 // 2), int(14 * u),
                  BLACK, 'lm', True)
        hint1 = 'тяните пальцем по полю'
        if self.hint1_x + text_size(hint1, int(13 * u))[0] < self.W - self.M:
            blit_text(s, hint1, (self.hint1_x, y1 + h1 // 2), int(13 * u),
                      DGRAY, 'lm')
        # --- ряд 2: числовой ввод ---
        hint2 = 'коснитесь поля — ввод с экранной клавиатуры'
        if self.hint2_x + text_size(hint2, int(13 * u))[0] < self.W - self.M:
            blit_text(s, hint2, (self.hint2_x, y2 + h2 // 2), int(13 * u),
                      DGRAY, 'lm')
        # --- ряд 3 и 4 ---
        blit_text(s, 'Режим:', (self.M, y3 + h3 // 2), int(14 * u), BLACK,
                  'lm', True)
        blit_text(s, 'Размер:', (self.size_lab_x, y3 + h3 // 2), int(14 * u),
                  BLACK, 'lm', True)
        blit_text(s, 'Огонь:', (self.M, y4 + h4 // 2), int(14 * u), BLACK,
                  'lm', True)
        for row in (self.row_angles, self.row_build, self.row_battle):
            for wdg in row:
                wdg.draw(s)

    def draw_panel(self, s, r, fld, idx):
        u = self.u
        pad = int(10 * u)
        pygame.draw.rect(s, PANEL_BG, r)
        pygame.draw.rect(s, BORDER, r, 1)
        md, ph = self.game['mode'], self.game['phase']
        if idx == 0:
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
        if idx == 1 and md == 'ai' and ph not in ('place1', 'place2'):
            blit_text(s, 'мои ходы: %d' % self.game['my_moves'],
                      (r.x + pad, r.bottom - int(46 * u)),
                      max(11, int(13 * u)), BLACK, 'lt')
            blit_text(s, 'его ходы: %d' % self.game['enemy_moves'],
                      (r.x + pad, r.bottom - int(28 * u)),
                      max(11, int(13 * u)), BLACK, 'lt')
        if idx == 0:
            blit_text(s, 'сложность: %s' % self.settings['difficulty'],
                      (r.x + pad, r.bottom - int(24 * u)),
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

        # оси tg/ctg
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

        # подписи делений: шаг подбирается так, чтобы подписи не слипались
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

        # прицел
        if self.game['phase'] == 'battle' and self.active_side() == side:
            self.draw_aim(s, side, px)


    def draw_aim(self, s, side, px):
        u = self.u
        c1, s1, c2, s2, tg2, ctg2 = self.update_angles()
        R = self.br[side]
        sc = R.width * 0.96 / (2 * LIMIT)
        lw = max(2, int(3 * u))

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
        on1 = self.shot_sel['p'] == 'P1'
        if self.state['P1'] is not None:
            Px, Py = self.state['P1']
            fx, fy = px(Px, Py)
            col = BLACK if on1 else mix(WHITE, BLACK, 0.25)
            draw_star(s, col, fx, fy, star_r, max(2, int(2 * u)))
            self.aim_label(s, 'P1 = (%.2f, %.2f)' % (Px, Py), fx, fy, R,
                           col, lbl_size)
        if self.state['P2'] is not None:
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
            t = int(clamp(0.028 * H, 15, 26))
            blit_text(s, 'С компьютером:', (int(W * 0.28), int(0.14 * H)),
                      t, BLACK, 'mm', True)
            blit_text(s, 'Вдвоём на экране:', (int(W * 0.73), int(0.14 * H)),
                      t, BLACK, 'mm', True)
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
        return self.user_state

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
            self.profile_db.logout()
        except Exception:                     # noqa: BLE001
            pass
        self.user_state.update(user_id=None, nickname=None, email=None,
                               logged_in=False)
        self.form['password'] = self.form['password2'] = ''
        self.set_msg('Вы вышли из профиля', NAVY)
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

    def net_start_client_ip(self):
        ip = (self.form['ip'] or '').strip()
        if not ip:
            self.set_msg('Введите IP-адрес соперника', DKRED)
            return
        self.net_close()
        try:
            cli = netgame.Client(self.my_nick())
            cli.connect_ip(ip)
        except Exception as e:                # noqa: BLE001
            self.set_msg(str(e), DKRED)
            return
        self.net = cli
        self.net_role = 'client'
        self.net_state = 'connected'
        self.show_screen('net_join')
        self.set_msg('Подключение к %s установлено' % ip, DGREEN)

    def net_begin_placement(self):
        """Соединение есть: начинаем расставлять свой флот.

        По сети у каждого игрока ровно одно поле — своё. Левое помечено
        «Вы», правое — ник соперника; флот соперника придёт сразу после
        его подтверждения о готовности.
        """
        self.game['mode'] = 'net'
        self.FL['name'] = 'Вы (%s)' % self.my_nick()
        self.FR['name'] = self.net_peer_nick
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
            self._net_handle(msg)

    def _net_handle(self, msg):
        kind = msg.get('t')
        if kind == 'hello':
            nick = str(msg.get('nick') or 'Соперник')[:16]
            self.net_peer_nick = nick
            self.FR['name'] = nick
            self.set_msg('Соперник: %s' % nick, DGREEN)
        elif kind == 'angles':
            # углы общие: отсюда обе формулы выстрела считаются одинаково
            self.sliders[0].set(msg.get('a1', self.s1), exact=True)
            self.sliders[1].set(msg.get('a2', self.s2), exact=True)
            self.s1, self.s2 = self.sliders[0].value, self.sliders[1].value
            self.update_angles()
        elif kind == 'ready':
            self.net_peer_ready = True
            self.FR['units'] = netgame.decode_fleet(msg.get('units'))
            self.FR['misses'].clear()
            self.FR['hints'].clear()
            self._net_maybe_start()
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

    def net_send_ready(self):
        """Отправляем свой флот и ждём флот соперника."""
        if self.net is None or self.net_ready_sent:
            return
        if not self.FL['units']:
            self.set_msg('Сначала расставьте флот!', DKRED)
            return
        self.net.send({'t': 'ready',
                       'units': netgame.encode_fleet(self.FL['units'])})
        self.net_ready_sent = True
        self.set_msg('Флот отправлен. Ждём флот соперника...', NAVY)
        self._net_maybe_start()

    def _net_maybe_start(self):
        """Оба флота получены — начинаем бой. Ход первого — у хоста."""
        if not (self.net_ready_sent and self.net_peer_ready):
            return
        if self.game['phase'] == 'battle':
            return
        self.net_state = 'battle'
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
        P = self.state['P1'] if who == 'player1' else self.state['P2']
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
        px, py = msg.get('x', 0.0), msg.get('y', 0.0)
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
        self._net_save_stats(won)

    def _net_lose(self):
        if self.game['phase'] == 'over':
            return
        self.game['phase'] = 'over'
        self.net_state = 'over'
        won = False
        self.set_msg('Ваш флот уничтожен.', DKRED)
        self.show_victory('Победил %s!' % self.net_peer_nick)
        self._net_save_stats(won)

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

        # Кнопка профиля живёт в левом верхнем углу КАЖДОГО экрана меню:
        # по ней вход/регистрация, ник и статистика.
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

        back = lambda lst: btn(lst, cx - bw / 2, back_y, bw, bh, 'Назад',
                               lambda: self.show_screen('menu'),
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

        # --- выбор режима ---
        diff = []
        y = int(0.22 * H)
        for label, cb, col in (
                ('Низкий', lambda: self.choose_diff('Низкий'),
                 DIFF_COLORS['Низкий']),
                ('Средний', lambda: self.choose_diff('Средний'),
                 DIFF_COLORS['Средний']),
                ('Высокий', lambda: self.choose_diff('Высокий'),
                 DIFF_COLORS['Высокий'])):
            btn(diff, W * 0.28 - bw2 / 2, y, bw2, bh, label, cb, col)
            y += bh + int(0.018 * H)
        btn(diff, W * 0.73 - bw2 / 2, int(0.22 * H), bw2, int(bh * 1.7),
            'Локальная игра', self.start_local, LAVENDER, 26)
        btn(diff, W * 0.73 - bw2 / 2, int(0.22 * H) + int(bh * 1.7) +
            int(0.018 * H), bw2, int(bh * 1.4), 'Туториал',
            self.start_tutorial, LTSKY, 24)
        btn(diff, W * 0.73 - bw2 / 2, int(0.22 * H) + int(bh * 1.7) +
            int(bh * 1.4) + 2 * int(0.018 * H), bw2, int(bh * 1.4),
            'Игра по сети', lambda: self.show_screen('net'), LTGREEN, 24)
        back(diff)
        self.screens['difficulty'] = diff
        add_profile(diff)

        # --- правила / обратная связь ---
        self.screens['rules'] = []
        back(self.screens['rules'])
        self.screens['feedback'] = []
        back(self.screens['feedback'])
        add_profile(self.screens['rules'])
        add_profile(self.screens['feedback'])

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
        add_profile(sett)

        # --- победа ---
        vic = []
        y = int(0.42 * H)
        btn(vic, cx - bw / 2, y, bw, bh, 'Показать раскладку',
            lambda: self.show_screen('game'), LTGREEN, 22)
        btn(vic, cx - bw / 2, y + bh + int(0.02 * H), bw, bh, 'В меню',
            lambda: self.show_screen('menu'), (210, 210, 210), 22)
        self.screens['victory'] = vic
        add_profile(vic)

        self.build_profile_ui(btn, add_profile, form_field, back, cx, bw, bh)

    # ---------------- ЭКРАНЫ ПРОФИЛЕЙ И СЕТИ ----------------
    def build_profile_ui(self, btn, add_profile, form_field, back, cx, bw, bh):
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
        add_profile(lg)

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
        add_profile(rg)

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
        add_profile(pf)

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
        add_profile(nt)

        # --- хост: показ кода ---
        nh = []
        self._net_code_y = int(0.30 * H)
        btn(nh, fx, int(0.62 * H), fw, bh, 'Отмена', self.net_cancel,
            LTRED, 20)
        self.screens['net_host'] = nh
        add_profile(nh)

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
        add_profile(nj)

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
        add_profile(ni)

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
        self.btn_mode_angles, self.btn_mode_ships, self.btn_mode_planes = \
            self.make_buttons(y3 + (h3 - small) // 2, small, mode_specs, x,
                              gap, self.W - M)[0]
        x = self.btn_mode_planes.rect.right + gap
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
            ('Поверот', lambda: self.rotate(1), LTGREEN, f16, True, False,
             False),
            ('Удалить', self.delete_selected, LTRED, f16, True, False, False),
            ('Очистить всё', self.clear_field, (215, 215, 215), f16, False,
             False, True)], x, gap, self.W - M)
        self.btn_rotate, self.btn_del, self.btn_clear = rest
        self.row_build = [self.btn_mode_angles, self.btn_mode_ships,
                          self.btn_mode_planes] + self.size_buttons + rest

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
                  False, False, True)]
        btns, _ = self.make_buttons(y4 + (h4 - small) // 2, small, specs, x,
                                    gap, self.W - M)
        (self.btn_shot1, self.btn_shot2, self.btn_move, self.btn_start,
         self.btn_menu, self.btn_tut_next, self.btn_tut_skip,
         self.btn_reset_ang) = btns
        self.btn_tut_next.visible = False
        self.btn_tut_skip.visible = False
        if self.tutorial['active']:         # кнопки туториала на месте
            self.btn_tut_next.visible = True
            self.btn_tut_skip.visible = True
        self.row_battle = btns

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