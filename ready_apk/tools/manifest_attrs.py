# -*- coding: utf-8 -*-
"""Читает AndroidManifest.xml из APK и печатает значения атрибутов.

Зачем: `screenOrientation` в бинарном манифесте хранится НЕ строкой,
а целым числом (0 = landscape, 1 = portrait, 6 = sensorLandscape,
-1 = unspecified). Поэтому «посмотреть в тексте» нельзя — нужно
разобрать бинарный XML. Этот скрипт читает только строковый пул и
START_TAG, ничего не меняя в APK.

Запуск:  python ready_apk/tools/manifest_attrs.py путь-к-apk
"""

import struct
import sys
import zipfile

CHUNK_STRING_POOL = 0x0001
CHUNK_START_TAG = 0x0102

# android:screenOrientation
ORIENT = {
    -1: 'unspecified (система решает сама)',
    0: 'landscape',
    1: 'portrait',
    2: 'user',
    3: 'behind',
    4: 'sensor',
    5: 'nosensor',
    6: 'sensorLandscape',
    7: 'sensorPortrait',
    8: 'reverseLandscape',
    9: 'reversePortrait',
    10: 'fullSensor',
    11: 'userLandscape',
    12: 'userPortrait',
    13: 'fullUser',
    14: 'locked',
}


def read_pool(data, start):
    """-> (список строк, конец блока)."""
    # ResChunk_header занимает 8 байт; поля пула идут сразу за ним
    _, _, size = struct.unpack_from('<HHI', data, start)
    hdr_size = 28
    count, style_count, flags, str_off, style_off = struct.unpack_from(
        '<IIIII', data, start + 8)
    utf8 = bool(flags & (1 << 8))
    offsets = struct.unpack_from('<%dI' % count, data, start + hdr_size)
    # строки лежат от начала блока (stringsStart — смещение от его начала)
    base = start + str_off
    out = []
    for off in offsets:
        p = base + off
        if utf8:
            # два байта длины в utf8, потом данные, потом 0x00
            n = data[p]
            p += 2 if n & 0x80 else 1
            m = data[p]
            if m & 0x80:
                m = ((m & 0x7F) << 8) | data[p + 1]
                p += 2
            else:
                p += 1
            out.append(data[p:p + m].decode('utf-8', 'replace'))
        else:
            n = struct.unpack_from('<H', data, p)[0]
            out.append(data[p + 2:p + 2 + n * 2].decode('utf-16-le',
                                                        'replace'))
    return out, start + size


def attributes(data, start, pool):
    _, hdr_size, size = struct.unpack_from('<HHI', data, start)
    attr_start, attr_size, attr_count = struct.unpack_from(
        '<HHH', data, start + hdr_size + 8)
    base = start + hdr_size + attr_start
    out = []
    for i in range(attr_count):
        ns, name, raw = struct.unpack_from('<III', data, base + i * attr_size)
        _sz, _res0, dtype, dval = struct.unpack_from(
            '<HBBI', data, base + i * attr_size + 12)
        out.append((pool[name] if name < len(pool) else '?',
                    dtype, dval, pool[raw] if raw != 0xFFFFFFFF and
                    raw < len(pool) else None))
    return out, start + size


def main():
    apk = sys.argv[1] if len(sys.argv) > 1 else \
        'ready_apk/bin/trigbattle_0.2.3.apk'
    data = zipfile.ZipFile(apk).read('AndroidManifest.xml')
    pool = []
    pos = 8                                  # заголовок файла
    found = []
    while pos < len(data) - 8:
        ctype, hdr, size = struct.unpack_from('<HHI', data, pos)
        if size <= 0:
            break
        if ctype == CHUNK_STRING_POOL:
            pool, _ = read_pool(data, pos)
        elif ctype == CHUNK_START_TAG:
            attrs, _ = attributes(data, pos, pool)
            for name, dtype, dval, raw in attrs:
                if 'orientation' in name.lower():
                    found.append((pool[pos and 0 or 0] if False else name,
                                  dtype, dval, raw))
        pos += size

    print('Атрибуты ориентации в %s:' % apk)
    if not found:
        print('  НЕТ — ориентация не зафиксирована в манифесте')
        return 1
    for name, dtype, dval, raw in found:
        if dtype == 0x03:                     # TYPE_STRING
            print('  %s = "%s"' % (name, raw))
        elif dtype == 0x10:                   # TYPE_INT_DEC
            print('  %s = %d (%s)' % (name, dval,
                                      ORIENT.get(dval, 'неизвестно')))
        else:
            print('  %s = тип 0x%02x, значение %d' % (name, dtype, dval))
    return 0


if __name__ == '__main__':
    sys.exit(main())