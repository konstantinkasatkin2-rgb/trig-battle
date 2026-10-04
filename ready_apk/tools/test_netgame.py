# -*- coding: utf-8 -*-
"""
Проверка игры по сети двумя игроками в одном процессе.

Что проверяем (без реального телефона и без интернета):
  1) хост раздаёт код, клиент находит его по этому коду и подключается;
  2) оба переходят к расстановке своего флота;
  3) после «Готово» оба получают флот друг друга и начинают бой;
  4) выстрел хоста долетает до клиента и превращается в попадание
     ровно на той клетке, которую выбрал хост;
  5) синхронизация углов: смена ползунка приходит к сопернику;
  6) топление последнего юнита завершает партию.

Запуск:
    python tools/test_netgame.py
"""

import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, os.pardir, os.pardir))
sys.path.insert(0, ROOT)

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')

import pygame                                        # noqa: E402

ok = True


def check(cond, ok_msg, fail_msg):
    global ok
    print(('  OK   ' if cond else '  FAIL ') + (ok_msg if cond else fail_msg))
    ok = ok and bool(cond)
    return bool(cond)


def pump(app, seconds):
    """Крутит игровой цикл игрока, чтобы он обрабатывал сеть.

    Обязательно рисует кадр: сеть проверяется вместе с отрисовкой.
    Раньше тест гонял только протокол, и из-за этого пропустил ошибку
    KeyError: 'type' — на телефоне приложение падало при получении
    флота соперника, потому что принимались одни координаты, а рисовальщик
    ждал ещё тип, размер и направление.
    """
    end = time.time() + seconds
    while time.time() < end:
        if app.net is not None:
            app._net_poll()
        app.draw()
        pygame.event.pump()
        time.sleep(0.01)


def main():
    pygame.init()
    pygame.display.set_mode((1280, 720))
    import trig_battle_pygame as g
    import netgame

    # порты, отдельные от основных, чтобы не мешать живому запуску
    tcp_port, udp_port = 39301, 39302
    IP_PORT = 39311
    netgame.DEFAULT_TCP_PORT = tcp_port
    netgame.DEFAULT_UDP_PORT = udp_port

    print('Проверка игры по сети')
    host = g.TrigBattle()
    cli = g.TrigBattle()

    # --- 1. хост и клиент ---
    host.net = netgame.HostServer('Хост', tcp_port=tcp_port,
                                  udp_port=udp_port)
    host.net.start_beacon()
    host.net_role = 'host'
    host.net_code = host.net.code
    host.net_state = 'waiting'

    cli.net = netgame.Client('Клиент')
    cli.net_role = 'client'
    cli.net_state = 'waiting'
    cli.net.search_code(host.net.code, udp_port=udp_port)

    for _ in range(150):
        host._net_poll()
        cli._net_poll()
        host.draw()          # рисуем на каждом шаге: ловим падения отрисовки
        cli.draw()
        if host.net_state == 'connected' and cli.net_state == 'connected':
            break
        time.sleep(0.02)
    check(host.net_state == 'connected' and cli.net_state == 'connected',
          'клиент подключился по коду %s' % host.net_code,
          'соединение не установилось (хост=%s, клиент=%s)'
          % (host.net_state, cli.net_state))

    check(host.game['mode'] == 'net' and cli.game['mode'] == 'net',
          'оба перешли в сетевой режим', 'режим не переключился')
    check(host.screen_name == 'game' and cli.screen_name == 'game',
          'оба на экране расстановки', 'не на экране расстановки')
    check(host._net_my_turn() != cli._net_my_turn(),
          'ходят за разные стороны (хост=player%s, клиент=player%s)'
          % (host._net_my_turn()[-1], cli._net_my_turn()[-1]),
          'оба играют за одну сторону')

    # --- 2. флоты ---
    host.place_unit(host.FL, [(0.10, 0.20), (0.20, 0.20)], 0, 2, 'ship')
    cli.place_unit(cli.FL, [(0.50, 0.50), (0.60, 0.50)], 0, 2, 'ship')
    # второй корабль нужен, чтобы проверить выстрел по P2, не обрывая партию
    cli.place_unit(cli.FL, [(0.15, 0.75), (0.25, 0.75)], 0, 2, 'ship')
    check(len(host.FL['units']) == 1 and len(cli.FL['units']) == 2,
          'флоты расставлены', 'флот не расставлен')

    host.advance()
    cli.advance()
    for _ in range(120):
        host._net_poll()
        cli._net_poll()
        host.draw()
        cli.draw()
        if host.game['phase'] == 'battle' and cli.game['phase'] == 'battle':
            break
        time.sleep(0.02)
    check(host.game['phase'] == 'battle' and cli.game['phase'] == 'battle',
          'бой начался у обоих',
          'бой не начался (хост=%s, клиент=%s)'
          % (host.game['phase'], cli.game['phase']))
    check(len(host.FR['units']) == 2 and len(cli.FR['units']) == 1,
          'каждый получил флот соперника',
          'флот соперника не пришёл (хост=%d, клиент=%d)'
          % (len(host.FR['units']), len(cli.FR['units'])))
    # Юниты соперника должны быть такими же полными, как свои: рисовальщик
    # читает type/size/dir/pts/hits/fld/visible. Раньше приходили только
    # координаты, и приложение падало с KeyError: 'type'.
    need_keys = {'type', 'size', 'dir', 'pts', 'hits', 'fld', 'visible'}
    for who, app_ in (('хост', host), ('клиент', cli)):
        for un in app_.FR['units']:
            missing = need_keys - set(un)
            check(not missing,
                  'у %s юниты соперника полные' % who,
                  'у %s в юните не хватает: %s' % (who, sorted(missing)))
            break
    check(host.game['turn'] == host._net_my_turn(),
          'первым ходит хост', 'первым ходит не тот, кто создал игру')

    # --- 3. углы: у каждого игрока своя пара, синхронизации нет ---
    # У каждого свои два угла: один под синусы/косинусы, другой под
    # тангенсы/котангенсы. Соперник шлёт только точку выстрела, поэтому
    # его углы на нашем экране не появляются и не могут сдвинуть наш
    # прицел — это и было причиной жалобы на «хаотичный» угол.
    host.set_angle1(37)
    host.set_angle2(120)
    cli_s1, cli_s2 = cli.s1, cli.s2
    for _ in range(60):
        cli._net_poll()
        cli.draw()
        time.sleep(0.02)
    check(abs(host.s1 - 37.0) < 0.01 and abs(host.s2 - 120.0) < 0.01,
          'оба угла хоста меняются независимо (%.0f°, %.0f°)'
          % (host.s1, host.s2),
          'у хоста углы не настроились: %.0f°, %.0f°' % (host.s1, host.s2))
    check(abs(cli.s1 - cli_s1) < 0.01 and abs(cli.s2 - cli_s2) < 0.01,
          'углы соперника не приходят к нам (%.0f°, %.0f°)' % (cli.s1, cli.s2),
          'чужие углы переписали наши: %.0f°->%.0f°, %.0f°->%.0f°'
          % (cli_s1, cli.s1, cli_s2, cli.s2))

    # Сообщение с углами может прийти только от старой версии игры:
    # принимать его нельзя.
    cli._net_handle({'t': 'angles', 'n': 1, 'a': 200.0})
    check(abs(cli.s1 - cli_s1) < 0.01,
          'углы из сообщения старой версии игнорируются',
          'сообщение старой версии переписало наш угол: %.0f° -> %.0f°'
          % (cli_s1, cli.s1))

    cli.set_angle1(64)
    cli.set_angle2(15)
    check(abs(cli.s1 - 64.0) < 0.01 and abs(cli.s2 - 15.0) < 0.01,
          'оба угла клиента меняются независимо (%.0f°, %.0f°)'
          % (cli.s1, cli.s2),
          'у клиента углы не настроились: %.0f°, %.0f°' % (cli.s1, cli.s2))

    # --- 3b. скрытность: поле, флот и точка прицела соперника ---
    # Своё поле видно всегда, чужое — только потопленные корабли.
    for who, app_ in (('хост', host), ('клиент', cli)):
        own = app_.FL['units'][0]
        foe = app_.FR['units'][0]
        check(app_.unit_visible(own, app_.FL),
              'у %s свой флот виден' % who,
              'у %s не виден свой флот' % who)
        check(not app_.unit_visible(foe, app_.FR),
              'у %s флот соперника скрыт' % who,
              'у %s виден флот соперника' % who)
        app_.FR['units'][0]['hits'] = set(app_.FR['units'][0]['pts'])
        check(app_.unit_visible(foe, app_.FR),
              'у %s потопленный корабль соперника виден' % who,
              'у %s не виден потопленный корабль соперника' % who)
        app_.FR['units'][0]['hits'] = set()

    # Обе точки (P1 и P2) считаются из НАШИХ углов, поэтому обе наши и
    # независимые: видны обе, и стрелять можно по любой из них.
    # Проверяем по факту отрисовки, а не по признаку.
    for who, app_ in (('хост', host), ('клиент', cli)):
        app_.state['P1'] = (0.31, 0.42)
        app_.state['P2'] = (-0.17, 0.28)
        app_.set_shot('P1')
        app_.draw()
        drawn = list(app_.aim_points_drawn)
        check(drawn == ['P1', 'P2'],
              'у %s нарисованы обе точки, P1 и P2 (нарисовано %r)'
              % (who, drawn),
              'у %s нарисованы не обе точки: %r' % (who, drawn))

    # Оба угла, оба поля ввода и выбор точки огня — на месте: по сети
    # ничего скрывать не нужно, у нас всё своё.
    for who, app_ in (('хост', host), ('клиент', cli)):
        check(all(w.visible for w in app_.row_angles[:6]),
              'у %s оба ползунка углов на месте' % who,
              'у %s ползунки углов скрыты' % who)
        check(all(w.visible for w in (app_.f_sin, app_.f_cos,
                                      app_.f_tg, app_.f_ctg)),
              'у %s все поля ввода угла на месте' % who,
              'у %s часть полей ввода угла скрыта' % who)
        check(app_.btn_aim1.visible and app_.btn_aim2.visible,
              'у %s выбор угла для поля доступен' % who,
              'у %s кнопки выбора угла скрыты' % who)
        check(app_.btn_shot1.visible and app_.btn_shot2.visible,
              'у %s можно выбрать точку огня P1 или P2' % who,
              'у %s выбор точки выстрела скрыт' % who)

    # --- 4. выстрел: целимся точно в клетку флота соперника ---
    target = (0.50, 0.50)
    host.update_angles()
    host.state['P1'] = target          # подменяем результат тригонометрии
    check(host.game['turn'] == host._net_my_turn(),
          'ходим в свою очередь', 'ход соперника, выстрел не должен идти')
    host._net_fire()
    for _ in range(120):
        cli._net_poll()
        cli.draw()
        hit = any((0.50, 0.50) in un['hits'] for un in cli.FL['units'])
        if hit or cli.game['phase'] == 'over':
            break
        time.sleep(0.02)
    hit = any((0.50, 0.50) in un['hits'] for un in cli.FL['units'])
    check(hit, 'попадание пришло клиенту и отмечено на его поле',
          'попадание не отмечено у клиента')
    check(host.game['turn'] == host._net_my_turn(),
          'после попадания ход остаётся у стрелка', 'ход ушёл сопернику')
    check(cli.game['turn'] != cli._net_my_turn(),
          'у клиента сейчас ход соперника (ждём, turn=%s)'
          % cli.game['turn'], 'у клиента неверный ход: %s'
          % cli.game['turn'])

    # --- 4b. стреляем по выбранной точке: P1 и P2 независимы ---
    # Выбираем P2 и целимся во вторую клетку флота клиента, оставляя P1
    # увести в сторону: попадание должно прийти именно по P2.
    host.set_shot('P2')
    host.state['P1'] = (-0.60, -0.60)          # в сторону, не в флот
    host.state['P2'] = (0.15, 0.75)
    check(host.shot_sel['p'] == 'P2', 'выбрана точка P2',
          'выбрана не та точка: %s' % host.shot_sel['p'])
    host._net_fire()
    for _ in range(120):
        cli._net_poll()
        cli.draw()
        hit = any((0.15, 0.75) in un['hits'] for un in cli.FL['units'])
        if hit or cli.game['phase'] == 'over':
            break
        time.sleep(0.02)
    hit = any((0.15, 0.75) in un['hits'] for un in cli.FL['units'])
    check(hit, 'выстрел по P2 попал туда, куда указывала P2',
          'выстрел по P2 не попал: у клиента попаданий %r'
          % [p for un in cli.FL['units'] for p in un['hits']])
    check(host.game['turn'] == host._net_my_turn(),
          'после попадания по P2 ход остаётся у стрелка',
          'ход ушёл сопернику после выстрела по P2')

    # --- 5. промах: ход переходит к сопернику ---
    host.update_angles()
    host.state['P1'] = (-0.85, -0.85)          # точно мимо флота
    host._net_fire()
    for _ in range(120):
        cli._net_poll()
        cli.draw()
        if cli.game['turn'] == cli._net_my_turn():
            break
        time.sleep(0.02)
    check(cli.game['turn'] == cli._net_my_turn(),
          'после промаха ход перешёл к клиенту (turn=%s)'
          % cli.game['turn'], 'ход не перешёл: turn=%s' % cli.game['turn'])
    check(host.game['turn'] != host._net_my_turn(),
          'хост ждёт соперника', 'хост считает, что ходит снова')

    # --- 6. концовка: клиент промахивается, хост добивает флот ---
    # после промаха хоста ход перешёл к клиенту, значит первым стреляет
    # именно он — иначе проверка была бы проверкой несуществующего хода
    check(cli.game['turn'] == cli._net_my_turn(),
          'после промаха ход клиенту', 'клиент не получил ход')
    cli.update_angles()
    cli.state['P2'] = (-0.85, -0.85)          # клиент стреляет мимо
    cli._net_fire()
    for _ in range(120):
        host._net_poll()
        host.draw()
        if host.game['turn'] == host._net_my_turn():
            break
            time.sleep(0.02)
    check(host.game['turn'] == host._net_my_turn(),
          'после промаха клиента ход вернулся хосту', 'хост не получил ход')

    # добиваем оставшиеся клетки обоих кораблей клиента
    for cell in [(0.60, 0.50), (0.25, 0.75)]:
        host.update_angles()
        # стреляем по выбранной точке: раньше выбирали P2
        host.state[host.shot_sel['p']] = cell
        host._net_fire()
        # ждём конца у ОБЕИХ сторон: ход заканчивается по разному
        for _ in range(150):
            cli._net_poll()
            host._net_poll()
            cli.draw()
            host.draw()
            if host.game['phase'] == 'over' and cli.game['phase'] == 'over':
                break
            time.sleep(0.02)
    check(host.game['phase'] == 'over',
          'партия завершена победой хоста', 'партия не завершилась')
    check(cli.game['phase'] == 'over',
          'клиент тоже увидел конец партии',
          'клиент не знает о конце (phase=%s)' % cli.game['phase'])

    # --- 7. Устойчивость: чужие и испорченные данные не роняют игру.
    #     Именно из-за этого на устройстве с прежней версией было
    #     «could not convert string to float: 's'».
    print(' проверка устойчивости к чужим данным')
    try:
        host._net_handle({'t': 'hello', 'nick': 'Старый'})
        host._net_handle({'t': 'ready',
                          'units': [[[0.1, 0.2], [0.2, 0.2], [0.3, 0.2]]]})
        host.draw()
        check(True, 'принят флот в старом формате (совместимость версий)',
              '')
    except Exception as e:                                # noqa: BLE001
        check(False, '', 'старый формат флота ломает игру: %r' % (e,))

    for bad in (None, [], 'мусор', [None, {}, ['ship']], [{'x': 1}]):
        try:
            host._net_handle({'t': 'ready', 'units': bad})
            host.draw()
        except Exception as e:                            # noqa: BLE001
            check(False, '', 'испорченный флот %r ломает игру: %r'
                  % (str(bad)[:16], e))
    check(True, 'испорченный флот игнорируется без падения', '')

    for coords in ({'x': 's', 'y': 'q'}, {'x': None, 'y': None}, {}):
        try:
            host._net_handle({'t': 'shot', **coords})
            host.draw()
        except Exception as e:                            # noqa: BLE001
            check(False, '', 'битые координаты %r ломают игру: %r'
                  % (str(coords)[:16], e))
    check(True, 'битые координаты выстрела игнорируются', '')

    # --- 8. Подключение по IP: клиент обязан дойти до расстановки,
    #     а не остаться на экране ввода кода.
    print(' проверка подключения по IP')
    host2 = g.TrigBattle()
    cli2 = g.TrigBattle()
    host2.net = netgame.HostServer('Хост', tcp_port=IP_PORT,
                                   udp_port=IP_PORT + 1)
    host2.net_role = 'host'
    host2.net_code = host2.net.code
    host2.net_state = 'waiting'
    cli2.show_screen('net_ip')
    cli2.form['ip'] = '127.0.0.1'
    cli2.net_start_client_ip(port=IP_PORT)
    check(cli2.net_state == 'waiting',
          'после соединения состояние waiting (иначе пропустим переход)',
          'состояние %s — переход в игру не сработает' % cli2.net_state)
    for _ in range(150):
        host2._net_poll()
        cli2._net_poll()
        host2.draw()
        cli2.draw()
        if cli2.screen_name == 'game' and host2.screen_name == 'game':
            break
        time.sleep(0.02)
    check(cli2.screen_name == 'game',
          'клиент по IP дошёл до расстановки (был экран %s)' % cli2.screen_name,
          'клиент остался на экране %s' % cli2.screen_name)
    check(host2.screen_name == 'game', 'хост тоже перешёл в игру',
          'хост остался на %s' % host2.screen_name)
    check(cli2._net_my_turn() != host2._net_my_turn(),
          'стороны назначены верно (хост и клиент играют за разные)',
          'оба играют за одну сторону')
    host2.net.close()
    cli2.net.close()

    host.net.close()
    cli.net.close()
    print('Итог: ' + ('все проверки пройдены' if ok else 'ЕСТЬ ОШИБКИ'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
