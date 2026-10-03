"""
Локальный рецепт `pygame` для python-for-android.

Зачем он нужен
--------------
Штатный рецепт p4a собирает pygame 2.1.0, а его Cython-расширения
содержат:

    #ifndef CYTHON_USE_PYLONG_INTERNALS
      #define CYTHON_USE_PYLONG_INTERNALS 1
    #endif
    ...
    #if CYTHON_USE_PYLONG_INTERNALS
      #include "longintrepr.h"
    #endif

В Python 3.11 заголовок longintrepr.h переехал из `Include/` в
`Include/cpython/`, а в Python 3.12+ он удалён вообще. Из-за этого
сборка падает с:

    src_c/_sdl2/sdl2.c:211:12: fatal error: 'longintrepr.h' file not found

Исправление: выставляем `CYTHON_USE_PYLONG_INTERNALS 0` — это штатный
и поддерживаемый Cython режим (доступ к long идёт через публичный API),
без него расширение всё равно собирается и работает.

Заодно оставлен только arm64-v8a (см. buildozer.spec): для armeabi-v7a
на свежих NDK падает grpmodule.c (`-Werror=implicit-function-declaration`).
"""

import os
from os.path import join

from pythonforandroid.logger import info
from pythonforandroid.recipe import CompiledComponentsPythonRecipe
from pythonforandroid.toolchain import current_directory


class PygameRecipe(CompiledComponentsPythonRecipe):
    version = '2.1.0'
    url = 'https://github.com/pygame/pygame/archive/{version}.tar.gz'

    site_packages_name = 'pygame'
    name = 'pygame'

    depends = ['sdl2', 'sdl2_image', 'sdl2_mixer', 'sdl2_ttf',
               'setuptools', 'jpeg', 'png']
    call_hostpython_via_targetpython = False   # из-за setuptools
    install_in_hostpython = False

    def prebuild_arch(self, arch):
        super().prebuild_arch(arch)
        with current_directory(self.get_build_dir(arch.arch)):
            self.write_setup(arch)
            self.disable_pylong_internals()

    def write_setup(self, arch):
        """Сгенерировать файл Setup (без него setup.py не знает, что собирать)."""
        setup_template = open(
            join('buildconfig', 'Setup.Android.SDL2.in')).read()
        env = self.get_recipe_env(arch)
        env['ANDROID_ROOT'] = join(self.ctx.ndk.sysroot, 'usr')

        png = self.get_recipe('png', self.ctx)
        png_lib_dir = join(png.get_build_dir(arch.arch), '.libs')
        png_inc_dir = png.get_build_dir(arch)

        jpeg = self.get_recipe('jpeg', self.ctx)
        jpeg_inc_dir = jpeg_lib_dir = jpeg.get_build_dir(arch.arch)

        sdl_mixer_includes = ''
        for include_dir in self.get_recipe('sdl2_mixer', self.ctx)\
                .get_include_dirs(arch):
            sdl_mixer_includes += f'-I{include_dir} '

        sdl2_image_includes = ''
        for include_dir in self.get_recipe('sdl2_image', self.ctx)\
                .get_include_dirs(arch):
            sdl2_image_includes += f'-I{include_dir} '

        setup_file = setup_template.format(
            sdl_includes=(
                ' -I' + join(self.ctx.bootstrap.build_dir, 'jni', 'SDL',
                             'include') +
                ' -L' + join(self.ctx.bootstrap.build_dir, 'libs', str(arch)) +
                ' -L' + png_lib_dir + ' -L' + jpeg_lib_dir +
                ' -L' + arch.ndk_lib_dir_versioned),
            sdl_ttf_includes='-I' + join(self.ctx.bootstrap.build_dir, 'jni',
                                         'SDL2_ttf'),
            sdl_image_includes=sdl2_image_includes,
            sdl_mixer_includes=sdl_mixer_includes,
            jpeg_includes='-I' + jpeg_inc_dir,
            png_includes='-I' + png_inc_dir,
            freetype_includes='')
        open('Setup', 'w').write(setup_file)

    def disable_pylong_internals(self):
        """Отключить CYTHON_USE_PYLONG_INTERNALS во всех .c pygame."""
        patched = 0
        for root, _dirs, files in os.walk('src_c'):
            for name in files:
                if not name.endswith('.c'):
                    continue
                path = join(root, name)
                try:
                    with open(path, encoding='utf-8', errors='ignore') as f:
                        text = f.read()
                except OSError:
                    continue
                if '#include "longintrepr.h"' not in text:
                    continue
                new = text.replace(
                    '#define CYTHON_USE_PYLONG_INTERNALS 1',
                    '#define CYTHON_USE_PYLONG_INTERNALS 0')
                if new != text:
                    with open(path, 'w', encoding='utf-8') as f:
                        f.write(new)
                    patched += 1
        info('pygame: CYTHON_USE_PYLONG_INTERNALS выключен в {} файл(ах)',
             patched)

    def get_recipe_env(self, arch):
        env = super().get_recipe_env(arch)
        env['USE_SDL2'] = '1'
        env['PYGAME_CROSS_COMPILE'] = 'TRUE'
        env['PYGAME_ANDROID'] = 'TRUE'
        return env


recipe = PygameRecipe()