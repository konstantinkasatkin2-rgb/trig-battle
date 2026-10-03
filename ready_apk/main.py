# -*- coding: utf-8 -*-
"""
Точка входа APK: buildozer требует, чтобы скрипт назывался `main.py` и лежал
в корне `source.dir`. Вся игра — в `trig_battle_pygame.py` рядом.

Запуск из исходников на ПК:
    python main.py
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from trig_battle_pygame import main   # noqa: E402

if __name__ == '__main__':
    main()