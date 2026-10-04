"""
Рецепт python-for-android: кладёт код игры в site-packages сборки.

Зачем он нужен
--------------
Приложение состоит из файлов Python, и их нужно доставить внутрь APK.
Возможных путей два, и оба оказались ненадёжными:

1. Копирование проекта «по шаблонам» — в этой версии python-for-android
   такого механизма нет вообще.
2. Установка проекта через `setup.py` (то, что делает опция
   `p4a.setup_py`) — buildozer кладёт `setup.py` в приватный каталог
   ПОЗЖЕ, чем p4a проверяет его наличие, поэтому p4a пишет
   «No Python modules and no setup.py to process, skipping», и APK
   собирается без единого файла игры: приложение стартует и сразу
   закрывается. Сборка при этом успешна — ошибки никто не видит.

Рецепт же срабатывает на этапе сборки рецептов, то есть ДО сборки
бандла, и читает исходники прямо из рабочей копии репозитория
(`get_recipe_dir()` -> каталог с этим рецептом), а не из приватной
копии, которую buildozer создаёт позже. Поэтому код игры гарантированно
попадает в site-packages, откуда он импортируется при запуске.

Модули кладутся в site-packages рядом с pygame: лаунчер Android
импортирует `main`, тот — `trig_battle_pygame`, а тот — `profiles`
(профили) и `netgame` (игра по сети). Забыть любой из них нельзя:
игра упадёт на старте с ImportError, поэтому отсутствие файла здесь
приводит к остановке сборки.
"""

from os.path import abspath, dirname, exists, join
import shutil

from pythonforandroid.recipe import Recipe
from pythonforandroid.util import ensure_dir, info

# Модули, которые обязаны оказаться в APK.
# main.py — точка входа, которую запускает Android;
# trig_battle_pygame.py — сама игра.
GAME_MODULES = ('trig_battle_pygame.py', 'profiles.py', 'netgame.py')

# Точка входа лежит в каталоге сборки, игра и библиотеки — в корне
# репозитория, поэтому каждый модуль ищется отдельно.
ENTRY_MODULE = 'main.py'

# Сколько уровней вверх искать модули: рецепт лежит в
# ready_apk/p4a-recipes/trigbattle_src/, игра — на два уровня выше.
SEARCH_UP_LEVELS = 3


def arch_name(arch):
    """Имя архитектуры из аргумента рецепта.

    python-for-android передаёт аргументы в НЕОДИНАКОВОМ виде
    (build_recipes, v2024.01.21):
        recipe.prepare_build_dir(arch.arch)  -> строка 'arm64-v8a'
        recipe.build_arch(arch)              -> объект Arch
    Поэтому принимаем оба варианта — иначе рецепт падает с
    «'str' object has no attribute 'arch'».
    """
    return arch if isinstance(arch, str) else arch.arch


class TrigbattleSrcRecipe(Recipe):
    """Копирует .py-файлы игры в site-packages целевой сборки."""

    version = '0.2.1'
    name = 'trigbattle_src'

    # Файлы игры — обычные .py, ничего компилировать не нужно.
    depends = ('python3',)

    def find_module(self, name):
        """Ищет файл модуля рядом с рецептом, поднимаясь вверх по дереву.

        Рецепт лежит в ready_apk/p4a-recipes/trigbattle_src/, поэтому за
        два уровня вверх — корень репозитория с игрой и библиотеками, а
        на один уровень — каталог сборки с main.py.

        Если файл не найден, рецепт ПАДАЕТ: молча собрать APK без игры
        можно, и ровно так уже вышло с версией 0.2.0.
        """
        start = abspath(self.get_recipe_dir())
        candidate = start
        for level in range(SEARCH_UP_LEVELS + 1):
            path = join(candidate, name)
            if exists(path):
                return path
            if level == SEARCH_UP_LEVELS:
                break
            candidate = dirname(candidate)
        raise RuntimeError(
            'Рецепт {name}: не найден файл {mod} (искал от {start} вверх на '
            '{levels} уровней). Проверьте, что он лежит в корне репозитория '
            'или в каталоге сборки.'
            .format(name=self.name, mod=name, start=start,
                    levels=SEARCH_UP_LEVELS)
        )

    def prepare_build_dir(self, arch):
        # Базовый Recipe пытается распаковать архив (self.unpack), но у
        # этого рецепта нет ни url, ни source_dir — распаковывать нечего.
        ensure_dir(self.get_build_dir(arch_name(arch)))

    def build_arch(self, arch):
        name = arch_name(arch)
        dest = self.ctx.get_python_install_dir(name)
        ensure_dir(dest)
        for module in (ENTRY_MODULE,) + GAME_MODULES:
            path = self.find_module(module)
            shutil.copy(path, join(dest, module))
            info('trigbattle_src: {} -> {}'.format(module, dest))


# python-for-android загружает рецепт и достаёт из модуля ИМЕННО объект с
# именем `recipe` (pythonforandroid/recipe.py: `recipe = mod.recipe`).
# Без этой строки p4a падает с
#   AttributeError: module 'pythonforandroid.recipes.trigbattle_src'
#                  has no attribute 'recipe'
recipe = TrigbattleSrcRecipe()
