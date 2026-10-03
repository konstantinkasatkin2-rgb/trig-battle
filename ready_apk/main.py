# -*- coding: utf-8 -*-
"""
Точка входа APK: buildozer требует, чтобы скрипт назывался `main.py` и лежал
в корне `source.dir`. Вся игра — в `trig_battle_pygame.py` рядом.

Здесь же — страховка на Android: если при старте что-то пойдёт не так
(например, не найдётся pygame или не создастся окно), приложение не должно
молча закрываться. Текст ошибки печатается в logcat (виден через
`adb logcat`) и показывается на экране несколько секунд.

Запуск из исходников на ПК:
    python main.py
"""

import os
import sys
import time
import traceback

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# pygame не должен печатать приветствие поверх наших логов
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')


def log(msg):
    """Печать в stdout -> попадает в logcat."""
    try:
        print('[trigbattle] %s' % msg, flush=True)
    except Exception:
        pass


def show_error(text):
    """Показать ошибку на экране, чтобы её было видно без adb."""
    try:
        import pygame
        pygame.init()
        surf = pygame.display.set_mode((900, 420))
        surf.fill((24, 24, 34))
        font = pygame.font.Font(None, 26)
        title = font.render('Не удалось запустить игру', True, (255, 120, 120))
        surf.blit(title, (20, 16))
        small = pygame.font.Font(None, 20)
        for i, line in enumerate(text.splitlines()[-12:]):
            surf.blit(small.render(line[:110], True, (230, 230, 230)),
                      (20, 56 + i * 26))
        log('см. текст ошибки на экране; полный лог — adb logcat')
        pygame.display.flip()
        deadline = time.time() + 12
        while time.time() < deadline:
            pygame.event.pump()
            time.sleep(0.05)
        pygame.quit()
    except Exception:
        pass


def memory_mb():
    """Размер доступной памяти, МБ (на разных платформах по-разному)."""
    try:
        return os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES') // \
            1048576
    except Exception:
        return 0


def run():
    try:
        from trig_battle_pygame import main
        log('python %s, память ~%d МБ, запуск игры'
            % (sys.version.split()[0], memory_mb()))
        main()
    except BaseException:                 # noqa: BLE001 - ловим и SystemExit
        text = traceback.format_exc()
        log('ЗАПУСК НЕ УДАЛСЯ:\n' + text)
        try:
            sys.stdout.flush()
        except Exception:
            pass
        show_error(text)
        sys.exit(1)


if __name__ == '__main__':
    run()