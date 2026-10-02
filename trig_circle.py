# -*- coding: utf-8 -*-
"""
ТРИГОНОМЕТРИЧЕСКИЙ МОРСКОЙ БОЙ

Главное меню:
  Начать игру    -> с компьютером (Низкий/Средний/Высокий) или ЛОКАЛЬНАЯ ИГРА
  Правила        -> правила игры
  Настройки      -> "Включить самолеты", "Включить музыку (будет потом)"
  Обратная связь -> konstantinkasatkin2@gmail.com

Локальная игра (2 игрока на одном экране):
  1) Игрок 1 (слева) расставляет юниты.
  2) Игрок 2 (справа) расставляет юниты — поле игрока 1 скрыто.
  3) Бой: в ход игрока поле соперника показывает ТОЛЬКО попадания/промахи.
"""

import random
import numpy as np
import matplotlib
matplotlib.rcParams['toolbar'] = 'None'   # убрать тулбар (крестик и др.)
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.widgets import Slider, RadioButtons, TextBox, Button

STEP = 0.1
GRID = 0.1
LIMIT = 1.6
ANGLE1_0 = 50
ANGLE2_0 = 110
HIT_TOL = 0.05
FADE = 0.1
FLEET_SHIPS  = {1: 5, 2: 4, 3: 3, 4: 2, 5: 1}
FLEET_PLANES = {1: 3, 2: 2, 3: 1}
MAX_SIZE = {'ship': 5, 'plane': 3}
UNIT_STYLE = {'ship':  {'marker': 'o', 'color': 'navy'},
              'plane': {'marker': '^', 'color': 'teal'}}

DIRECTIONS = [(1, 0), (1, 1), (0, 1), (-1, 1),
              (-1, 0), (-1, -1), (0, -1), (1, -1)]

ALL_CELLS = [(round(i * GRID, 2), round(j * GRID, 2))
             for i in range(-16, 17) for j in range(-16, 17)]
SQ_CELLS = [c for c in ALL_CELLS if abs(c[0]) <= 1 and abs(c[1]) <= 1]

settings = {'planes': True, 'music': False, 'difficulty': 'Средний'}

fig = plt.figure(figsize=(16, 9))
fig.canvas.manager.set_window_title('Тригонометрический морской бой')

axL = fig.add_axes([0.04, 0.28, 0.42, 0.64])
axR = fig.add_axes([0.54, 0.28, 0.42, 0.64])


def draw_static(ax, with_legend=False):
    theta = np.linspace(0, 2 * np.pi, 500)
    ax.plot(np.cos(theta), np.sin(theta), 'b-', linewidth=2,
            label='Единичная окружность' if with_legend else None)
    ax.plot([-1, 1, 1, -1, -1], [-1, -1, 1, 1, -1], color='black',
            linewidth=1.8, label='Квадрат [-1, 1]²' if with_legend else None)
    ax.plot([0, 1, 1, 0, 0], [0, 0, 1, 1, 0], color='dimgray',
            linestyle='-.', linewidth=1.4,
            label='Единичный квадрат' if with_legend else None)
    ax.annotate('', xy=(LIMIT, 0), xytext=(-LIMIT, 0),
                arrowprops=dict(arrowstyle='->', color='black', lw=1.4,
                                alpha=FADE))
    ax.annotate('', xy=(0, LIMIT), xytext=(0, -LIMIT),
                arrowprops=dict(arrowstyle='->', color='black', lw=1.4,
                                alpha=FADE))
    ax.axvline(1, color='red', linestyle='--', linewidth=1.6, alpha=FADE)
    ax.axhline(1, color='green', linestyle='--', linewidth=1.6, alpha=FADE)
    ticks_all = np.round(np.arange(-LIMIT, LIMIT + STEP, STEP), 1)
    labels = [f'{t + 0.0:.1f}' if -1.0 <= t <= 1.0 else ''
              for t in ticks_all]
    ax.set_xticks(ticks_all)
    ax.set_yticks(ticks_all)
    ax.set_xticklabels(labels, fontsize=6, rotation=90)
    ax.set_yticklabels(labels, fontsize=6)
    for lbl in ax.get_xticklabels() + ax.get_yticklabels():
        lbl.set_alpha(FADE)
    ax.grid(True, which='major', linestyle='-', linewidth=0.3,
            color='gray', alpha=0.5)
    ax.set_aspect('equal')
    ax.set_xlim(-LIMIT, LIMIT)
    ax.set_ylim(-LIMIT, LIMIT)


draw_static(axL)
draw_static(axR, with_legend=True)
axL.set_title('ПОЛЕ ИГРОКА 1', fontsize=13, fontweight='bold')
axR.set_title('ПОЛЕ ИГРОКА 2', fontsize=13, fontweight='bold')

# ===================== ПРИЦЕЛЫ (на обоих полях) =====================
def create_kit(ax, ray_color, marker, proj_color, with_float_texts):
    kit = {
        'ray':      ax.plot([], [], color=ray_color, lw=2)[0],
        'pt':       ax.plot([], [], marker, color=ray_color, ms=7)[0],
        'arc':      ax.plot([], [], color=ray_color, lw=1.2)[0],
        'ang_txt':  ax.text(0, 0, '', color=ray_color, fontsize=10),
        'cos_line': ax.plot([], [], color=proj_color, lw=1.2, alpha=FADE)[0],
        'sin_line': ax.plot([], [], color=proj_color, lw=1.2, alpha=FADE)[0],
        'tg_line':  ax.plot([], [], color='red', lw=1.2, alpha=FADE)[0],
        'tg_pt':    ax.plot([], [], 's', color='red', ms=7, alpha=FADE)[0],
        'ctg_line': ax.plot([], [], color='green', lw=1.2, alpha=FADE)[0],
        'ctg_pt':   ax.plot([], [], '^', color='green', ms=7, alpha=FADE)[0],
    }
    if with_float_texts:
        kit['cos_txt'] = ax.text(0, 0, '', color=proj_color, fontsize=9,
                                 alpha=FADE)
        kit['sin_txt'] = ax.text(0, 0, '', color=proj_color, fontsize=9,
                                 alpha=FADE)
        kit['tg_txt']  = ax.text(0, 0, '', color='red', fontsize=9,
                                 fontweight='bold', clip_on=True, alpha=FADE)
        kit['ctg_txt'] = ax.text(0, 0, '', color='green', fontsize=9,
                                 fontweight='bold', clip_on=True, alpha=FADE)
    return kit


def create_aim(ax):
    return {
        'ax': ax,
        'kit1': create_kit(ax, 'purple', 'o', 'blue', True),
        'kit2': create_kit(ax, 'darkorange', 'D', 'gray', False),
        'ext1': ax.plot([], [], color='purple', ls='--', lw=1.2,
                        alpha=FADE)[0],
        'i1': ax.plot([], [], '*', color='black', ms=16, zorder=5)[0],
        't1': ax.text(0, 0, '', color='black', fontsize=9, fontweight='bold',
                      clip_on=True,
                      bbox=dict(boxstyle='round', fc='lightyellow',
                                ec='gray', alpha=0.9)),
        'ext2': ax.plot([], [], color='darkorange', ls='--', lw=1.2,
                        alpha=FADE)[0],
        'i2': ax.plot([], [], '*', color='darkgreen', ms=16, zorder=5)[0],
        't2': ax.text(0, 0, '', color='darkgreen', fontsize=9,
                      fontweight='bold', clip_on=True,
                      bbox=dict(boxstyle='round', fc='honeydew', ec='gray',
                                alpha=0.9)),
        'info': ax.text(0.98, 0.98, '', transform=ax.transAxes, ha='right',
                        va='top', fontsize=9, family='monospace',
                        bbox=dict(boxstyle='round', fc='white', ec='gray',
                                  alpha=0.9)),
    }


aimL = create_aim(axL)
aimR = create_aim(axR)
aimR['kit1']['ray'].set_label('Угол 1 (ЛКМ)')
aimR['kit2']['ray'].set_label('Угол 2 (ПКМ)')
aimR['i1'].set_label('Точка пересечения P₁')
aimR['i2'].set_label('Точка пересечения P₂')

state = {'P1': None, 'P2': None}


def compute_angles():
    a1 = np.deg2rad(slider1.val)
    a2 = np.deg2rad(slider2.val)
    c1, s1 = float(np.cos(a1)), float(np.sin(a1))
    c2, s2 = float(np.cos(a2)), float(np.sin(a2))
    tg2 = s2 / c2 if abs(c2) > 1e-9 else None
    ctg2 = c2 / s2 if abs(s2) > 1e-9 else None
    return c1, s1, c2, s2, tg2, ctg2


def draw_kit(kit, angle_deg, primary):
    a = np.deg2rad(angle_deg)
    c, s = float(np.cos(a)), float(np.sin(a))
    kit['ray'].set_data([0, c], [0, s])
    kit['pt'].set_data([c], [s])
    kit['cos_line'].set_data([c, c], [0, s])
    kit['sin_line'].set_data([0, c], [s, s])
    arc_t = np.linspace(0, a, 120)
    kit['arc'].set_data(0.25 * np.cos(arc_t), 0.25 * np.sin(arc_t))
    kit['ang_txt'].set_position((0.34 * np.cos(a / 2), 0.34 * np.sin(a / 2)))
    kit['ang_txt'].set_text(f'{angle_deg:.0f}°')
    m = max(abs(c), abs(s))
    bx, by = (c / m, s / m) if m > 0 else (0.0, 0.0)
    kit['tg_line'].set_data([0, bx], [0, by])
    kit['ctg_line'].set_data([0, bx], [0, by])

    if abs(c) > 1e-9:
        kit['tg_pt'].set_data([1], [s / c])
        if primary:
            kit['tg_txt'].set_position((1.04, np.clip(s / c, -LIMIT + 0.1,
                                                      LIMIT - 0.1)))
            kit['tg_txt'].set_text(f'tg = {s / c:.2f}')
    else:
        kit['tg_pt'].set_data([], [])
        if primary:
            kit['tg_txt'].set_text('')
    if abs(s) > 1e-9:
        kit['ctg_pt'].set_data([c / s], [1])
        if primary:
            kit['ctg_txt'].set_position((np.clip(c / s, -LIMIT + 0.1,
                                                 LIMIT - 0.1), 1.08))
            kit['ctg_txt'].set_text(f'ctg = {c / s:.2f}')
    else:
        kit['ctg_pt'].set_data([], [])
        if primary:
            kit['ctg_txt'].set_text('')
    if primary:
        kit['cos_txt'].set_position((c - 0.15, -0.14))
        kit['cos_txt'].set_text(f'cos = {c:.2f}')
        kit['sin_txt'].set_position((-0.48, s))
        kit['sin_txt'].set_text(f'sin = {s:.2f}')


def clear_aim(aim):
    for kit in (aim['kit1'], aim['kit2']):
        for art in (kit['ray'], kit['pt'], kit['arc'], kit['cos_line'],
                    kit['sin_line'], kit['tg_line'], kit['tg_pt'],
                    kit['ctg_line'], kit['ctg_pt']):
            art.set_data([], [])
        for txt in kit.values():
            if isinstance(txt, matplotlib.text.Text):
                txt.set_text('')
    aim['ext1'].set_data([], [])
    aim['ext2'].set_data([], [])
    aim['i1'].set_data([], [])
    aim['i2'].set_data([], [])
    aim['t1'].set_text('')
    aim['t2'].set_text('')
    aim['info'].set_text('')


def draw_aim(aim, vals):
    c1, s1, c2, s2, tg2, ctg2 = vals
    draw_kit(aim['kit1'], slider1.val, primary=True)
    draw_kit(aim['kit2'], slider2.val, primary=False)

    if tg2 is not None:
        Px, Py = c1, tg2 * c1
        aim['ext1'].set_data([c1, c1], [s1, Py])
        aim['i1'].set_data([Px], [Py])
        aim['t1'].set_position((
            np.clip(Px + 0.06, -LIMIT + 0.05, LIMIT - 0.8),
            np.clip(Py, -LIMIT + 0.1, LIMIT - 0.15)))
        aim['t1'].set_text(f'P₁ = ({Px:.2f}, {Py:.2f})')
        p1_str = f'({Px: .2f}, {Py: .2f})'
    else:
        aim['ext1'].set_data([], [])
        aim['i1'].set_data([], [])
        aim['t1'].set_text('')
        p1_str = 'нет'

    if ctg2 is not None:
        Qx, Qy = ctg2 * s1, s1
        aim['ext2'].set_data([c1, Qx], [s1, s1])
        aim['i2'].set_data([Qx], [Qy])
        aim['t2'].set_position((
            np.clip(Qx + 0.06, -LIMIT + 0.05, LIMIT - 0.8),
            np.clip(Qy, -LIMIT + 0.1, LIMIT - 0.15)))
        aim['t2'].set_text(f'P₂ = ({Qx:.2f}, {Qy:.2f})')
        p2_str = f'({Qx: .2f}, {Qy: .2f})'
    else:
        aim['ext2'].set_data([], [])
        aim['i2'].set_data([], [])
        aim['t2'].set_text('')
        p2_str = 'нет'

    f = lambda v: f'{v: .2f}' if v is not None else '   —'
    aim['info'].set_text(
        f'угол 1 = {slider1.val:5.1f}°\n'
        f'  sin={f(s1)} cos={f(c1)}\n'
        f'угол 2 = {slider2.val:5.1f}°\n'
        f'  tg ={f(tg2)} ctg={f(ctg2)}\n'
        f'P₁ = {p1_str}\n'
        f'P₂ = {p2_str}')


def active_aim():
    """Прицел активен только в бою, на поле текущего стрелка."""
    if game['phase'] != 'battle':
        return None
    if game['mode'] == 'ai':
        return aimR
    return aimR if game['turn'] == 'player1' else aimL


def update_all(_=None):
    vals = compute_angles()
    c1, s1, c2, s2, tg2, ctg2 = vals
    state['P1'] = (c1, tg2 * c1) if tg2 is not None else None
    state['P2'] = (ctg2 * s1, s1) if ctg2 is not None else None
    act = active_aim()
    for aim in (aimL, aimR):
        if aim is act:
            draw_aim(aim, vals)
        else:
            clear_aim(aim)
    fig.canvas.draw_idle()


# ===================== ПОЛЯ И ЮНИТЫ =====================
def make_field(ax, name):
    return {
        'ax': ax, 'name': name, 'units': [], 'misses': [],
        'hit_layer':  ax.plot([], [], linestyle='', marker='x', color='red',
                              ms=14, mew=3, zorder=8)[0],
        'miss_layer': ax.plot([], [], linestyle='', marker='o',
                              color='silver', mec='gray', ms=6, zorder=7)[0],
        'halo_layer': ax.plot([], [], linestyle='', marker='x', color='gray',
                              ms=10, mew=2, zorder=7)[0],
        'preview':    ax.plot([], [], 'o-', lw=3, ms=8, alpha=0.55,
                              color='lime', zorder=6)[0],
    }


FL = make_field(axL, 'Игрок 1')
FR = make_field(axR, 'Игрок 2')

fleet_txt = axL.text(0.02, 0.98, '', transform=axL.transAxes, ha='left',
                     va='top', fontsize=9, family='monospace',
                     bbox=dict(boxstyle='round', fc='white', ec='gray',
                               alpha=0.9))
enemy_txt = axR.text(0.02, 0.98, '', transform=axR.transAxes, ha='left',
                     va='top', fontsize=9, family='monospace',
                     bbox=dict(boxstyle='round', fc='white', ec='gray',
                               alpha=0.9))
game_msg = fig.text(0.5, 0.955, '', ha='center', va='center',
                    fontsize=13, fontweight='bold')

unit_state = {'size': 3, 'dir_idx': 0, 'selected': None, 'last': None}
mode = {'name': 'angles'}
game = {'mode': 'ai', 'phase': 'place1', 'turn': 'player1',
        'my_moves': 0, 'enemy_moves': 0, 'last': '—'}
enemy_ai = {'tried': set(), 'hunt': [], 'thits': []}
shot_sel = {'p': 'P₁'}


def set_msg(text, color='black'):
    game_msg.set_text(text)
    game_msg.set_color(color)
    fig.canvas.draw_idle()


def fleets():
    return dict(FLEET_SHIPS), \
        (dict(FLEET_PLANES) if settings['planes'] else {})


def snap(v):
    return round(round(v / GRID) * GRID, 2)


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


def remaining(units):
    fsh, fpl = fleets()
    rem = {'ship': fsh, 'plane': fpl}
    for un in units:
        rem[un['type']][un['size']] -= 1
    return rem


def unit_at(units, x, y, tol=0.045):
    for un in reversed(units):
        for px, py in un['pts']:
            if abs(px - x) <= tol and abs(py - y) <= tol:
                return un
    return None


def is_sunk(un):
    return len(un['pts']) > 0 and len(un['hits']) == len(un['pts'])


def all_sunk(units):
    return len(units) > 0 and all(is_sunk(un) for un in units)


def base_color(un):
    return 'red' if is_sunk(un) else UNIT_STYLE[un['type']]['color']


def build_fld():
    """Поле, на котором сейчас идёт стройка."""
    if game['phase'] == 'place1':
        return FL
    if game['phase'] == 'place2':
        return FR
    return None


def target_fld():
    """Поле, по которому стреляет текущий игрок."""
    if game['mode'] == 'ai' or game['turn'] == 'player1':
        return FR
    return FL


def select(un):
    deselect()
    unit_state['selected'] = un
    if un is not None:
        un['line'].set_color('gold')
    fig.canvas.draw_idle()


def deselect():
    if unit_state['selected'] is not None:
        unit_state['selected']['line'].set_color(
            base_color(unit_state['selected']))
        unit_state['selected'] = None


def place_unit(fld, pts, dir_idx, size, utype, visible=True):
    st = UNIT_STYLE[utype]
    line, = fld['ax'].plot([p[0] for p in pts], [p[1] for p in pts],
                           marker=st['marker'], linestyle='-',
                           color=st['color'], lw=3, ms=8, zorder=6,
                           visible=visible)
    fld['units'].append({'type': utype, 'pts': pts, 'dir': dir_idx,
                         'size': size, 'line': line, 'hits': set(),
                         'fld': fld})
    apply_visibility()
    update_panels()
    fig.canvas.draw_idle()


def remove_unit(un):
    fld = un['fld']
    if unit_state['selected'] is un:
        unit_state['selected'] = None
    un['line'].remove()
    fld['units'].remove(un)
    refresh_field(fld)
    update_panels()
    update_preview()


def rotate(step):
    un = unit_state['selected']
    if un is None:
        unit_state['dir_idx'] = (unit_state['dir_idx'] + step) % 8
        update_preview()
    else:
        x0, y0 = un['pts'][0]
        new_dir = (un['dir'] + step) % 8
        new_pts = unit_points(x0, y0, un['size'], new_dir)
        if points_ok(new_pts, un['type'], un['fld']['units'], ignore=un):
            un['pts'] = new_pts
            un['dir'] = new_dir
            un['line'].set_data([p[0] for p in new_pts],
                                [p[1] for p in new_pts])
    update_panels()
    fig.canvas.draw_idle()


def cur_type():
    return 'plane' if mode['name'] == 'planes' else 'ship'


def update_preview():
    fld = build_fld()
    for f in (FL, FR):
        if f is not fld:
            f['preview'].set_data([], [])
    if fld is None or mode['name'] not in ('ships', 'planes') or \
       unit_state['last'] is None:
        if fld is not None:
            fld['preview'].set_data([], [])
        return
    gx, gy = unit_state['last']
    utype = cur_type()
    size = min(unit_state['size'], MAX_SIZE[utype])
    rem = remaining(fld['units'])[utype].get(size, 0)
    pts = unit_points(gx, gy, size, unit_state['dir_idx'])
    ok = points_ok(pts, utype, fld['units']) and rem > 0
    fld['preview'].set_data([p[0] for p in pts], [p[1] for p in pts])
    fld['preview'].set_marker(UNIT_STYLE[utype]['marker'])
    fld['preview'].set_color('lime' if ok else 'red')
    fig.canvas.draw_idle()


# ===================== ВИДИМОСТЬ ЮНИТОВ =====================
def unit_visible(un, fld):
    """Классические правила скрытия: чужие юниты не видны (кроме потопленных)."""
    if game['phase'] == 'over' or is_sunk(un):
        return True
    if game['mode'] == 'ai':
        return fld is FL
    if game['phase'] == 'place1':
        return fld is FL
    if game['phase'] == 'place2':
        return fld is FR
    # локальный бой: своё поле видно, поле соперника — нет
    own = (fld is FL) == (game['turn'] == 'player1')
    return own


def apply_visibility():
    for fld in (FL, FR):
        for un in fld['units']:
            un['line'].set_visible(unit_visible(un, fld))
    fig.canvas.draw_idle()


# ===================== ВЫСТРЕЛЫ =====================
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
                if q in occupied:
                    continue
                halo.add(q)
    return halo


def refresh_field(fld):
    xs, ys, hx, hy = [], [], [], []
    for un in fld['units']:
        for p in un['hits']:
            xs.append(p[0])
            ys.append(p[1])
        if is_sunk(un):
            if un is not unit_state['selected']:
                un['line'].set_color('red')
            for q in halo_points(un, fld['units']):
                hx.append(q[0])
                hy.append(q[1])
    fld['hit_layer'].set_data(xs, ys)
    fld['halo_layer'].set_data(hx, hy)
    fld['miss_layer'].set_data([m[0] for m in fld['misses']],
                               [m[1] for m in fld['misses']])
    apply_visibility()


def fire_at(fld, Px, Py):
    for un in fld['units']:
        for p in un['pts']:
            if p not in un['hits'] and \
               abs(Px - p[0]) <= HIT_TOL and abs(Py - p[1]) <= HIT_TOL:
                un['hits'].add(p)
                return 'sunk' if is_sunk(un) else 'hit'
    fld['misses'].append((round(Px, 3), round(Py, 3)))
    return 'miss'


# ===================== ПРОТИВНИК (ИИ) =====================
def enemy_place():
    fsh, fpl = fleets()
    for utype, fleet in (('ship', fsh), ('plane', fpl)):
        for size in sorted(fleet, reverse=True):
            for _ in range(fleet[size]):
                for _try in range(600):
                    x0 = random.randint(-10, 10) / 10
                    y0 = random.randint(-10, 10) / 10
                    d = random.randrange(8)
                    pts = unit_points(round(x0, 2), round(y0, 2), size, d)
                    if points_ok(pts, utype, FR['units']):
                        place_unit(FR, pts, d, size, utype, visible=False)
                        break
    update_panels()


def enemy_pick_cell():
    diff = settings['difficulty']
    while enemy_ai['hunt']:
        p = enemy_ai['hunt'].pop(0)
        if p not in enemy_ai['tried']:
            return p
    untried = [c for c in SQ_CELLS if c not in enemy_ai['tried']]
    if diff != 'Низкий':
        cb = [c for c in untried
              if (round(c[0] / GRID) + round(c[1] / GRID)) % 2 == 0]
        if cb:
            untried = cb
    return random.choice(untried) if untried else None


def enemy_turn():
    cell = enemy_pick_cell()
    if cell is None:
        return
    enemy_ai['tried'].add(cell)
    game['enemy_moves'] += 1
    result = fire_at(FL, cell[0], cell[1])
    diff = settings['difficulty']
    if result in ('hit', 'sunk') and diff != 'Низкий':
        enemy_ai['thits'].append(cell)
        for dx, dy in ((GRID, 0), (-GRID, 0), (0, GRID), (0, -GRID)):
            q = (round(cell[0] + dx, 2), round(cell[1] + dy, 2))
            if q in SQ_CELLS and q not in enemy_ai['tried']:
                enemy_ai['hunt'].append(q)
        if diff == 'Высокий' and len(enemy_ai['thits']) >= 2:
            dx = round(enemy_ai['thits'][-1][0] - enemy_ai['thits'][-2][0], 2)
            dy = round(enemy_ai['thits'][-1][1] - enemy_ai['thits'][-2][1], 2)
            q = (round(cell[0] + dx, 2), round(cell[1] + dy, 2))
            if q in SQ_CELLS and q not in enemy_ai['tried']:
                enemy_ai['hunt'].insert(0, q)
    if result == 'sunk':
        enemy_ai['thits'] = []
    refresh_field(FL)
    txt = {'hit': 'ПОПАДАНИЕ!', 'sunk': 'ПОТОПЛЕН ВАШ ЮНИТ!',
           'miss': 'мимо'}[result]
    set_msg(f'Противник стреляет ({cell[0]:.1f}, {cell[1]:.1f}) — {txt}',
            'darkred' if result != 'miss' else 'black')
    update_panels()
    plt.pause(0.7)
    if all_sunk(FL['units']):
        game['phase'] = 'over'
        set_msg('ПРОТИВНИК ПОБЕДИЛ. Все ваши юниты потоплены.', 'darkred')
        apply_visibility()
    elif result in ('hit', 'sunk'):
        # ПРАВИЛО 6 (для ИИ): попадание -> игрок пропускает ход
        set_msg(f'Противник попал ({cell[0]:.1f}, {cell[1]:.1f}) — '
                f'вы пропускаете ход!', 'darkred')
        plt.pause(0.7)
        enemy_turn()


# ===================== ХОД ИГРЫ =====================
def make_move(_=None):
    if game['phase'] != 'battle':
        set_msg('Сначала завершите расстановку юнитов!')
        return
    if game['mode'] == 'ai' and game['turn'] != 'player1':
        return

    P = state['P1'] if shot_sel['p'] == 'P₁' else state['P2']
    if P is None:
        set_msg(f'точка {shot_sel["p"]} не определена')
        return

    target = target_fld()
    shooter = 'Вы' if game['mode'] == 'ai' else \
        ('Игрок 1' if game['turn'] == 'player1' else 'Игрок 2')

    if abs(P[0]) > 1 or abs(P[1]) > 1:
        result = 'miss'
        res_txt = 'МИМО (вне квадрата)'
        target['misses'].append((round(P[0], 3), round(P[1], 3)))
    else:
        result = fire_at(target, P[0], P[1])
        res_txt = {'hit': 'ПОПАДАНИЕ!', 'sunk': 'ПОТОПЛЕН!',
                   'miss': 'МИМО'}[result]

    game['my_moves'] += 1
    game['last'] = res_txt
    refresh_field(target)
    update_panels()

    if all_sunk(target['units']):
        game['phase'] = 'over'
        if game['mode'] == 'ai':
            set_msg(f'ПОБЕДА! Флот противника уничтожен за '
                    f'{game["my_moves"]} ходов!', 'darkgreen')
        else:
            set_msg(f'{shooter.upper()} ПОБЕДИЛ! Все юниты соперника '
                    f'потоплены.', 'darkgreen')
        apply_visibility()
        return

    # ПРАВИЛО 6: попадание -> соперник пропускает ход (стрелок ходит снова)
    extra_turn = result in ('hit', 'sunk')

    if game['mode'] == 'ai':
        if extra_turn:
            set_msg(f'{res_txt} Противник пропускает ход — '
                    f'стреляйте ещё раз!', 'darkgreen')
        else:
            set_msg(f'Ваш ход ({shot_sel["p"]}): {res_txt}  '
                    f'Теперь ход противника...')
            game['turn'] = 'enemy'
            fig.canvas.draw_idle()
            plt.pause(0.5)
            enemy_turn()
            if game['phase'] == 'battle':
                game['turn'] = 'player1'
                set_msg(f'ВАШ ХОД ({shot_sel["p"]}). Последний выстрел: '
                        f'{res_txt}', 'darkgreen')
    else:
        if extra_turn:
            set_msg(f'{shooter}: {res_txt} Соперник пропускает ход — '
                    f'{shooter} ходит снова!', 'darkgreen')
        else:
            game['turn'] = 'player2' if game['turn'] == 'player1' \
                else 'player1'
            nxt = 'Игрок 1' if game['turn'] == 'player1' else 'Игрок 2'
            side = 'правом' if game['turn'] == 'player1' else 'левом'
            set_msg(f'{shooter}: {res_txt}   →   ХОД {nxt.upper()}А '
                    f'(прицел на {side} поле)', 'darkgreen')
            apply_visibility()
    update_panels()
    update_all()


def advance(_=None):
    """Кнопка 'Начать бой' / 'Готово'."""
    if game['phase'] == 'place1':
        if not FL['units']:
            set_msg('Игрок 1: постройте хотя бы один юнит!', 'darkred')
            return
        if game['mode'] == 'ai':
            enemy_place()
            game['phase'] = 'battle'
            game['turn'] = 'player1'
            btn_start.label.set_text('Бой идёт')
            set_msg('ВАШ ХОД: выберите P₁ или P₂, наведите и жмите '
                    '"Совершить ход"', 'darkgreen')
        else:
            game['phase'] = 'place2'
            btn_start.label.set_text('Готово (Игрок 2)')
            set_msg('Игрок 2 расставляет юниты на ПРАВОМ поле. '
                    'Поле игрока 1 скрыто.', 'navy')
    elif game['phase'] == 'place2':
        if not FR['units']:
            set_msg('Игрок 2: постройте хотя бы один юнит!', 'darkred')
            return
        game['phase'] = 'battle'
        game['turn'] = 'player1'
        btn_start.label.set_text('Бой идёт')
        set_msg('ХОД ИГРОКА 1 (прицел на правом поле)', 'darkgreen')
    else:
        return
    deselect()
    unit_state['last'] = None
    update_preview()
    apply_visibility()
    update_panels()
    update_all()


def reset_game():
    for fld in (FL, FR):
        for un in fld['units'][:]:
            un['line'].remove()
        fld['units'].clear()
        fld['misses'].clear()
        refresh_field(fld)
    enemy_ai['tried'].clear()
    enemy_ai['hunt'].clear()
    enemy_ai['thits'].clear()
    game.update(phase='place1', turn='player1', my_moves=0,
                enemy_moves=0, last='—')
    unit_state.update(selected=None, last=None)
    btn_start.label.set_text('Начать бой' if game['mode'] == 'ai'
                             else 'Готово (Игрок 1)')
    slider1.reset()
    slider2.reset()
    for f in (FL, FR):
        f['preview'].set_data([], [])
    apply_visibility()
    update_panels()
    update_all()


# ===================== ПАНЕЛИ =====================
def build_lines(units, title):
    fsh, fpl = fleets()
    rem = remaining(units)
    lines = [title]
    for s in sorted(fsh):
        row = f'{s}: {"■" * rem["ship"][s]}' \
              f'{"□" * (fsh[s] - rem["ship"][s])}'
        if fpl and s in fpl:
            row += f'  {"▲" * rem["plane"][s]}' \
                   f'{"△" * (fpl[s] - rem["plane"][s])}'
        lines.append(row)
    if not fpl:
        lines.append('самолёты выкл.')
    return lines


def alive_lines(units, title):
    fsh, fpl = fleets()
    alive = {'ship': dict.fromkeys(fsh, 0), 'plane': dict.fromkeys(fpl, 0)}
    for un in units:
        if not is_sunk(un):
            alive[un['type']][un['size']] += 1
    lines = [title]
    for s in sorted(fsh):
        row = f'{s}: {"■" * alive["ship"][s]}'
        if fpl and s in fpl:
            row += f'  {"▲" * alive["plane"][s]}'
        lines.append(row)
    hits = sum(len(un['hits']) for un in units)
    sunks = sum(1 for un in units if is_sunk(un))
    lines.append(f'подбито: {hits}  потоплено: {sunks}')
    return lines


def build_status_line():
    if mode['name'] not in ('ships', 'planes'):
        return ''
    utype = cur_type()
    size = min(unit_state['size'], MAX_SIZE[utype])
    fld = build_fld()
    rem = remaining(fld['units'])[utype].get(size, 0) if fld else 0
    dx, dy = DIRECTIONS[unit_state['dir_idx']]
    deg = int(np.degrees(np.arctan2(dy, dx)) % 360)
    return f'размер {size} (ост. {rem}), {deg}°'


def update_panels():
    ph, md = game['phase'], game['mode']
    # левая панель
    if ph == 'place1':
        lines = build_lines(FL['units'], 'ИГРОК 1 — СТРОЙКА:')
        st = build_status_line()
        if st:
            lines.append(st)
    else:
        lines = alive_lines(FL['units'],
                            'ИГРОК 1 (в живых):' if md == 'local'
                            else 'МОИ ЮНИТЫ (в живых):')
    fleet_txt.set_text('\n'.join(lines))

    # правая панель
    if md == 'ai':
        if ph == 'place1':
            lines = ['ПРОТИВНИК:', 'расставляет флот...']
        else:
            lines = alive_lines(FR['units'], 'ПРОТИВНИК (в живых):')
            lines.append(f'мои ходы: {game["my_moves"]}  '
                         f'его ходы: {game["enemy_moves"]}')
    else:
        if ph == 'place2':
            lines = build_lines(FR['units'], 'ИГРОК 2 — СТРОЙКА:')
            st = build_status_line()
            if st:
                lines.append(st)
        elif ph == 'place1':
            lines = ['ИГРОК 2:', 'ждёт своей очереди...']
        else:
            lines = alive_lines(FR['units'], 'ИГРОК 2 (в живых):')
    enemy_txt.set_text('\n'.join(lines))
    fig.canvas.draw_idle()


# ===================== ИГРОВЫЕ ВИДЖЕТЫ =====================
ax_s1 = fig.add_axes([0.25, 0.16, 0.5, 0.022])
ax_s2 = fig.add_axes([0.25, 0.13, 0.5, 0.022])
slider1 = Slider(ax_s1, 'Угол 1, °', 0, 360, valinit=ANGLE1_0,
                 valstep=1, valfmt='%0.0f', color='purple')
slider2 = Slider(ax_s2, 'Угол 2, °', 0, 360, valinit=ANGLE2_0,
                 valstep=1, valfmt='%0.0f', color='darkorange')
slider1.on_changed(update_all)
slider2.on_changed(update_all)


def make_box(x, label, initial):
    bax = fig.add_axes([x, 0.085, 0.10, 0.03])
    tb = TextBox(bax, label, initial=initial)
    tb.label.set_fontsize(9)
    return tb


_a1 = np.deg2rad(ANGLE1_0)
_a2 = np.deg2rad(ANGLE2_0)
tb_sin = make_box(0.20, 'sin₁ ', f'{np.sin(_a1):.2f}')
tb_cos = make_box(0.34, 'cos₁ ', f'{np.cos(_a1):.2f}')
tb_tg  = make_box(0.48, 'tg₂ ', f'{np.tan(_a2):.2f}')
tb_ctg = make_box(0.62, 'ctg₂ ', f'{1 / np.tan(_a2):.2f}')

btn_move_ax = fig.add_axes([0.80, 0.085, 0.12, 0.045])
btn_move = Button(btn_move_ax, 'Совершить ход',
                  color='lightgoldenrodyellow', hovercolor='gold')
btn_move.on_clicked(make_move)

btn_start_ax = fig.add_axes([0.80, 0.025, 0.12, 0.045])
btn_start = Button(btn_start_ax, 'Начать бой',
                   color='lightgreen', hovercolor='lime')
btn_start.on_clicked(advance)

shot_label = fig.text(0.80, 0.208, 'Огонь:', fontsize=9, fontweight='bold')
shot_ax = fig.add_axes([0.80, 0.145, 0.10, 0.058])
shot_radio = RadioButtons(shot_ax, ('P₁', 'P₂'), active=0, useblit=False)
for t in shot_ax.texts:
    t.set_fontsize(9)


def on_shot(label):
    shot_sel['p'] = label
    fig.canvas.draw_idle()


shot_radio.on_clicked(on_shot)

btn_menu_ax = fig.add_axes([0.03, 0.025, 0.08, 0.04])
btn_menu = Button(btn_menu_ax, 'Меню', color='lightgray',
                  hovercolor='silver')


def parse_tb(tb):
    try:
        return float(tb.text.replace(',', '.').strip())
    except ValueError:
        return None


def nearest_angle(cands, ref):
    return min(cands, key=lambda a: abs((a - ref + 180) % 360 - 180))


def submit_sin(_):
    v = parse_tb(tb_sin)
    if v is None or abs(v) > 1:
        return
    a1 = np.deg2rad(slider1.val)
    slider1.set_val(np.degrees(np.arctan2(v, np.cos(a1))) % 360)


def submit_cos(_):
    v = parse_tb(tb_cos)
    if v is None or abs(v) > 1:
        return
    a1 = np.deg2rad(slider1.val)
    slider1.set_val(np.degrees(np.arctan2(np.sin(a1), v)) % 360)


def submit_tg(_):
    v = parse_tb(tb_tg)
    if v is None:
        return
    base = np.degrees(np.arctan(v)) % 360
    slider2.set_val(nearest_angle([base, (base + 180) % 360], slider2.val))


def submit_ctg(_):
    v = parse_tb(tb_ctg)
    if v is None:
        return
    if abs(v) < 1e-12:
        slider2.set_val(nearest_angle([90.0, 270.0], slider2.val))
    else:
        base = np.degrees(np.arctan(1.0 / v)) % 360
        slider2.set_val(nearest_angle([base, (base + 180) % 360],
                                      slider2.val))


tb_sin.on_submit(submit_sin)
tb_cos.on_submit(submit_cos)
tb_tg.on_submit(submit_tg)
tb_ctg.on_submit(submit_ctg)

mode_label = fig.text(0.02, 0.955, 'Режим:', fontsize=9, fontweight='bold')
mode_ax = fig.add_axes([0.012, 0.82, 0.085, 0.125])
mode_radio = RadioButtons(mode_ax, ('Углы', 'Корабли', 'Самолёты'), active=0,
                          useblit=False)
for t in mode_ax.texts:
    t.set_fontsize(9)


def on_mode(label):
    mode['name'] = {'Углы': 'angles', 'Корабли': 'ships',
                    'Самолёты': 'planes'}[label]
    if mode['name'] == 'planes':
        unit_state['size'] = min(unit_state['size'], MAX_SIZE['plane'])
    if mode['name'] == 'angles':
        for f in (FL, FR):
            f['preview'].set_data([], [])
        unit_state['last'] = None
        deselect()
    update_panels()
    fig.canvas.draw_idle()


mode_radio.on_clicked(on_mode)

hint_text = fig.text(0.5, 0.235,
                     'Стройка: ЛКМ — построить/выбрать, колесо или R — '
                     'поворот, 1–5 (1–3) — размер, ПКМ — удалить\n'
                     'Бой: ЛКМ/ПКМ — прицел по активному полю, поля sin₁ '
                     'cos₁ tg₂ ctg₂ + Enter, огонь P₁/P₂ → "Совершить ход"\n'
                     'Корабли — внутри окружности, самолёты — внутри '
                     'квадрата, но вне окружности, выстрел — в границах '
                     'квадрата',
                     ha='center', va='top', fontsize=8.5, color='dimgray')

# ===================== ЭКРАНЫ / МЕНЮ =====================
# Меню рисуется вручную в ОДНОЙ полноэкранной оси (ui_ax): кнопки —
# прямоугольники (FancyBboxPatch) + текст, клики обрабатываются сами.
# Это надёжнее виджетов matplotlib при перекрывающихся осях.
game_axes = [axL, axR, ax_s1, ax_s2, btn_move_ax, btn_start_ax, shot_ax,
             btn_menu_ax, mode_ax,
             tb_sin.ax, tb_cos.ax, tb_tg.ax, tb_ctg.ax]
game_texts = [game_msg, mode_label, shot_label, hint_text]

ui_ax = fig.add_axes([0, 0, 1, 1])
ui_ax.set_facecolor('whitesmoke')
ui_ax.set_xticks([])
ui_ax.set_yticks([])
for sp in ui_ax.spines.values():
    sp.set_visible(False)
ui_ax.set_navigate(False)

screens = {}       # имя экрана -> список его артистов
menu_buttons = []  # (патч кнопки, callback)
cur_screen = {'name': 'menu'}


def ui_text(screen, x, y, s, **kw):
    kw.setdefault('transform', ui_ax.transAxes)
    kw.setdefault('ha', 'center')
    kw.setdefault('va', 'center')
    t = ui_ax.text(x, y, s, **kw)
    screens.setdefault(screen, []).append(t)
    return t


def ui_button(screen, x, y, w, h, label, callback,
              color='lightsteelblue', fontsize=13):
    patch = mpatches.FancyBboxPatch(
        (x, y), w, h, boxstyle='round,pad=0.008',
        transform=ui_ax.transAxes, facecolor=color, edgecolor='black',
        linewidth=1.2, zorder=3)
    ui_ax.add_patch(patch)
    screens.setdefault(screen, []).append(patch)
    ui_text(screen, x + w / 2, y + h / 2, label, fontsize=fontsize, zorder=4)
    menu_buttons.append((patch, callback))
    return patch


def ui_checkbox(screen, x, y, label, getter, setter):
    box = mpatches.Rectangle((x, y), 0.032, 0.042,
                             transform=ui_ax.transAxes, facecolor='white',
                             edgecolor='black', linewidth=1.4, zorder=3)
    ui_ax.add_patch(box)
    screens.setdefault(screen, []).append(box)
    mark = ui_text(screen, x + 0.016, y + 0.021, '✓', fontsize=15,
                   color='darkgreen', fontweight='bold', zorder=4)
    ui_text(screen, x + 0.05, y + 0.021, label, fontsize=13, ha='left',
            zorder=4)
    mark.set_visible(getter())

    def toggle():
        setter(not getter())
        mark.set_visible(getter())
        fig.canvas.draw_idle()

    menu_buttons.append((box, toggle))


def show_screen(name):
    cur_screen['name'] = name
    is_game = (name == 'game')
    ui_ax.set_visible(not is_game)
    for a in game_axes:
        a.set_visible(is_game)
    for t in game_texts:
        t.set_visible(is_game)
    for n, arts in screens.items():
        for art in arts:
            art.set_visible(n == name)
    fig.canvas.draw_idle()


def on_ui_press(event):
    """Клики по кнопкам меню (свой hit-test по видимым патчам)."""
    if cur_screen['name'] == 'game' or event.inaxes is not ui_ax:
        return
    for patch, cb in menu_buttons:
        if patch.get_visible() and patch.contains(event)[0]:
            cb()
            return


# --- Главное меню ---
ui_text('menu', 0.5, 0.78, 'Тригонометрический\nморской бой',
        fontsize=30, fontweight='bold', color='navy')
ui_button('menu', 0.38, 0.56, 0.24, 0.08, 'Начать игру',
          lambda: show_screen('difficulty'))
ui_button('menu', 0.38, 0.45, 0.24, 0.08, 'Правила',
          lambda: show_screen('rules'))
ui_button('menu', 0.38, 0.34, 0.24, 0.08, 'Настройки',
          lambda: show_screen('settings'))
ui_button('menu', 0.38, 0.23, 0.24, 0.08, 'Обратная связь',
          lambda: show_screen('feedback'))

# --- Выбор режима/сложности ---
ui_text('difficulty', 0.30, 0.72, 'С компьютером:', fontsize=16,
        fontweight='bold')
ui_text('difficulty', 0.72, 0.72, 'Вдвоём на одном экране:', fontsize=16,
        fontweight='bold')


def choose_diff(diff):
    settings['difficulty'] = diff
    game['mode'] = 'ai'
    reset_game()
    show_screen('game')
    set_msg(f'Сложность: {diff}. Расставьте флот на ЛЕВОМ поле и нажмите '
            f'"Начать бой"', 'navy')


def start_local():
    game['mode'] = 'local'
    reset_game()
    show_screen('game')
    set_msg('ЛОКАЛЬНАЯ ИГРА. Игрок 1 расставляет юниты на ЛЕВОМ поле, '
            'затем — "Готово (Игрок 1)"', 'navy')


ui_button('difficulty', 0.21, 0.58, 0.18, 0.08, 'Низкий',
          lambda: choose_diff('Низкий'), color='honeydew')
ui_button('difficulty', 0.21, 0.47, 0.18, 0.08, 'Средний',
          lambda: choose_diff('Средний'), color='lightgoldenrodyellow')
ui_button('difficulty', 0.21, 0.36, 0.18, 0.08, 'Высокий',
          lambda: choose_diff('Высокий'), color='mistyrose')
ui_button('difficulty', 0.61, 0.42, 0.22, 0.22, 'Локальная\nигра',
          lambda: start_local(), color='lavender', fontsize=16)
ui_button('difficulty', 0.38, 0.16, 0.24, 0.08, 'Назад',
          lambda: show_screen('menu'), color='lightgray')

# --- Правила ---
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
ui_text('rules', 0.5, 0.62, RULES, fontsize=13)
ui_button('rules', 0.38, 0.08, 0.24, 0.08, 'Назад',
          lambda: show_screen('menu'), color='lightgray')

# --- Настройки ---
ui_text('settings', 0.5, 0.78, 'Настройки', fontsize=22, fontweight='bold')
ui_checkbox('settings', 0.36, 0.60, 'Включить самолеты',
            lambda: settings['planes'],
            lambda v: settings.__setitem__('planes', v))
ui_checkbox('settings', 0.36, 0.52, 'Включить музыку (будет потом)',
            lambda: settings['music'],
            lambda v: settings.__setitem__('music', v))
ui_button('settings', 0.38, 0.22, 0.24, 0.08, 'Назад',
          lambda: show_screen('menu'), color='lightgray')

# --- Обратная связь ---
ui_text('feedback', 0.5, 0.6, 'Обратная связь:\n\n'
        'konstantinkasatkin2@gmail.com', fontsize=20, fontweight='bold')
ui_button('feedback', 0.38, 0.25, 0.24, 0.08, 'Назад',
          lambda: show_screen('menu'), color='lightgray')

btn_menu.on_clicked(lambda _: show_screen('menu'))

# ===================== СОБЫТИЯ =====================
dragging = {'btn': None}


def on_press(event):
    on_ui_press(event)
    if event.xdata is None:
        return
    aim = active_aim()
    if aim is not None and event.inaxes == aim['ax']:
        if event.button in (1, 3):
            dragging['btn'] = event.button
        return
    fld = build_fld()
    if fld is not None and event.inaxes == fld['ax'] and \
       mode['name'] in ('ships', 'planes'):
        gx, gy = snap(event.xdata), snap(event.ydata)
        hit = unit_at(fld['units'], event.xdata, event.ydata)
        utype = cur_type()
        if event.button == 1:
            if hit is not None:
                select(hit)
            else:
                deselect()
                size = min(unit_state['size'], MAX_SIZE[utype])
                pts = unit_points(gx, gy, size, unit_state['dir_idx'])
                if remaining(fld['units'])[utype].get(size, 0) > 0 and \
                   points_ok(pts, utype, fld['units']):
                    place_unit(fld, pts, unit_state['dir_idx'], size, utype)
        elif event.button == 3:
            if hit is not None:
                remove_unit(hit)


def on_release(event):
    dragging['btn'] = None


def on_motion(event):
    if event.xdata is None:
        return
    aim = active_aim()
    if aim is not None and event.inaxes == aim['ax']:
        if dragging['btn']:
            angle = np.degrees(np.arctan2(event.ydata, event.xdata)) % 360
            (slider1 if dragging['btn'] == 1 else slider2).set_val(angle)
        return
    fld = build_fld()
    if fld is not None and event.inaxes == fld['ax'] and \
            mode['name'] in ('ships', 'planes'):
        unit_state['last'] = (snap(event.xdata), snap(event.ydata))
        update_preview()


def on_scroll(event):
    fld = build_fld()
    if fld is not None and event.inaxes == fld['ax'] and \
       mode['name'] in ('ships', 'planes'):
        rotate(1 if event.button == 'up' else -1)


def on_key(event):
    if build_fld() is None or mode['name'] not in ('ships', 'planes'):
        return
    k = event.key
    max_size = MAX_SIZE[cur_type()]
    if k in ('1', '2', '3', '4', '5') and int(k) <= max_size:
        unit_state['size'] = int(k)
        update_preview()
        update_panels()
    elif k == 'r':
        rotate(1)
    elif k == 'z':
        fld = build_fld()
        if fld['units']:
            remove_unit(fld['units'][-1])
    elif k == 'c':
        fld = build_fld()
        for un in fld['units'][:]:
            remove_unit(un)
    elif k == 'escape':
        deselect()
        fig.canvas.draw_idle()
    elif k == 'delete':
        if unit_state['selected'] is not None:
            remove_unit(unit_state['selected'])


fig.canvas.mpl_connect('button_press_event', on_press)
fig.canvas.mpl_connect('button_release_event', on_release)
fig.canvas.mpl_connect('motion_notify_event', on_motion)
fig.canvas.mpl_connect('scroll_event', on_scroll)
fig.canvas.mpl_connect('key_press_event', on_key)

axR.legend(loc='lower left', fontsize=9)
update_panels()
update_all()
show_screen('menu')
plt.show()
