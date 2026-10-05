# -*- coding: utf-8 -*-
"""Дымовая проверка: локальная игра и игра против ИИ рисуются.

Правки сетевого режима затронули общий код отрисовки (прицел, панель
управления, видимость юнитов), поэтому обычный режим тоже нужно
прогнать: рисуем экраны во всех режимах и всех фазах.

Запуск:  python ready_apk/tools/test_local_draw.py
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


def draw_frames(app, n=3):
    for _ in range(n):
        app.draw()
        pygame.event.pump()


def main():
    pygame.init()
    pygame.display.set_mode((1280, 720))
    import trig_battle_pygame as g

    print('Проверка отрисовки локальной игры и игры против ИИ')

    # --- локальная игра: оба поля, оба прицела, обе панели ---
    app = g.TrigBattle()
    app.start_local()
    draw_frames(app)
    check(app.game['mode'] == 'local' and app.screen_name == 'game',
          'локальная игра открылась', 'локальная игра не открылась')

    app.place_unit(app.FL, [(0.10, 0.20), (0.20, 0.20)], 0, 2, 'ship')
    app.place_unit(app.FL, [(-0.3, -0.3), (-0.3, -0.2)], 1, 2, 'ship')
    app.advance()                       # Игрок 1 готов
    draw_frames(app)
    check(app.game['phase'] == 'place2',
          'фаза расстановки Игрока 2 (фаза=%s)' % app.game['phase'],
          'не перешли к расстановке Игрока 2: фаза=%s' % app.game['phase'])
    app.place_unit(app.FR, [(0.4, 0.4), (0.5, 0.4)], 0, 2, 'ship',
                   visible=False)
    app.advance()                       # бой
    draw_frames(app)
    check(app.game['phase'] == 'battle',
          'бой начался (фаза=%s)' % app.game['phase'],
          'бой не начался: фаза=%s' % app.game['phase'])
    check(app.active_side() is not None,
          'прицел активен на поле Игрока 1',
          'прицел не активен в начале боя')

    # оба прицела должны быть видны в локальной игре — это правило
    # изменили только для сети
    app.shot_sel['p'] = 'P2'
    draw_frames(app)
    check(app.state['P2'] is not None or app.state['P1'] is not None,
          'точки пересечения посчитаны', 'точки пересечения не посчитаны')

    app.game['turn'] = 'player2'
    app.game['awaiting_tap'] = False
    draw_frames(app)
    check(app.active_side() == 'L',
          'после хода прицел перешёл на левое поле',
          'после хода прицел остался на правом поле')

    # Классическое правило должно работать: свой флот виден, чужой нет
    foe = app.FR['units'][0]
    app.game['turn'] = 'player1'
    check(app.unit_visible(foe, app.FR) is False,
          'флот Игрока 2 скрыт, когда ходит Игрок 1',
          'флот Игрока 2 виден в чужий ход')
    app.game['turn'] = 'player2'
    check(app.unit_visible(foe, app.FR) is True,
          'флот Игрока 2 виден в его собственном ход',
          'флот Игрока 2 скрыт у него самого')
    check(app.unit_visible(app.FL['units'][0], app.FL) is False,
          'флот Игрока 1 скрыт, когда ходит Игрок 2',
          'флот Игрока 1 виден в чужой ход')

    # --- игра против ИИ ---
    ai = g.TrigBattle()
    ai.choose_diff('обычная')
    draw_frames(ai)
    check(ai.game['mode'] == 'ai' and ai.screen_name == 'game',
          'игра против ИИ открылась', 'игра против ИИ не открылась')
    ai.place_unit(ai.FL, [(0.0, 0.0), (0.1, 0.0)], 0, 2, 'ship')
    ai.advance()
    draw_frames(ai)
    check(ai.game['phase'] == 'battle',
          'бой с ИИ начался (фаза=%s)' % ai.game['phase'],
          'бой с ИИ не начался: фаза=%s' % ai.game['phase'])
    check(all(w.visible for w in ai.row_angles),
          'в обычном режиме оба ползунка углов на месте',
          'в обычном режиме часть ползунков скрыта')
    check(ai.btn_aim1.visible and ai.btn_shot1.visible,
          'в обычном режиме кнопки выбора угла и прицела на месте',
          'в обычном режиме кнопки выбора угла/прицела скрыты')

    # выстрел по своему расчёту: точка должна куда-то попасть
    ai.state['P1'] = (0.05, 0.05)
    ai.game['turn'] = 'player1'
    ai.make_move()
    draw_frames(ai)
    check(ai.game['last'] != '—',
          'выстрел обработан (%s)' % ai.game['last'],
          'выстрел не обработан')

    # --- скрытность чужого флота: и против ИИ, и в локальной игре ---
    # Просьба игрока: чужого флота видеть нельзя, пока он не подбит.
    app = g.TrigBattle()
    app.layout(1280, 720)
    app.build_ui()
    app.show_screen('game')
    app.choose_diff('Низкий')
    app.place_unit(app.FR, [(0.4, 0.4), (0.5, 0.4)], 0, 2, 'ship')
    foe = app.FR['units'][0]
    app.game['phase'] = 'battle'
    app.game['mode'] = 'ai'
    app.game['turn'] = 'player1'
    check(not app.unit_visible(foe, app.FR),
          'против ИИ чужой флот скрыт',
          'против ИИ виден чужой флот')
    app.FR['units'][-1]['hits'] = set(app.FR['units'][-1]['pts'])
    check(app.unit_visible(app.FR['units'][-1], app.FR),
          'против ИИ потопленный корабль виден',
          'против ИИ не виден потопленный корабль')
    app.FR['units'][-1]['hits'] = set()      # снова в строю
    app.game['mode'] = 'local'
    app.game['turn'] = 'player1'
    check(not app.unit_visible(foe, app.FR),
          'в локальной игре флот соперника скрыт на его ходу',
          'в локальной игре виден флот соперника')
    app.game['turn'] = 'player2'
    check(app.unit_visible(foe, app.FR),
          'в локальной игре виден только свой флот',
          'в локальной игре не виден собственный флот')
    app.game['turn'] = 'player1'

    # --- меню и профиль рисуются после всех этих правок ---
    menu = g.TrigBattle()
    draw_frames(menu)
    check(menu.screen_name in ('menu', 'profile'),
          'меню на месте (экран=%s)' % menu.screen_name,
          'меню не открылось: экран=%s' % menu.screen_name)

    print('Итог: %s' % ('все проверки пройдены' if ok else 'ЕСТЬ ОШИБКИ'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())