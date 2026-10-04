# -*- coding: utf-8 -*-
"""
Находит блок подписи APK (схема v2/v3) и печатает его отпечаток.

Зачем отдельным файлом: разбирать блок подписи в shell неудобно, а на
устройстве runner'а apktool/apksigner может отсутствовать. Блок лежит
непосредственно перед центральным каталогом и начинается магией
"APK Sig Block 42"; берём отпечаток первых 4 КБ после неё — этого
достаточно, чтобы отличать одну подпись от другой.

Печатает пустую строку, если блока нет (тогда подпись только v1).

Запуск:
    python find_sig_block.py путь/к/app.apk
"""

import hashlib
import sys

MAGIC = b'APK Sig Block 42'
WINDOW = 4096


def find_sig_block(apk_path):
    """-> отпечаток SHA-256 блока подписи или ''."""
    with open(apk_path, 'rb') as fd:
        data = fd.read()
    pos = data.rfind(MAGIC)
    if pos < 0:
        return ''
    return hashlib.sha256(data[pos:pos + WINDOW]).hexdigest()


def main():
    if len(sys.argv) < 2:
        sys.exit('укажите путь к APK')
    print(find_sig_block(sys.argv[1]), end='')


if __name__ == '__main__':
    main()
