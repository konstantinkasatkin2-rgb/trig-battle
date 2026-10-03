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
import gzip
import io
import os
import sys
import tarfile
import zipfile

# Модули игры: p4a может положить их как .py (при установке через setup.py)
# или как .pyc — принимаем оба варианта.
REQUIRED = ('main', 'trig_battle_pygame')


def verify(apk):
    print('APK: %s (%.1f МБ)' % (os.path.basename(apk),
                                 os.path.getsize(apk) / 1048576))
    z = zipfile.ZipFile(apk)
    libs = [n for n in z.namelist() if n.endswith('libpybundle.so')]
    if not libs:
        sys.exit('ОШИБКА: в APK нет libpybundle.so (сборка сломана)')
    raw = gzip.decompress(z.read(libs[0]))
    names = tarfile.open(fileobj=io.BytesIO(raw)).getnames()

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