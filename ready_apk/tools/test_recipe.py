# -*- coding: utf-8 -*-
"""
Локальная проверка рецепта trigbattle_src без python-for-android.

Смысл: рецепт — единственное, что кладёт код игры в APK. Если он
молча ничего не скопирует, сборка пройдёт успешно, а приложение будет
падать при запуске. Поэтому проверяем его поведение прямо здесь,
подменяя pythonforandroid заглушками:

  1) рецепт находит каталог с main.py / trig_battle_pygame.py;
  2) build_arch кладёт оба файла в site-packages целевой сборки;
  3) если файлов игры нет — рецепт ПАДАЕТ, а не собирает APK без игры.

Запуск:  python tools/test_recipe.py
"""

import importlib.util
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
RECIPE = os.path.join(HERE, os.pardir, 'p4a-recipes', 'trigbattle_src',
                      '__init__.py')


def load_recipe_with_stubs(tmp):
    """Импортирует рецепт, подменив pythonforandroid заглушками."""
    pkg = type(sys)('pythonforandroid')
    pkg.__path__ = []
    recipe_mod = type(sys)('pythonforandroid.recipe')
    util_mod = type(sys)('pythonforandroid.util')

    class Recipe(object):
        def __init__(self):
            self.ctx = None

        # копия реализации из pythonforandroid/recipe.py
        def get_recipe_dir(self):
            local = os.path.join(self.ctx.local_recipes, self.name)
            if os.path.exists(local):
                return local
            raise RuntimeError('локальный рецепт не найден: ' + local)

    recipe_mod.Recipe = Recipe
    util_mod.ensure_dir = lambda d: os.makedirs(d, exist_ok=True)
    util_mod.info = lambda msg: None
    sys.modules['pythonforandroid'] = pkg
    sys.modules['pythonforandroid.recipe'] = recipe_mod
    sys.modules['pythonforandroid.util'] = util_mod

    spec = importlib.util.spec_from_file_location('trigbattle_src', RECIPE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    class Ctx(object):
        def __init__(self, recipes_dir, site):
            self.local_recipes = recipes_dir
            self.site = site

        def get_python_install_dir(self, arch):
            return os.path.join(self.site, arch)

    return mod, Ctx


def check(cond, ok_msg, fail_msg):
    print(('  OK   ' if cond else '  FAIL ') + (ok_msg if cond else fail_msg))
    return bool(cond)


def main():
    ok = True
    print('Проверка рецепта trigbattle_src')
    mod, Ctx = load_recipe_with_stubs(None)

    # --- проверка 0: p4a достаёт из модуля объект с именем `recipe`.
    #     Именно на этом уже падал рецепт: класс был назван иначе, и
    #     python-for-android ругался
    #     «has no attribute 'recipe'» — через 9 минут сборки.
    print(' проверка 0: модуль отдаёт объект `recipe` (его ждёт p4a)')
    obj = getattr(mod, 'recipe', None)
    ok &= check(obj is not None, 'объект recipe есть',
                'нет атрибута `recipe` — p4a упадёт с AttributeError')
    ok &= check(isinstance(obj, mod.Recipe), 'recipe — экземпляр Recipe',
                'recipe не является экземпляром Recipe')

    # --- случай 1: раскладка как в репозитории — игра в корне проекта,
    #     рецепт в <корень>/p4a-recipes/trigbattle_src
    with tempfile.TemporaryDirectory() as tmp:
        app = os.path.join(tmp, 'ready_apk')
        recipes = os.path.join(app, 'p4a-recipes')
        rdir = os.path.join(recipes, 'trigbattle_src')
        os.makedirs(rdir)
        src = app
        for name in mod.GAME_MODULES:
            with open(os.path.join(src, name), 'w', encoding='utf-8') as fd:
                fd.write('# ' + name + '\n')

        site = os.path.join(tmp, 'site-packages')
        r = mod.recipe          # берём ровно тот объект, который возьмёт p4a
        r.ctx = Ctx(recipes, site)
        r.build_arch(type('Arch', (), {'arch': 'arm64-v8a'})())

        print(' случай 1: игра в корне проекта, рецепт в p4a-recipes/')
        for name in mod.GAME_MODULES:
            got = os.path.join(site, 'arm64-v8a', name)
            ok &= check(os.path.exists(got), '%s -> site-packages' % name,
                        '%s НЕ скопирован' % name)

    # --- случай 2: файлов игры нет -> должно быть исключение, а не
    #     тихая сборка APK без игры
    with tempfile.TemporaryDirectory() as tmp:
        recipes = os.path.join(tmp, 'p4a-recipes')
        os.makedirs(os.path.join(recipes, 'trigbattle_src'))
        r = mod.recipe          # берём ровно тот объект, который возьмёт p4a
        r.ctx = Ctx(recipes, os.path.join(tmp, 'site-packages'))
        print(' случай 2: файлов игры нет')
        try:
            r.build_arch(type('Arch', (), {'arch': 'arm64-v8a'})())
            ok &= check(False, '', 'ожидалась ошибка, а сборка прошла '
                                   'без файлов игры')
        except RuntimeError as e:
            ok &= check('не найдены файлы игры' in str(e), str(e)[:60],
                        'не то сообщение об ошибке')

    print('Итог: ' + ('все проверки пройдены' if ok else 'ЕСТЬ ОШИБКИ'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
