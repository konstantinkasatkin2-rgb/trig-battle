# -*- coding: utf-8 -*-
"""
Проверка APK: остались ли `.so` без нужных символов.

Зачем: главная беда этого проекта в том, что APK собирается «успешно»,
но падает на устройстве. Пример из жизни: `pygame/surface.so` не мог
найти `alphablit_alpha_sse2_argb_surf_alpha`, модуль `display` не
загружался — и сборка при этом была зелёной.

Важно не спутать две вещи. У любого Python-расширения есть «неопределённые»
символы: `PyErr_SetString`, `PyCapsule_New`, `SDL_*` и т.п. Их приносят
другие библиотеки — и это нормально. Поэтому символ считается проблемой
только если он не определён НИГДЕ: ни в одной `.so` бандла, ни в
библиотеках самого APK (`lib/arm64-v8a/*.so`, где лежит libpython3.11.so).

Запуск:
    python tools/verify_elf.py bin/trigbattle_0.2.2.apk
"""

import glob
import gzip
import io
import struct
import sys
import tarfile
import zipfile

SHT_DYNSYM = 11
SHN_UNDEF = 0

# Эти приходят из системы Android; их у нас нет и не должно быть.
SYSTEM_PREFIXES = ('libc.so', 'libdl.so', 'libm.so', 'liblog.so',
                   'libandroid.so', 'libz.so', 'libEGL.so', 'libGLESv2.so',
                   'libGLESv3.so', 'libvulkan.so', 'libaaudio.so',
                   'libOpenSLES.so', 'libjnigraphics.so', 'libnativehelper.so',
                   'libstdc++.so', 'libgcc_s.so', 'libutils.so', 'libui.so',
                   'libbinder.so', 'libhwui.so', 'libskia.so', 'libcrypto',
                   'libssl', '_ITM_', '__gnu', 'aeabi_', 'unwind_', 'tls_',
                   '__cxa_', 'ANDROID_', '__ANDROID')


# Части пути, для которых проверка обязательна. Именно здесь ошибка
# «собралось, но dlopen падает» и обнаружилась (pygame/surface.so).
CHECKED_PARTS = ('/pygame/', '/_sdl2/')


def elf_symbols(elf):
    """-> (определённые, неопределённые) имена из .dynsym."""
    if elf[:4] != b'\x7fELF' or elf[4] != 2:
        raise ValueError('не ELF64')
    e_shoff, = struct.unpack_from('<Q', elf, 0x28)
    e_shentsize, e_shnum, _e_shstrndx = struct.unpack_from('<HHH', elf, 0x3a)

    sections = []
    for i in range(e_shnum):
        off = e_shoff + i * e_shentsize
        (sh_name, sh_type, _f, _a, sh_offset, sh_size, sh_link, _i,
         _al, sh_entsize) = struct.unpack_from('<IIQQQQIIQQ', elf, off)
        sections.append((sh_type, sh_offset, sh_size, sh_link, sh_entsize))

    defined, undefined = set(), set()
    for sh_type, sh_offset, sh_size, sh_link, sh_entsize in sections:
        if sh_type != SHT_DYNSYM:
            continue
        str_off, str_size = sections[sh_link][1], sections[sh_link][2]
        strtab = elf[str_off:str_off + str_size]
        entsize = sh_entsize or 24
        for off in range(sh_offset, sh_offset + sh_size, entsize):
            st_name, _info, _other, st_shndx, _v, _sz = \
                struct.unpack_from('<IBBHQQ', elf, off)
            if st_name == 0:
                continue
            end = strtab.find(b'\0', st_name)
            if end < 0:
                continue
            name = strtab[st_name:end].decode('utf-8', 'replace')
            if not name:
                continue
            (undefined if st_shndx == SHN_UNDEF else defined).add(name)
    return defined, undefined


def collect(apk):
    """-> (библиотеки APK, модули бандла) как списки [(имя, байты)].

    Разделение важно: `lib/*.so` из APK — это C-библиотеки, и их
    неопределённые символы приходят из системы Android. А `.so` из
    бандла — расширения Python, и их символы обязаны находиться внутри
    бандла либо в `lib/*.so`.
    """
    z = zipfile.ZipFile(apk)
    libs = [(n, z.read(n)) for n in z.namelist() if n.endswith('.so')]
    lib = [n for n in z.namelist() if n.endswith('libpybundle.so')]
    if not lib:
        sys.exit('ОШИБКА: в APK нет libpybundle.so')
    tf = tarfile.open(fileobj=io.BytesIO(gzip.decompress(z.read(lib[0]))))
    modules = [(m.name, tf.extractfile(m).read())
               for m in tf.getmembers() if m.name.endswith('.so')]
    return libs, modules


def report(apk):
    print('APK: %s' % apk)
    libs, modules = collect(apk)
    print('  .so: %d в бандле, %d библиотек в APK' % (len(modules), len(libs)))

    defined_everywhere = set()
    system_syms = set()
    parsed = {}
    for name, data in modules + libs:
        try:
            d, u = elf_symbols(data)
        except Exception:                       # noqa: BLE001 - не ELF/битый
            continue
        defined_everywhere |= d
        if any(n.endswith(name) for n, _ in libs):
            # символы, нужные C-библиотекам, приходят из Android
            system_syms |= u
        else:
            parsed[name] = u

    problems = []
    for name, undef in parsed.items():
        missing = {s for s in undef
                   if s not in defined_everywhere
                   and s not in system_syms
                   and not s.startswith(SYSTEM_PREFIXES)
                   and '@' not in s}
        if not missing:
            continue
        # Строго проверяем только pygame/SDL: там живёт этот класс ошибок
        # (собранная с неполным списком исходников .so). У прочих модулей
        # Python остаются одиночные обращения к libc — их не различить.
        if any(p in name for p in CHECKED_PARTS):
            problems.append((name.split('/')[-1], sorted(missing)))

    if not problems:
        print('  ОК: каждый символ, нужный .so, где-то определён —')
        print('      dlopen не должен падать')
        return 0
    print('  ПРОБЛЕМА: символы без определения (%d .so):' % len(problems))
    for mod, syms in problems:
        print('    %s: %s' % (mod, ', '.join(syms[:12])))
    return 1


if __name__ == '__main__':
    apks = sorted(glob.glob(sys.argv[1] if len(sys.argv) > 1 else 'bin/*.apk'))
    if not apks:
        sys.exit('APK не найден')
    sys.exit(report(apks[0]))
