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
    """Контрольная сумма файла.

    Переводы строк нормализуются: в git файл хранится с LF, а рабочая
    копия на Windows — с CRLF. Без нормализации одна и та же правка даёт
    разные хеши на разных машинах, и проверка врёт в обе стороны.
    """
    with open(path, 'rb') as fd:
        raw = fd.read()
    raw = raw.replace(b'\r\n', b'\n')
    return hashlib.sha256(raw).hexdigest()


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


def install_dirs(argv):
    """Каталоги site-packages сборки, если дерево уже создано.

    Путь не угадываем: p4a создаёт каталог python-installs не сразу под
    platform/, а глубже (build-<arch>/build/python-installs), и с
    изменением версий путь менялся. Раньше здесь был зашит неверный
    адрес, и синхронизация молча ничего не делала, а в APK уезжал
    старый код игры. Поэтому ищем все каталоги python-installs где
    угодно под .buildozer и обновляем их все.
    """
    if len(argv) > 1:
        return [argv[1]]
    base = os.path.join(ROOT, 'ready_apk', '.buildozer')
    if not os.path.isdir(base):
        return []
    found = []
    for dirpath, dirnames, _ in os.walk(base):
        if os.path.basename(dirpath) != 'python-installs':
            continue
        for dist in sorted(dirnames):
            dist_dir = os.path.join(dirpath, dist)
            for arch in sorted(os.listdir(dist_dir)):
                arch_dir = os.path.join(dist_dir, arch)
                if os.path.isdir(arch_dir):
                    found.append(arch_dir)
        dirnames[:] = []          # внутрь python-installs не лезем
    return found


def copy_into(dest):
    """Копирует модули и манифест, затем ПРОВЕРЯЕТ результат по хешам."""
    import shutil
    print('\nобновляю код игры в %s' % dest)
    for rel in (ENTRY_MODULE,) + GAME_MODULES:
        src = os.path.join(ROOT, rel)
        name = os.path.basename(rel)
        shutil.copy(src, os.path.join(dest, name))
        print('   %s' % name)
    write_manifest(dest)
    print('   %s' % MANIFEST_NAME)
    # копирование молча ничего не делает, если путь перепущен: проверяем
    wanted = {}
    for line in manifest_text().strip().splitlines():
        parts = line.split()
        wanted[parts[0]] = parts[1]
    for name, digest in wanted.items():
        path = os.path.join(dest, name)
        with open(path, 'rb') as fd:
            got = hashlib.sha256(
                fd.read().replace(b'\r\n', b'\n')).hexdigest()
        if got != digest:
            print('   ОШИБКА: %s в дереве не совпадает с исходником' % name)
            return False
    print('   проверено: все четыре модуля совпадают с исходником')
    return True


def main():
    text = manifest_text()
    print('манифест сборки:')
    for line in text.strip().splitlines():
        print('   ' + line)

    dests = install_dirs(sys.argv)
    if not dests:
        print('\nдерево сборки ещё не создано — код скопирует рецепт '
              '(холодная сборка)')
        return 0
    bad = 0
    for dest in dests:
        if not copy_into(dest):
            bad += 1
    if bad:
        print('\nОШИБКА: не удалось обновить %d каталог(ов) сборки. Сборка '
              'упала бы с устаревшим кодом внутри APK.' % bad)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
