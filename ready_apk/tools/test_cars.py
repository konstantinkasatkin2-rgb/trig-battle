# -*- coding: utf-8 -*-
"""Проверки нового режима: машинки и препятствия (версия 0.3.3).

Модель игры: отдельного «нападающего» и «защитника» нет. Каждый игрок
одновременно и защитник, и нападающий:
  * свои машинки ставит на поле СОПЕРНИКА (за пределами окружности);
  * свои стены строит на СВОЁМ поле (внутри окружности) и только
    во время боя, в свой ход, одна за ход;
  * машинка, коснувшаяся жёлтого круга на чужом поле, приносит победу;
  * у кого кончились машинки — тот проиграл;
  * чужие фигуры видны только после столкновения;
  * у границы квадрата и при таране машинка разворачивается на 180°.

Запуск:  python ready_apk/tools/test_cars.py
"""

import io
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import pygame                                            # noqa: E402
import profiles as profiles_db                            # noqa: E402

Profiles = profiles_db.Profiles
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

# сколько ждём сообщений по сети в проверках (секунды)
NET_WAIT = 15.0

ok = True


def check(cond, ok_msg, fail_msg):
    global ok
    print(('  OK   ' if cond else '  FAIL ') + (ok_msg if cond else fail_msg))
    ok = ok and bool(cond)
    return bool(cond)


def new_app(w=1280, h=720):
    app = TrigBattle()
    app.layout(w, h)
    app.build_ui()
    app.show_screen('game')
    return app


def tap(app, fld, x, y, btn=1):
    """Тап по клетке поля (в координатах поля)."""
    side = 'L' if fld is app.FL else 'R'
    app.board_touch(side, app.to_px(side, x, y), 'down', btn)


def car_draw_radius(app, side, un):
    """Радиус круга машинки, который приложение рисует на самом деле."""
    got = []
    orig = pygame.draw.circle

    def spy(surf, color, center, radius, width=0):
        if width == 0:
            got.append(radius)
        return orig(surf, color, center, radius, width)

    pygame.draw.circle = spy
    try:
        app.car_draw_car(app.base, un, side)
    finally:
        pygame.draw.circle = orig
    return got[0] if got else 0


def put_cars(app, who, pts):
    """Расставляет машинки игрока who на поле его соперника."""
    app.game['turn'] = who
    for p in pts:
        tap(app, app.car_foe_fld(), *p)
    app.game['turn'] = who


# клетки для машинок: за пределами единичной окружности, внутри квадрата
# и не ближе двух клеток друг друг (иначе стянутся)
# квадрата и не ближе двух клеток друг к другу (иначе ст��наются)
CAR_CELLS_L = [(-1.0, -1.0), (-1.0, -0.7), (-1.0, -0.4), (-1.0, -0.2)]
CAR_CELLS_R = [(-x, -y) for (x, y) in CAR_CELLS_L]
CORNERS = {'player1': CAR_CELLS_L, 'player2': CAR_CELLS_R}


def battle_app(cars=2, walls=0, play='local', human='player1'):
    """Готовая партия: машинки расставлены, стены (если walls) — в бою."""
    app = new_app()
    app.car_start(play, human)
    put_cars(app, 'player1', CORNERS['player1'][:cars])
    app.advance()
    if play == 'local':
        put_cars(app, 'player2', CORNERS['player2'][:cars])
        app.advance()
    else:
        app.advance()            # ИИ расставит свои машинки сам
    for who, n in (('player1', walls), ('player2', walls)):
        if not n:
            continue
        app.game['turn'] = who
        fld = app.car_fld_of(who)
        for i in range(n):
            app.game['turn'] = who
            tap(app, fld, 0.4 + 0.1 * i, 0.4)
    app.game['turn'] = 'player1'
    return app


def do_move(app, un):
    """Ход фигуры так, как это делает игрок: выбрать и нажать кнопку.

    turn выставляется обязательно: чужая фигура за ход не едет.
    """
    app.game['turn'] = app.car_owner(un)
    app.car_clear_sel()
    app.car_select(un)
    app.car_make_move()
    return un['pts'][0]


def steer_to_center(app, un):
    """Курс фигуры, который уменьшает расстояние до центра."""
    x, y = un['pts'][0]
    best, bd = None, abs(x) + abs(y)
    for d in range(8):
        dx, dy = DIRECTIONS[d]
        nxt = (round(x + dx * GRID, 2), round(y + dy * GRID, 2))
        if not app.car_in_square(nxt):
            continue
        dist = abs(nxt[0]) + abs(nxt[1])
        if dist < bd:
            best, bd = d, dist
    if best is not None:
        un['dir'] = best


def main():
    pygame.init()
    pygame.display.set_mode((1280, 720))
    import trig_battle_pygame as g                       # noqa: E402
    globals().update(g.__dict__)

    print('Проверка нового режима 0.3.3: машинки и препятствия')

    # --- 1. флоты ---
    check(sum(FLEET_WALLS.values()) == 10 and
          FLEET_WALLS == {1: 4, 2: 3, 3: 2, 4: 1},
          'препятствия 1:4, 2:3, 3:2, 4:1 (всего %d)'
          % sum(FLEET_WALLS.values()),
          'флот препятствий неверный: %r' % (FLEET_WALLS,))
    check(sum(FLEET_CARS.values()) == 4,
          'машинок %d' % sum(FLEET_CARS.values()),
          'флот машинок неверный: %r' % (FLEET_CARS,))
    check(YELLOW_R == 0.2, 'жёлтый круг [-0.2; 0.2]',
          'жёлтый круг неверный: %r' % YELLOW_R)

    # --- 2. зоны расстановки ---
    app = battle_app()
    check(app.car_points_ok([(0.9, 0.9)], 'car', []),
          'машинку можно поставить в углу за окружностью',
          'машинку нельзя поставить в углу')
    check(not app.car_points_ok([(0.2, 0.2)], 'car', []),
          'машинку нельзя поставить внутри окружности',
          'машинку можно поставить внутри окружности')
    check(app.car_points_ok([(0.3, 0.3)], 'wall', []),
          'стену можно поставить внутри окружности',
          'стену нельзя поставить внутри окружности')
    check(not app.car_points_ok([(0.9, 0.9)], 'wall', []),
          'стену нельзя поставить снаружи (на territory врага)',
          'стена встала снаружи окружности')
    check(not app.car_points_ok([(0.1, 0.1)], 'wall', []),
          'жёлтый круг закрывать нельзя',
          'жёлтый круг можно закрыть')

    # --- 3. модель сторон: владелец поля и владелец фигуры ---
    app = new_app()
    app.car_start('local')
    check(app.car_side_of_fld(app.FL) == 'player1' and
          app.car_side_of_fld(app.FR) == 'player2',
          'поля принадлежат игрокам: левое — игроку 1',
          'владение полями определено неверно')
    app.game['turn'] = 'player1'
    check(app.car_my_fld() is app.FL and app.car_foe_fld() is app.FR,
          'в свой ход играем на своём поле (левое) и атакуем правое',
          'своё/чужие поля перепутаны')
    put_cars(app, 'player1', [(-0.9, -0.9)])
    car1 = app.car_my_cars()[0]
    check(car1['fld'] is app.FR,
          'своя машинка стоит на поле СОПЕРНИКА',
          'машинка стоит не на поле соперника')
    check(app.car_owner(car1) == 'player1',
          'владелец машинки — поставивший её игрок',
          'владелец машинки определён неверно')
    app.game['turn'] = 'player2'
    put_cars(app, 'player2', [(0.9, 0.9)])
    car2 = app.car_my_cars()[0]
    check(car2['fld'] is app.FL and app.car_owner(car2) == 'player2',
          'машинка игрока 2 стоит на поле игрока 1',
          'второй игрок ставит машинку не туда')
    wall = None
    app.place_unit(app.FL, [(0.4, 0.4)], 0, 1, 'wall')
    wall = app.FL['units'][-1]
    check(app.car_owner(wall) == 'player1',
          'стена принадлежит владельцу поля, где стоит',
          'владелец стены определён неверно')

    # --- 4. расстановка: только машинки и только на поле врага ---
    app = new_app()
    app.car_start('local')
    n_before = len(app.FL['units']) + len(app.FR['units'])
    tap(app, app.car_my_fld(), 0.4, 0.4)              # своё поле — нельзя
    check(len(app.FL['units']) + len(app.FR['units']) == n_before,
          'на своём поле на расстановке ничего не ставится',
          'на своём поле что-то поставили')
    tap(app, app.car_foe_fld(), -0.9, -0.9)
    check(len(app.car_owner_cars('player1')) == 1,
          'машинка ставится на поле соперника',
          'машинка не поставилась')
    app.advance()
    check(app.game['phase'] == 'place' and
          app.game['turn'] == 'player2',
          'после «Готово» ход переходит второму игроку (фаза %s, ход %s)'
          % (app.game['phase'], app.game['turn']),
          'после «Готово» не переход ко второму: %s/%s'
          % (app.game['phase'], app.game['turn']))
    put_cars(app, 'player2', [(0.9, 0.9)])
    app.advance()
    check(app.game['phase'] == 'battle',
          'после расстановки обоих начинается бой',
          'бой не начался: фаза %s' % app.game['phase'])
    check(not app.car_units('wall'),
          'до боя стен на поле нет',
          'стены появились до боя: %d' % len(app.car_units('wall')))

    # --- 5. стены: только в бою, на своём поле, одна за ход ---
    app = battle_app()
    my, foe = app.FL, app.FR
    n_foe = len([u for u in foe['units'] if u['type'] == 'wall'])
    tap(app, foe, 0.4, 0.4)
    check(len([u for u in foe['units'] if u['type'] == 'wall']) == n_foe,
          'в бою стена на чужом поле не строится',
          'стена построена на чужом поле')
    n_my = len([u for u in my['units'] if u['type'] == 'wall'])
    app.game['turn'] = 'player1'
    tap(app, my, 0.4, 0.4)
    n_after = len([u for u in my['units'] if u['type'] == 'wall'])
    check(n_after == n_my + 1,
          'в свой ход стена на своём поле строится',
          'стена на своём поле не построилась: %d -> %d' % (n_my, n_after))
    check(app.game['turn'] == 'player2',
          'после стены ход уходит сопернику',
          'ход остался у построившего: %s' % app.game['turn'])
    app.game['turn'] = 'player1'
    tap(app, my, 0.5, 0.4)
    check(len([u for u in my['units'] if u['type'] == 'wall']) == n_after,
          'вторую стену за один ход поставить нельзя',
          'за один ход построено несколько стен')
    app.game['turn'] = 'player2'
    tap(app, my, 0.5, 0.4)
    check(len([u for u in my['units'] if u['type'] == 'wall']) == n_after,
          'в чужой ход стена на этом поле не строится',
          'стена построена не в свой ход')
    app.game['turn'] = 'player1'
    tap(app, my, 0.1, 0.1)
    check(len([u for u in my['units'] if u['type'] == 'wall']) == n_after,
          'на жёлтый круг стена не ставится',
          'стена встала на жёлтый круг')

    # --- 6. стена не наезжает на другую стену своего поля ---
    app = battle_app()
    my = app.FL
    for un in list(my['units']):
        if un['type'] == 'wall':
            my['units'].remove(un)
    app.place_unit(my, [(0.4, 0.4)], 0, 1, 'wall')
    app.place_unit(my, [(0.5, 0.4)], 0, 1, 'wall')
    wall = my['units'][-2]
    wall['dir'] = 0
    do_move(app, wall)
    check(wall['pts'][0] == (0.4, 0.4),
          'стена не встаёт на соседнюю стену: %r' % (wall['pts'][0],),
          'стены слиплись: стена уехала на %r' % (wall['pts'][0],))

    # --- 7. ход машинки: клетка, диагональ, запас ходов ---
    app = battle_app()
    car = app.car_owner_cars('player1')[0]
    car['dir'] = 0
    before = car['pts'][0]
    do_move(app, car)
    dx = round(car['pts'][0][0] - before[0], 3)
    check(abs(dx - GRID) < 1e-6,
          'прямой ход — ровно одна клетка: %r -> %r' % (before, car['pts'][0]),
          'прямой ход неверный: %r -> %r' % (before, car['pts'][0]))
    # диагональ проверяем на машинке, которой есть куда ехать по
    # диагонали: из угла квадрата ход был бы запрещён
    diag = app.car_owner_cars('player1')[-1]
    diag['dir'] = 7
    before = diag['pts'][0]
    do_move(app, diag)
    ddx = abs(diag['pts'][0][0] - before[0])
    ddy = abs(diag['pts'][0][1] - before[1])
    check(abs(ddx - ddy) < 1e-6 and abs(ddx - GRID) < 1e-6,
          'диагональный ход — тоже клетка по обеим осям',
          'диагональный ход неверный: (%.3f, %.3f)' % (ddx, ddy))
    check(car['left'] == CAR_STEPS - 1,
          'каждый ход тратит запас: осталось %d' % car['left'],
          'ходы не тратятся: осталось %d' % car['left'])

    # --- 7a. выбрать можно не больше трёх машинок ---
    app = battle_app(cars=3)
    cars = app.car_owner_cars('player1')
    check(len(cars) == 3,
          'машинок на поле соперника: %d' % len(cars),
          'машинок на поле соперника: %d' % len(cars))
    for c in cars[:3]:
        app.car_select(c)
    check(len([c for c in app.car_selected() if c['type'] == 'car']) == 3,
          'выбраны три машинки из трёх',
          'выбрано %d машинок'
          % len([c for c in app.car_selected() if c['type'] == 'car']))
    before = {id(c): tuple(c['pts'][0]) for c in app.car_selected()}
    app.game['turn'] = 'player1'
    app.car_make_move()
    moved = [c for c in cars[:3] if tuple(c['pts'][0]) != before[id(c)]]
    check(len(moved) == 3,
          '«Совершить ход» двигает все выбранные машинки (%d из 3)'
          % len(moved),
          'двинулись только %d из 3 машинок' % len(moved))
    check(app.game['turn'] == 'player2',
          'после хода выбирает соперник',
          'ход остался у игрока: %s' % app.game['turn'])
    # четвёртую машинку выбрать нельзя
    app = battle_app(cars=4)
    cars = app.car_owner_cars('player1')
    if len(cars) == 4:
        for c in cars[:3]:
            app.car_select(c)
        app.car_select(cars[3])
        n_sel = len([c for c in app.car_selected() if c['type'] == 'car'])
        check(n_sel == 3,
              'четвёртую машинку выбрать нельзя (максимум %d)'
              % app.CAR_SELECT_MAX,
              'выбрано %d машинок вместо %d' % (n_sel, app.CAR_SELECT_MAX))
    else:
        check(False, 'машинок должно быть 4, а их %d' % len(cars),
              'машинок %d, ожидалось 4' % len(cars))

    # --- 8. разворот у границы квадрата ---
    app = battle_app()
    cf = app.car_foe_fld()
    side = 'L' if cf is app.FL else 'R'
    bad = []
    for d, start in enumerate([(1.0, 0.0), (0.9, 0.9), (0.0, 1.0),
                               (-0.9, 0.9), (-1.0, 0.0), (-0.9, -0.9),
                               (0.0, -1.0), (0.9, -0.9)]):
        for un in list(cf['units']):
            if un['type'] == 'car':
                cf['units'].remove(un)
        app.place_unit(cf, [start], d, 1, 'car')
        car = cf['units'][-1]
        car['left'] = CAR_STEPS
        do_move(app, car)
        if not (car['dir'] == (d + 4) % 8 or car['pts'][0] != start):
            bad.append(d)
    check(not bad,
          'у границы квадрата машинка разворачивается на 180° (8 '
          'направлений)',
          'не развернулись направления: %r' % bad)
    for un in list(cf['units']):
        if un['type'] == 'car':
            cf['units'].remove(un)
    app.place_unit(cf, [(1.0, 0.0)], 0, 1, 'car')
    car = cf['units'][-1]
    car['left'] = CAR_STEPS
    do_move(app, car)
    check(car['pts'][0] == (1.0, 0.0) and car['dir'] == 4,
          'у границы машинка остаётся на клетке и разворачивается',
          'у границы: %r, направление %d' % (car['pts'][0], car['dir']))
    app.game['turn'] = app.car_owner(car)
    app.car_clear_sel()
    app.car_select(car)
    app.car_make_move()
    check(car['pts'][0] == (0.9, 0.0),
          'после разворота уезжает внутрь: %r' % (car['pts'][0],),
          'после разворота осталась на месте: %r' % (car['pts'][0],))
    do_move(app, car)

    # --- 9. таран: разворот, стена теряет клетку, обе стороны раскрыты ---
    app = battle_app()
    walls = [u for u in app.FL['units'] if u['type'] == 'wall']
    cars = [u for u in app.FR['units'] if u['type'] == 'car']
    app.place_unit(app.FL, [(0.3, 0.4), (0.4, 0.4)], 0, 2, 'wall')
    wall = app.FL['units'][-1]
    car = cars[0]
    car['pts'] = [(0.2, 0.4)]
    car['dir'] = 0
    # смотрим глазами соперника: у него эта стена чужая
    app.game['turn'] = 'player2'
    check(not app.car_seen(wall, 'R'),
          'чужая стена не видна до столкновения',
          'чужая стена видна заранее')
    do_move(app, car)
    check(car['dir'] == 4,
          'при таране машинка разворачивается на 180°',
          'машинка не развернулась: направление %d' % car['dir'])
    check(len(wall['pts']) == 1,
          'стена теряет клетку от тарана: %r' % (wall['pts'],),
          'стена не пострадала: %r' % (wall['pts'],))
    check(app.car_seen(wall, 'R') and car.get('revealed'),
          'после тарана стена и машинка раскрыты',
          'после тарана фигуры не раскрылись')
    check(walls is not None, 'стены обеих игроков на своих полях', '')

    # --- 10. машинка коснулась жёлтого круга: победа атаковавшего ---
    app = battle_app()
    for fld in (app.FL, app.FR):
        for un in list(fld['units']):
            if un['type'] == 'wall':
                fld['units'].remove(un)
    car = app.car_owner_cars('player1')[0]
    car['pts'] = [(0.1, 0.0)]
    car['dir'] = 0
    do_move(app, car)
    check(app.game['phase'] == 'over',
          'касание жёлтого круга заканчивает партию',
          'партия не закончилась: фаза %s' % app.game['phase'])
    check('победил' in app.msg[0],
          'в финале называется победитель: %r' % app.msg[0],
          'в финале нет победителя: %r' % app.msg[0])

    # --- 11. кончились машинки: проигравший определён верно ---
    app = battle_app(cars=1)
    car = app.car_owner_cars('player2')[0]
    # из угла квадрата
    # машинка только
    # разворачивается,
    # поэтому ставим
    # её у края, откуда
    # уедет и потратит
    # последний ход
    car['pts'] = [(1.0, 0.6)]
    car['dir'] = 3
    car['left'] = 1
    do_move(app, car)
    check(app.game['phase'] == 'over' and 'проиграл' in app.msg[0],
          'кончились машинки — игрок проиграл: %r' % app.msg[0],
          'итог неверный: фаза %s, %r' % (app.game['phase'], app.msg[0]))
    check(not app.car_owner_cars('player1') == [],
          'у победителя машинки остались',
          'у победителя машинки тоже исчезли')

    # --- 12. туман ---
    app = battle_app()
    walls = [u for u in app.FL['units'] if u['type'] == 'wall']
    if not walls:
        app.place_unit(app.FL, [(0.4, 0.4)], 0, 1, 'wall')
        walls = [app.FL['units'][-1]]
    wall = walls[0]
    app.game['turn'] = 'player2'      # смотрим глазами соперника
    check(not app.car_seen(wall, 'R'),
          'чужая стена на чужом поле скрыта, пока не врезались',
          'чужая стена видна до столкновения')
    check(not app.car_seen(app.car_owner_cars('player1')[0], 'L'),
          'чужая машинка скрыта, пока не врезалась',
          'чужая машинка видна сразу')
    app.game['turn'] = 'player1'      # смотрим глазами хозяина
    check(app.car_seen(wall, 'L'),
          'на своём поле стена видна',
          'на своём поле стена скрыта')
    check(app.car_seen(app.car_owner_cars('player1')[0], 'R'),
          'своя машинка на поле врага видна',
          'своя машинка на поле врага не видна')

    # --- 13. размер машинки = примерно клетка ---
    app = battle_app()
    car = app.car_owner_cars('player1')[0]
    side = 'L' if car['fld'] is app.FL else 'R'
    cell_px = GRID * app.br[side].width * 0.96 / (2 * LIMIT)
    r = car_draw_radius(app, side, car)
    check(0.7 * cell_px <= 2 * r <= 1.6 * cell_px,
          'машинка размером примерно в клетку: диаметр %d px, клетка '
          '%.1f px' % (2 * r, cell_px),
          'машинка не размером в клетку: диаметр %d px, клетка %.1f px'
          % (2 * r, cell_px))
    check(r == max(3, int(CAR_R * app.br[side].width)),
          'радиус машинки берётся из CAR_R (%.3f)' % CAR_R,
          'радиус машинки не соответствует CAR_R')

    # --- 14. ход машинки виден плавно ---
    app = battle_app()
    car = app.car_owner_cars('player1')[0]
    car['dir'] = 0
    do_move(app, car)
    check(car.get('anim') is not None,
          'ход машинки показывается плавно',
          'после хода анимации нет — движение не видно')
    car['anim'] = ([(-1.5, 0.0)], 0)
    check(app.car_anim_pos(car) == car['pts'][0],
          'анимация заканчивается на новой клетке',
          'анимация не доходит до новой клетки')

    # --- 15. препятствие вращается ---
    app = battle_app()
    my = app.FL
    for cells in ([(-0.6, 0.2), (-0.5, 0.2), (-0.4, 0.2)],
                  [(0.2, -0.6), (0.2, -0.5), (0.2, -0.4)]):
        for un in list(my['units']):
            if un['type'] == 'wall':
                my['units'].remove(un)
        app.place_unit(my, list(cells), 0, len(cells), 'wall')
        wall = my['units'][-1]
        app.select(wall)
        app.on_rotate(1)
        turned = (wall['dir'] != 0 and len(wall['pts']) == len(cells) and
                  app.car_points_ok(wall['pts'], 'wall', my['units'],
                                    ignore=wall))
        check(turned, '«Поворот» разворачивает препятствие %r -> %r'
              % (cells, wall['pts']),
              'препятствие не повернулось: %r' % (wall['pts'],))
        app.select(wall)
        app.on_rotate(7)
        check(wall['dir'] == 0 and
              app.car_points_ok(wall['pts'], 'wall', my['units'],
                                ignore=wall),
              'полный оборот (8×45°) возвращает направление стены: %r'
              % (wall['pts'],),
              'после оборота стена нелегална: %r (направление %d)'
              % (wall['pts'], wall['dir']))

    # --- 16. элементы управления без тригонометрии ---
    app = battle_app()
    check(not any(w.visible for w in app.row_angles),
          'ползунков углов на экране нет',
          'ползунки углов видны')
    check(not any(w.visible for w in (app.f_sin, app.f_cos, app.f_tg,
                                      app.f_ctg)),
          'полей sin/cos/tg/ctg на экране нет',
          'поля ввода угла видны')
    check(app.btn_wait.visible, 'кнопка «Ждать» на месте',
          'кнопки «Ждать» нет')
    check(app.btn_move.label == 'Ход',
          'кнопка хода называется «Ход»', 'подпись: %r' % app.btn_move.label)
    check(not app.btn_reset_ang.visible,
          '«Сброс углов» скрыта — углов тут нет',
          '«Сброс углов» видна')
    check(not app.btn_start.visible,
          'в бою кнопка «Готово» скрыта',
          '«Готово» видна в бою')
    app.game['phase'] = 'place'
    app.cars_widgets_apply()
    check(app.btn_start.visible,
          'на расстановке «Готово» на месте',
          '«Готово» не появилась на расстановке')
    app.game['phase'] = 'battle'
    app.game['mode'] = 'ai'
    app.cars_widgets_apply()
    check(any(w.visible for w in app.row_angles),
          'в тригонометрическом режиме углы вернулись',
          'углы не вернулись после выхода из нового режима')
    app.game['mode'] = CAR_MODE

    # --- 17. экран рисуется и подписей лишних нет ---
    app = battle_app(walls=2)
    try:
        app.draw()
        drew = True
        err = ''
    except Exception as e:                               # noqa: BLE001
        drew, err = False, repr(e)
    check(drew, 'кадр нового режима рисуется', 'падение: %s' % err)
    seen = []
    orig = g.blit_text

    def spy(surf, text, *a, **kw):
        seen.append(text)
        return orig(surf, text, *a, **kw)

    g.blit_text = spy
    try:
        app.draw()
    finally:
        g.blit_text = orig
    bad = [t for t in seen
           if any(w in t for w in ('Угол', 'Прицел:', 'Режим:', 'Размер:',
                                   'Огонь:', 'ctg', 'tg2', 'МОИ ЮНИТЫ',
                                   'сложность:'))]
    check(not bad, 'на экране боя нет тригонометрических подписей',
          'остались лишние подписи: %r' % bad[:6])
    check(any('ИГРОК 1' in t for t in seen) and
          any('ИГРОК 2' in t for t in seen),
          'на экране есть названия сторон',
          'нет названий сторон на экране')

    # --- 18. меню ---
    app = new_app()
    names = set(app.screens)
    check({'menu', 'difficulty', 'play_trig', 'play_cars', 'ai_diff',
           'cars_role'} <= names,
          'экраны выбора режима и типа игры на месте',
          'нет экранов: %s' % sorted(
              {'menu', 'difficulty', 'play_trig', 'play_cars'} - names))
    labels = {s: [getattr(w, 'label', '') for w in app.screens[s]]
              for s in ('difficulty', 'play_trig', 'play_cars', 'ai_diff',
                        'cars_role')}
    check('Тригонометрический морской бой' in labels['difficulty'] and
          'Новый режим' in labels['difficulty'],
          'после «Начать игру» — два режима',
          'на экране выбора нет двух режимов: %r' % labels['difficulty'])
    want = ['Игра против ИИ', 'Игра против игрока', 'Туториал', 'Игра по сети']
    for scr, title in (('play_cars', 'нового режима'),
                       ('play_trig', 'тригонометрического режима')):
        check(all(w in labels[scr] for w in want),
              'у %s есть все четыре кнопки' % title,
              'у %s неполный набор: %r' % (title, labels[scr]))
    check(labels['ai_diff'][:3] == ['Низкий', 'Средний', 'Высокий'],
          'сложность выбирается отдельным экраном',
          'на экране сложности не три уровня: %r' % labels['ai_diff'])
    check(labels['cars_role'][:2] == ['Я — МАШИНКИ', 'Я — ПРЕПЯТСТВИЯ'],
          'роль против ИИ выбирается отдельным экраном',
          'на экране роли нет двух кнопок: %r' % labels['cars_role'])

    # --- 19. туториал ---
    app = new_app()
    app.start_cars_tutorial()
    check(app.cars_tut_active() and len(app.CAR_TUT) == 5,
          'туториал запускается, шагов %d' % len(app.CAR_TUT),
          'туториал не запустился или шагов %d' % len(app.CAR_TUT))
    check('СОПЕРНИКА' in app.msg[0],
          'туториал объясняет, что машинки ставятся на поле соперника',
          'в туториале нет про поле соперника: %r' % app.msg[0][:60])
    put_cars(app, 'player1', [(-0.9, -0.9)])
    check(app.cars_tut.get('step') == 1,
          'после постановки машинки туториал идёт дальше',
          'шаг туториала не сменился: %r' % app.cars_tut)
    app.unit_state['selected'] = app.car_my_cars()[0]
    app.on_rotate(1)
    check(app.cars_tut.get('step') == 2,
          'после поворота туториал идёт дальше',
          'шаг туториала не сменился: %r' % app.cars_tut)
    app.advance()
    check(app.game['phase'] == 'battle' and app.cars_tut.get('step') == 3,
          'после «Готово» бой начинается и туториал ждёт стену',
          'после «Готово»: фаза %s, шаг %r'
          % (app.game['phase'], app.cars_tut))

    # --- 20. против ИИ ---
    app = new_app()
    app.car_start('ai', 'player1')
    put_cars(app, 'player1', CORNERS['player1'][:2])
    app.advance()
    ai_cars = [u for u in app.car_my_fld()['units'] if u['type'] == 'car']
    check(app.game['phase'] == 'battle' and len(ai_cars) >= 1,
          'ИИ поставил свои машинки на наше поле: %d' % len(ai_cars),
          'ИИ не поставил машинки на наше поле: %d' % len(ai_cars))
    app.game['turn'] = 'player1'
    tap(app, app.car_my_fld(), 0.4, 0.4)
    check(len([u for u in app.car_my_fld()['units']
               if u['type'] == 'wall']) == 1,
          'игрок построил стену на своём поле',
          'стена игрока не построилась')
    ai_walls_before = len([u for u in app.car_ai_fld()['units']
                           if u['type'] == 'wall'])
    for _ in range(3):
        if app.game['phase'] != 'battle':
            break
        if app.game['turn'] == app.car_ai_side():
            app.car_ai_turn()
        else:
            cars = app.car_my_cars()
            if not cars:
                break
            steer_to_center(app, cars[0])
            do_move(app, cars[0])
    ai_walls_after = len([u for u in app.car_ai_fld()['units']
                          if u['type'] == 'wall'])
    check(ai_walls_after > ai_walls_before,
          'ИИ тоже строит стены на своём поле: %d -> %d'
          % (ai_walls_before, ai_walls_after),
          'ИИ стены не строит: %d -> %d' % (ai_walls_before, ai_walls_after))

    # --- 21. по сети ---
    import netgame                                   # noqa: E402
    tcp, udp = 39601, 39602
    netgame.DEFAULT_TCP_PORT = tcp
    netgame.DEFAULT_UDP_PORT = udp
    host, cli = new_app(), new_app()
    for a in (host, cli):
        a.pending_mode = CAR_MODE
    host.net = netgame.HostServer('Хост', tcp_port=tcp, udp_port=udp)
    host.net.start_beacon()
    host.net_role = 'host'
    host.net_state = 'waiting'
    cli.net = netgame.Client('Клиент')
    cli.net_role = 'client'
    cli.net_state = 'waiting'
    cli.net.search_code(host.net.code, udp_port=udp)
    deadline = time.time() + NET_WAIT
    while time.time() < deadline:
        host._net_poll()
        cli._net_poll()
        if host.net_state == 'connected' and cli.net_state == 'connected':
            break
        time.sleep(0.02)
    check(host.net_state == 'connected' and cli.net_state == 'connected',
          'соединение в новом режиме установлено',
          'соединение не установлено: %s/%s'
          % (host.net_state, cli.net_state))
    check(host.car_mode() and cli.car_mode(),
          'обе стороны в новом режиме',
          'режим сбился: %r/%r' % (host.game['mode'], cli.game['mode']))
    my_fld = 'FL' if host.car_my_fld() is host.FL else 'FR'
    check(my_fld != ('FL' if cli.car_my_fld() is cli.FL else 'FR'),
          'у сторон разные поля: хост %s, клиент %s'
          % (my_fld, 'FL' if cli.car_my_fld() is cli.FL else 'FR'),
          'у сторон одно и то же поле')

    put_cars(host, 'player1', [(-0.9, -0.9), (-0.9, 0.9)])
    host.advance()
    deadline = time.time() + NET_WAIT
    while time.time() < deadline and cli.game['phase'] != 'place':
        host._net_poll()
        cli._net_poll()
        time.sleep(0.02)
    put_cars(cli, cli.car_now(), [(0.9, -0.9), (0.9, 0.9)])
    cli.advance()
    deadline = time.time() + NET_WAIT
    while time.time() < deadline:
        host._net_poll()
        cli._net_poll()
        if host.game['phase'] == 'battle' and cli.game['phase'] == 'battle':
            break
        time.sleep(0.02)
    check(host.game['phase'] == 'battle' and cli.game['phase'] == 'battle',
          'бой начался у обеих сторон',
          'бой не начался: %s/%s' % (host.game['phase'], cli.game['phase']))
    check(len(host.car_owner_cars(cli.car_now())) == 2,
          'машинки соперника пришли на наше поле',
          'машинки соперника не пришли: %d'
          % len(host.car_owner_cars(cli.car_now())))
    check(not host.car_units('wall') and not cli.car_units('wall'),
          'до боя стен нет ни у кого',
          'до боя появились стены')

    # стена в бою уходит сопернику
    who = host.car_now()
    host.game['turn'] = who
    mine = host.car_my_fld()
    my_side = 'L' if mine is host.FL else 'R'
    host.unit_state['size'] = 2
    n_my_walls = len([u for u in mine['units'] if u['type'] == 'wall'])
    host.board_touch(my_side, host.to_px(my_side, 0.4, 0.4), 'down', 1)
    check(len([u for u in mine['units'] if u['type'] == 'wall']) ==
          n_my_walls + 1,
          'стена в бою построена у соперника на своём поле',
          'стена не построилась: %d -> %d'
          % (n_my_walls,
             len([u for u in mine['units'] if u['type'] == 'wall'])))
    # состояние соперника смотрим на его стороне: у клиента наше
    # поле — это car_peer_fld() с его точки зрения
    peer_fld = cli.car_peer_fld(my_side)
    deadline = time.time() + NET_WAIT
    while time.time() < deadline:
        host._net_poll()
        cli._net_poll()
        if [u for u in peer_fld['units'] if u['type'] == 'wall']:
            break
        time.sleep(0.02)
    peer_walls = [u for u in peer_fld['units'] if u['type'] == 'wall']
    check(len(peer_walls) == 1 and
          sorted(peer_walls[0]['pts']) == sorted(mine['units'][-1]['pts']),
          'стена, построенная в бою, доехала до соперника: %r'
          % (peer_walls[0]['pts'] if peer_walls else None,),
          'стена соперника не появилась: %r' % peer_walls)

    # ход фигуры одинаков у обеих сторон
    wall = mine['units'][-1]
    wall['dir'] = 0
    do_move(host, wall)
    deadline = time.time() + NET_WAIT
    while time.time() < deadline and peer_walls[-1]['pts'] != wall['pts']:
        host._net_poll()
        cli._net_poll()
        cli.draw()
        time.sleep(0.02)
    check(peer_walls[-1]['pts'] == wall['pts'],
          'ход стены одинаков у обеих сторон: %r' % (wall['pts'],),
          'ходы разошлись: хост %r, клиент %r'
          % (wall['pts'], peer_walls[-1]['pts']))

    # --- 21. панель нового режима: без тригонометрии ---
    app = battle_app()
    app.draw()
    trig_widgets = [w for w in app.row_angles if w.visible]
    trig_fields = [f for f in (app.f_sin, app.f_cos, app.f_tg, app.f_ctg)
                   if f.visible]
    check(not trig_widgets and not trig_fields,
          'в новом режиме тригонометрических полей нет',
          'в новом режиме видны тригонометрические элементы: '
          '%d ползунков, %d полей' % (len(trig_widgets), len(trig_fields)))
    panel = set(id(w) for w in app.row_cars)
    left_over = [w.label for w in app.row_build
                 if w is not None and w.visible and id(w) not in panel
                 and w not in app.size_buttons]
    check(not left_over,
          'третий ряд (режимы, размеры, поворот) в новом режиме скрыт',
          'в новом режиме видны лишние кнопки: %s' % left_over)
    names = [b.label for b in app.row_cars]
    check(names == ['Машинки', 'Стены', 'Поворот', 'Готов',
                    'Совершить ход', 'Выход'],
          'у нового режима своя панель: %s' % ', '.join(names),
          'панель нового режима неверная: %s' % ', '.join(names))
    check(app.btn_exit.rect.right <= app.W
          and app.btn_exit.rect.top >= app.H - app.CTRL_H,
          'кнопки панели помещаются в экран',
          'панель вылезла за экран: %r' % (app.btn_exit.rect,))
    check(app.btn_commit.visible is True and app.btn_ready.visible is False,
          'в бою видна «Совершить ход», а «Готов» спрятана',
          'кнопки хода показаны неверно: Готов=%s Ход=%s'
          % (app.btn_ready.visible, app.btn_commit.visible))
    app.game['phase'] = 'place'
    app.draw()
    check(app.btn_commit.visible is False and app.btn_ready.visible is True,
          'на расстановке «Готов» есть, а «Совершить ход» — нет',
          'на расстановке кнопки перепутаны: Готов=%s Ход=%s'
          % (app.btn_ready.visible, app.btn_commit.visible))

    # --- 22. выбор «Машинки»/«Стены» и запрет машинок в бою ---
    app = battle_app()
    app.car_set_kind('wall')
    check(app.unit_state.get('car_kind_btn') == 'wall',
          'кнопка «Стены» переключает, что ставим',
          'переключение «Стены» не сработало')
    app.car_set_kind('car')
    check('ДО боя' in app.msg[0] or 'стены' in app.msg[0].lower(),
          'в бою машинки ставить нельзя — сообщение объясняет почему',
          'в бою можно выбрать машинки молча: %r' % app.msg[0])

    # --- 23. после нового режима тригонометрия возвращается ---
    app = new_app()
    app.car_start('local')
    app.show_screen('menu')
    app.choose_diff('Средний')
    check(any(w.visible for w in app.row_angles)
          and any(f.visible for f in (app.f_sin, app.f_cos, app.f_tg,
                                      app.f_ctg)),
          'после нового режима тригонометрия снова на месте',
          'после нового режима тригонометрия не вернулась: %s'
          % app.mode['name'])
    check(app.btn_aim1.visible and app.btn_shot1.visible
          and not app.btn_wait.visible,
          'в тригонометрии есть прицел и огонь, а «Ждать» спрятана',
          'интерфейс тригонометрии после нового режима битый')
    app.set_mode('angles')
    app.set_angle1(35)
    app.set_angle2(70)
    app.update_angles()
    app.draw()
    check(set(app.aim_points_drawn) == {'P1', 'P2'},
          'точки пересечения рисуются уже на расстановке: %s'
          % app.aim_points_drawn,
          'точки пересечения не нарисованы: %s' % app.aim_points_drawn)

    # --- 24. после выхода из режима не остаётся последнего действия ---
    app = battle_app()
    app.set_msg('Ход сделан: машинка проехала', NAVY)
    app.game['last'] = 'Машинка проехала на клетку'
    app.show_screen('menu')
    check(app.msg[0] == '' and app.game['last'] == '\u2014',
          'после выхода из режима нижняя надпись чистая',
          'после выхода осталось: %r / %r'
          % (app.msg[0][:30], app.game['last']))

    # --- 25. статистика игрока ---
    app = new_app()
    app.profile_db = Profiles(os.path.join(
        tempfile.mkdtemp(), 'stats.db'))
    acc = app.profile_db.register('stat@b.ru', 'pass1234', 'Счётчик')
    app.set_user(acc)
    check('Статистика' in [w.label for w in app.screens['menu']],
          'вошедшему игроку кнопка «Статистика» есть в меню',
          'в меню нет кнопки «Статистика»')
    app.open_stats()
    check(app.screen_name == 'stats',
          'кнопка открывает экран статистики',
          'экран статистики не открылся: %s' % app.screen_name)
    app.game['my_moves'] = 3
    app.stat_add('moves', 3)
    app.stat_shot(True)
    app.stat_shot(False)
    # подсказку даём на поле с фигурами: на пустом её негде выдать
    app.place_unit(app.FL, [(0.4, 0.4), (0.5, 0.4)], 0, 2, 'ship')
    check(app.reveal_hint(app.FL),
          'подсказка выдаётся и сразу записывается в статистику',
          'подсказка не выдалась: поле пустое или счётчик сломан')
    app.show_screen('game')
    app.choose_diff('Средний')
    app.show_victory('Победил Счётчик!')
    txt = dict(line.split(':', 1) for line in app.stats_text()
               if ':' in line)
    check(int(txt['Ходов сделано'].strip()) == 3,
          'статистика считает ходы: %s' % txt['Ходов сделано'].strip(),
          'ходы не посчитаны: %s' % txt['Ходов сделано'].strip())
    check(int(txt['Попаданий'].strip()) == 1
          and int(txt['Промахов'].strip()) == 1,
          'статистика считает попадания и промахи',
          'попадания/промахи неверны: %s / %s'
          % (txt['Попаданий'].strip(), txt['Промахов'].strip()))
    check(int(txt['Подсказок взято'].strip()) == 1,
          'статистика считает подсказки',
          'подсказки не посчитаны: %s' % txt['Подсказок взято'].strip())
    check(int(txt['Сыграно игр'].strip()) == 1
          and int(txt['Побед'].strip()) == 1,
          'статистика считает игры и победы',
          'игры/победы неверны: %s / %s'
          % (txt['Сыграно игр'].strip(), txt['Побед'].strip()))
    st = app.profile_db.get_stats(acc['id'])
    check(st['moves'] == 3 and st['games'] == 1 and st['wins'] == 1,
          'в базе те же числа: %s' % st,
          'в базе расхождение: %s' % st)
    app.do_logout()
    check('Статистика' not in [w.label for w in app.screens['menu']],
          'после выхода кнопка статистики исчезает',
          'кнопка «Статистика» осталась после выхода из профиля')

    # --- 25a. кнопки панели нажимаются (иначе меню «не работает») ---
    app = battle_app()
    app.draw()          # положение кнопок панели задаётся при отрисовке
    clickable = [w.label for w in app.game_widgets if w in app.row_cars]
    check(clickable == ['Машинки', 'Стены', 'Поворот', 'Готов',
                        'Совершить ход', 'Выход'],
          'все кнопки панели нажимаемые: %s' % ', '.join(clickable),
          'панель нарисована, но не нажимается: %s' % ', '.join(clickable))
    car = app.car_owner_cars('player1')[0]
    app.car_select(car)
    d0 = car['dir']
    c = app.btn_car_turn.rect.center
    app.on_down(c, 1)
    app.on_up(c, 1)
    check(car['dir'] == (d0 + 1) % 8,
          'кнопка «Поворот» поворачивает машинку на 45°',
          '«Поворот» не сработал: направление %d -> %d' % (d0, car['dir']))

    # --- 25b. фигура рисуется только на том поле, где стоит ---
    app = battle_app(cars=2)
    app.game['turn'] = 'player1'
    shown = {}
    for fld, nm in ((app.FL, 'L'), (app.FR, 'R')):
        shown[nm] = [un for un in fld['units']
                     if app.car_seen(un, nm)]
    own_r = [un for un in shown['R'] if un in app.car_owner_cars('player1')]
    check(own_r and not [u for u in shown['L']
                         if u in app.car_owner_cars('player1')],
          'свои машинки видны только на поле врага',
          'машинки нарисованы не на своём месте: %s / %s'
          % (len(shown['L']), len(shown['R'])))
    check(not [u for u in shown['L'] if u in app.car_owner_cars('player2')],
          'чужие машинки скрыты туманом войны',
          'чужие машинки видны сразу')

    # --- 25c. углы тригонометрии только на поле врага ---------------
    app = new_app()
    app.choose_diff('Средний')
    app.set_mode('angles')
    app.set_angle1(35)
    app.set_angle2(70)
    app.update_angles()
    check(app.aim_side() == 'R',
          'углы показываются на правом (вражеском) поле: %s'
          % app.aim_side(),
          'поле с углами определено неверно: %s' % app.aim_side())
    app.draw()
    check(app.aim_sides_drawn == ['R'],
          'прицел нарисован только на поле врага: %s'
          % app.aim_sides_drawn,
          'прицел нарисован не там: %s' % app.aim_sides_drawn)
    check(app.aim_points_drawn == ['P1', 'P2'],
          'обе точки пересечения нарисованы: %s' % app.aim_points_drawn,
          'точки пересечения не нарисованы: %s' % app.aim_points_drawn)
    check(all(w.visible for w in app.row_build if w is not None),
          'в тригонометрическом режиме третий ряд на месте',
          'в тригонометрическом режиме пропали кнопки третьего ряда')

    # --- 25d. кнопки не наезжают на текст ---------------------------
    app = new_app()
    app.profile_db = Profiles(os.path.join(
        tempfile.mkdtemp(), 'stats2.db'))
    app.set_user(app.profile_db.register('b@b.ru', 'pass1234', 'Текст'))
    app.open_stats()
    app.draw()
    t2 = int(clamp(0.026 * app.H, 13, 24))
    text_bottom = int(0.09 * app.H) + len(app.stats_text()) * int(t2 * 1.5)
    check(all(w.rect.top >= text_bottom for w in app.widgets()),
          'кнопки статистики ниже текста',
          'кнопки наезжают на текст статистики: %s'
          % [(w.label, w.rect.top, text_bottom) for w in app.widgets()])
    app.net_code = 'AB12C'
    app.show_screen('net_host')
    app.draw()
    size, lines = app.fit_lines(
        'Пока соперник не подключился. Передайте ему этот код — '
        'он введёт его в пункте «Подключиться по коду».',
        app.W - 2 * app.M, int(clamp(0.022 * app.H, 11, 19)),
        int(0.20 * app.H))
    text_bottom_net = int(0.62 * app.H) + len(lines) * int(size * 1.4)
    check(all(w.rect.top >= text_bottom_net for w in app.widgets()),
          '«Отмена» на экране ожидания ниже текста',
          '«Отмена» наезжает на текст: %s < %s'
          % ([(w.label, w.rect.top) for w in app.widgets()],
             text_bottom_net))

    # --- 26. версия ---
    spec = io.open(os.path.join(ROOT, 'ready_apk', 'buildozer.spec'),
                   encoding='utf-8').read()
    check('version = 0.3.3' in spec,
          'в buildozer.spec версия 0.3.3',
          'в buildozer.spec неверная версия: %s'
          % [ln for ln in spec.splitlines() if 'version' in ln][:1])

    print()
    print('Итог: %s' % ('все проверки пройдены' if ok else 'ЕСТЬ ОШИБКИ'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())