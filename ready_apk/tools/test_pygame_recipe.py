# -*- coding: utf-8 -*-
"""
Проверка правки рецепта pygame: в расширение `surface` должны попасть
`simd_blitters_sse2.c` и `simd_blitters_avx2.c`.

Почему это важно проверять: без них APK собирается без единой ошибки,
но при запуске на телефоне падает с

    NotImplementedError: display module not available
    (ImportError: dlopen failed: cannot locate symbol
     "alphablit_alpha_sse2_argb_surf_alpha" referenced by
     ".../pygame/surface.so")

То есть ровно тот случай, когда сборка зелёная, а приложение не
запускается. Проверка занимает секунду и не требует ни Android, ни
python-for-android: рецепт грузится с заглушками.

Запуск:  python tools/test_pygame_recipe.py
"""

import importlib.util
import sys
import types

HERE = __import__('os').path.dirname(__import__('os').path.abspath(__file__))
RECIPE = __import__('os').path.join(
    HERE, __import__('os').path.pardir, 'p4a-recipes', 'pygame', '__init__.py')

# Реальные строки из pygame 2.1.3 buildconfig/Setup.Android.SDL2.in
SETUP_TEMPLATE = (
    '# This works differently from the other templates\n'
    '\n'
    'SDL = -I{sdl_includes} -D_REENTRANT -DSDL2 -lSDL2\n'
    'DEBUG =\n'
    '\n'
    'font src_c/font.c $(SDL) $(FONT) $(DEBUG)\n'
    'surface src_c/surface.c src_c/alphablit.c src_c/surface_fill.c '
    '$(SDL) $(DEBUG)\n'
    'transform src_c/transform.c src_c/rotozoom.c src_c/scale2x.c '
    '$(SDL) $(DEBUG)\n'
)


def load_recipe():
    """Импортирует рецепт pygame, подменив pythonforandroid заглушками."""
    pkg = types.ModuleType('pythonforandroid')
    pkg.__path__ = []
    recipe_mod = types.ModuleType('pythonforandroid.recipe')
    toolchain = types.ModuleType('pythonforandroid.toolchain')

    class CompiledComponentsPythonRecipe(object):
        def __init__(self):
            self.ctx = None

    recipe_mod.CompiledComponentsPythonRecipe = CompiledComponentsPythonRecipe
    toolchain.current_directory = lambda d: None
    sys.modules['pythonforandroid'] = pkg
    sys.modules['pythonforandroid.recipe'] = recipe_mod
    sys.modules['pythonforandroid.toolchain'] = toolchain

    spec = importlib.util.spec_from_file_location('pygame_recipe', RECIPE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def check(cond, ok_msg, fail_msg):
    print(('  OK   ' if cond else '  FAIL ') + (ok_msg if cond else fail_msg))
    return bool(cond)


def main():
    ok = True
    print('Проверка рецепта pygame (simd_blitters в surface)')
    mod = load_recipe()

    # 1) объект `recipe`, который возьмёт python-for-android
    obj = getattr(mod, 'recipe', None)
    ok &= check(obj is not None, 'модуль отдаёт объект `recipe`',
                'нет атрибута `recipe` — p4a упадёт с AttributeError')

    # 2) строка surface получает оба SIMD-файла
    patched = obj.fix_surface_sources(SETUP_TEMPLATE)
    line = [ln for ln in patched.splitlines() if ln.startswith('surface ')]
    ok &= check(len(line) == 1, 'строка surface на месте',
                'строка surface потерялась')
    line = line[0] if line else ''
    for src in mod.SIMD_SOURCES:
        ok &= check(src in line, '%s добавлен' % src,
                    '%s НЕ добавлен — surface.so не соберётся' % src)

    # 3) порядок важен: исходники до флагов, иначе -lSDL2 уедет не туда
    for src in mod.SIMD_SOURCES:
        ok &= check(line.index(src) < line.index('$(SDL)'),
                    '%s стоит до $(SDL)' % src,
                    '%s после $(SDL) — флаги применятся не к тому файлу' % src)

    # 4) остальные строки не пострадали
    ok &= check('src_c/transform.c' in patched and
                'src_c/font.c' in patched,
                'остальные расширения не изменены',
                'изменены чужие строки Setup')
    ok &= check(patched.count('simd_blitters') ==
                len(mod.SIMD_SOURCES),
                'каждый файл добавлен ровно один раз',
                'файлы продублированы или потеряны')

    # 5) если строки surface нет — падаем, а не собираем APK без неё
    try:
        obj.fix_surface_sources('font src_c/font.c $(SDL)\n')
        ok &= check(False, '', 'ожидалась ошибка при отсутствии строки surface')
    except RuntimeError:
        ok &= check(True, 'отсутствие строки surface даёт понятную ошибку', '')

    print('Итог: ' + ('все проверки пройдены' if ok else 'ЕСТЬ ОШИБКИ'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
