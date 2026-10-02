# -*- coding: utf-8 -*-
"""
ТРИГОНОМЕТРИЧЕСКИЙ МОРСКОЙ БОЙ — Kivy/Android версия.
Игра против ИИ (3 сложности) или локально вдвоём.
"""

import math
import random

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.core.text import Label as CoreLabel
from kivy.graphics import Color, Line, Rectangle, Ellipse
from kivy.metrics import sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.uix.slider import Slider
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

# ===================== КОНСТАНТЫ =====================
GRID = 0.1
LIMIT = 1.6
HIT_TOL = 0.05
FLEET_SHIPS = {1: 5, 2: 4, 3: 3, 4: 2, 5: 1}
FLEET_PLANES = {1: 3, 2: 2, 3: 1}
MAX_SIZE = {'ship': 5, 'plane': 3}
DIRECTIONS = [(1, 0), (1, 1), (0, 1), (-1, 1),
              (-1, 0), (-1, -1), (0, -1), (1, -1)]
SQ_CELLS = [(round(i * GRID, 2), round(j * GRID, 2))
            for i in range(-10, 11) for j in range(-10, 11)]

COL = {
    'ship': (0.10, 0.10, 0.50),
    'plane': (0.0, 0.50, 0.50),
    'sunk': (0.85, 0.1, 0.1),
    'sel': (0.9, 0.75, 0.1),
}

RULES = ('Правила\n\n'
         '1 - Точка в которую вы стреляете, это точка пересечения tg и cos, '
         'либо ctg и sin.\n\n'
         '2 - Корабли и прочие юниты могут стоять как диаганально, так и '
         'вертикально/горизонтально\n\n'
         '3 - Корабли можно ставить лишь в пределах единичной окружности\n\n'
         '4 - Самолеты могут стоять лишь в пределах квадрата, но не в '
         'пределах единичной окружности.\n\n'
         '5 - Точка атаки может быть лишь в границах квадрата\n\n'
         '6 - При попадании по вражескому кораблю враг пропускает ход')


# ===================== ИГРОВАЯ ЛОГИКА =====================
def unit_points(x0, y0, size, dir_idx):
    dx, dy = DIRECTIONS[dir_idx]
    return [(round(x0 + k * dx * GRID, 2), round(y0 + k * dy * GRID, 2))
            for k in range(size)]


def no_touch(pts, units, ignore=None):
    for un in units:
        if un is ignore:
            continue
        for p in pts:
            for q in un['pts']:
                if max(abs(p[0] - q[0]), abs(p[1] - q[1])) <= GRID + 1e-9:
                    return False
    return True


def points_ok(pts, utype, units, ignore=None):
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
    return no_touch(pts, units, ignore)


def is_sunk(un):
    return len(un['pts']) > 0 and len(un['hits']) == len(un['pts'])


def all_sunk(units):
    return len(units) > 0 and all(is_sunk(un) for un in units)


def halo_points(un, units):
    halo = set()
    occupied = {q for o in units for q in o['pts']}
    for px, py in un['pts']:
        for dx in (-GRID, 0.0, GRID):
            for dy in (-GRID, 0.0, GRID):
                if dx == 0 and dy == 0:
                    continue
                q = (round(px + dx, 2), round(py + dy, 2))
                if not (-LIMIT <= q[0] <= LIMIT and -LIMIT <= q[1] <= LIMIT):
                    continue
                if q not in occupied:
                    halo.add(q)
    return halo


def fire_at(fld, Px, Py):
    for un in fld['units']:
        for p in un['pts']:
            if p not in un['hits'] and \
               abs(Px - p[0]) <= HIT_TOL and abs(Py - p[1]) <= HIT_TOL:
                un['hits'].add(p)
                return 'sunk' if is_sunk(un) else 'hit'
    fld['misses'].append((round(Px, 3), round(Py, 3)))
    return 'miss'


def snap(v):
    return round(round(v / GRID) * GRID, 2)


# ===================== ИГРОВОЕ ПОЛЕ (виджет) =====================
class BoardWidget(Widget):
    """Игровое поле в стиле настольной matplotlib-версии."""

    FADE = 0.15   # прозрачность "второстепенных" элементов

    def __init__(self, app, side, **kw):
        super().__init__(**kw)
        self.app = app
        self.side = side
        self.bind(size=lambda *a: self.redraw(),
                  pos=lambda *a: self.redraw())

    # ---------- координаты ----------
    def to_px(self, x, y):
        s = min(self.width, self.height) * 0.96
        cx, cy = self.center_x, self.center_y
        return cx + x / (2 * LIMIT) * s, cy + y / (2 * LIMIT) * s

    def to_data(self, px, py):
        s = min(self.width, self.height) * 0.96
        return ((px - self.center_x) / s * 2 * LIMIT,
                (py - self.center_y) / s * 2 * LIMIT)

    # ---------- текст ----------
    def _texture(self, s, size, color, bold=False):
        lbl = CoreLabel(text=s, font_size=sp(size), color=color,
                        bold=bold, font_name='DejaVuSans')
        lbl.refresh()
        return lbl.texture

    def draw_text(self, x, y, s, color=(0, 0, 0, 1), size=11,
                  anchor='mm', bold=False):
        tex = self._texture(s, size, color, bold)
        w, h = tex.size
        px, py = self.to_px(x, y)
        ox = {'l': 0, 'm': -w / 2, 'r': -w}[anchor[0]]
        oy = {'b': 0, 'm': -h / 2, 't': -h}[anchor[1]]
        Rectangle(texture=tex, pos=(px + ox, py + oy), size=(w, h))

    def panel_px(self, px, py, lines, fg=(0, 0, 0, 1), bg=(1, 1, 1, 0.92),
                 border=(0.5, 0.5, 0.5, 1), anchor='rt', size=10):
        textures = [self._texture(ln, size, fg) for ln in lines]
        w = max(t.size[0] for t in textures) + 12
        h = sum(t.size[1] for t in textures) + 12
        x0 = px - w if 'r' in anchor else px
        y0 = py - h if 't' in anchor else py
        Color(*bg)
        Rectangle(pos=(x0, y0), size=(w, h))
        Color(*border)
        Line(rectangle=(x0, y0, w, h), width=1)
        yy = y0 + 6
        for t in textures:
            Color(*fg)
            Rectangle(texture=t, pos=(x0 + 6, yy), size=t.size)
            yy += t.size[1]

    # ---------- фигуры ----------
    def draw_x(self, px, py, r, w=2.0):
        Line(points=[px - r, py - r, px + r, py + r], width=w)
        Line(points=[px - r, py + r, px + r, py - r], width=w)

    def draw_star(self, px, py, r):
        for ang in (0, 60, 120):
            a = math.radians(ang)
            dx, dy = math.cos(a) * r, math.sin(a) * r
            Line(points=[px - dx, py - dy, px + dx, py + dy], width=2.2)

    def draw_arrow(self, x1, y1, x2, y2, color):
        Color(*color)
        p1 = self.to_px(x1, y1)
        p2 = self.to_px(x2, y2)
        Line(points=[*p1, *p2], width=1.4)
        ang = math.atan2(p2[1] - p1[1], p2[0] - p1[0])
        for da in (2.6, -2.6):
            Line(points=[p2[0], p2[1], p2[0] - 10 * math.cos(ang + da),
                         p2[1] - 10 * math.sin(ang + da)], width=1.4)

    # ---------- основная отрисовка ----------
    def redraw(self):
        app = self.app
        if self.width <= 1:
            return
        fld = app.FL if self.side == 'L' else app.FR
        F = self.FADE
        self.canvas.clear()
        with self.canvas:
            Color(1, 1, 1, 1)
            Rectangle(pos=self.pos, size=self.size)

            # клетки
            Color(0.7, 0.7, 0.7, 0.5)
            for i in range(-16, 17):
                v = i / 10.0
                x1, y1 = self.to_px(v, -LIMIT)
                x2, y2 = self.to_px(v, LIMIT)
                Line(points=[x1, y1, x2, y2], width=0.4)
                x1, y1 = self.to_px(-LIMIT, v)
                x2, y2 = self.to_px(LIMIT, v)
                Line(points=[x1, y1, x2, y2], width=0.4)

            # оси со стрелками (прозрачные)
            self.draw_arrow(-LIMIT, 0, LIMIT, 0, (0, 0, 0, F))
            self.draw_arrow(0, -LIMIT, 0, LIMIT, (0, 0, 0, F))
            self.draw_text(LIMIT - 0.3, -0.12, 'x (ось абсцисс)',
                           (0, 0, 0, F), 9, bold=True)
            self.draw_text(0.06, LIMIT - 0.1, 'y (ось ординат)',
                           (0, 0, 0, F), 9, anchor='lm', bold=True)

            # ось тангенсов / котангенсов (прозрачные)
            Color(1, 0, 0, F)
            Line(points=[*self.to_px(1, -LIMIT), *self.to_px(1, LIMIT)],
                 width=1.5)
            Color(0, 0.7, 0, F)
            Line(points=[*self.to_px(-LIMIT, 1), *self.to_px(LIMIT, 1)],
                 width=1.5)
            self.draw_text(1.0, -LIMIT + 0.04, 'ось тангенсов',
                           (1, 0, 0, F), 8, anchor='mb')
            self.draw_text(-LIMIT + 0.04, 1.05, 'ось котангенсов',
                           (0, 0.6, 0, F), 8, anchor='lb')

            # подписи делений 0.1 (прозрачные), от -1.0 до 1.0
            for i in range(-10, 11):
                v = round(i / 10, 1)
                lbl = f'{v + 0.0:.1f}'
                self.draw_text(v, -0.03, lbl, (0, 0, 0, F), 6.5, anchor='mt')
                self.draw_text(0.02, v, lbl, (0, 0, 0, F), 6.5, anchor='lb')

            # окружность и квадраты (непрозрачные)
            cx, cy = self.to_px(0, 0)
            r = abs(self.to_px(1, 0)[0] - cx)
            Color(0, 0, 0.9, 1)
            Line(circle=(cx, cy, r), width=1.8)
            Color(0, 0, 0, 1)
            p = [self.to_px(-1, -1), self.to_px(1, -1), self.to_px(1, 1),
                 self.to_px(-1, 1)]
            Line(points=[c for pt in p for c in pt], close=True, width=1.8)
            Color(0.4, 0.4, 0.4, 1)
            p = [self.to_px(0, 0), self.to_px(1, 0), self.to_px(1, 1),
                 self.to_px(0, 1)]
            Line(points=[c for pt in p for c in pt], close=True, width=1.2,
                 dash_length=8, dash_offset=4)

            # призрак постройки
            gh = app.ghost_pts(self.side)
            if gh:
                ok = app.ghost_ok(self.side)
                if ok:
                    Color(0.1, 0.8, 0.1, 0.6)
                else:
                    Color(0.9, 0.1, 0.1, 0.6)
                pts = [self.to_px(*q) for q in gh]
                Line(points=[c for pt in pts for c in pt], width=3)
                for px, py in pts:
                    Ellipse(pos=(px - 5, py - 5), size=(10, 10))

            # юниты
            for un in fld['units']:
                if not app.unit_visible(un, fld):
                    continue
                col = COL['sel'] if un is app.unit_state['selected'] else \
                    (COL['sunk'] if is_sunk(un) else COL[un['type']])
                Color(*col, 1)
                pts = [self.to_px(*q) for q in un['pts']]
                Line(points=[c for pt in pts for c in pt], width=3)
                for px, py in pts:
                    if un['type'] == 'ship':
                        Ellipse(pos=(px - 6, py - 6), size=(12, 12))
                    else:
                        Line(points=[px, py + 8, px - 7, py - 6, px + 7,
                                     py - 6], close=True, width=2)

            # серые кресты вокруг потопленных
            Color(0.5, 0.5, 0.5, 1)
            drawn = set()
            for un in fld['units']:
                if is_sunk(un):
                    for q in halo_points(un, fld['units']):
                        if q not in drawn:
                            drawn.add(q)
                            px, py = self.to_px(*q)
                            self.draw_x(px, py, 5, 1.5)

            # промахи
            for m in fld['misses']:
                px, py = self.to_px(*m)
                Color(0.65, 0.65, 0.65, 1)
                Ellipse(pos=(px - 4, py - 4), size=(8, 8))

            # попадания
            Color(0.9, 0.05, 0.05, 1)
            for un in fld['units']:
                for q in un['hits']:
                    px, py = self.to_px(*q)
                    self.draw_x(px, py, 8, 3)

            # прицел в стиле настольной версии
            if app.aim_side() == self.side and \
                    app.game['phase'] == 'battle':
                self.draw_aim(app, cx, cy, r)

    # ---------- прицел (как на ПК) ----------
    def draw_aim(self, app, cx, cy, r_circle):
        F = self.FADE
        a1 = math.radians(app.slider1.value)
        a2 = math.radians(app.slider2.value)
        c1, s1 = math.cos(a1), math.sin(a1)
        c2, s2 = math.cos(a2), math.sin(a2)
        r_arc = r_circle * 0.25

        # --- угол 1: луч, дуга, проекции ---
        Color(0.6, 0.1, 0.8, 1)
        Line(points=[cx, cy, *self.to_px(c1, s1)], width=2)
        Line(circle=(cx, cy, r_arc, 0, app.slider1.value), width=1.2)
        p1x, p1y = self.to_px(c1, s1)
        Ellipse(pos=(p1x - 4, p1y - 4), size=(8, 8))
        self.draw_text(0.34 * math.cos(a1 / 2), 0.34 * math.sin(a1 / 2),
                       f'{int(app.slider1.value)}°', (0.6, 0.1, 0.8, 1), 9)
        Color(0, 0, 1, F)
        Line(points=[*self.to_px(c1, 0), *self.to_px(c1, s1)], width=1.2)
        Line(points=[*self.to_px(0, s1), *self.to_px(c1, s1)], width=1.2)
        self.draw_text(c1 - 0.04, -0.1, f'cos={c1:.2f}', (0, 0, 1, F), 8)
        self.draw_text(-0.03, s1, f'sin={s1:.2f}', (0, 0, 1, F), 8,
                       anchor='rm')

        # --- угол 2: луч, дуга, проекции ---
        Color(0.85, 0.55, 0.0, 1)
        Line(points=[cx, cy, *self.to_px(c2, s2)], width=2)
        Line(circle=(cx, cy, r_arc, 0, app.slider2.value), width=1.2)
        p2x, p2y = self.to_px(c2, s2)
        Ellipse(pos=(p2x - 4, p2y - 4), size=(8, 8))
        self.draw_text(0.34 * math.cos(a2 / 2), 0.34 * math.sin(a2 / 2),
                       f'{int(app.slider2.value)}°', (0.85, 0.55, 0.0, 1), 9)
        Color(0.5, 0.5, 0.5, F)
        Line(points=[*self.to_px(c2, 0), *self.to_px(c2, s2)], width=1.2)
        Line(points=[*self.to_px(0, s2), *self.to_px(c2, s2)], width=1.2)

        # --- линии tg/ctg до границы квадрата (прозрачные) ---
        for c, s in ((c1, s1), (c2, s2)):
            m = max(abs(c), abs(s))
            bx, by = (c / m, s / m) if m > 0 else (0.0, 0.0)
            Color(1, 0, 0, F)
            Line(points=[cx, cy, *self.to_px(bx, by)], width=1.2)
            Color(0, 0.7, 0, F)
            Line(points=[cx, cy, *self.to_px(bx, by)], width=1.2)

        # --- маркеры tg/ctg на осях (прозрачные) ---
        if abs(c2) > 1e-9:
            tg2 = s2 / c2
            if abs(tg2) <= LIMIT:
                px, py = self.to_px(1, tg2)
                Color(1, 0, 0, F)
                Line(rectangle=(px - 4, py - 4, 8, 8), width=1.6)
        if abs(s2) > 1e-9:
            ctg2 = c2 / s2
            if abs(ctg2) <= LIMIT:
                px, py = self.to_px(ctg2, 1)
                Color(0, 0.7, 0, F)
                Line(points=[px, py + 5, px - 4, py - 3, px + 4, py - 3],
                     close=True, width=1.6)

        # --- точки пересечения P1 / P2 ---
        if app.state['P1'] is not None:
            Px, Py = app.state['P1']
            if -LIMIT <= Px <= LIMIT and -LIMIT <= Py <= LIMIT:
                px, py = self.to_px(Px, Py)
                Color(0, 0, 0, 1)
                self.draw_star(px, py, 10)
                self.draw_text(Px + 0.05, Py,
                               f'P₁ = ({Px:.2f}, {Py:.2f})',
                               (0, 0, 0, 1), 8, anchor='lm', bold=True)
        if app.state['P2'] is not None:
            Qx, Qy = app.state['P2']
            if -LIMIT <= Qx <= LIMIT and -LIMIT <= Qy <= LIMIT:
                px, py = self.to_px(Qx, Qy)
                Color(0, 0.5, 0.15, 1)
                self.draw_star(px, py, 10)
                self.draw_text(Qx + 0.05, Qy,
                               f'P₂ = ({Qx:.2f}, {Qy:.2f})',
                               (0, 0.5, 0.15, 1), 8, anchor='lm', bold=True)

        # --- инфо-панель (как на ПК) ---
        tg2s = f'{s2 / c2: .2f}' if abs(c2) > 1e-9 else '   —'
        ctg2s = f'{c2 / s2: .2f}' if abs(s2) > 1e-9 else '   —'
        p1s = (f'({app.state["P1"][0]: .2f}, {app.state["P1"][1]: .2f})'
               if app.state['P1'] else 'нет')
        p2s = (f'({app.state["P2"][0]: .2f}, {app.state["P2"][1]: .2f})'
               if app.state['P2'] else 'нет')
        lines = [
            f'угол 1 = {app.slider1.value:5.1f}°',
            f'  sin={s1: .2f} cos={c1: .2f}',
            f'угол 2 = {app.slider2.value:5.1f}°',
            f'  tg ={tg2s} ctg={ctg2s}',
            f'P₁ = {p1s}',
            f'P₂ = {p2s}',
        ]
        self.panel_px(self.x + self.width - 6, self.y + self.height - 6,
                      lines, anchor='rt', size=9)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.app.board_touch(self.side, touch, 'down')
            return True
        return False

    def on_touch_move(self, touch):
        if self.collide_point(*touch.pos):
            self.app.board_touch(self.side, touch, 'move')
            return True
        return False

    def on_touch_up(self, touch):
        if self.collide_point(*touch.pos):
            self.app.board_touch(self.side, touch, 'up')
            return True
        return False


# ===================== ПРИЛОЖЕНИЕ =====================
class TrigBattleApp(App):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.settings = {'planes': True, 'music': False,
                         'difficulty': 'Средний'}
        self.game = {'mode': 'ai', 'phase': 'place1', 'turn': 'player1',
                     'my_moves': 0, 'enemy_moves': 0, 'last': '—'}
        self.FL = {'units': [], 'misses': []}
        self.FR = {'units': [], 'misses': []}
        self.unit_state = {'size': 3, 'dir_idx': 0, 'selected': None,
                           'last': None}
        self.mode = 'ships'          # angles / ships / planes
        self.shot_sel = 'P1'
        self.aim_sel = 1
        self.state = {'P1': None, 'P2': None}
        self.enemy_ai = {'tried': set(), 'hunt': [], 'thits': []}
        self._built = False

    # ---------- вспомогательное ----------
    def fleets(self):
        return dict(FLEET_SHIPS), \
            (dict(FLEET_PLANES) if self.settings['planes'] else {})

    def remaining(self, units):
        fsh, fpl = self.fleets()
        rem = {'ship': fsh, 'plane': fpl}
        for un in units:
            rem[un['type']][un['size']] -= 1
        return rem

    def unit_visible(self, un, fld):
        g = self.game
        if g['phase'] == 'over' or is_sunk(un):
            return True
        if g['mode'] == 'ai':
            return fld is self.FL
        if g['phase'] == 'place1':
            return fld is self.FL
        if g['phase'] == 'place2':
            return fld is self.FR
        return (fld is self.FL) == (g['turn'] == 'player1')

    def build_fld(self):
        return {'place1': self.FL, 'place2': self.FR}.get(
            self.game['phase'])

    def build_side(self):
        return {'place1': 'L', 'place2': 'R'}.get(self.game['phase'])

    def aim_side(self):
        if self.game['mode'] == 'ai' or self.game['turn'] == 'player1':
            return 'R'
        return 'L'

    def target_fld(self):
        return self.FR if self.aim_side() == 'R' else self.FL

    def ghost_pts(self, side):
        if side != self.build_side() or self.mode not in ('ships',
                                                          'planes') or \
           self.unit_state['last'] is None:
            return None
        gx, gy = self.unit_state['last']
        size = min(self.unit_state['size'], MAX_SIZE[self.utype()])
        return unit_points(gx, gy, size, self.unit_state['dir_idx'])

    def ghost_ok(self, side):
        fld = self.build_fld()
        pts = self.ghost_pts(side)
        if not pts or fld is None:
            return False
        ut = self.utype()
        size = min(self.unit_state['size'], MAX_SIZE[ut])
        return points_ok(pts, ut, fld['units']) and \
            self.remaining(fld['units'])[ut].get(size, 0) > 0

    def utype(self):
        return 'plane' if self.mode == 'planes' else 'ship'

    # ---------- UI helpers ----------
    def set_msg(self, text, color=(0, 0, 0, 1)):
        self.msg.text = text
        self.msg.color = color

    def mark_toggle(self, buttons, active_idx, color=(0.4, 0.7, 1, 1)):
        for i, b in enumerate(buttons):
            b.background_color = color if i == active_idx else (1, 1, 1, 1)

    # ---------- экраны ----------
    def make_menu_screen(self, name, title, items):
        scr = Screen(name=name)
        lay = BoxLayout(orientation='vertical', padding=40, spacing=12)
        lay.add_widget(Label(text=title, font_size='28sp', bold=True,
                             color=(0, 0, 0.5, 1), size_hint_y=0.3))
        for text, cb in items:
            b = Button(text=text, font_size='18sp', size_hint_y=None,
                       height='60dp')
            b.bind(on_release=cb)
            lay.add_widget(b)
        scr.add_widget(lay)
        return scr

    def build(self):
        Window.clearcolor = (0.94, 0.94, 0.94, 1)
        self.sm = ScreenManager()

        # --- меню ---
        self.sm.add_widget(self.make_menu_screen(
            'menu', 'Тригонометрический\nморской бой', [
                ('Начать игру', lambda *_: self.go('difficulty')),
                ('Правила', lambda *_: self.go('rules')),
                ('Настройки', lambda *_: self.go('settings')),
                ('Обратная связь', lambda *_: self.go('feedback')),
            ]))

        # --- сложность / режим ---
        self.sm.add_widget(self.make_menu_screen(
            'difficulty', 'С компьютером или вдвоём?', [
                ('Низкий', lambda *_: self.start_ai('Низкий')),
                ('Средний', lambda *_: self.start_ai('Средний')),
                ('Высокий', lambda *_: self.start_ai('Высокий')),
                ('Локальная игра', lambda *_: self.start_local()),
                ('Назад', lambda *_: self.go('menu')),
            ]))

        # --- правила ---
        scr = Screen(name='rules')
        lay = BoxLayout(orientation='vertical', padding=30, spacing=10)
        rules_lbl = Label(text=RULES, font_size='15sp',
                          color=(0, 0, 0, 1), halign='left', valign='top')
        rules_lbl.bind(size=lambda i, v: setattr(i, 'text_size', v))
        lay.add_widget(rules_lbl)
        b = Button(text='Назад', size_hint_y=None, height='55dp')
        b.bind(on_release=lambda *_: self.go('menu'))
        lay.add_widget(b)
        scr.add_widget(lay)
        self.sm.add_widget(scr)

        # --- настройки ---
        scr = Screen(name='settings')
        lay = BoxLayout(orientation='vertical', padding=40, spacing=14)
        lay.add_widget(Label(text='Настройки', font_size='24sp', bold=True,
                             color=(0, 0, 0, 1), size_hint_y=0.25))
        self.cb_planes = self._setting_row(lay, 'Включить самолеты',
                                           self.settings['planes'],
                                           lambda v: self.settings.
                                           __setitem__('planes', v))
        self.cb_music = self._setting_row(lay, 'Включить музыку '
                                               '(будет потом)',
                                          self.settings['music'],
                                          lambda v: self.settings.
                                          __setitem__('music', v))
        b = Button(text='Назад', size_hint_y=None, height='55dp')
        b.bind(on_release=lambda *_: self.go('menu'))
        lay.add_widget(b)
        scr.add_widget(lay)
        self.sm.add_widget(scr)

        # --- обратная связь ---
        self.sm.add_widget(self.make_menu_screen(
            'feedback', 'Обратная связь:\n\n'
            'konstantinkasatkin2@gmail.com',
            [('Назад', lambda *_: self.go('menu'))]))

        # --- игра ---
        self.sm.add_widget(self.make_game_screen())
        self.go('menu')
        self._built = True
        return self.sm

    def _setting_row(self, parent, label, initial, setter):
        from kivy.uix.checkbox import CheckBox
        row = BoxLayout(size_hint_y=None, height='50dp', spacing=10)
        cb = CheckBox(active=initial, size_hint_x=None, width='50dp')
        cb.bind(active=lambda inst, v: setter(v))
        row.add_widget(cb)
        row.add_widget(Label(text=label, font_size='17sp',
                             color=(0, 0, 0, 1), halign='left'))
        parent.add_widget(row)
        return cb

    def make_game_screen(self):
        scr = Screen(name='game')
        root = BoxLayout(orientation='vertical', padding=4, spacing=3)

        self.msg = Label(text='', size_hint_y=0.055, font_size='15sp',
                         bold=True, color=(0, 0, 0, 1))
        root.add_widget(self.msg)

        mid = BoxLayout(size_hint_y=0.585, spacing=6)
        self.boardL = BoardWidget(self, 'L')
        self.boardR = BoardWidget(self, 'R')
        self.panelL = Label(text='', size_hint_x=0.18, font_size='12sp',
                            color=(0, 0, 0, 1), halign='left',
                            valign='top', font_name='DejaVuSans')
        self.panelR = Label(text='', size_hint_x=0.18, font_size='12sp',
                            color=(0, 0, 0, 1), halign='left',
                            valign='top', font_name='DejaVuSans')
        self.panelL.bind(size=lambda i, v: setattr(i, 'text_size', v))
        self.panelR.bind(size=lambda i, v: setattr(i, 'text_size', v))
        mid.add_widget(self.panelL)
        mid.add_widget(self.boardL)
        mid.add_widget(self.boardR)
        mid.add_widget(self.panelR)
        root.add_widget(mid)

        ctrl = GridLayout(rows=4, size_hint_y=0.36, spacing=2)

        # ряд 1: слайдеры углов
        r1 = BoxLayout(spacing=4)
        r1.add_widget(self._lab('Угол 1', 0.09))
        self.slider1 = Slider(min=0, max=360, value=50)
        self.slider1.bind(value=self.on_slider)
        self.l_ang1 = self._lab('50°', 0.07)
        r1.add_widget(self.slider1)
        r1.add_widget(self.l_ang1)
        r1.add_widget(self._lab('Угол 2', 0.09))
        self.slider2 = Slider(min=0, max=360, value=110)
        self.slider2.bind(value=self.on_slider)
        self.l_ang2 = self._lab('110°', 0.07)
        r1.add_widget(self.slider2)
        r1.add_widget(self.l_ang2)
        ctrl.add_widget(r1)

        # ряд 2: численный ввод
        r2 = BoxLayout(spacing=3)
        self.tb_sin = self._input(r2, 'sin₁', '0.77')
        self.tb_cos = self._input(r2, 'cos₁', '0.64')
        self.tb_tg = self._input(r2, 'tg₂', '-2.75')
        self.tb_ctg = self._input(r2, 'ctg₂', '-0.36')
        ctrl.add_widget(r2)

        # ряд 3: режим стройки
        r3 = BoxLayout(spacing=3)
        self.b_mode_angles = Button(text='Углы')
        self.b_mode_ships = Button(text='Корабли')
        self.b_mode_planes = Button(text='Самолёты')
        self.b_mode_angles.bind(on_release=lambda *_: self.set_mode('angles'))
        self.b_mode_ships.bind(on_release=lambda *_: self.set_mode('ships'))
        self.b_mode_planes.bind(on_release=lambda *_: self.set_mode('planes'))
        for b in (self.b_mode_angles, self.b_mode_ships,
                  self.b_mode_planes):
            r3.add_widget(b)
        self.size_buttons = []
        for s in range(1, 6):
            b = Button(text=str(s))
            b.bind(on_release=lambda _i, s=s: self.set_size(s))
            self.size_buttons.append(b)
            r3.add_widget(b)
        self.b_rot = Button(text='⟳')
        self.b_rot.bind(on_release=lambda *_: self.rotate(1))
        self.b_del = Button(text='Удалить')
        self.b_del.bind(on_release=lambda *_: self.delete_selected())
        r3.add_widget(self.b_rot)
        r3.add_widget(self.b_del)
        ctrl.add_widget(r3)

        # ряд 4: бой
        r4 = BoxLayout(spacing=3)
        self.b_shot1 = Button(text='Огонь P₁')
        self.b_shot2 = Button(text='Огонь P₂')
        self.b_shot1.bind(on_release=lambda *_: self.set_shot('P1'))
        self.b_shot2.bind(on_release=lambda *_: self.set_shot('P2'))
        self.b_aim1 = Button(text='Прицел ∠1')
        self.b_aim2 = Button(text='Прицел ∠2')
        self.b_aim1.bind(on_release=lambda *_: self.set_aim_sel(1))
        self.b_aim2.bind(on_release=lambda *_: self.set_aim_sel(2))
        self.b_move = Button(text='Совершить ход',
                             background_color=(1, 0.85, 0.4, 1))
        self.b_move.bind(on_release=lambda *_: self.make_move())
        self.b_start = Button(text='Начать бой',
                              background_color=(0.6, 0.95, 0.6, 1))
        self.b_start.bind(on_release=lambda *_: self.advance())
        self.b_menu = Button(text='Меню')
        self.b_menu.bind(on_release=lambda *_: self.go('menu'))
        for b in (self.b_shot1, self.b_shot2, self.b_aim1, self.b_aim2,
                  self.b_move, self.b_start, self.b_menu):
            r4.add_widget(b)
        ctrl.add_widget(r4)

        root.add_widget(ctrl)
        scr.add_widget(root)

        self.set_mode('angles')
        self.set_shot('P1')
        self.set_aim_sel(1)
        self.set_size(3)
        return scr

    def _lab(self, text, sx=None):
        l = Label(text=text, color=(0, 0, 0, 1), font_size='13sp')
        if sx:
            l.size_hint_x = sx
        return l

    def _input(self, parent, label, initial):
        parent.add_widget(self._lab(label, 0.12))
        tb = TextInput(text=initial, multiline=False, font_size='15sp',
                       input_filter='float', padding_y=[8, 0])
        tb.bind(on_text_validate=self.on_value_input)
        parent.add_widget(tb)
        return tb

    # ---------- стартовые сценарии ----------
    def go(self, name):
        self.sm.current = name
        if name == 'game':
            self.redraw_all()

    def start_ai(self, diff):
        self.settings['difficulty'] = diff
        self.game['mode'] = 'ai'
        self.reset_game()
        self.go('game')
        self.set_msg(f'Сложность: {diff}. Расставьте флот на ЛЕВОМ поле, '
                     f'затем "Начать бой"', (0, 0, 0.5, 1))

    def start_local(self):
        self.game['mode'] = 'local'
        self.reset_game()
        self.go('game')
        self.set_msg('ЛОКАЛЬНАЯ ИГРА. Игрок 1 расставляет юниты на ЛЕВОМ '
                     'поле', (0, 0, 0.5, 1))

    def reset_game(self):
        self.FL = {'units': [], 'misses': []}
        self.FR = {'units': [], 'misses': []}
        self.enemy_ai = {'tried': set(), 'hunt': [], 'thits': []}
        self.game.update(phase='place1', turn='player1', my_moves=0,
                         enemy_moves=0, last='—')
        self.unit_state.update(selected=None, last=None)
        self.b_start.text = 'Начать бой' if self.game['mode'] == 'ai' \
            else 'Готово (Игрок 1)'
        self.slider1.value = 50
        self.slider2.value = 110
        self.set_mode('angles')
        self.update_aim()
        self.redraw_all()

    # ---------- UI-состояние ----------
    def set_mode(self, m):
        self.mode = m
        self.mark_toggle([self.b_mode_angles, self.b_mode_ships,
                          self.b_mode_planes],
                         {'angles': 0, 'ships': 1, 'planes': 2}[m])
        if m == 'planes':
            self.set_size(min(self.unit_state['size'], 3))
        self.redraw_all()

    def set_size(self, s):
        self.unit_state['size'] = s
        for i, b in enumerate(self.size_buttons, 1):
            b.background_color = (0.4, 0.7, 1, 1) if i == s else (1, 1, 1, 1)

    def set_shot(self, p):
        self.shot_sel = p
        self.mark_toggle([self.b_shot1, self.b_shot2],
                         0 if p == 'P1' else 1, (1, 0.75, 0.4, 1))

    def set_aim_sel(self, n):
        self.aim_sel = n
        self.mark_toggle([self.b_aim1, self.b_aim2], n - 1,
                         (0.75, 0.5, 0.9, 1))

    def on_slider(self, *_):
        self.l_ang1.text = f'{int(self.slider1.value)}°'
        self.l_ang2.text = f'{int(self.slider2.value)}°'
        self.update_aim()

    def on_value_input(self, tb):
        try:
            v = float(tb.text.replace(',', '.'))
        except ValueError:
            return
        a1 = math.radians(self.slider1.value)
        if tb is self.tb_sin and abs(v) <= 1:
            self.slider1.value = math.degrees(
                math.atan2(v, math.cos(a1))) % 360
        elif tb is self.tb_cos and abs(v) <= 1:
            self.slider1.value = math.degrees(
                math.atan2(math.sin(a1), v)) % 360
        else:
            ref = self.slider2.value
            if tb is self.tb_tg:
                base = math.degrees(math.atan(v)) % 360
            elif tb is self.tb_ctg and abs(v) > 1e-12:
                base = math.degrees(math.atan(1 / v)) % 360
            elif tb is self.tb_ctg:
                self.slider2.value = min([90, 270],
                                         key=lambda a: abs(
                                             (a - ref + 180) % 360 - 180))
                return
            else:
                return
            self.slider2.value = min([base, (base + 180) % 360],
                                     key=lambda a: abs(
                                         (a - ref + 180) % 360 - 180))

    # ---------- прицел ----------
    def update_aim(self):
        a1 = math.radians(self.slider1.value)
        a2 = math.radians(self.slider2.value)
        c1, s1 = math.cos(a1), math.sin(a1)
        c2, s2 = math.cos(a2), math.sin(a2)
        self.state['P1'] = (c1, s2 / c2 * c1) if abs(c2) > 1e-9 else None
        self.state['P2'] = (c2 / s2 * s1, s1) if abs(s2) > 1e-9 else None
        if self._built:
            self.boardL.redraw()
            self.boardR.redraw()

    # ---------- касания ----------
    def board_touch(self, side, touch, phase):
        if self.sm.current != 'game':
            return
        dx, dy = (self.boardL if side == 'L' else self.boardR).\
            to_data(*touch.pos)

        if self.game['phase'] == 'battle' and side == self.aim_side():
            ang = math.degrees(math.atan2(dy, dx)) % 360
            (self.slider1 if self.aim_sel == 1 else
             self.slider2).value = ang
            return

        fld = self.build_fld()
        if fld is None or side != self.build_side() or \
           self.mode not in ('ships', 'planes'):
            return
        gx, gy = snap(dx), snap(dy)
        if phase == 'down':
            un = self.unit_at(fld, dx, dy)
            if un is not None:
                self.unit_state['selected'] = un
            else:
                self.unit_state['selected'] = None
                ut = self.utype()
                size = min(self.unit_state['size'], MAX_SIZE[ut])
                pts = unit_points(gx, gy, size, self.unit_state['dir_idx'])
                if self.remaining(fld['units'])[ut].get(size, 0) > 0 and \
                   points_ok(pts, ut, fld['units']):
                    fld['units'].append(
                        {'type': ut, 'pts': pts,
                         'dir': self.unit_state['dir_idx'], 'size': size,
                         'hits': set()})
            self.update_panels()
            self.redraw_all()
        elif phase == 'move':
            self.unit_state['last'] = (gx, gy)
            (self.boardL if side == 'L' else self.boardR).redraw()

    def unit_at(self, fld, x, y, tol=0.06):
        for un in reversed(fld['units']):
            for px, py in un['pts']:
                if abs(px - x) <= tol and abs(py - y) <= tol:
                    return un
        return None

    def rotate(self, step):
        un = self.unit_state['selected']
        if un is None:
            self.unit_state['dir_idx'] = \
                (self.unit_state['dir_idx'] + step) % 8
        else:
            x0, y0 = un['pts'][0]
            nd = (un['dir'] + step) % 8
            fld = self.FL if un in self.FL['units'] else self.FR
            new_pts = unit_points(x0, y0, un['size'], nd)
            if points_ok(new_pts, un['type'], fld['units'], ignore=un):
                un['pts'] = new_pts
                un['dir'] = nd
        self.redraw_all()

    def delete_selected(self):
        un = self.unit_state['selected']
        if un is None:
            return
        for fld in (self.FL, self.FR):
            if un in fld['units']:
                fld['units'].remove(un)
        self.unit_state['selected'] = None
        self.update_panels()
        self.redraw_all()

    # ---------- бой ----------
    def advance(self):
        g = self.game
        if g['phase'] == 'place1':
            if not self.FL['units']:
                self.set_msg('Игрок 1: постройте хотя бы один юнит!',
                             (0.7, 0, 0, 1))
                return
            if g['mode'] == 'ai':
                self.enemy_place()
                g['phase'] = 'battle'
                g['turn'] = 'player1'
                self.b_start.text = 'Бой идёт'
                self.set_msg('ВАШ ХОД: цельтесь на правом поле и жмите '
                             '"Совершить ход"', (0, 0.5, 0, 1))
            else:
                g['phase'] = 'place2'
                self.b_start.text = 'Готово (Игрок 2)'
                self.set_msg('Игрок 2 расставляет юниты на ПРАВОМ поле. '
                             'Поле игрока 1 скрыто.', (0, 0, 0.5, 1))
        elif g['phase'] == 'place2':
            if not self.FR['units']:
                self.set_msg('Игрок 2: постройте хотя бы один юнит!',
                             (0.7, 0, 0, 1))
                return
            g['phase'] = 'battle'
            g['turn'] = 'player1'
            self.b_start.text = 'Бой идёт'
            self.set_msg('ХОД ИГРОКА 1 (прицел на правом поле)',
                         (0, 0.5, 0, 1))
        else:
            return
        self.unit_state.update(selected=None, last=None)
        self.update_panels()
        self.update_aim()
        self.redraw_all()

    def make_move(self):
        g = self.game
        if g['phase'] != 'battle':
            self.set_msg('Сначала завершите расстановку юнитов!')
            return
        if g['mode'] == 'ai' and g['turn'] != 'player1':
            return

        P = self.state['P1'] if self.shot_sel == 'P1' else self.state['P2']
        if P is None:
            self.set_msg(f'Точка {self.shot_sel} не определена')
            return

        target = self.target_fld()
        shooter = 'Вы' if g['mode'] == 'ai' else \
            ('Игрок 1' if g['turn'] == 'player1' else 'Игрок 2')

        if abs(P[0]) > 1 or abs(P[1]) > 1:
            result = 'miss'
            res_txt = 'МИМО (вне квадрата)'
            target['misses'].append((round(P[0], 3), round(P[1], 3)))
        else:
            result = fire_at(target, P[0], P[1])
            res_txt = {'hit': 'ПОПАДАНИЕ!', 'sunk': 'ПОТОПЛЕН!',
                       'miss': 'МИМО'}[result]
        g['my_moves'] += 1
        g['last'] = res_txt

        if all_sunk(target['units']):
            g['phase'] = 'over'
            self.set_msg(f'{shooter.upper()} ПОБЕДИЛ(А)!',
                         (0, 0.5, 0, 1))
            self.update_panels()
            self.redraw_all()
            return

        # ПРАВИЛО 6: попадание -> соперник пропускает ход
        extra_turn = result in ('hit', 'sunk')

        if g['mode'] == 'ai':
            if extra_turn:
                self.set_msg(f'{res_txt} Противник пропускает ход — '
                             f'стреляйте ещё раз!', (0, 0.5, 0, 1))
                self.update_panels()
                self.redraw_all()
            else:
                g['turn'] = 'enemy'
                self.set_msg(f'{res_txt}  Ход противника...')
                self.update_panels()
                self.redraw_all()
                Clock.schedule_once(self.enemy_turn, 0.8)
        else:
            if extra_turn:
                self.set_msg(f'{shooter}: {res_txt} Соперник пропускает '
                             f'ход — {shooter} ходит снова!', (0, 0.5, 0, 1))
            else:
                g['turn'] = 'player2' if g['turn'] == 'player1' \
                    else 'player1'
                nxt = 'ИГРОКА 1' if g['turn'] == 'player1' else 'ИГРОКА 2'
                side = 'правом' if g['turn'] == 'player1' else 'левом'
                self.set_msg(f'{shooter}: {res_txt}   →   ХОД {nxt} '
                             f'(прицел на {side} поле)', (0, 0.5, 0, 1))
            self.update_panels()
            self.redraw_all()

    def enemy_place(self):
        fsh, fpl = self.fleets()
        for utype, fleet in (('ship', fsh), ('plane', fpl)):
            for size in sorted(fleet, reverse=True):
                for _ in range(fleet[size]):
                    for _try in range(600):
                        x0 = random.randint(-10, 10) / 10
                        y0 = random.randint(-10, 10) / 10
                        d = random.randrange(8)
                        pts = unit_points(round(x0, 2), round(y0, 2),
                                          size, d)
                        if points_ok(pts, utype, self.FR['units']):
                            self.FR['units'].append(
                                {'type': utype, 'pts': pts, 'dir': d,
                                 'size': size, 'hits': set()})
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

    def enemy_turn(self, *_):
        g = self.game
        if g['phase'] != 'battle':
            return
        cell = self.enemy_pick_cell()
        if cell is None:
            return
        self.enemy_ai['tried'].add(cell)
        g['enemy_moves'] += 1
        result = fire_at(self.FL, cell[0], cell[1])
        diff = self.settings['difficulty']
        if result in ('hit', 'sunk') and diff != 'Низкий':
            self.enemy_ai['thits'].append(cell)
            for dx, dy in ((GRID, 0), (-GRID, 0), (0, GRID), (0, -GRID)):
                q = (round(cell[0] + dx, 2), round(cell[1] + dy, 2))
                if q in SQ_CELLS and q not in self.enemy_ai['tried']:
                    self.enemy_ai['hunt'].append(q)
            if diff == 'Высокий' and len(self.enemy_ai['thits']) >= 2:
                ddx = round(self.enemy_ai['thits'][-1][0] -
                            self.enemy_ai['thits'][-2][0], 2)
                ddy = round(self.enemy_ai['thits'][-1][1] -
                            self.enemy_ai['thits'][-2][1], 2)
                q = (round(cell[0] + ddx, 2), round(cell[1] + ddy, 2))
                if q in SQ_CELLS and q not in self.enemy_ai['tried']:
                    self.enemy_ai['hunt'].insert(0, q)
        if result == 'sunk':
            self.enemy_ai['thits'] = []

        txt = {'hit': 'ПОПАДАНИЕ!', 'sunk': 'ВАШ ЮНИТ ПОТОПЛЕН!',
               'miss': 'мимо'}[result]
        if all_sunk(self.FL['units']):
            g['phase'] = 'over'
            self.set_msg('ПРОТИВНИК ПОБЕДИЛ. Все ваши юниты потоплены.',
                         (0.7, 0, 0, 1))
            self.update_panels()
            self.redraw_all()
        elif result in ('hit', 'sunk'):
            # ПРАВИЛО 6 (для ИИ): попадание -> игрок пропускает ход
            self.set_msg(f'Противник ({cell[0]:.1f}, {cell[1]:.1f}) — '
                         f'{txt} Вы пропускаете ход!', (0.7, 0, 0, 1))
            self.update_panels()
            self.redraw_all()
            Clock.schedule_once(self.enemy_turn, 0.9)
        else:
            g['turn'] = 'player1'
            self.set_msg(f'Противник ({cell[0]:.1f}, {cell[1]:.1f}) — '
                         f'{txt}   ВАШ ХОД.', (0, 0.5, 0, 1))
            self.update_panels()
            self.redraw_all()

    # ---------- панели и перерисовка ----------
    def build_lines(self, units, title):
        fsh, fpl = self.fleets()
        rem = self.remaining(units)
        lines = [title]
        for s in sorted(fsh):
            row = f'{s}: {"■" * rem["ship"][s]}' \
                  f'{"□" * (fsh[s] - rem["ship"][s])}'
            if fpl and s in fpl:
                row += f' {"▲" * rem["plane"][s]}' \
                       f'{"△" * (fpl[s] - rem["plane"][s])}'
            lines.append(row)
        if not fpl:
            lines.append('самолёты выкл.')
        return lines

    def alive_lines(self, units, title):
        fsh, fpl = self.fleets()
        alive = {'ship': dict.fromkeys(fsh, 0),
                 'plane': dict.fromkeys(fpl, 0)}
        for un in units:
            if not is_sunk(un):
                alive[un['type']][un['size']] += 1
        lines = [title]
        for s in sorted(fsh):
            row = f'{s}: {"■" * alive["ship"][s]}'
            if fpl and s in fpl:
                row += f' {"▲" * alive["plane"][s]}'
            lines.append(row)
        hits = sum(len(un['hits']) for un in units)
        sunks = sum(1 for un in units if is_sunk(un))
        lines.append(f'подбито {hits}, потопл. {sunks}')
        return lines

    def update_panels(self):
        g = self.game
        if g['phase'] == 'place1':
            self.panelL.text = '\n'.join(
                self.build_lines(self.FL['units'], 'ИГРОК 1\nстройка:'))
        else:
            self.panelL.text = '\n'.join(
                self.alive_lines(self.FL['units'], 'ИГРОК 1\nв живых:'))
        if g['mode'] == 'ai':
            if g['phase'] == 'place1':
                self.panelR.text = 'ПРОТИВНИК\nрасставляет\nфлот...'
            else:
                self.panelR.text = '\n'.join(
                    self.alive_lines(self.FR['units'],
                                     'ПРОТИВНИК\nв живых:')) + \
                    f'\nходы {g["my_moves"]}/{g["enemy_moves"]}'
        else:
            if g['phase'] == 'place2':
                self.panelR.text = '\n'.join(
                    self.build_lines(self.FR['units'], 'ИГРОК 2\nстройка:'))
            elif g['phase'] == 'place1':
                self.panelR.text = 'ИГРОК 2\nждёт...'
            else:
                self.panelR.text = '\n'.join(
                    self.alive_lines(self.FR['units'], 'ИГРОК 2\nв живых:'))

    def redraw_all(self):
        if self._built:
            self.boardL.redraw()
            self.boardR.redraw()


if __name__ == '__main__':
    TrigBattleApp().run()
