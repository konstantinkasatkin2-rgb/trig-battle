# -*- coding: utf-8 -*-
"""
Точка входа APK: buildozer требует, чтобы скрипт назывался `main.py` и лежал
в корне `source.dir`. Вся игра — в `trig_battle_pygame.py` рядом.

Здесь же — диагностика для Android. Приложение падало с пустым экраном и
без сообщения, потому что:
  * всё, что напечатано в stdout, уходит в logcat, а без adb его не видно;
  * сообщение об ошибке выводилось средствами pygame, а если SDL не смог
    создать окно, то сообщение показать нечем — получался «молчаливый» вылет.

Поэтому ошибка показывается тремя независимыми способами:
  1. файл-журнал  /sdcard/Android/data/org.kasatkin.trigbattle/files/trigbattle.log
  2. нативный Toast поверх любых окон Android (не зависит от SDL)
  3. экран средствами pygame — если окно всё-таки есть
Плюс всё печатается в stdout -> logcat (`adb logcat -s trigbattle python`).

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

_LOG_PATH = [None]        # вычисляется один раз, при первом обращении
_MILESTONES = []


# ---------------------------------------------------------------- журнал
def log_file_path():
    """Путь файла-журнала (None, если это не Android или нет jnius).

    Используется внешний каталог приложения: он доступен и без root, и без
    разрешений, и его видно в файловом менеджере телефона.
    """
    if _LOG_PATH[0] is not None:
        return _LOG_PATH[0] or None
    path = None
    try:
        from jnius import autoclass
        activity = autoclass('org.kivy.android.PythonActivity').mActivity
        folder = activity.getExternalFilesDir(None)
        if folder is not None:
            path = os.path.join(folder.getAbsolutePath(), 'trigbattle.log')
    except Exception:
        path = None
    _LOG_PATH[0] = path or ''
    return _LOG_PATH[0] or None


def log(msg):
    """Записать сообщение в stdout (-> logcat) и в файл-журнал."""
    line = '[trigbattle] %s' % msg
    _MILESTONES.append(line)
    try:
        print(line, flush=True)
    except Exception:
        pass
    path = log_file_path()
    if path:
        try:
            with open(path, 'a', encoding='utf-8') as fd:
                fd.write('%s %s\n' % (time.strftime('%H:%M:%S'), line))
                fd.flush()
        except Exception:
            pass
    return line


def android_toast(text):
    """Показать текст нативным Toast — работает, даже если SDL не смог
    открыть окно. Отдельный Looper обязателен: иначе Toast.makeText
    бросает исключение из потока Python."""
    try:
        from jnius import autoclass
        Looper = autoclass('android.os.Looper')
        if Looper.myLooper() is None:
            Looper.prepare()
        Toast = autoclass('android.widget.Toast')
        activity = autoclass('org.kivy.android.PythonActivity').mActivity
        Toast.makeText(activity, text[:170], Toast.LENGTH_LONG).show()
        return True
    except Exception:
        return False


# ---------------------------------------------------------------- ошибки
def show_error_pygame(text):
    """Показать ошибку на экране средствами pygame."""
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
        pygame.display.flip()
        deadline = time.time() + 12
        while time.time() < deadline:
            pygame.event.pump()
            time.sleep(0.05)
        pygame.quit()
    except Exception:
        pass


def report_error(text):
    """Показать причину всеми доступными способами."""
    first = ''
    for line in text.splitlines():
        s = line.strip()
        if s and not s.startswith(('Traceback', 'File "', '  ')):
            first = s
            break
    short = first or 'см. файл trigbattle.log'
    log('ТОЧКА ВХОДА УПАЛА: %s' % (first or 'причина в файле журнала'))
    log('полный текст ошибки:\n' + text)
    shown = android_toast(short)
    log('Toast показан: %s' % shown)
    path = log_file_path()
    if path:
        log('файл журнала: %s' % path)
    show_error_pygame(text)


# ---------------------------------------------------------------- запуск
def memory_mb():
    """Размер доступной памяти, МБ (на разных платформах по-разному)."""
    try:
        return os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES') // \
            1048576
    except Exception:
        return 0


def run():
    log('старт: python %s, память ~%d МБ' % (sys.version.split()[0],
                                              memory_mb()))
    log('рабочий каталог: %s' % os.getcwd())
    try:
        import pygame
        log('pygame %s импортирован' % pygame.version.ver)
    except Exception:
        log('ВНИМАНИЕ: pygame не импортируется:\n' + traceback.format_exc())
    try:
        from trig_battle_pygame import main
        log('модуль игры импортирован, запускаю')
        main()
        log('игра завершилась штатно')
    except BaseException:                 # noqa: BLE001 - ловим и SystemExit
        report_error(traceback.format_exc())
        sys.exit(1)


if __name__ == '__main__':
    run()
