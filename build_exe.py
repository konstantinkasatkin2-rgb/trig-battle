# -*- coding: utf-8 -*-
"""
Сборка .exe игры «Тригонометрический морской бой» (pygame).

Зачем отдельный скрипт: buildozer/python-for-android умеют только Android,
а для Windows достаточно PyInstaller. Скрипт кладёт в сборку всё, что нужно
для работы игры, и кладёт рядом каталог `dtb` с базой профилей — profiles.py
ищет существующий `dtb` вверх по дереву, поэтому база окажется рядом с .exe,
а не во временной папке PyInstaller.

Запуск (из корня репозитория):
    python build_exe.py
Результат:
    dist/Тригонометрический морской бой.exe
"""

import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(ROOT, 'dist')
BUILD = os.path.join(ROOT, 'build_exe')
EXE_NAME = 'Тригонометрический морской бой'

# Что входит в сборку: игра, точка входа и библиотеки профилей/сети.
GAME_SOURCES = ['trig_battle_pygame.py', 'netgame.py', 'profiles.py']


def check_sources():
    missing = [n for n in GAME_SOURCES if not os.path.exists(
        os.path.join(ROOT, n))]
    if missing:
        sys.exit('НЕ НАЙДЕНЫ файлы игры: %s\nОжидаются в корне репозитория.'
                 % ', '.join(missing))


def build():
    check_sources()
    import PyInstaller                     # noqa: F401 - проверка наличия

    # --onefile: одна программа, которую можно положить куда угодно.
    # --windowed: без окна консоли (иначе чёрное окно поверх игры).
    # --name:     имя .exe.
    # --add-data: профиль/сеть лежат рядом по умолчанию (мы в одной папке),
    #             но на всякий случай добавляем их внутрь сборки.
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--noconfirm', '--clean',
        '--onefile', '--windowed',
        '--name', EXE_NAME,
        '--distpath', DIST,
        '--workpath', BUILD,
        '--specpath', BUILD,
        '--paths', ROOT,
    ]
    for src in GAME_SOURCES:
        cmd += ['--add-data', '%s%s.' % (os.path.join(ROOT, src),
                                         os.pathsep)]
    cmd.append(os.path.join(ROOT, 'trig_battle_pygame.py'))

    print('Запуск PyInstaller:\n  ' + ' '.join(cmd[2:6]) + ' ...')
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        sys.exit('PyInstaller завершился с кодом %d' % result.returncode)

    exe = os.path.join(DIST, EXE_NAME + '.exe')
    if not os.path.exists(exe):
        sys.exit('Сборка прошла, но .exe не найден: ' + exe)

    # База профилей — рядом с программой (dtb/users.db создастся сама).
    dtb_src = os.path.join(ROOT, 'dtb')
    dtb_dst = os.path.join(DIST, 'dtb')
    if os.path.isdir(dtb_src):
        if os.path.isdir(dtb_dst):
            shutil.rmtree(dtb_dst)
        shutil.copytree(dtb_src, dtb_dst)
    else:
        os.makedirs(dtb_dst, exist_ok=True)
    # profiles.py при запуске из dist найдёт dtb рядом с .exe:
    # base_dir() = каталог .exe, каталог dtb уже существует.

    size = os.path.getsize(exe) / 1048576
    print('\nГотово: %s (%.1f МБ)' % (exe, size))
    print('Каталог базы профилей: %s' % dtb_dst)


if __name__ == '__main__':
    build()
