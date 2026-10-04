# -*- coding: utf-8 -*-
"""
Обновляет код игры в дереве сборки и пишет манифест сборки.

Зачем это нужно
----------------
python-for-android умеет переиспользовать уже собранный dist: если он
нашёл в кэше совместимую сборку, он НЕ строит рецепты заново, а просто
перепаковывает готовое дерево. Из-за этого рецепт, который копирует
код игры, не выполняется — и в APK попадает код из кэша, то есть
СТАРАЯ версия игры. Именно так несколько исправлений дошли до
репозитория, но не до телефона.

Поэтому перед сборкой файлы кладутся в дерево напрямую, а рядом
кладётся манифест с их контрольными суммами. Проверка
`tools/verify_apk.py` сравнивает манифест из APK с текущими файлами и
обязана упасть, если внутри пакета что-то устаревшее.

Запуск (из корня репозитория):
    python .github/scripts/sync_game_files.py [каталог_установки]
"""

import hashlib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
MANIFEST_NAME = 'build_manifest.txt'

# Модули игры. Пути — относительно корня репозитория.
GAME_MODULES = ('trig_battle_pygame.py', 'profiles.py', 'netgame.py')
# Точка входа лежит в каталоге сборки.
ENTRY_MODULE = os.path.join('ready_apk', 'main.py')


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fd:
        for chunk in iter(lambda: fd.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def manifest_text():
    """Манифест: <имя файла> <sha256> — по строке на модуль."""
    rows = []
    for rel in (ENTRY_MODULE,) + GAME_MODULES:
        path = os.path.join(ROOT, rel)
        rows.append('%s %s' % (os.path.basename(rel), sha256(path)))
    return '\n'.join(rows) + '\n'


def write_manifest(dest_dir):
    text = manifest_text()
    path = os.path.join(dest_dir, MANIFEST_NAME)
    with open(path, 'w', encoding='utf-8') as fd:
        fd.write(text)
    return path


def install_dir_from_arg(argv):
    """Каталог site-packages сборки, если он уже существует."""
    if len(argv) > 1:
        return argv[1]
    base = os.path.join(ROOT, 'ready_apk', '.buildozer', 'android',
                        'platform', 'python-installs')
    if not os.path.isdir(base):
        return None
    found = []
    for dist in os.listdir(base):
        arch_dir = os.path.join(base, dist)
        if not os.path.isdir(arch_dir):
            continue
        for arch in os.listdir(arch_dir):
            found.append(os.path.join(arch_dir, arch))
    return found[0] if found else None


def main():
    dest = install_dir_from_arg(sys.argv)
    text = manifest_text()
    print('манифест сборки:')
    for line in text.strip().splitlines():
        print('   ' + line)

    if dest is None:
        print('\nдерево сборки ещё не создано — код скопирует рецепт '
              '(холодная сборка)')
        return 0
    if not os.path.isdir(dest):
        print('\nкаталог %s не найден, пропускаю' % dest)
        return 0

    print('\nобновляю код игры в %s' % dest)
    import shutil
    for rel in (ENTRY_MODULE,) + GAME_MODULES:
        src = os.path.join(ROOT, rel)
        name = os.path.basename(rel)
        target = os.path.join(dest, name)
        shutil.copy(src, target)
        print('   %s -> %s' % (name, target))
    path = write_manifest(dest)
    print('   %s -> %s' % (MANIFEST_NAME, path))
    return 0


if __name__ == '__main__':
    sys.exit(main())
