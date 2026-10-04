# -*- coding: utf-8 -*-
"""
Проверка собранного APK: внутри обязательно должны быть файлы игры.

Нужна потому, что python-for-android умеет молча собрать APK с Python и
pygame, но БЕЗ кода игры: приложение стартует и сразу закрывается, а
причина не видна нигде — сборка зелёная. Код игры кладёт в бандл
рецепт p4a-recipes/trigbattle_src; если он отвалится, этот скрипт
остановит прогон. (Именно так вёл себя APK 0.2.0.)

Запуск:
    python tools/verify_apk.py dist/trigbattle_0.2.1.apk
"""

import glob
import hashlib
import gzip
import io
import os
import sys
import tarfile
import zipfile

# Модули игры: p4a может положить их как .py (при установке через setup.py)
# или как .pyc — принимаем оба варианта.
REQUIRED = ('main', 'trig_battle_pygame')


MANIFEST_NAME = 'build_manifest.txt'
GAME_MODULES = ('main.py', 'trig_battle_pygame.py', 'profiles.py',
                'netgame.py')


def local_manifest():
    """-> {имя файла: sha256} для текущего исходника."""
    root = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))
    out = {}
    for name in GAME_MODULES:
        # main.py лежит в каталоге сборки, остальное — в корне репозитория
        for candidate in (os.path.join(root, name),
                          os.path.join(root, 'ready_apk', name)):
            if os.path.exists(candidate):
                with open(candidate, 'rb') as fd:
                    out[name] = hashlib.sha256(fd.read()).hexdigest()
                break
    return out


def check_fresh_code(names, tf):
    """Свежий ли код игры внутри APK. Ничего не распознано — ругаемся."""
    packed = [n for n in names if n.endswith('/' + MANIFEST_NAME)]
    if not packed:
        print('  НЕТ манифест сборки %s — нечем подтвердить свежесть '
              'кода' % MANIFEST_NAME)
        return False
    text = tf.extractfile(packed[0]).read().decode('utf-8', 'replace')
    inside = {}
    for line in text.strip().splitlines():
        parts = line.split()
        if len(parts) == 2:
            inside[parts[0]] = parts[1]
    local = local_manifest()
    if not inside or not local:
        print('  НЕ УДАЛОСЬ прочитать манифест')
        return False
    stale = []
    for name, digest in sorted(local.items()):
        got = inside.get(name)
        if got is None:
            print('  НЕТ   %s в манифесте APK' % name)
            stale.append(name)
        elif got != digest:
            print('  СТАРЕЕ %s: в APK %s..., в исходнике %s...'
                  % (name, got[:12], digest[:12]))
            stale.append(name)
        else:
            print('  ОК    %s совпадает с исходником' % name)
    if stale:
        print('  ИТОГ: в APK устаревший код: %s.' % ', '.join(stale))
        print('        Причина: python-for-android переиспользовал '
              'закэшированный dist и не выполнил рецепт, который копирует '
              'код игры.')
        print('        Соберите заново без кэша дерева (см. sync_game_files.py).')
        return False
    return True


def verify(apk):
    print('APK: %s (%.1f МБ)' % (os.path.basename(apk),
                                 os.path.getsize(apk) / 1048576))
    z = zipfile.ZipFile(apk)
    libs = [n for n in z.namelist() if n.endswith('libpybundle.so')]
    if not libs:
        sys.exit('ОШИБКА: в APK нет libpybundle.so (сборка сломана)')
    raw = gzip.decompress(z.read(libs[0]))
    tf = tarfile.open(fileobj=io.BytesIO(raw))
    names = tf.getnames()

    print('  файлов в бандле: %d' % len(names))
    tops = sorted({n.split('/')[1] for n in names if n.count('/') >= 1})
    print('  верхний уровень бандла: %s' % ', '.join(tops[:12]))
    archs = sorted({n.split('/')[1] for n in z.namelist()
                    if n.startswith('lib/')})
    print('  архитектуры: %s' % ', '.join(archs))
    big = sorted(((z.getinfo(n).file_size, n) for n in z.namelist()),
                 reverse=True)[:5]
    print('  крупнейшие части APK:')
    for size, name in big:
        print('    %7.1f МБ  %s' % (size / 1048576, name))

    ok = True
    for need in REQUIRED:
        hit = [m for m in names
               if m.endswith('/' + need + '.py')
               or m.endswith('/' + need + '.pyc')]
        print('  %s %s%s' % ('OK  ' if hit else 'НЕТ ', need,
                             '  -> ' + hit[0] if hit else ''))
        ok = ok and bool(hit)
    hit = [m for m in names if 'site-packages/pygame' in m]
    print('  %s pygame в site-packages' % ('OK  ' if hit else 'НЕТ '))
    ok = ok and bool(hit)

    # Разрешение INTERNET обязательно для игры по сети. Без него Android
    # запрещает любую работу с сокетами, и кнопка «Создать игру» молча
    # не работает (версия 0.2.3). Имена разрешений лежат в манифесте
    # как UTF-16 строки.
    manifest = z.read('AndroidManifest.xml')
    need_perm = b'android.permission.INTERNET'.decode()
    have_perm = need_perm.encode('utf-16-le') in manifest
    print('  %s разрешение INTERNET в манифесте' % ('OK  ' if have_perm
                                                    else 'НЕТ '))
    ok = ok and have_perm

    # Модули профилей и сети обязаны быть рядом с игрой: без них
    # приложение упадёт с ImportError на старте.
    for need in ('profiles', 'netgame'):
        hit = [m for m in names if m.endswith('/' + need + '.pyc')
               or m.endswith('/' + need + '.py')]
        print('  %s %s.py в бандле' % ('OK  ' if hit else 'НЕТ ', need))
        ok = ok and bool(hit)

    # Код внутри APK обязан совпадать с текущим исходником. Такая
    # проверка нужна потому, что python-forandroid умеет переиспользовать
    # закэшированный dist: рецепт, копирующий игру, при этом не
    # выполняется, и в пакет попадает СТАРАЯ версия игры — при зелёной
    # сборке и полностью рабочем APK предыдущего релиза.
    ok = check_fresh_code(names, tf) and ok

    if not ok:
        sys.exit('\nОШИБКА: игра не попала в APK — приложение не запустится.\n'
                 'Проверьте рецепт p4a-recipes/trigbattle_src (он кладёт\n'
                 'main.py и trig_battle_pygame.py в site-packages) и его\n'
                 'наличие в requirements в buildozer.spec.')
    print('\nВсё в порядке: игра внутри APK есть.')


if __name__ == '__main__':
    apks = sorted(glob.glob(sys.argv[1] if len(sys.argv) > 1
                            else 'dist/*.apk'))
    if not apks:
        sys.exit('APK не найден')
    verify(apks[0])