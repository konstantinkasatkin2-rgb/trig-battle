# -*- coding: utf-8 -*-
"""
Точка входа для сборки APK (buildozer) версии на pygame.

Buildozer требует, чтобы скрипт назывался `main.py` и лежал в корне
`source.dir`. Сама игра — в `trig_battle_pygame.py` рядом с этим файлом
(на уровень выше), этот файл только запускает её.

Сборка:
    buildozer -c android-pygame/buildozer.spec android debug
APK появится в android-pygame/bin/
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_HERE)
if _PARENT not in sys.path:      # запуск из исходников (на ПК)
    sys.path.insert(0, _PARENT)

from trig_battle_pygame import main   # noqa: E402

if __name__ == '__main__':
    main()