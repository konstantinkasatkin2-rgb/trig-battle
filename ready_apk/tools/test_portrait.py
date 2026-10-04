# -*- coding: utf-8 -*-
"""Проверка книжной ориентации и кнопки профиля.

На телефоне приложение обязано работать альбомным: в книжном окне
игра раньше падала при разборе списка кнопок (`ValueError: not enough
values to unpack`). Теперь холст строится в альбомных размерах и
выводится повёрнутым, а касания пересчитываются обратно.

Запуск:  python ready_apk/tools/test_portrait.py
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


# книжные и совсем малые окна — как их может отдать телефон
SIZES = ((1080, 1920), (1080, 2340), (720, 1280), (1440, 3120),
         (1600, 900), (1280, 720), (900, 480), (640, 360))


def try_size(app, w, h, phase):
    """Разложить интерфейс под окно w x h и нарисовать кадр."""
    app.win = pygame.display.set_mode((w, h), pygame.RESIZABLE)
    app.layout(w, h)
    app.build_ui()
    app.draw()
    app.present()
    pygame.event.pump()
    if phase == 'game':
        app.start_local()
        app.place_unit(app.FL, [(0.1, 0.2), (0.2, 0.2)], 0, 2, 'ship')
        app.draw()
        app.present()
    return app


def main():
    pygame.init()
    pygame.display.set_mode((1280, 720))
    import trig_battle_pygame as g

    print('Проверка книжной ориентации')
    app = g.TrigBattle()

    # --- книжные окна: не падаем и получаем альбомный холст ---
    for w, h in SIZES:
        portrait = h > w
        try:
            app = try_size(app, w, h, 'menu')
        except Exception as e:                         # noqa: BLE001
            check(False, '', 'окно %dx%d: падение %r' % (w, h, e))
            continue
        # окна меньше минимального размера поднимаются до MIN_W x MIN_H —
        # это задумано, иначе в интерфейсе нечего рисовать
        want = (max(g.MIN_W, h if portrait else w),
                max(g.MIN_H, w if portrait else h))
        check((app.W, app.H) == want and app.rotated == portrait,
              'окно %dx%d: холст %dx%d, повёрнуто=%s'
              % (w, h, app.W, app.H, app.rotated),
              'окно %dx%d: холст %dx%d вместо %dx%d (повёрнуто=%s)'
              % (w, h, app.W, app.H, want[0], want[1], app.rotated))

    # --- игровой экран в книжном окне тоже должен рисоваться ---
    try:
        app = try_size(app, 1080, 1920, 'game')
        check(True, 'игровой экран в книжном окне нарисован', '')
    except Exception as e:                             # noqa: BLE001
        check(False, '', 'игровой экран в книжном окне: падение %r' % (e,))

    # --- касание переводится в координаты холста без смещения ---
    app = try_size(app, 1080, 1920, 'menu')
    for w, h in ((1080, 1920), (720, 1280), (1600, 900)):
        app = try_size(app, w, h, 'menu')
        for pos in ((w // 2, h // 2), (10, 10), (w - 10, h - 10)):
            got = app.to_design(pos)
            inside = 0 <= got[0] < app.W and 0 <= got[1] < app.H
            check(inside,
                  'окно %dx%d, точка %s -> холст %s (в пределах)'
                  % (w, h, pos, got),
                  'окно %dx%d, точка %s -> холст %s: вне холста %dx%d'
                  % (w, h, pos, got, app.W, app.H))

    # --- при повороте холста касание попадает туда же, куда рисовали ---
    app = try_size(app, 1080, 1920, 'menu')
    canvas_pt = (400, 300)
    # куда эта точка холста попадает на экране при rotate(90)
    win_pt = (canvas_pt[1], app.W - 1 - canvas_pt[0])
    back = app.to_design(win_pt)
    check(abs(back[0] - canvas_pt[0]) <= 1 and abs(back[1] - canvas_pt[1]) <= 1,
          'обратный пересчёт касания точен: %s -> %s -> %s'
          % (canvas_pt, win_pt, back),
          'обратный пересчёт касания сбился: %s -> %s -> %s'
          % (canvas_pt, win_pt, back))

    # --- узкий экран: кнопок не влезает, разбор не должен падать ---
    # Именно на этом приложение падало в книжной ориентации:
    # `ValueError: not enough values to unpack` при разборе списка
    # кнопок. Само условие трудно воспроизвести окном (после поворота
    # холст всегда альбомный и достаточно широкий), поэтому подменяем
    # make_buttons: он возвращает меньше кнопок, чем ожидают.
    app = try_size(app, 1280, 720, 'menu')
    real_make_buttons = app.make_buttons
    for keep in (1, 2, 5, 8):
        def narrow(y, h, specs, x0, gap, limit, keep=keep):
            btns, x = real_make_buttons(y, h, specs, x0, gap, limit)
            return list(btns)[:keep], x
        app.make_buttons = narrow
        try:
            app.build_ui()
            app.draw()
            app.present()
            check(True, 'разбор кнопок переживает, когда их %d из 8' % keep,
                  '')
        except Exception as e:                         # noqa: BLE001
            check(False, '',
                  'при %d кнопках из 8 падение %r' % (keep, e))
    app.make_buttons = real_make_buttons
    app.build_ui()

    # --- приложение просит альбомную ориентацию у Android ---
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            '..', '..', 'trig_battle_pygame.py'),
               encoding='utf-8').read()
    check('setRequestedOrientation(0)' in src,
          'при запуске просим у Android альбомную ориентацию',
          'приложение не просит альбомную ориентацию у Android')
    check('def force_landscape' in src and 'force_landscape()' in src,
          'force_landscape вызывается при старте',
          'force_landscape не вызывается')

    # --- кнопка профиля только в главном меню ---
    print()
    print('Проверка кнопки профиля')
    app = g.TrigBattle()
    app.layout(1280, 720)
    app.build_ui()

    def profile_buttons(screen):
        n = 0
        for w in app.screens.get(screen, []):
            if getattr(w, 'cb', None) == app.open_profile:
                n += 1
        return n

    if app.profile_db is None:
        print('  ПРОПУСК  базы профилей нет — кнопки не будет в любом случае')
    else:
        check(profile_buttons('menu') == 1,
              'в главном меню кнопка профиля есть',
              'в главном меню кнопка профиля отсутствует или продублирована')
        others = [s for s in app.screens
                  if s != 'menu' and profile_buttons(s)]
        check(not others,
              'на остальных экранах кнопки профиля нет',
              'кнопка профиля торчит на экранах: %s' % ', '.join(others))

    print('Итог: %s' % ('все проверки пройдены' if ok else 'ЕСТЬ ОШИБКИ'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())