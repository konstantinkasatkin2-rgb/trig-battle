# -*- coding: utf-8 -*-
"""Проверка скрипта, обновляющего код игры в дереве сборки.

Скрипт ищет каталоги python-installs под ready_apk/.buildozer. Именно на
этом он уже ошибался: p4a создаёт
`.buildozer/android/platform/build-<arch>/build/python-installs`, а не
`.buildozer/android/platform/python-installs`, и сборка уходила с
устаревшим кодом игры. Проверка создаёт дерево такой формы, с
устаревшим кодом внутри, и требует, чтобы скрипт его обновил.

Запуск:  python ready_apk/tools/test_sync_game_files.py
"""

import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
SYNC = os.path.join(ROOT, '.github', 'scripts', 'sync_game_files.py')
GAME = os.path.join(ROOT, 'trig_battle_pygame.py')

# Настоящий путь, который p4a создаёт на сборщике
TREE = os.path.join('ready_apk', '.buildozer', 'android', 'platform',
                    'build-arm64-v8a', 'build', 'python-installs',
                    'trigbattle', 'arm64-v8a')

ok = True


def check(cond, ok_msg, fail_msg):
    global ok
    print(('  OK   ' if cond else '  FAIL ') + (ok_msg if cond else fail_msg))
    ok = ok and bool(cond)
    return bool(cond)


def main():
    print('Проверка обновления кода в дереве сборки')
    sandbox = tempfile.mkdtemp(prefix='sync-test-')
    try:
        work = os.path.join(sandbox, 'repo')
        os.makedirs(os.path.join(work, '.github', 'scripts'))
        os.makedirs(os.path.join(work, 'ready_apk'))
        shutil.copy(SYNC, os.path.join(work, '.github', 'scripts',
                                       'sync_game_files.py'))
        shutil.copy(GAME, os.path.join(work, 'trig_battle_pygame.py'))
        for name in ('profiles.py', 'netgame.py'):
            shutil.copy(os.path.join(ROOT, name),
                        os.path.join(work, name))
        shutil.copy(os.path.join(ROOT, 'ready_apk', 'main.py'),
                    os.path.join(work, 'ready_apk', 'main.py'))

        # --- холодная сборка: дерева нет, падать не на чем ---
        p = subprocess.run([sys.executable, '.github/scripts/'
                            'sync_game_files.py'], cwd=work,
                           capture_output=True, text=True,
                           encoding='utf-8', errors='replace')
        check(p.returncode == 0 and 'холодная сборка' in p.stdout,
              'без дерева сборки скрипт молча выходит (код скопирует рецепт)',
              'без дерева сборки скрипт ошибся: код=%s, вывод=%r'
              % (p.returncode, (p.stdout + p.stderr)[-200:]))

        # --- тёплая сборка: дерево есть, внутри устаревший код ---
        dest = os.path.join(work, TREE)
        os.makedirs(dest)
        for name in ('main.py', 'trig_battle_pygame.py', 'profiles.py',
                     'netgame.py'):
            with open(os.path.join(dest, name), 'w',
                      encoding='utf-8') as fd:
                fd.write('# устаревшая версия\n')
            # p4a кладёт рядом скомпилированную копию. Python берёт .pyc
            # вместо .py, поэтому старый байт-код и переживал все правки.
            with open(os.path.join(dest, name + 'c'), 'wb') as fd:
                fd.write(b'stale bytecode')
        os.makedirs(os.path.join(dest, '__pycache__'))
        with open(os.path.join(dest, '__pycache__',
                               'netgame.cpython-311.pyc'), 'wb') as fd:
            fd.write(b'stale cache')
        p = subprocess.run([sys.executable, '.github/scripts/'
                            'sync_game_files.py'], cwd=work,
                           capture_output=True, text=True,
                           encoding='utf-8', errors='replace')
        out = p.stdout + p.stderr
        check(p.returncode == 0 and 'обновляю код игры' in out,
              'дерево сборки найдено по настоящему пути p4a',
              'дерево не найдено — код в APK останется старым: %s'
              % out.strip()[-200:])
        fresh = open(os.path.join(dest, 'trig_battle_pygame.py'),
                     encoding='utf-8').read()
        check('устаревшая' not in fresh and 'point_is_mine' in fresh,
              'в дерево записан свежий код игры',
              'в дереве остался старый код игры')
        check(not os.path.exists(os.path.join(dest,
                                              'trig_battle_pygame.pyc')) and
              not os.path.exists(os.path.join(dest, '__pycache__')),
              'старый байт-код удалён, а не оставлен рядом с исходником',
              'старый .pyc/__pycache__ остались в дереве')
        check(os.path.exists(os.path.join(dest, 'build_manifest.txt')),
              'манифест сборки записан в дерево',
              'манифест в дереве не появился')
        check('проверено: все четыре модуля совпадают' in out,
              'скрипт сам проверил результат по хешам',
              'скрипт не проверил, что копирование удалось')

        # --- каталог приложения не трогаем: им распоряжается buildozer ---
        app_dir = os.path.join(work, 'ready_apk', '.buildozer', 'android',
                               'app')
        os.makedirs(app_dir)
        shutil.copy(os.path.join(work, 'ready_apk', 'main.py'),
                    os.path.join(app_dir, 'main.py'))
        p = subprocess.run([sys.executable, '.github/scripts/'
                            'sync_game_files.py'], cwd=work,
                           capture_output=True, text=True,
                           encoding='utf-8', errors='replace')
        check(not os.path.exists(os.path.join(app_dir, 'netgame.py')),
              'каталог приложения buildozer не трогаем',
              'скрипт влез в каталог приложения: %s'
              % os.listdir(app_dir))

        # --- две архитектуры: обновляем обе ---
        dest2 = os.path.join(work, 'ready_apk', '.buildozer', 'android',
                             'platform', 'build-x86_64', 'build',
                             'python-installs', 'trigbattle', 'x86_64')
        os.makedirs(dest2)
        with open(os.path.join(dest2, 'netgame.py'), 'w',
                  encoding='utf-8') as fd:
            fd.write('# устаревшая версия\n')
        p = subprocess.run([sys.executable, '.github/scripts/'
                            'sync_game_files.py'], cwd=work,
                           capture_output=True, text=True,
                           encoding='utf-8', errors='replace')
        check('устаревшая' not in open(os.path.join(dest2, 'netgame.py'),
                                       encoding='utf-8').read(),
              'обновлены обе архитектуры',
              'вторая архитектура осталась старой')

        # --- бандл, который p4a уже собрал раньше, тоже обновляем ---
        bundle = os.path.join(work, 'ready_apk', '.buildozer', 'android',
                              'platform', 'build-arm64-v8a', 'build',
                              '_python_bundle', 'site-packages')
        os.makedirs(bundle)
        with open(os.path.join(bundle, 'trig_battle_pygame.pyc'), 'wb') as fd:
            fd.write(b'stale bytecode')
        p = subprocess.run([sys.executable, '.github/scripts/'
                            'sync_game_files.py'], cwd=work,
                           capture_output=True, text=True,
                           encoding='utf-8', errors='replace')
        out = p.stdout + p.stderr
        check(not os.path.exists(os.path.join(
                  bundle, 'trig_battle_pygame.pyc')) and
              'point_is_mine' in open(os.path.join(
                  bundle, 'trig_battle_pygame.py'), encoding='utf-8').read(),
              'устаревший бандл очищен и обновлён',
              'в бандле остался старый байт-код: %s' % out.strip()[-200:])

        # --- обратный контроль: прежний путь искал не там, где надо ---
        # Скрипт уже один раз ошибся именно так: искал
        # .buildozer/android/platform/python-installs, тогда как p4a
        # создаёт build-<arch>/build/python-installs. Проверка обязана
        # ловить этот путь, иначе она ничего не проверяет.
        with open(SYNC, encoding='utf-8') as fd:
            sync_src = fd.read()
        check('wanted & set(filenames)' in sync_src,
              'каталоги ищутся обходом дерева, а не по одному адресу',
              'в скрипте вернулся путь, которого p4a не создаёт')
        check('android/platform/python-installs' not in sync_src,
              'старый неверный путь больше не используется',
              'в скрипте остался неверный путь android/platform/'
              'python-installs')
        check('проверено: все четыре модуля' in sync_src,
              'копирование проверяется по хешам',
              'копирование ничем не проверяется')
        check("name + 'c'" in sync_src and '__pycache__' in sync_src,
              'старый байт-код вычищается из дерева',
              'скрипт не трогает .pyc — они переживают правки кода')
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)

    print('Итог: %s' % ('все проверки пройдены' if ok else 'ЕСТЬ ОШИБКИ'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())