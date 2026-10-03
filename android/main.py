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
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget
from kivy.uix.slider import Slider
import threading
import uuid
import json
import time
from kivy.network.urlrequest import UrlRequest

try:
    from auth_db import auth_db
except Exception:
    auth_db = None

# ===================== BLUETOOTH P2P LAYER =====================
class BTManager:
    """Bluetooth P2P менеджер для Android (host/client)."""
    def __init__(self, app):
        self.app = app
        self.socket = None
        self.server_socket = None
        self.connected = False
        self.is_host = False
        self.peer_name = ""
        self.callbacks = {'connected': None, 'data': None, 'disconnected': None}
        self._listen_thread = None
        self._read_thread = None
        self.app_uuid = uuid.UUID("12345678-1234-5678-1234-56789abcdef0")
        self._bt_available = None

    def _detect_bt(self):
        """True, если на устройстве есть BluetoothAdapter."""
        try:
            from jnius import autoclass
            adapter = autoclass(
                'android.bluetooth.BluetoothAdapter').getDefaultAdapter()
            return adapter is not None
        except Exception:
            return False

    def is_available(self):
        if self._bt_available is None:
            self._bt_available = self._detect_bt()
        return self._bt_available

    def generate_code(self):
        """Генерирует 5-символьный код: цифра/буква (0-9, A-Z кроме O,I)."""
        import random
        chars = "0123456789ABCDEFGHJKLMNPQRSTUVWXYZ"
        return ''.join(random.choice(chars) for _ in range(5))
    
    def start_host(self, code, on_connected):
        if not self.is_available():
            Clock.schedule_once(lambda dt: on_connected(False, "Bluetooth не поддерживается на этом устройстве"))
            return
        self.is_host = True
        self.callbacks['connected'] = on_connected
        self.peer_name = code
        
        def run_server():
            try:
                from jnius import autoclass
                BluetoothAdapter = autoclass('android.bluetooth.BluetoothAdapter')
                BluetoothServerSocket = autoclass('android.bluetooth.BluetoothServerSocket')
                BluetoothSocket = autoclass('android.bluetooth.BluetoothSocket')
                UUID = autoclass('java.util.UUID')
                
                adapter = BluetoothAdapter.getDefaultAdapter()
                if not adapter or not adapter.isEnabled():
                    Clock.schedule_once(lambda dt: self.app.set_msg('Bluetooth выключен!', (0.7,0,0,1)))
                    return
                
                uuid_obj = UUID.fromString(str(self.app_uuid))
                self.server_socket = adapter.listenUsingRfcommWithServiceRecord(
                    "TrigBattle", uuid_obj)
                
                Clock.schedule_once(lambda dt: self.app.show_host_code(self.peer_name))
                
                self.socket = self.server_socket.accept()
                self.connected = True
                self.server_socket.close()
                
                Clock.schedule_once(lambda dt: self._on_connected())
                self._start_read_loop()
                
            except Exception as e:
                Clock.schedule_once(lambda dt, e=e: self.app.set_msg(f'Ошибка хоста: {e}', (0.7,0,0,1)))
        
        self._listen_thread = threading.Thread(target=run_server, daemon=True)
        self._listen_thread.start()
    
    def connect_to_host(self, code, on_connected):
        if not self.is_available():
            Clock.schedule_once(lambda dt: on_connected(False, "Bluetooth не поддерживается на этом устройстве"))
            return
        self.is_host = False
        self.callbacks['connected'] = on_connected
        self.peer_name = code
        
        def run_client():
            try:
                from jnius import autoclass
                BluetoothAdapter = autoclass('android.bluetooth.BluetoothAdapter')
                BluetoothSocket = autoclass('android.bluetooth.BluetoothSocket')
                UUID = autoclass('java.util.UUID')
                
                adapter = BluetoothAdapter.getDefaultAdapter()
                if not adapter or not adapter.isEnabled():
                    Clock.schedule_once(lambda dt: self.app.set_msg('Bluetooth выключен!', (0.7,0,0,1)))
                    return
                
                mac = code.replace('-', ':').upper()
                device = adapter.getRemoteDevice(mac)
                
                uuid_obj = UUID.fromString(str(self.app_uuid))
                self.socket = device.createRfcommSocketToServiceRecord(uuid_obj)
                self.socket.connect()
                self.connected = True
                
                Clock.schedule_once(lambda dt: self._on_connected())
                self._start_read_loop()
                
            except Exception as e:
                Clock.schedule_once(lambda dt, e=e: self.app.set_msg(f'Ошибка подключения: {e}', (0.7,0,0,1)))
        
        threading.Thread(target=run_client, daemon=True).start()
    
    def _on_connected(self):
        self.connected = True
        if self.callbacks['connected']:
            self.callbacks['connected']()
    
    def _start_read_loop(self):
        def read_loop():
            try:
                input_stream = self.socket.getInputStream()
                buffer = bytearray(1024)
                while self.connected:
                    bytes_read = input_stream.read(buffer)
                    if bytes_read > 0:
                        data = bytes(buffer[:bytes_read]).decode('utf-8')
                        Clock.schedule_once(lambda dt: self._handle_data(data))
                    elif bytes_read == -1:
                        break
            except Exception as e:
                Clock.schedule_once(lambda dt, e=e: self._on_disconnected(str(e)))
        
        self._read_thread = threading.Thread(target=read_loop, daemon=True)
        self._read_thread.start()
    
    def _handle_data(self, data):
        try:
            msg = json.loads(data)
            if self.callbacks['data']:
                self.callbacks['data'](msg)
        except:
            pass
    
    def send(self, msg_dict):
        if not self.connected or not self.socket:
            return False
        try:
            data = json.dumps(msg_dict).encode('utf-8')
            output_stream = self.socket.getOutputStream()
            output_stream.write(data)
            output_stream.flush()
            return True
        except:
            self._on_disconnected("send error")
            return False
    
    def _on_disconnected(self, reason=""):
        self.connected = False
        if self.callbacks['disconnected']:
            self.callbacks['disconnected'](reason)
    
    def disconnect(self):
        self.connected = False
        try:
            if self.socket:
                self.socket.close()
            if self.server_socket:
                self.server_socket.close()
        except:
            pass

# Глобальный менеджер
bt_manager = None

# ===================== КОНСТАНТЫ =====================
GRID = 0.1
LIMIT = 1.6
HIT_TOL = 0.05
FLEET_SHIPS = {1: 4, 2: 4, 3: 3, 4: 2, 5: 1}
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

            # подписи зон в туториале
            if app.tut.get('zones') and self.side == 'L':
                self.draw_text(0, 0.52, 'ОКЕАН', (0, 0, 0.5, 0.85), 15,
                               bold=True)
                self.draw_text(0, 0.40, 'только корабли', (0, 0, 0.5, 0.85),
                               9)
                for zx in (0.9, -0.9):
                    for zy in (0.9, -0.9):
                        self.draw_text(zx, zy, 'ВОЗДУХ', (0, 0.5, 0.5, 0.9),
                                       9, bold=True)

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

            # подсказки (оранжевые кольца на раскрытых клетках)
            if not app.game.get('awaiting_tap'):
                Color(1.0, 0.55, 0.0, 1)
                for q in fld['hints']:
                    px, py = self.to_px(*q)
                    Line(circle=(px, py, 11), width=2.5)

            # прицел в стиле настольной версии
            if app.aim_side() == self.side and \
                    app.game['phase'] == 'battle' and \
                    not app.game.get('awaiting_tap'):
                self.draw_aim(app, cx, cy, r)

    # ---------- прицел (как на ПК) ----------
    def draw_aim(self, app, cx, cy, r_circle):
        F = self.FADE
        a1 = math.radians(app.slider1.value)
        a2 = math.radians(app.slider2.value)
        c1, s1 = math.cos(a1), math.sin(a1)
        c2, s2 = math.cos(a2), math.sin(a2)

        # --- угол 1: луч и проекции ---
        Color(0.6, 0.1, 0.8, 1)
        Line(points=[cx, cy, *self.to_px(c1, s1)], width=2)
        p1x, p1y = self.to_px(c1, s1)
        Ellipse(pos=(p1x - 4, p1y - 4), size=(8, 8))
        Color(0, 0, 1, F)
        Line(points=[*self.to_px(c1, 0), *self.to_px(c1, s1)], width=1.2)
        Line(points=[*self.to_px(0, s1), *self.to_px(c1, s1)], width=1.2)
        self.draw_text(c1 - 0.04, -0.1, f'cos={c1:.2f}', (0, 0, 1, F), 8)
        self.draw_text(-0.03, s1, f'sin={s1:.2f}', (0, 0, 1, F), 8,
                       anchor='rm')

        # --- угол 2: луч и проекции ---
        Color(0.85, 0.55, 0.0, 1)
        Line(points=[cx, cy, *self.to_px(c2, s2)], width=2)
        p2x, p2y = self.to_px(c2, s2)
        Ellipse(pos=(p2x - 4, p2y - 4), size=(8, 8))
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
        # выбранная точка огня яркая, вторая — прозрачная
        a1 = 1.0 if app.shot_sel == 'P1' else 0.15
        a2 = 1.0 if app.shot_sel == 'P2' else 0.15
        if app.state['P1'] is not None:
            Px, Py = app.state['P1']
            if -LIMIT <= Px <= LIMIT and -LIMIT <= Py <= LIMIT:
                px, py = self.to_px(Px, Py)
                Color(0, 0, 0, a1)
                self.draw_star(px, py, 10)
                self.draw_text(Px + 0.05, Py,
                               f'P1 = ({Px:.2f}, {Py:.2f})',
                               (0, 0, 0, a1), 8, anchor='lm', bold=True)
        if app.state['P2'] is not None:
            Qx, Qy = app.state['P2']
            if -LIMIT <= Qx <= LIMIT and -LIMIT <= Qy <= LIMIT:
                px, py = self.to_px(Qx, Qy)
                Color(0, 0.5, 0.15, a2)
                self.draw_star(px, py, 10)
                self.draw_text(Qx + 0.05, Qy,
                               f'P2 = ({Qx:.2f}, {Qy:.2f})',
                               (0, 0.5, 0.15, a2), 8, anchor='lm', bold=True)

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
            f'P1 = {p1s}',
            f'P2 = {p2s}',
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
        self.settings = {'planes': True, 'music': False, 'hints': False,
                         'difficulty': 'Средний'}
        self.game = {'mode': 'ai', 'phase': 'place1', 'turn': 'player1',
                     'my_moves': 0, 'enemy_moves': 0, 'last': '—',
                     'awaiting_tap': False,
                     'streak': {'player1': 0, 'player2': 0}}
        self.FL = {'units': [], 'misses': [], 'hints': set()}
        self.FR = {'units': [], 'misses': [], 'hints': set()}
        self.unit_state = {'size': 3, 'dir_idx': 0, 'selected': None,
                           'last': None}
        self.mode = 'ships'          # angles / ships / planes
        self.shot_sel = 'P1'
        self.aim_sel = 1
        self.state = {'P1': None, 'P2': None}
        self.enemy_ai = {'tried': set(), 'hunt': [], 'thits': []}
        self.tut = {'active': False, 'step': -1, 'waiting': None,
                    'end': None, 'zones': False}
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
        # локальная игра: экран "нажмите на экран" — всё скрыто
        if g.get('awaiting_tap') and g['phase'] == 'battle':
            return False
        if g['mode'] == 'ai':
            return fld is self.FL
        if g['mode'] == 'bluetooth':
            # В блютуз-режиме: свои юниты видимы, чужие — только подбитые/потопленные
            if fld is self.FL:
                return True
            else:
                return is_sunk(un) or len(un['hits']) > 0
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
        # профиль в левом верхнем углу
        top_bar = BoxLayout(size_hint_y=0.12, spacing=8)
        self.profile_btn = Button(text='👤', size_hint_x=0.12,
                                  font_size='24sp', font_name='DejaVuSans')
        self.profile_btn.bind(on_release=lambda *_: self.go('profile'))
        top_bar.add_widget(self.profile_btn)
        self.nick_label = Label(text=f'Ник: {self.nickname}',
                                font_size='16sp', color=(0, 0, 0.5, 1),
                                halign='left', valign='center',
                                font_name='DejaVuSans', size_hint_x=0.88)
        self.nick_label.bind(size=lambda i, v: setattr(i, 'text_size', v))
        top_bar.add_widget(self.nick_label)
        lay.add_widget(top_bar)
        lay.add_widget(Label(text=title, font_size='24sp', bold=True,
                             color=(0, 0, 0.5, 1), size_hint_y=0.25))
        for text, cb in items:
            b = Button(text=text, font_size='18sp', size_hint_y=None,
                       height='60dp')
            b.bind(on_release=cb)
            lay.add_widget(b)
        scr.add_widget(lay)
        return scr

    def save_nickname(self):
        new_nick = self.nick_input.text.strip()
        if new_nick:
            self.nickname = new_nick[:12]  # макс 12 символов
            self.nick_label.text = f'Ник: {self.nickname}'
            self.set_msg(f'Ник изменён на "{self.nickname}"', (0, 0.5, 0, 1))
        self.go('menu')

    def build(self):
        global bt_manager
        bt_manager = BTManager(self)
        Window.clearcolor = (0.94, 0.94, 0.94, 1)
        self.sm = ScreenManager()
        self.nickname = 'Игрок'  # дефолтный ник
        self.user_state = {'user_id': None, 'nickname': None,
                           'email': None, 'logged_in': False}

        # --- профиль (ник + вход/регистрация) ---
        scr = Screen(name='profile')
        lay = BoxLayout(orientation='vertical', padding=40, spacing=10)
        lay.add_widget(Label(text='Профиль',
                             font_size='24sp', bold=True,
                             color=(0, 0, 0.5, 1), size_hint_y=0.12))
        lay.add_widget(Label(text=f'Текущий ник: {self.nickname}',
                             font_size='18sp', color=(0.3, 0.3, 0.3, 1),
                             size_hint_y=None, height='40dp'))
        self.nick_input = TextInput(text=self.nickname,
                                    hint_text='Введите новый ник',
                                    multiline=False, font_size='20sp',
                                    size_hint_y=None, height='50dp',
                                    font_name='DejaVuSans')
        lay.add_widget(self.nick_input)
        b = Button(text='Сохранить ник', size_hint_y=None, height='50dp',
                   background_color=(0.6, 0.95, 0.6, 1),
                   font_name='DejaVuSans')
        b.bind(on_release=lambda *_: self.save_nickname())
        lay.add_widget(b)
        lay.add_widget(Label(text='Вход', font_size='18sp', bold=True,
                             size_hint_y=None, height='36dp'))
        self.login_email = TextInput(hint_text='Email', multiline=False,
                                     font_size='18sp', size_hint_y=None,
                                     height='46dp', font_name='DejaVuSans')
        self.login_pass = TextInput(hint_text='Пароль', password=True,
                                    multiline=False, font_size='18sp',
                                    size_hint_y=None, height='46dp',
                                    font_name='DejaVuSans')
        lay.add_widget(self.login_email)
        lay.add_widget(self.login_pass)
        b = Button(text='Войти', size_hint_y=None, height='46dp',
                   background_color=(0.6, 0.8, 1, 1),
                   font_name='DejaVuSans')
        b.bind(on_release=lambda *_: self.login_user())
        lay.add_widget(b)
        lay.add_widget(Label(text='Регистрация', font_size='18sp',
                             bold=True, size_hint_y=None, height='36dp'))
        self.reg_nick = TextInput(hint_text='Ник', multiline=False,
                                  font_size='18sp', size_hint_y=None,
                                  height='46dp', font_name='DejaVuSans')
        self.reg_email = TextInput(hint_text='Email', multiline=False,
                                   font_size='18sp', size_hint_y=None,
                                   height='46dp', font_name='DejaVuSans')
        self.reg_pass = TextInput(hint_text='Пароль', password=True,
                                  multiline=False, font_size='18sp',
                                  size_hint_y=None, height='46dp',
                                  font_name='DejaVuSans')
        self.reg_pass2 = TextInput(hint_text='Повтор пароля',
                                   password=True, multiline=False,
                                   font_size='18sp', size_hint_y=None,
                                   height='46dp', font_name='DejaVuSans')
        lay.add_widget(self.reg_nick)
        lay.add_widget(self.reg_email)
        lay.add_widget(self.reg_pass)
        lay.add_widget(self.reg_pass2)
        b = Button(text='Зарегистрироваться', size_hint_y=None,
                   height='46dp', background_color=(1, 0.9, 0.6, 1),
                   font_name='DejaVuSans')
        b.bind(on_release=lambda *_: self.register_user())
        lay.add_widget(b)
        b = Button(text='Выйти из аккаунта', size_hint_y=None, height='46dp',
                   background_color=(1, 0.6, 0.6, 1), font_name='DejaVuSans')
        b.bind(on_release=lambda *_: self.logout_user())
        lay.add_widget(b)
        b = Button(text='Назад', size_hint_y=None, height='55dp')
        b.bind(on_release=lambda *_: self.go('menu'))
        lay.add_widget(b)
        scroll = ScrollView()
        scroll.add_widget(lay)
        scr.add_widget(scroll)
        self.sm.add_widget(scr)

        # --- меню ---
        self.sm.add_widget(self.make_menu_screen(
            'menu', 'Тригонометрический\nморской бой', [
                ('Начать игру', lambda *_: self.go('difficulty')),
                ('Блютуз-битва', lambda *_: self.go('bluetooth')),
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
                ('Туториал', lambda *_: self.start_tutorial()),
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
        self.cb_hints = self._setting_row(lay, 'Включить подсказки',
                                          self.settings['hints'],
                                          lambda v: self.settings.
                                          __setitem__('hints', v))
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

        # --- блютуз: хост ---
        scr = Screen(name='bluetooth_host')
        lay = BoxLayout(orientation='vertical', padding=40, spacing=14)
        lay.add_widget(Label(text='Создать игру',
                             font_size='24sp', bold=True,
                             color=(0, 0, 0.5, 1), size_hint_y=0.25))
        self.bt_host_code = Label(text='Код: ---',
                                  font_size='28sp', bold=True,
                                  color=(0, 0.5, 0, 1), size_hint_y=0.2)
        lay.add_widget(self.bt_host_code)
        lay.add_widget(Label(text='Отправьте код другу.\n'
                                 'Он должен ввести его в "Присоединиться".',
                             font_size='15sp', color=(0.3, 0.3, 0.3, 1),
                             halign='center', size_hint_y=0.15))
        b = Button(text='Отмена', size_hint_y=None, height='55dp')
        b.bind(on_release=lambda *_: self.bt_cancel_host())
        lay.add_widget(b)
        scr.add_widget(lay)
        self.sm.add_widget(scr)

        # --- блютуз: присоединиться ---
        scr = Screen(name='bluetooth_join')
        lay = BoxLayout(orientation='vertical', padding=40, spacing=14)
        lay.add_widget(Label(text='Присоединиться к игре',
                             font_size='24sp', bold=True,
                             color=(0, 0, 0.5, 1), size_hint_y=0.2))
        self.bt_join_input = TextInput(hint_text='Код друга (XXXXX)',
                                       multiline=False, font_size='24sp',
                                       size_hint_y=None, height='70dp',
                                       font_name='DejaVuSans',
                                       input_filter=lambda t, _: t.upper())
        lay.add_widget(self.bt_join_input)
        b = Button(text='Подключиться', size_hint_y=None, height='60dp',
                   background_color=(0.6, 0.95, 0.6, 1),
                   font_name='DejaVuSans')
        b.bind(on_release=lambda *_: self.bt_do_join())
        lay.add_widget(b)
        b = Button(text='Назад', size_hint_y=None, height='55dp')
        b.bind(on_release=lambda *_: self.go('bluetooth'))
        lay.add_widget(b)
        scr.add_widget(lay)
        self.sm.add_widget(scr)

        # --- блютуз: меню выбора ---
        scr = Screen(name='bluetooth')
        lay = BoxLayout(orientation='vertical', padding=40, spacing=14)
        lay.add_widget(Label(text='БЛЮТУЗ-БИТВА',
                             font_size='24sp', bold=True,
                             color=(0, 0, 0.5, 1), size_hint_y=0.2))
        b = Button(text='Создать игру (Хост)',
                   size_hint_y=None, height='70dp',
                   background_color=(0.6, 0.95, 0.6, 1),
                   font_name='DejaVuSans', font_size='18sp')
        b.bind(on_release=lambda *_: self.bt_start_host())
        lay.add_widget(b)
        b = Button(text='Присоединиться к игре',
                   size_hint_y=None, height='70dp',
                   background_color=(0.6, 0.85, 1, 1),
                   font_name='DejaVuSans', font_size='18sp')
        b.bind(on_release=lambda *_: self.go('bluetooth_join'))
        lay.add_widget(b)
        b = Button(text='Назад', size_hint_y=None, height='55dp')
        b.bind(on_release=lambda *_: self.go('menu'))
        lay.add_widget(b)
        scr.add_widget(lay)
        self.sm.add_widget(scr)

        # --- блютуз: ожидание подключения ---
        scr = Screen(name='bluetooth_wait')
        lay = BoxLayout(orientation='vertical', padding=40, spacing=14)
        lay.add_widget(Label(text='Ожидание соперника...',
                             font_size='22sp', bold=True,
                             color=(0, 0.5, 0, 1), size_hint_y=0.3))
        self.bt_wait_code = Label(text='Ваш код: ---',
                                  font_size='20sp', bold=True,
                                  color=(0, 0.5, 0, 1), size_hint_y=0.2)
        lay.add_widget(self.bt_wait_code)
        b = Button(text='Отмена', size_hint_y=None, height='55dp')
        b.bind(on_release=lambda *_: self.bt_cancel_host())
        lay.add_widget(b)
        scr.add_widget(lay)
        self.sm.add_widget(scr)

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
                         bold=True, color=(0, 0, 0, 1),
                         font_name='DejaVuSans')
        root.add_widget(self.msg)

        # панель туториала (скрыта по умолчанию)
        self.tut_lbl = Label(text='', color=(0.45, 0.28, 0, 1),
                             font_size='13sp', halign='center',
                             valign='center', font_name='DejaVuSans')
        self.tut_lbl.bind(size=lambda i, v: setattr(i, 'text_size', v))
        self.tut_next_b = Button(text='Далее ▶', size_hint_x=0.16,
                                 background_color=(1, 0.8, 0.3, 1),
                                 font_name='DejaVuSans')
        self.tut_skip_b = Button(text='Пропустить', size_hint_x=0.16,
                                 font_name='DejaVuSans')
        self.tut_next_b.bind(on_release=lambda *_: self.on_tut_next())
        self.tut_skip_b.bind(on_release=lambda *_: self.tut_exit())
        self.tut_bar = BoxLayout(size_hint_y=0, spacing=4)
        self.tut_bar.add_widget(self.tut_lbl)
        self.tut_bar.add_widget(self.tut_next_b)
        self.tut_bar.add_widget(self.tut_skip_b)
        root.add_widget(self.tut_bar)

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
        self.b_rot = Button(text='Поворот', font_name='DejaVuSans')
        self.b_rot.bind(on_release=lambda *_: self.rotate(1))
        self.b_del = Button(text='Удалить')
        self.b_del.bind(on_release=lambda *_: self.delete_selected())
        r3.add_widget(self.b_rot)
        r3.add_widget(self.b_del)
        ctrl.add_widget(r3)

        # ряд 4: бой
        r4 = BoxLayout(spacing=3)
        self.b_shot1 = Button(text='Огонь P1', font_name='DejaVuSans')
        self.b_shot2 = Button(text='Огонь P2', font_name='DejaVuSans')
        self.b_shot1.bind(on_release=lambda *_: self.set_shot('P1'))
        self.b_shot2.bind(on_release=lambda *_: self.set_shot('P2'))
        self.b_aim1 = Button(text='Прицел 1', font_name='DejaVuSans')
        self.b_aim2 = Button(text='Прицел 2', font_name='DejaVuSans')
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
        l = Label(text=text, color=(0, 0, 0, 1), font_size='13sp',
                  font_name='DejaVuSans')
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

    # ===================== BLUETOOTH P2P =====================
    def bt_start_host(self):
        if not bt_manager.is_available():
            self.set_msg('Bluetooth не поддерживается на этом устройстве', (0.7,0,0,1))
            return
        code = bt_manager.generate_code()
        self.bt_wait_code.text = f'Ваш код: {code}'
        self.go('bluetooth_wait')
        bt_manager.start_host(code, self._on_bt_connected)

    def bt_do_join(self):
        if not bt_manager.is_available():
            self.set_msg('Bluetooth не поддерживается на этом устройстве', (0.7,0,0,1))
            return
        code = self.bt_join_input.text.strip().upper()
        if len(code) != 5:
            self.set_msg('Код должен быть 5 символов!', (0.7,0,0,1))
            return
        self.go('bluetooth_wait')
        self.bt_wait_code.text = f'Подключение к {self.bt_join_input.text.upper()}...'
        bt_manager.connect_to_host(self.bt_join_input.text.upper(), self._on_bt_connected)

    def _on_bt_connected(self):
        self.set_msg('Подключено! Расставляйте корабли.', (0, 0.5, 0, 1))
        self.game['mode'] = 'bluetooth'
        self.reset_game()
        self.go('game')
        # регистрируем callback для входящих сообщений
        bt_manager.callbacks['data'] = self._on_bt_data

    def _on_bt_data(self, msg):
        """Обработка входящих блютуз-сообщений."""
        mtype = msg.get('type')
        if mtype == 'move':
            # соперник сделал ход
            self._on_bt_move(msg)
        elif mtype == 'game_over':
            self._on_bt_game_over(msg)

    def _on_bt_move(self, msg):
        """Обработка хода соперника."""
        result = msg.get('result')
        x, y = msg.get('x'), msg.get('y')
        point = msg.get('point')
        
        # применяем ход к нашему полю (FL - наше поле)
        target = self.FL
        res = fire_at(target, x, y)
        
        self.update_panels()
        self.redraw_all()
        
        if res == 'sunk':
            self.set_msg(f'Соперник потопил ваш корабль!', (0.7, 0, 0, 1))
        elif res == 'hit':
            self.set_msg(f'Соперник попал в ({x:.1f}, {y:.1f})!', (0.7, 0, 0, 1))
        else:
            self.set_msg(f'Соперник промахнулся в ({x:.1f}, {y:.1f}). Ваш ход.', (0, 0.5, 0, 1))
        
        # проверка победы
        if all_sunk(self.FL['units']):
            self.game['phase'] = 'over'
            self.set_msg('Соперник победил!', (0.7, 0, 0, 1))
            self.show_victory('Победил соперник!')
            return
        
        # ход переходит к нам
        self.game['turn'] = 'player1'
        self.set_msg('Ваш ход!', (0, 0.5, 0, 1))
        self.update_panels()
        self.redraw_all()

    def _on_bt_game_over(self, msg):
        winner = msg.get('winner', 'Соперник')
        self.game['phase'] = 'over'
        self.show_victory(f'Победил {winner}!')

    def show_host_code(self, code):
        self.bt_host_code.text = f'Код: {code}'
        self.go('bluetooth_host')

    def bt_cancel_host(self):
        bt_manager.disconnect()
        self.go('bluetooth')

    def bt_send_move(self, msg):
        if bt_manager:
            bt_manager.send(msg)

    # ===================== АУТЕНТИФИКАЦИЯ =====================
    def login_user(self):
        email = self.login_email.text.strip().lower()
        password = self.login_pass.text
        if not email or not password:
            self.set_msg('Введите email и пароль', (0.7, 0, 0, 1))
            return
        if auth_db is None:
            self.set_msg('База аккаунтов недоступна', (0.7, 0, 0, 1))
            return
        result = auth_db.login_user(email, password)
        if result['success']:
            self.user_state.update({
                'logged_in': True,
                'user_id': result['user_id'],
                'nickname': result['nickname'],
                'email': result['email']
            })
            self.nickname = result['nickname']
            self.nick_label.text = f'Ник: {self.nickname}'
            self.set_msg(f'Добро пожаловать, {self.nickname}!', (0, 0.5, 0, 1))
            self.go('menu')
        else:
            self.set_msg(result['error'], (0.7, 0, 0, 1))

    def register_user(self):
        email = self.reg_email.text.strip().lower()
        password = self.reg_pass.text
        password2 = self.reg_pass2.text
        nickname = self.reg_nick.text.strip()[:12] or 'Игрок'
        
        if password != password2:
            self.set_msg('Пароли не совпадают', (0.7, 0, 0, 1))
            return
        if len(password) < 6:
            self.set_msg('Пароль минимум 6 символов', (0.7, 0, 0, 1))
            return
        if auth_db is None:
            self.set_msg('База аккаунтов недоступна', (0.7, 0, 0, 1))
            return

        result = auth_db.register_user(email, password, nickname)
        if result['success']:
            self.set_msg('Регистрация успешна! Войдите в аккаунт', (0, 0.5, 0, 1))
            self.go('profile')
        else:
            self.set_msg(result['error'], (0.7, 0, 0, 1))

    def logout_user(self):
        self.user_state.update({
            'logged_in': False,
            'user_id': None,
            'nickname': None,
            'email': None
        })
        self.nickname = 'Игрок'
        self.nick_label.text = 'Ник: Игрок'
        self.set_msg('Вы вышли из аккаунта', (0, 0.5, 0, 1))
        self.go('menu')

    # ===================== ТУТОРИАЛ =====================
    TUT_STEPS = [
        {'key': 'intro', 'wait': None,
         'text': 'ДОБРО ПОЖАЛОВАТЬ В ТУТОРИАЛ!\n'
                 'Научимся играть за пару минут. Нажмите «Далее»'},
        {'key': 'zones', 'wait': None, 'zones': True,
         'text': 'Синяя окружность — ОКЕАН: там стоят ТОЛЬКО КОРАБЛИ.\n'
                 'Уголки квадрата — ВОЗДУХ: там ТОЛЬКО САМОЛЁТЫ.\n'
                 'Сегодня тренируем корабли.'},
        {'key': 'mode', 'wait': None, 'hl': 'mode',
         'text': 'Режим «Корабли» уже выбран, размер = 2.\n'
                 'Нажмите «Далее»'},
        {'key': 'place', 'wait': 'place',
         'text': 'ПОСТАВЬТЕ КОРАБЛЬ: тапните по точке ВНУТРИ '
                 'окружности.\n«Призрак» покажет, где встанет корабль.'},
        {'key': 'select', 'wait': 'select',
         'text': 'Теперь ВЫБЕРИТЕ корабль — тапните по нему.\n'
                 'Он подсветится золотым.'},
        {'key': 'rotate', 'wait': 'rotate', 'hl': 'rot',
         'text': 'РАЗВЕРНИТЕ корабль кнопкой «Поворот».'},
        {'key': 'start', 'wait': 'start', 'hl': 'start',
         'text': 'Корабль готов! Нажмите «Начать бой».\n'
                 'У противника — один такой же корабль.'},
        {'key': 'aim', 'wait': None,
         'text': 'ПРИЦЕЛИВАНИЕ. Попробуйте:\n'
                 '• тянуть палец по полю («Прицел 1/2» — выбор угла)\n'
                 '• двигать ползунки\n'
                 '• переключать «Огонь P1/P2»\n'
                 'Наигрались? — «Далее»'},
        {'key': 'fire1', 'wait': 'fire', 'hl': 'fire',
         'text': 'ТОЧНЫЙ ВЫСТРЕЛ. Выберите огонь P2 и введите:\n'
                 'sin₁ = 0.2  и  ctg₂ = 1.5  (Enter в каждом поле)\n'
                 '— P2 окажется в (0.3, 0.2). «Совершить ход»!'},
        {'key': 'fire2', 'wait': 'fire', 'hl': 'fire',
         'text': 'ПОПАДАНИЕ! Добиваем: введите ctg₂ = 2.0 (Enter)\n'
                 '— P2 попадёт в (0.4, 0.2). «Совершить ход»!'},
    ]

    def tut_say(self, text, next_label=None):
        self.tut_lbl.text = text
        if next_label:
            self.tut_next_b.text = next_label
            self.tut_next_b.opacity = 1
            self.tut_next_b.disabled = False
        else:
            self.tut_next_b.opacity = 0
            self.tut_next_b.disabled = True

    def hl_btn(self, key):
        targets = {'mode': self.b_mode_ships, 'fire': self.b_move,
                   'start': self.b_start, 'rot': self.b_rot}
        for b in targets.values():
            if not hasattr(b, '_orig_bg'):
                b._orig_bg = list(b.background_color)
            b.background_color = list(b._orig_bg)
        if key in targets:
            targets[key].background_color = (1, 0.45, 0.2, 1)

    def start_tutorial(self):
        self.tut.update(active=True, step=-1, waiting=None, end=None,
                        zones=False)
        self.settings['difficulty'] = 'Низкий'
        self.game['mode'] = 'ai'
        self.reset_game()
        self.go('game')
        self.tut_bar.size_hint_y = 0.10
        self.set_msg('ТУТОРИАЛ — следуйте подсказкам', (0.45, 0.28, 0, 1))
        self.tut_next()

    def tut_next(self):
        t = self.tut
        t['step'] += 1
        if t['step'] >= len(self.TUT_STEPS):
            return
        st = self.TUT_STEPS[t['step']]
        t['waiting'] = st.get('wait')
        self.tut_say(st['text'], 'Далее ▶' if st.get('wait') is None
                     else None)
        t['zones'] = bool(st.get('zones'))
        self.hl_btn(st.get('hl'))
        if st['key'] == 'mode':
            self.set_mode('ships')
            self.set_size(2)
        self.redraw_all()

    def on_tut_next(self):
        t = self.tut
        if t.get('end'):
            if t['end'] == 'lose':
                t['end'] = None
                self.start_tutorial()
            else:
                self.tut_exit()
            return
        if t['waiting'] is None:
            self.tut_next()

    def tut_exit(self):
        self.tut.update(active=False, waiting=None, end=None, zones=False)
        self.tut_bar.size_hint_y = 0
        self.hl_btn(None)
        self.go('menu')

    def tutorial_enemy_fire(self):
        """Скриптованный враг: бьёт по первой неподбитой точке игрока."""
        for un in self.FL['units']:
            for p in un['pts']:
                if p not in un['hits']:
                    fire_at(self.FL, p[0], p[1])
                    return p
        return None

    def tutorial_fire(self):
        """Ход игрока в туториале (скриптованный бой)."""
        g = self.game
        P = self.state['P1'] if self.shot_sel == 'P1' else self.state['P2']
        if P is None:
            self.set_msg('Точка не определена — поверните углы')
            return
        result = fire_at(self.FR, P[0], P[1])
        g['my_moves'] += 1
        self.update_panels()
        self.redraw_all()
        if all_sunk(self.FR['units']):
            g['phase'] = 'over'
            self.redraw_all()
            self.tut_end(True)
            return
        if result == 'miss':
            self.set_msg('МИМО! Противник отвечает...', (0.7, 0, 0, 1))
            hp = self.tutorial_enemy_fire()
            self.update_panels()
            self.redraw_all()
            if all_sunk(self.FL['units']):
                g['phase'] = 'over'
                self.redraw_all()
                self.tut_end(False)
                return
            self.set_msg(f'Противник попал в ({hp[0]:.1f}, {hp[1]:.1f})! '
                         f'Снова ваш ход.', (0.7, 0, 0, 1))
            self.tut_say('МИМО — враг попал по вашему кораблю!\n'
                         'Введите ТОЧНО: огонь P2, sin₁ = 0.2, '
                         'ctg₂ = 1.5 и «Совершить ход».')
        else:
            self.set_msg('ПОПАДАНИЕ!' if result == 'hit' else 'ПОТОПЛЕН!',
                         (0, 0.5, 0, 1))
            if self.tut['waiting'] == 'fire':
                self.tut_next()

    def tut_end(self, win):
        t = self.tut
        t['waiting'] = None
        t['step'] = len(self.TUT_STEPS)
        self.hl_btn(None)
        if win:
            t['end'] = 'win'
            self.tut_say('🎉 ПОБЕДА! Вражеский корабль потоплен.\n'
                         'ТУТОРИАЛ ПРОЙДЕН! Нажмите «Завершить».',
                         next_label='Завершить')
        else:
            t['end'] = 'lose'
            self.tut_say('😢 ПОРАЖЕНИЕ... Но это была тренировка!\n'
                         '«Заново» — ещё раз, «Завершить» — выйти.',
                         next_label='Заново')

    def reset_game(self):
        self.FL = {'units': [], 'misses': [], 'hints': set()}
        self.FR = {'units': [], 'misses': [], 'hints': set()}
        self.enemy_ai = {'tried': set(), 'hunt': [], 'thits': []}
        self.game.update(phase='place1', turn='player1', my_moves=0,
                         enemy_moves=0, last='—', awaiting_tap=False,
                         streak={'player1': 0, 'player2': 0})
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
        self.redraw_all()

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
        # точки пересечения не выходят за пределы квадрата [-1, 1]
        if abs(c2) > 1e-9:
            self.state['P1'] = (c1, max(-1.0, min(1.0, s2 / c2 * c1)))
        else:
            self.state['P1'] = None
        if abs(s2) > 1e-9:
            self.state['P2'] = (max(-1.0, min(1.0, c2 / s2 * s1)), s1)
        else:
            self.state['P2'] = None
        if self._built:
            self.boardL.redraw()
            self.boardR.redraw()

    # ---------- касания ----------
    def board_touch(self, side, touch, phase):
        if self.sm.current != 'game':
            return
        g = self.game
        # локальная игра: экран ожидания — тап следующего игрока
        if g.get('awaiting_tap') and g['phase'] == 'battle':
            g['awaiting_tap'] = False
            nxt = 'ИГРОКА 1' if g['turn'] == 'player1' else 'ИГРОКА 2'
            side_txt = 'правом' if g['turn'] == 'player1' else 'левом'
            self.set_msg(f'ХОД {nxt} (прицел на {side_txt} поле)',
                         (0, 0.5, 0, 1))
            self.update_panels()
            self.redraw_all()
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
                if self.tut['active'] and self.tut['waiting'] == 'select':
                    self.tut_next()
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
                    if self.tut['active'] and \
                            self.tut['waiting'] == 'place' and size == 2:
                        self.tut_next()
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
        if self.tut['active'] and self.tut['waiting'] == 'rotate':
            self.tut_next()

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
        # туториал: скриптованный противник — один 2-точечный корабль
        if self.tut['active'] and g['phase'] == 'place1':
            if not self.FL['units']:
                self.set_msg('Сначала поставьте корабль!', (0.7, 0, 0, 1))
                return
            self.FR['units'].append(
                {'type': 'ship', 'pts': [(0.3, 0.2), (0.4, 0.2)],
                 'dir': 0, 'size': 2, 'hits': set()})
            g['phase'] = 'battle'
            g['turn'] = 'player1'
            self.b_start.text = 'Бой идёт'
            self.update_panels()
            self.update_aim()
            self.redraw_all()
            if self.tut['waiting'] == 'start':
                self.tut_next()
            return
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
            elif g['mode'] == 'bluetooth':
                # В блютуз-режиме: ждём, пока второй игрок тоже поставит корабли
                self.set_msg('Ожидаем, пока соперник расставит корабли...', (0.3, 0.3, 0.5, 1))
                g['phase'] = 'place2_wait'
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
        elif g['phase'] == 'place2_wait':
            # Блютуз: ждём, пока соперник тоже нажмёт "Начать бой"
            self.set_msg('Ожидаем готовности соперника...', (0.3, 0.3, 0.5, 1))
            return
        else:
            return
        self.unit_state.update(selected=None, last=None)
        self.update_panels()
        self.update_aim()
        self.redraw_all()

    def make_move(self):
        g = self.game
        if self.tut['active']:
            if g['phase'] == 'battle':
                self.tutorial_fire()
            return
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

        # подсказка: 15 промахов подряд -> раскрыть одну вражескую клетку
        if self.settings['hints']:
            key = 'player1' if (g['mode'] == 'ai' or
                                g['turn'] == 'player1') else 'player2'
            if result == 'miss':
                g['streak'][key] += 1
                if g['streak'][key] >= 15:
                    g['streak'][key] = 0
                    if self.reveal_hint(target):
                        res_txt += ' 💡подсказка!'
            else:
                g['streak'][key] = 0
        g['last'] = res_txt

        if all_sunk(target['units']):
            g['phase'] = 'over'
            winner = 'Игрок 1' if g['mode'] == 'ai' or shooter == 'Игрок 1' \
                else 'Игрок 2'
            self.set_msg(f'{shooter.upper()} ПОБЕДИЛ(А)!',
                         (0, 0.5, 0, 1))
            self.update_panels()
            self.redraw_all()
            self.show_victory(f'Победил {self.nickname}!')
            # отправляем победу сопернику
            self.bt_send_move({'type': 'game_over', 'winner': self.nickname})
            return

        # ПРАВИЛО 6: попадание -> соперник пропускает ход
        extra_turn = result in ('hit', 'sunk')

        # отправляем ход сопернику по блютузу
        if g['mode'] == 'bluetooth':
            self.bt_send_move({
                'type': 'move',
                'point': self.shot_sel,
                'x': P[0], 'y': P[1],
                'result': result
            })

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
                # в блютуз-режиме нет экрана "нажмите на экран"
                if g['mode'] == 'bluetooth':
                    self.set_msg(f'{shooter}: {res_txt}  Ход соперника...', (0, 0.5, 0, 1))
                else:
                    g['awaiting_tap'] = True
                    n = '2' if g['turn'] == 'player2' else '1'
                    self.set_msg(f'Игрок {n} нажмите на экран',
                                 (0, 0, 0.5, 1))
            self.update_panels()
            self.redraw_all()

    def reveal_hint(self, fld):
        """Раскрыть одну случайную неподбитую клетку противника."""
        cands = [p for un in fld['units'] for p in un['pts']
                 if p not in un['hits']]
        if cands:
            fld['hints'].add(random.choice(cands))
            return True
        return False

    def show_victory(self, text):
        box = BoxLayout(orientation='vertical', padding=12, spacing=10)
        box.add_widget(Label(text=text, font_size='22sp', bold=True,
                             color=(0, 0, 0.5, 1)))
        box.add_widget(Label(text=f'Победитель: {self.nickname}',
                             font_size='16sp', color=(0, 0.5, 0, 1)))
        btn = Button(text='Показать раскладку', size_hint_y=None,
                     height='55dp', font_name='DejaVuSans')
        box.add_widget(btn)
        popup = Popup(title='Игра окончена', content=box,
                      size_hint=(0.7, 0.5), auto_dismiss=False)
        btn.bind(on_release=lambda *_: (popup.dismiss(),
                                        self.redraw_all()))
        popup.open()

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
            self.show_victory('Победил противник (ИИ)!')
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
