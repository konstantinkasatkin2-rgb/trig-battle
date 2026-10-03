"""
Локальный рецепт `pygame` для python-for-android.

Зачем он нужен
--------------
Штатный рецепт p4a жёстко зафиксирован на pygame **2.1.0**, а его
Cython-расширения несовместимы с Python 3.11:

  * `#include "longintrepr.h"` — в 3.11 заголовок переехал в
    `Include/cpython/`, а в 3.12+ удалён;
  * обращения к внутренностям `PyFrameObject` (`sizeof`, `offsetof`) —
    в 3.11 структура стала непрозрачной.

pygame **2.1.3** (январь 2023) — первая версия с официальной поддержкой
Python 3.11, и Android-шаблон `buildconfig/Setup.Android.SDL2.in` в ней
ещё есть (в 2.1.6 его уже удалили). Поэтому в рецепте меняется только
номер версии, логика сборки остаётся штатной p4a.

Всё остальное (генерация файла Setup, список зависимостей) скопировано
из рецепта python-for-android без изменений.
"""

from os.path import join

from pythonforandroid.recipe import CompiledComponentsPythonRecipe
from pythonforandroid.toolchain import current_directory


class PygameRecipe(CompiledComponentsPythonRecipe):
    version = '2.1.3'
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

    def write_setup(self, arch):
        """Сгенерировать файл Setup: без него setup.py не знает, что собирать."""
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
            sdl_mixer_includes += '-I{} '.format(include_dir)

        sdl2_image_includes = ''
        for include_dir in self.get_recipe('sdl2_image', self.ctx)\
                .get_include_dirs(arch):
            sdl2_image_includes += '-I{} '.format(include_dir)

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
        with open('Setup', 'w') as f:
            f.write(setup_file)

    def get_recipe_env(self, arch):
        env = super().get_recipe_env(arch)
        env['USE_SDL2'] = '1'
        env['PYGAME_CROSS_COMPILE'] = 'TRUE'
        env['PYGAME_ANDROID'] = 'TRUE'
        return env


recipe = PygameRecipe()