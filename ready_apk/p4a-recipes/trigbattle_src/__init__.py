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

Файлы кладутся в site-packages рядом с pygame: лаунчер Android
импортирует модуль `main`, а тот импортирует `trig_battle_pygame`.
"""

from os.path import abspath, dirname, exists, join
import shutil

from pythonforandroid.recipe import Recipe
from pythonforandroid.util import ensure_dir, info

# Модули, которые обязаны оказаться в APK.
# main.py — точка входа, которую запускает Android;
# trig_battle_pygame.py — сама игра.
GAME_MODULES = ('main.py', 'trig_battle_pygame.py')

# Сколько уровней вверх искать каталог с файлами игры: рецепт лежит в
# ready_apk/p4a-recipes/trigbattle_src/, игра — в ready_apk/.
SEARCH_UP_LEVELS = 3


class TrigbattleSrcRecipe(Recipe):
    """Копирует .py-файлы игры в site-packages целевой сборки."""

    version = '0.2.1'
    name = 'trigbattle_src'

    # Файлы игры — обычные .py, ничего компилировать не нужно.
    depends = ('python3',)

    def find_game_dir(self):
        """Ищет каталог с файлами игры рядом с рецептом.

        Рецепт лежит в <корень>/p4a-recipes/trigbattle_src, а игра — в
        <корень>. Поднимаемся вверх, но если не нашли — падаем с
        внятным сообщением, а не молча собираем APK без игры.
        """
        start = abspath(self.get_recipe_dir())
        candidate = start
        for level in range(SEARCH_UP_LEVELS + 1):
            if all(exists(join(candidate, m)) for m in GAME_MODULES):
                return candidate
            if level == SEARCH_UP_LEVELS:
                break
            candidate = dirname(candidate)
        raise RuntimeError(
            'Рецепт {name}: не найдены файлы игры {mods} (искал от {start} '
            'вверх на {levels} уровней). Проверьте, что main.py и '
            'trig_battle_pygame.py лежат в каталоге рецепта или рядом.'
            .format(name=self.name, mods=', '.join(GAME_MODULES),
                    start=start, levels=SEARCH_UP_LEVELS)
        )

    def prepare_build_dir(self, arch):
        # Базовый Recipe пытается распаковать архив (self.unpack), но у
        # этого рецепта нет ни url, ни source_dir — распаковывать нечего.
        ensure_dir(self.get_build_dir(arch.arch))

    def build_arch(self, arch):
        src = self.find_game_dir()
        dest = self.ctx.get_python_install_dir(arch.arch)
        ensure_dir(dest)
        for module in GAME_MODULES:
            shutil.copy(join(src, module), join(dest, module))
            info('trigbattle_src: {} -> {}'.format(module, dest))
        # main.py может тянуть за собой ресурсы; копируем и их, если есть.
        for res in ('arialbd.ttf', 'arial.ttf'):
            path = join(src, res)
            if exists(path):
                shutil.copy(path, join(dest, res))
                info('trigbattle_src: {} -> {}'.format(res, dest))
