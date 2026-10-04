# -*- coding: utf-8 -*-
"""
setup.py для сборки APK.

Зачем он нужен: buildozer передаёт python-for-android `--ignore-setup-py`,
если опция `p4a.setup_py` не выставлена. А p4a кладёт файлы проекта в
APK ТОЛЬКО через setup.py (никакого копирования «по шаблонам» в этой
версии нет). Без setup.py в бандл попадает Python с pygame, но без
main.py — приложение стартует и мгновенно закрывается.

Поэтому: setup.py + в buildozer.spec -> `p4a.setup_py = True`.
"""

from setuptools import setup

setup(
    name='trigbattle',
    version='0.2.3',
    description='Тригонометрический морской бой (pygame)',
    # игра и её точка входа — обычные модули верхнего уровня
    py_modules=['main', 'trig_battle_pygame'],
    # зависимости НЕ указываем: pygame ставится рецептом python-for-android,
    # а pip-установка внутри сборки требует компиляции
    install_requires=[],
)