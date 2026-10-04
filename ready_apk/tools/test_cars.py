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
    for scr in ('difficulty', 'play_trig', 'play_cars'):
        labels[scr] = [getattr(w, 'label', '') for w in app.screens[scr]]
    check('Тригонометрический морской бой' in labels['difficulty'] and
          'Новый режим' in labels['difficulty'],
          'после «Начать игру» — два режима',
          'на экране выбора нет двух режимов: %r' % labels['difficulty'])
    check(any('Игра по сети' in l for l in labels['play_cars']) and
          any('Туториал' in l for l in labels['play_cars']) and
          any('Локальная' in l for l in labels['play_cars']) and
          any('ИИ' in l for l in labels['play_cars']),
          'у нового режима есть ИИ, локальная игра, туториал и сеть',
          'у нового режима неполный набор кнопок: %r' % labels['play_cars'])
    check(any('Игра по сети' in l for l in labels['play_trig']) and
          any('Туториал' in l for l in labels['play_trig']),
          'у тригонометрического режима кнопки на месте',
          'у тригонометрического режима неполный набор: %r'
          % labels['play_trig'])

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

    print()
    print('Итог: %s' % ('все проверки пройдены' if ok else 'ЕСТЬ ОШИБКИ'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())