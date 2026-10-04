# -*- coding: utf-8 -*-
"""Проверки нового режима: машинки против препятствий.

Проверяем правила буквально по требованиям:
  * машинка ставится только за пределами окружности, внутри квадрата;
  * препятствие — до 4 клеток, жёлтый круг закрывать нельзя;
  * за ход машинка проезжает ровно одну клетку, диагональ тоже клетка;
  * при столкновении с препятствием машинка разворачивается на 180°;
  * коснувшись жёлтого круга, машинка приносит победу атакующему;
  * когда все машинки израсходовали ходы, побеждает защитник;
  * флоты: 4 машинки и препятствия 1:4, 2:3, 3:2, 4:1.

Запуск:  python ready_apk/tools/test_cars.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import pygame                                            # noqa: E402

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
    return app


def car_draw_radius(app, side, un):
    """Радиус круга машинки, который приложение рисует на самом деле."""
    import pygame as pg
    got = []
    orig = pg.draw.circle

    def spy(surf, color, center, radius, width=0):
        if width == 0:
            got.append(radius)
        return orig(surf, color, center, radius, width)

    pg.draw.circle = spy
    try:
        app.car_draw_car(app.base, un, side)
    finally:
        pg.draw.circle = orig
    return got[0] if got else 0


def battle_app(cars=1, walls=1, wall_len=2, wall_dir=0, human='player1',
               play='local'):
    """Готовая партия: расставлены машинки и стены, ход у машинок."""
    app = new_app()
    app.car_start(play, human)
    cf, wf = app.car_field('car'), app.car_field('wall')
    pts = [(-0.9, 0.9), (-0.9, 0.8), (-0.9, 0.7), (-0.9, 0.6)][:cars]
    for p in pts:
        app.place_unit(cf, [p], 0, 1, 'car')
        cf['units'][-1]['left'] = CAR_STEPS
    for i in range(walls):
        base = (-0.1 + i * 0.3, 0.4)
        wall = [base, (base[0] + GRID, base[1])][:wall_len]
        app.place_unit(wf, wall, wall_dir, len(wall), 'wall')
    app.game['phase'] = 'battle'
    app.game['turn'] = 'player1'
    app.btn_start.label = 'Бой идёт'
    return app


def main():
    pygame.init()
    pygame.display.set_mode((1280, 720))
    import trig_battle_pygame as g
    globals().update(g.__dict__)

    print('Проверка нового режима: машинки и препятствия')

    # --- 1. флоты по условию ---
    check(sum(FLEET_WALLS.values()) == 10 and
          FLEET_WALLS == {1: 4, 2: 3, 3: 2, 4: 1},
          'препятствия 1:4, 2:3, 3:2, 4:1 (всего %d)'
          % sum(FLEET_WALLS.values()),
          'флот препятствий неверный: %r' % (FLEET_WALLS,))
    check(sum(FLEET_CARS.values()) == 4,
          'машинок %d (одна на 5 клеток препятствий)'
          % sum(FLEET_CARS.values()),
          'флот машинок неверный: %r' % (FLEET_CARS,))
    check(YELLOW_R == 0.2, 'жёлтый круг [-0.2; 0.2]',
          'жёлтый круг неверный: %r' % YELLOW_R)
    check(CAR_MAX_LEN == 4, 'длина препятствия не больше 4',
          'максимальная длина неверная: %r' % CAR_MAX_LEN)

    # --- 2. зоны расстановки ---
    app = new_app()
    app.car_start('local')
    cf, wf = app.car_field('car'), app.car_field('wall')
    check(app.car_points_ok([(0.9, 0.9)], 'car', []),
          'машинку можно поставить в углу за окружностью',
          'машинку нельзя поставить в углу: %.2f, %.2f'
          % ((0.9 * 0.9 + 0.9 * 0.9) ** 0.5, 0.9))
    check(not app.car_points_ok([(0.2, 0.2)], 'car', []),
          'машинку нельзя поставить внутрь окружности',
          'машинку можно поставить внутри окружности')
    check(app.car_points_ok([(0.2, 0.3)], 'wall', []),
          'препятствие можно поставить рядом с жёлтым кругом',
          'препятствие нельзя поставить у круга')
    check(not app.car_points_ok([(0.0, 0.1)], 'wall', []),
          'жёлтый круг закрывать нельзя',
          'жёлтый круг можно закрыть препятствием')
    check(not app.car_points_ok([(1.4, 0.0)], 'wall', []),
          'препятствие нельзя поставить за пределами квадрата',
          'препятствие можно выставить за квадрат')

    # --- 3. расстановка: количество и размер ---
    app = new_app()
    app.car_start('local')
    cf, wf = app.car_field('car'), app.car_field('wall')
    check(app.build_fld() is cf, 'сначала ставятся машинки',
          'первыми ставятся не машинки')
    app.place_unit(cf, [(-0.9, 0.9)], 0, 1, 'car')
    app.advance()
    check(app.game['phase'] == 'place2' and app.build_fld() is wf,
          'после «Готово» ставятся препятствия',
          'перехода к препятствиям не было: фаза=%s' % app.game['phase'])
    check(app.place_size('wall') <= CAR_MAX_LEN,
          'длина препятствия не больше %d' % CAR_MAX_LEN,
          'длина препятствия не ограничена: %r' % app.place_size('wall'))
    app.place_unit(wf, [(0.0, 0.3), (0.1, 0.3)], 0, 2, 'wall')
    app.advance()
    check(app.game['phase'] == 'battle' and app.game['turn'] == 'player1',
          'бой начался, первый ход у машинок',
          'бой не начался: фаза=%s ход=%s' % (app.game['phase'],
                                              app.game['turn']))

    # --- 4. ход машинки: одна клетка, диагональ тоже клетка ---
    app = battle_app(cars=1)
    car = app.car_field('car')['units'][0]
    app.unit_state['selected'] = car
    car['dir'] = 0                                   # направо
    app.car_make_move()
    check(car['pts'][0] == (-0.8, 0.9),
          'прямой ход — ровно одна клетка: %s' % (car['pts'][0],),
          'прямой ход неверный: %s' % (car['pts'][0],))
    car['dir'] = 7                                   # ↘ диагональ
    before = car['pts'][0]
    app.car_make_move()
    dx = abs(car['pts'][0][0] - before[0])
    dy = abs(car['pts'][0][1] - before[1])
    check(abs(dx - dy) < 1e-6 and abs(dx - GRID) < 1e-6,
          'диагональный ход — тоже одна клетка по обеим осям (%.3f, %.3f)'
          % (dx, dy),
          'диагональный ход неверный: dx=%.3f dy=%.3f' % (dx, dy))

    check(car['left'] == CAR_STEPS - 2,
          'каждый ход тратит запас ходов (два хода -> осталось %d)'
          % car['left'],
          'ходы не тратятся: после двух ходов осталось %d' % car['left'])

    # --- 5. разворот при столкновении ---
    app = battle_app(cars=1, walls=1, wall_len=2)
    car = app.car_field('car')['units'][0]
    wall = app.car_field('wall')['units'][0]
    app.unit_state['selected'] = car
    car['pts'] = [(-0.2, 0.4)]
    car['dir'] = 0                                   # направо, в стену
    before_dir = car['dir']
    app.car_make_move()
    check(car['dir'] == (before_dir + 4) % 8,
          'при столкновении машинка разворачивается на 180°',
          'машинка не развернулась: было %d, стало %d' % (before_dir,
                                                           car['dir']))
    check(len(wall['pts']) < 2 or wall not in app.car_field('wall')['units'],
          'препятствие теряет клетку от тарана',
          'препятствие не пострадало: %r' % (wall['pts'],))

    # --- 6. стена не пускает машинку ---
    app = battle_app(cars=1, walls=1, wall_len=3)
    car = app.car_field('car')['units'][0]
    wall = app.car_field('wall')['units'][0]
    app.unit_state['selected'] = car
    # ставим машинку вплотную к стене, лицом к ней
    wx, wy = wall['pts'][0]
    car['pts'] = [(round(wx - GRID, 3), wy)]
    car['dir'] = 0
    before = car['pts'][0]
    app.car_make_move()
    check(car['pts'][0] == before and car['dir'] == 4,
          'стена не пускает машинку: осталась на месте и развернулась',
          'стена не остановила машинку: %s -> %s, курс %d'
          % (before, car['pts'][0], car['dir']))

    # --- 7. машинка коснулась жёлтого круга ---
    app = battle_app(cars=1, walls=0)
    car = app.car_field('car')['units'][0]
    app.unit_state['selected'] = car
    car['pts'] = [(0.0, 0.3)]
    car['dir'] = 6                                   # вниз, к центру
    app.game['turn'] = 'player1'
    app.car_make_move()
    check(app.game['phase'] == 'over',
          'коснувшись жёлтого круга, машинка приносит победу',
          'партия не закончилась: фаза=%s, круг на расстоянии %.2f'
          % (app.game['phase'], app.car_dist(car['pts'][0])))
    check(app.victory_title == 'Машинки прорвались!',
          'победу объявляет атакующий (%r)' % app.victory_title,
          'неверный титул победы: %r' % app.victory_title)

    # --- 8. все машинки израсходовали ходы — побеждает защитник ---
    app = battle_app(cars=1, walls=1, wall_len=1)
    car = app.car_field('car')['units'][0]
    app.unit_state['selected'] = car
    car['left'] = 1
    car['pts'] = [(-0.9, 0.9)]
    for _ in range(4):
        if app.game['phase'] == 'over':
            break
        app.game['turn'] = 'player1'
        car['left'] = 0
        app.car_make_move()
    check(app.game['phase'] == 'over',
          'когда машинок не осталось, партия заканчивается',
          'партия не закончилась: фаза=%s' % app.game['phase'])
    check(app.victory_title == 'Защитник выстоял!',
          'побеждает защитник (%r)' % app.victory_title,
          'неверный титул победы: %r' % app.victory_title)

    # --- 9. поворот меняет курс машинки ---
    app = battle_app(cars=1)
    car = app.car_field('car')['units'][0]
    app.unit_state['selected'] = car
    car['dir'] = 0
    app.on_rotate(1)
    check(car['dir'] == 1 and car['pts'][0] == (-0.9, 0.9),
          '«Поворот» меняет направление на 45°, машинка остаётся на месте',
          'поворот сломан: dir=%d, точка=%s' % (car['dir'], car['pts'][0]))

    # --- 10. ходы чередуются, «Ждать» пропускает ---
    app = battle_app(cars=1, walls=1, wall_len=1)
    app.game['turn'] = 'player1'
    app.unit_state['selected'] = app.car_field('car')['units'][0]
    app.car_make_move()
    check(app.game['turn'] == 'player2',
          'после хода машинок ходит защита',
          'ход не перешёл к защите: %s' % app.game['turn'])
    app.car_wait()
    check(app.game['turn'] == 'player1',
          '«Ждать» пропускает ход защиты',
          '«Ждать» не сработал: ход=%s' % app.game['turn'])

    # --- 11. защитник двигает стену, машинка в стену не влезает ---
    app = battle_app(cars=1, walls=1, wall_len=1)
    wall = app.car_field('wall')['units'][0]
    app.game['turn'] = 'player2'
    app.unit_state['selected'] = wall
    before = wall['pts'][0]
    wall['dir'] = 0
    app.car_make_move()
    moved = wall['pts'][0] != before or wall not in app.car_field('wall')['units']
    check(moved, 'защитник двигает своё препятствие на клетку',
          'препятствие не сдвинулось: %s' % (wall['pts'],))

    # --- 12. игра с ИИ: компьютер ставит свою сторону и ходит ---
    for human in ('player1', 'player2'):
        app = new_app()
        app.car_start('ai', human)
        ai_side = app.car_ai_side()
        mine = 'player1' if app.car_local_cars() else 'player2'
        ai_kind = 'wall' if mine == 'player1' else 'car'
        n = len(app.car_field(ai_kind)['units'])
        check(n > 0,
              'ИИ (%s) сразу расставил свою сторону: %d фигур'
              % ('защита' if ai_kind == 'wall' else 'машинки', n),
              'ИИ ничего не расставил: %s' % ai_kind)
        if ai_kind == 'car':
            app.game['phase'] = 'battle'
            app.game['turn'] = 'player1'
            before = [tuple(u['pts'][0]) for u in app.car_field('car')['units']]
            app.car_ai_turn()
            after = [tuple(u['pts'][0]) for u in app.car_field('car')['units']]
            check(before != after,
                  'машинки компьютера двигаются',
                  'машинки компьютера не двигаются: %r' % (before,))
        else:
            app.game['phase'] = 'battle'
            app.game['turn'] = 'player1'
            app.car_start if False else None
            cf = app.car_field('car')
            app.place_unit(cf, [(-0.9, 0.9)], 0, 1, 'car')
            cf['units'][-1]['left'] = CAR_STEPS
            app.game['turn'] = 'player2'
            before = [tuple(p) for u in app.car_field('wall')['units']
                      for p in u['pts']]
            app.car_ai_turn()
            after = [tuple(p) for u in app.car_field('wall')['units']
                     for p in u['pts']]
            check(before != after,
                  'компьютер двигает стену к центру',
                  'компьютер не двигает стену: %r' % (before,))

    # --- 13. элементы управления: углов нет, «Ждать» есть ---
    app = battle_app(cars=1)
    check(not any(w.visible for w in app.row_angles),
          'в новом режиме ползунков углов на экране нет',
          'ползунки углов видны в новом режиме')
    check(not any(w.visible for w in (app.f_sin, app.f_cos, app.f_tg,
                                      app.f_ctg)),
          'полей sin/cos/tg/ctg на экране нет',
          'поля ввода угла видны в новом режиме')
    check(app.btn_wait.visible, 'кнопка «Ждать» на месте',
          'кнопки «Ждать» нет')
    check(app.btn_move.label == 'Ход',
          'кнопка хода называется «Ход» (%r)' % app.btn_move.label,
          'кнопка хода называется %r' % app.btn_move.label)
    app.game['mode'] = 'ai'
    app.cars_widgets_apply()
    check(any(w.visible for w in app.row_angles),
          'в тригонометрическом режиме углы вернулись',
          'углы не вернулись после выхода из нового режима')

    # --- 14. жёлтый круг рисуется, кадр строится ---
    app = battle_app(cars=1, walls=1, wall_len=2)
    try:
        app.draw()
        check(True, 'кадр нового режима рисуется', '')
    except Exception as e:                          # noqa: BLE001
        check(False, '', 'падение при отрисовке: %r' % (e,))

    # --- 15. меню ведёт в оба режима ---
    app = new_app()
    names = set(app.screens)
    check({'menu', 'difficulty', 'play_trig', 'play_cars'} <= names,
          'экраны выбора режима и типа игры на месте',
          'нет экранов выбора: %s' % sorted(
              {'menu', 'difficulty', 'play_trig', 'play_cars'} - names))
    labels = {}
    for scr in ('difficulty', 'play_trig', 'play_cars', 'ai_diff',
                 'cars_role'):
        labels[scr] = [getattr(w, 'label', '') for w in app.screens[scr]]
    check('Тригонометрический морской бой' in labels['difficulty'] and
          'Новый режим' in labels['difficulty'],
          'после «Начать игру» — два режима',
          'на экране выбора нет двух режимов: %r' % labels['difficulty'])
    want = ['Игра против ИИ', 'Игра против игрока', 'Туториал', 'Игра по сети']
    for scr, title in (('play_cars', 'нового режима'),
                       ('play_trig', 'тригонометрического режима')):
        check(all(w in labels[scr] for w in want),
              'у %s есть все четыре кнопки: %s' % (title, ', '.join(want)),
              'у %s неполный набор кнопок: %r' % (title, labels[scr]))
    check(sorted(labels['play_cars'][:4]) == sorted(labels['play_trig'][:4]),
          'набор кнопок у обоих режимов одинаковый',
          'наборы кнопок различаются: %r и %r'
          % (labels['play_cars'], labels['play_trig']))
    check([getattr(w, 'label', '') for w in app.screens['ai_diff']][:3] ==
          ['Низкий', 'Средний', 'Высокий'],
          'сложность выбирается отдельным экраном',
          'на экране сложности не три уровня: %r' % labels['ai_diff'])
    check([getattr(w, 'label', '') for w in app.screens['cars_role']][:2] ==
          ['Я — МАШИНКИ', 'Я — ПРЕПЯТСТВИЯ'],
          'роль против ИИ выбирается отдельным экраном',
          'на экране роли нет двух кнопок: %r' % labels['cars_role'])

    # --- 16. туториал нового режима запускается ---
    app = new_app()
    app.start_cars_tutorial()
    app.draw()
    check(app.car_mode() and app.game['phase'] == 'place1' and
          app.cars_tut_active() and len(app.CAR_TUT) == 4,
          'туториал нового режима запускается и содержит 4 шага',
          'туториал не запустился: фаза=%s, шаг=%s'
          % (app.game['phase'], getattr(app, 'cars_tut', None)))
    # туториал идёт по шагам вслед за действиями игрока
    cf = app.car_field('car')
    app.board_touch('L', app.to_px('L', -0.9, 0.9), 'down')
    check(app.cars_tut['step'] == 1,
          'после постановки машинки туториал идёт дальше',
          'туториал не реагирует на постановку: шаг=%s'
          % app.cars_tut['step'])
    app.unit_state['selected'] = cf['units'][0]
    app.on_rotate(1)
    check(app.cars_tut['step'] == 2,
          'после поворота туториал идёт дальше',
          'туториал не реагирует на поворот: шаг=%s' % app.cars_tut['step'])


    # --- 17. по сети: две стороны играют разные роли ---
    import netgame
    import time
    tcp, udp = 39501, 39502
    netgame.DEFAULT_TCP_PORT = tcp
    netgame.DEFAULT_UDP_PORT = udp
    host = new_app()
    cli = new_app()
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
    for _ in range(150):
        host._net_poll()
        cli._net_poll()
        host.draw()
        cli.draw()
        if host.net_state == 'connected' and cli.net_state == 'connected':
            break
        time.sleep(0.02)
    check(host.net_state == 'connected' and cli.net_state == 'connected',
          'соединение в новом режиме установлено',
          'соединение не установлено: хост=%s клиент=%s'
          % (host.net_state, cli.net_state))
    check(host.car_mode() and cli.car_mode(),
          'обе стороны остались в новом режиме после соединения',
          'режим сбился: хост=%r клиент=%r'
          % (host.game['mode'], cli.game['mode']))
    check(host._car_human_is_cars() and not cli._car_human_is_cars(),
          'хост играет за машинки, клиент — за защиту',
          'роли не разведены: хост=%s клиент=%s'
          % (host._car_human_is_cars(), cli._car_human_is_cars()))

    # хост ставит машинки и отправляет первый этап
    cf = host.car_field('car')
    for p in ((-0.9, 0.9), (-0.9, 0.8)):
        host.place_unit(cf, [p], 0, 1, 'car')
        cf['units'][-1]['left'] = CAR_STEPS
    host.advance()
    host.place_unit(host.car_field('wall'), [(0.3, 0.3), (0.4, 0.3)], 0, 2,
                    'wall')
    host.advance()                       # второй этап: стены
    for _ in range(60):
        cli._net_poll()
        cli.draw()
        time.sleep(0.02)
    check(cli.game['phase'] == 'place2' and
          len(cli.car_field('car')['units']) == 2,
          'клиент получил машинки хоста и перешёл к своим стенам',
          'клиент не получил машинки: фаза=%s, юнитов=%d'
          % (cli.game['phase'], len(cli.car_field('car')['units'])))
    cli.place_unit(cli.car_field('wall'), [(-0.3, -0.3), (-0.2, -0.3)], 0, 2,
                   'wall')
    cli.advance()
    for _ in range(80):
        host._net_poll()
        cli._net_poll()
        host.draw()
        cli.draw()
        if host.game['phase'] == 'battle' and cli.game['phase'] == 'battle':
            break
        time.sleep(0.02)
    check(host.game['phase'] == 'battle' and cli.game['phase'] == 'battle',
          'бой начался у обеих сторон (хост=%s, клиент=%s)'
          % (host.game['phase'], cli.game['phase']),
          'бой не начался: хост=%s клиент=%s'
          % (host.game['phase'], cli.game['phase']))

    # ход машинки хоста должен одинаково посчитаться у клиента
    car = host.car_field('car')['units'][0]
    host.game['turn'] = 'player1'
    host.unit_state['selected'] = car
    before = car['pts'][0]
    host.car_make_move()
    for _ in range(60):
        cli._net_poll()
        cli.draw()
        if cli.car_field('car')['units'][0]['pts'][0] != before:
            break
        time.sleep(0.02)
    peer = cli.car_field('car')['units'][0]
    check(peer['pts'][0] == car['pts'][0],
          'ход машинки у обоих одинаковый: %s' % (car['pts'][0],),
          'ходы разошлись: у хоста %s, у клиента %s'
          % (car['pts'][0], peer['pts'][0]))

    # стена, поставленная прямо в бою, уходит сопернику сообщением
    # (защитник — клиент, он играет за player2)
    cli.game['turn'] = 'player2'
    cli_wf = cli.car_my_field()
    cli_side = 'L' if cli_wf is cli.FL else 'R'
    cli.car_tap(cli_side, 0.5, -0.5, 1)
    host_wf = host.car_peer_fld(cli_side)     # поле соперника на хосте
    for _ in range(60):
        host._net_poll()
        host.draw()
        if len([u for u in host_wf['units'] if u['type'] == 'wall']) >= 2:
            break
        time.sleep(0.02)
    host_walls = [u for u in host_wf['units'] if u['type'] == 'wall']
    check(len(host_walls) == 2 and
          sorted(host_walls[-1]['pts']) == sorted(cli_wf['units'][-1]['pts']),
          'стена, поставленная в бою, доехала до соперника: %r'
          % (host_walls[-1]['pts'] if host_walls else None,),
          'стена соперника не появилась: у хоста %d стен, у клиента %r'
          % (len(host_walls), cli_wf['units'][-1]['pts']))

    # теперь на поле машинок есть и стена: адрес фигуры в ходу должен
    # считаться среди фигур своего вида, иначе стороны разойдутся
    host.game['turn'] = 'player1'
    host_cf = host.car_field('car')
    host.place_unit(host_cf, [(0.4, 0.4), (0.5, 0.4)], 0, 2, 'wall')
    wall_mix = host_cf['units'][-1]
    host.car_send_build(wall_mix)
    cli_mix = []
    for _ in range(60):
        cli._net_poll()
        cli.draw()
        cli_mix = [u for u in cli.car_field('car')['units']
                   if u['type'] == 'wall']
        if cli_mix:
            break
        time.sleep(0.02)
    check(cli_mix and sorted(cli_mix[-1]['pts']) == sorted(wall_mix['pts']),
          'стена на поле машинок доехала до соперника: %r'
          % (cli_mix[-1]['pts'] if cli_mix else None,),
          'стена на поле машинок не доехала: %r' % (cli_mix,))
    host.game['turn'] = 'player1'
    host.unit_state['selected'] = wall_mix
    wall_mix['dir'] = 0
    host.game['turn'] = 'player1'
    host.car_make_move()
    for _ in range(60):
        cli._net_poll()
        cli.draw()
        if cli_mix[-1]['pts'][0] != wall_mix['pts'][0]:
            break
        time.sleep(0.02)
    check(cli_mix[-1]['pts'] == wall_mix['pts'],
          'ход стены при смешанном поле (машинки и стены) одинаковый: %r'
          % (wall_mix['pts'],),
          'ходы разошлись: у хоста %r, у клиента %r'
          % (wall_mix['pts'], cli_mix[-1]['pts']))


    # --- 18. туман: чужие фигуры видны только после столкновения ---
    app = battle_app(cars=1, walls=1, wall_len=2)
    car = app.car_field('car')['units'][0]
    wall = app.car_field('wall')['units'][0]
    check(not app.car_seen(wall, 'L'),
          'стены соперника на своём поле не видны, пока не врезались',
          'чужая стена видна на чужом поле и до столкновения')
    check(app.car_seen(wall, 'R'),
          'на своём поле защитник свою стену видит',
          'защитник не видит свою стену')
    car['pts'] = [(-0.2, 0.4)]
    car['dir'] = 0
    app.unit_state['selected'] = car
    app.car_make_move()
    check(app.car_seen(wall, 'L'),
          'после тарана стена соперника становится видна',
          'стена осталась невидимой после столкновения')
    check(car.get('revealed'),
          'таранившая машинка раскрывается тоже',
          'машинка не раскрылась')

    # машинка соперника видна только когда сама врежется в стену
    app = battle_app(cars=1, walls=1, wall_len=2)
    car = app.car_field('car')['units'][0]
    app.unit_state['selected'] = car
    check(app.car_seen(car, 'L'),
          'своя машинка видна всегда',
          'своя машинка не видна')
    check(not app.car_seen(car, 'R'),
          'чужая машинка не видна, пока не врезалась',
          'чужая машинка видна сразу')

    # --- 19. стены можно ставить прямо во время боя ---
    # правило: стена ставится только в СВОЙ ход и только одна за ход
    app = battle_app(cars=1, walls=1, wall_len=2)
    wf = app.car_field('wall')
    side = 'L' if wf is app.FL else 'R'
    app.game['turn'] = app.car_side_of_fld(wf)      # ход защиты
    before = len(wf['units'])
    app.car_tap(side, 0.5, -0.5, 1)
    check(len(wf['units']) == before + 1,
          'в бою стена ставится на свободную клетку (%d -> %d)'
          % (before, len(wf['units'])),
          'стена в бою не поставилась: %d -> %d' % (before, len(wf['units'])))
    check(app.game['turn'] != app.car_side_of_fld(wf),
          'после стены ход уходит сопернику (был %s, стал %s)'
          % (app.car_side_of_fld(wf), app.game['turn']),
          'ход остался у построившего: %s' % app.game['turn'])
    n_walls = len(wf['units'])
    app.game['turn'] = app.car_side_of_fld(wf)      # снова наш ход
    app.car_tap(side, 0.5, -0.5, 1)
    check(len(wf['units']) == n_walls,
          'вторую стену за один ход поставить нельзя',
          'за один ход поставлено несколько стен: %d -> %d'
          % (n_walls, len(wf['units'])))
    app.game['turn'] = 'player2' if app.car_side_of_fld(wf) == 'player1'         else 'player1'
    app.car_tap(side, 0.6, -0.6, 1)
    check(len(wf['units']) == n_walls,
          'в чужой ход стена не ставится',
          'стена поставлена не в свой ход: %d -> %d'
          % (n_walls, len(wf['units'])))
    app.game['turn'] = app.car_side_of_fld(wf)
    app.car_tap(side, 0.1, 0.1, 1)
    check(len(wf['units']) == n_walls,
          'на жёлтый круг стена не ставится',
          'стена встала на жёлтый круг')
    for i in range(30):
        app.game['turn'] = app.car_side_of_fld(wf)
        app.car_tap(side, 0.7 - 0.1 * (i % 7), -0.7 + 0.1 * (i // 7), 1)
    check(len(wf['units']) <= 10,
          'число стен не превышает флот (поставлено %d, осталось %d)'
          % (len(wf['units']),
             sum(max(0, v) for v in app.car_remaining(wf)['wall'].values())),
          'стен больше флота: %d' % len(wf['units']))
    # против ИИ у экрана есть своё поле: на чужом стена не строится
    app = battle_app(cars=1, walls=1, wall_len=1, play='ai', human='player2')
    app.car_human = 'player2'
    my, other = app.car_field('wall'), app.car_field('car')
    n_my, n_other = len(my['units']), len(other['units'])
    app.game['turn'] = 'player2'
    app.car_tap('L' if other is app.FL else 'R', 0.5, -0.5, 1)
    check(len(other['units']) == n_other,
          'на чужом поле стена не строится',
          'правило своего поля не работает: чужое поле %d->%d, своё %d->%d'
          % (n_other, len(other['units']), n_my, len(my['units'])))
    app.game['turn'] = 'player2'
    app.car_tap('L' if my is app.FL else 'R', 0.5, -0.5, 1)
    check(len(my['units']) == n_my + 1,
          'на своём поле стена строится в свой ход (%d -> %d)'
          % (n_my, len(my['units'])),
          'на своём поле стена не построилась: %d -> %d'
          % (n_my, len(my['units'])))

    # --- 19a. стена не наезжает на другую стену своего поля ---
    app = battle_app(cars=1, walls=1, wall_len=1)
    wf = app.car_field('wall')
    wf['units'].clear()
    app.place_unit(wf, [(0.4, 0.4)], 0, 1, 'wall')
    app.place_unit(wf, [(0.5, 0.4)], 0, 1, 'wall')
    wall = wf['units'][0]
    wall['dir'] = 0
    app.select(wall)
    app.game['turn'] = app.car_side_of_fld(wf)
    app.car_make_move()
    check(wall['pts'][0] == (0.4, 0.4),
          'стена не встаёт на соседнюю стену того же поля: %r'
          % (wall['pts'][0],),
          'стены слиплись: стена уехала на %r' % (wall['pts'][0],))

    # --- 20. препятствие вращается ---
    for cells, d0 in (([(-0.6, 0.2), (-0.5, 0.2), (-0.4, 0.2)], 0),
                      ([(-0.6, 0.2), (-0.5, 0.2)], 0),
                      ([(0.2, -0.6), (0.2, -0.5), (0.2, -0.4)], 2)):
        app = battle_app(cars=1, walls=1, wall_len=len(cells))
        wall = app.car_field('wall')['units'][0]
        wall['pts'] = list(cells)
        wall['size'] = len(cells)
        wall['dir'] = d0
        app.unit_state['selected'] = wall
        app.on_rotate(1)
        turned = (wall['dir'] != d0 and len(wall['pts']) == len(cells) and
                  app.car_points_ok(wall['pts'], 'wall',
                                    app.car_field('wall')['units'],
                                    ignore=wall))
        check(turned, '«Поворот» разворачивает препятствие %r -> %r'
              % (cells, wall['pts']),
              'препятствие не повернулось: было %r (%d), стало %r (%d)'
              % (cells, d0, wall['pts'], wall['dir']))
        app.unit_state['selected'] = wall
        app.on_rotate(7)          # вместе с первым — полный оборот 360°
        check(set(wall['pts']) == set(cells) and wall['dir'] == d0,
              'полный оборот (8 поворотов на 45°) возвращает стену '
              'на место: %r' % (wall['pts'],),
              'после полного оборота стена уехала: %r (dir=%d) вместо %r'
              % (wall['pts'], wall['dir'], cells))

    # --- 21. машинка крупная и ход виден ---
    app = battle_app(cars=1)
    car = app.car_field('car')['units'][0]
    cell_px = GRID * app.br['L'].width * 0.96 / (2 * LIMIT)
    check(CAR_R >= 2.4 * 0.042,
          'машинка увеличена в 2.5 раза: радиус %.3f от ширины поля '
          'против прежних 0.042' % CAR_R,
          'машинка не увеличена: радиус %.3f от ширины поля' % CAR_R)
    check(car_draw_radius(app, 'L', car) == max(6, int(CAR_R *
                                                      app.br['L'].width)),
          'нарисованный круг машинки соответствует константе (%d px)'
          % car_draw_radius(app, 'L', car),
          'нарисованный круг машинки не соответствует константе')
    check(car_draw_radius(app, 'L', car) > 2 * cell_px,
          'машинка заметно крупнее клетки: радиус %d px против %.1f px'
          % (car_draw_radius(app, 'L', car), cell_px),
          'машинка меньше двух клеток: радиус %d px, клетка %.1f px'
          % (car_draw_radius(app, 'L', car), cell_px))
    app.unit_state['selected'] = car
    car['dir'] = 0
    app.car_make_move()
    check(car.get('anim') is not None,
          'ход машинки показывается плавно (анимация включена)',
          'после хода анимации нет — движение не видно')
    app.car_anim_pos(car)
    car['anim'] = ([(-1.5, 0.9)], 0)
    check(app.car_anim_pos(car) == car['pts'][0],
          'анимация заканчивается на новой клетке',
          'анимация не доходит до новой клетки')

    # --- 21a. у границ квадрата машинка разворачивается ---
    app = battle_app(cars=1)
    cf = app.car_field('car')
    edge = {0: (1.0, 0.0), 1: (0.9, 0.9), 2: (0.0, 1.0), 3: (-0.9, 0.9),
            4: (-1.0, 0.0), 5: (-0.9, -0.9), 6: (0.0, -1.0), 7: (0.9, -0.9)}
    bad_dirs = []
    for d, start in edge.items():
        cf['units'].clear()
        app.place_unit(cf, [start], d, 1, 'car')
        car = cf['units'][0]
        car['left'] = CAR_STEPS
        app.unit_state['selected'] = car
        app.game['turn'] = 'player1'
        app.car_make_move()
        if not (car['dir'] == (d + 4) % 8 or car['pts'][0] != start):
            bad_dirs.append(d)
    check(not bad_dirs,
          'у границы квадрата машинка разворачивается на 180° (все 8 '
          'направлений)',
          'не развернулись направления: %r' % bad_dirs)
    cf['units'].clear()
    app.place_unit(cf, [(1.0, 0.0)], 0, 1, 'car')      # у правой границы
    car = cf['units'][0]
    car['left'] = CAR_STEPS
    app.unit_state['selected'] = car
    app.game['turn'] = 'player1'
    app.car_make_move()
    check(car['pts'][0] == (1.0, 0.0) and car['dir'] == 4,
          'машинка у границы остаётся на клетке и разворачивается',
          'у границы: %r, направление %d' % (car['pts'][0], car['dir']))
    app.game['turn'] = 'player1'
    app.car_make_move()
    check(car['pts'][0] == (0.9, 0.0),
          'после разворота машинка уезжает от границы внутрь: %r'
          % (car['pts'][0],),
          'после разворота машинка осталась на месте: %r' % (car['pts'][0],))

    # --- 22. на экране нового режима нет trigonометрии ---
    app = battle_app(cars=1, walls=1, wall_len=2)
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
                                   'Огонь:', 'ctg', 'tg2', 'Игрок 1',
                                   'Игрок 2', 'МОИ ЮНИТЫ', 'сложность:'))]
    check(not bad,
          'на экране боя нового режима нет trigonометрических подписей',
          'остались лишние подписи: %r' % bad[:6])
    check(any('МАШИНКИ' in t for t in seen) and
          any('ПРЕПЯТСТВИЯ' in t for t in seen),
          'на экране есть названия сторон',
          'нет названий сторон на экране')

    print()
    print('Итог: %s' % ('все проверки пройдены' if ok else 'ЕСТЬ ОШИБКИ'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())