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

Заодно вычищается старый байт-код: Python берёт `.pyc`, если он есть
рядом с `.py`, поэтому скомпилированная копия из прошлой сборки
переживала любые правки и уезжала в APK вместо нового кода.

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
    """Все каталоги дерева сборки, где может лежать код игры.

    Путь не угадываем: p4a раскладывает модули по нескольким местам
    (каталог установки python-installs, собранный бандл
    _python_bundle, каталог приложения), и путь менялся от версии к
    версии. Раньше здесь был зашит один неверный адрес — синхронизация
    молча ничего не делала, и в APK уезжал старый код.

    Поэтому ищем все каталоги под .buildozer, где уже есть файл с
    именем одного из наших модулей. Каталог приложения (android/app)
    пропускаем: им распоряжается buildozer, и код оттуда не
    упаковывается.
    """
    if len(argv) > 1:
        return [argv[1]]
    base = os.path.join(ROOT, 'ready_apk', '.buildozer')
    if not os.path.isdir(base):
        return []
    wanted = set(module_names())
    # ищем и по .pyc: в уже собранном бандле лежат только скомпилированные
    # файлы, и такой каталог тоже нужно обновить
    wanted |= {name + 'c' for name in wanted}
    found = []
    for dirpath, dirnames, filenames in os.walk(base):
        norm = os.path.normpath(dirpath)
        if norm.endswith(os.sep + 'android' + os.sep + 'app'):
            dirnames[:] = []
            continue
        if wanted & set(filenames):
            found.append(dirpath)
            dirnames[:] = []              # глубше не лезем
    return found


def module_names():
    return [os.path.basename(ENTRY_MODULE)] + list(GAME_MODULES)


def drop_stale_bytecode(dest):
    """Удаляет скомпилированные версии наших модулей.

    Python на Android берёт .pyc, если он есть, даже когда рядом лежит
    более новый .py. Старый .pyc в закэшированном дереве переживал
    любые правки кода: в APK уезжал байт-код первой сборки. Удаляем
    .pyc и __pycache__, чтобы p4a скомпилировал текущий исходник.
    """
    removed = []
    for name in module_names():
        for stale in (name + 'c',):
            path = os.path.join(dest, stale)
            if os.path.exists(path):
                os.remove(path)
                removed.append(stale)
    cache = os.path.join(dest, '__pycache__')
    if os.path.isdir(cache):
        # имя вида netgame.cpython-311.pyc — модуль стоит первым, до точки
        bases = {os.path.splitext(n)[0] for n in module_names()}
        hit = [f for f in os.listdir(cache) if f.split('.')[0] in bases]
        for f in hit:
            os.remove(os.path.join(cache, f))
            removed.append('__pycache__/' + f)
        if not os.listdir(cache):
            os.rmdir(cache)
    return removed


def copy_into(dest):
    """Копирует модули и манифест, затем ПРОВЕРЯЕТ результат по хешам."""
    import shutil
    print('\nобновляю код игры в %s' % dest)
    for rel in (ENTRY_MODULE,) + GAME_MODULES:
        name = os.path.basename(rel)
        shutil.copy(os.path.join(ROOT, rel), os.path.join(dest, name))
        print('   %s' % name)
    removed = drop_stale_bytecode(dest)
    print('   удалено устаревшее: %s' % (', '.join(removed) or 'ничего'))
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
        stale = path + 'c'
        if os.path.exists(stale):
            print('   ОШИБКА: %s остался рядом со свежим исходником — '
                  'в APK уедет старый байт-код' % os.path.basename(stale))
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
