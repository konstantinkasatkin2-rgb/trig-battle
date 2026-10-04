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
    """Крутит игровой цикл игрока, чтобы он обрабатывал сеть."""
    end = time.time() + seconds
    while time.time() < end:
        if app.net is not None:
            app._net_poll()
        pygame.event.pump()
        time.sleep(0.01)


def main():
    pygame.init()
    pygame.display.set_mode((1280, 720))
    import trig_battle_pygame as g
    import netgame

    # порты, отдельные от основных, чтобы не мешать живому запуску
    tcp_port, udp_port = 39301, 39302
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
    check(len(host.FL['units']) == 1 and len(cli.FL['units']) == 1,
          'флоты расставлены', 'флот не расставлен')

    host.advance()
    cli.advance()
    for _ in range(120):
        host._net_poll()
        cli._net_poll()
        if host.game['phase'] == 'battle' and cli.game['phase'] == 'battle':
            break
        time.sleep(0.02)
    check(host.game['phase'] == 'battle' and cli.game['phase'] == 'battle',
          'бой начался у обоих',
          'бой не начался (хост=%s, клиент=%s)'
          % (host.game['phase'], cli.game['phase']))
    check(len(host.FR['units']) == 1 and len(cli.FR['units']) == 1,
          'каждый получил флот соперника',
          'флот соперника не пришёл (хост=%d, клиент=%d)'
          % (len(host.FR['units']), len(cli.FR['units'])))
    check(host.game['turn'] == host._net_my_turn(),
          'первым ходит хост', 'первым ходит не тот, кто создал игру')

    # --- 3. синхронизация углов ---
    host.set_angle1(37)
    host.on_slider(1)
    for _ in range(60):
        cli._net_poll()
        if abs(cli.s1 - 37.0) < 0.01:
            break
        time.sleep(0.02)
    check(abs(cli.s1 - 37.0) < 0.01,
          'угол соперника синхронизирован (%.1f)' % cli.s1,
          'угол не пришёл (у клиента %.1f)' % cli.s1)

    # --- 4. выстрел: целимся точно в клетку флота соперника ---
    target = (0.50, 0.50)
    host.update_angles()
    host.state['P1'] = target          # подменяем результат тригонометрии
    check(host.game['turn'] == host._net_my_turn(),
          'ходим в свою очередь', 'ход соперника, выстрел не должен идти')
    host._net_fire()
    for _ in range(120):
        cli._net_poll()
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

    # --- 5. промах: ход переходит к сопернику ---
    host.update_angles()
    host.state['P1'] = (-0.85, -0.85)          # точно мимо флота
    host._net_fire()
    for _ in range(120):
        cli._net_poll()
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
        if host.game['turn'] == host._net_my_turn():
            break
        time.sleep(0.02)
    check(host.game['turn'] == host._net_my_turn(),
          'после промаха клиента ход вернулся хосту', 'хост не получил ход')

    for cell in [(0.60, 0.50)]:               # последняя клетка флота клиента
        host.update_angles()
        host.state['P1'] = cell
        host._net_fire()
        # ждём конца у ОБЕИХ сторон: ход заканчивается по разному
        for _ in range(150):
            cli._net_poll()
            host._net_poll()
            if host.game['phase'] == 'over' and cli.game['phase'] == 'over':
                break
            time.sleep(0.02)
    check(host.game['phase'] == 'over',
          'партия завершена победой хоста', 'партия не завершилась')
    check(cli.game['phase'] == 'over',
          'клиент тоже увидел конец партии',
          'клиент не знает о конце (phase=%s)' % cli.game['phase'])

    host.net.close()
    cli.net.close()
    print('Итог: ' + ('все проверки пройдены' if ok else 'ЕСТЬ ОШИБКИ'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
