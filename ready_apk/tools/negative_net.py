# -*- coding: utf-8 -*-
"""Обратный контроль: проверки test_netgame обязаны падать на СТАРОМ коде.

Идея: временно возвращаем старую логику (чужой угол принимался любой,
правило видимости по сети убрано) и смотрим, что тесты это замечают.
Если проверки молчат — они ничего не проверяют.

Запуск:  python ready_apk/tools/negative_net.py
"""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
GAME = os.path.join(ROOT, 'trig_battle_pygame.py')
TEST = os.path.join(ROOT, 'ready_apk', 'tools', 'test_netgame.py')

# (что ломаем, что проверка обязана заметить)
CASES = [
    ('принимаем угол соперника в любой ползунок',
     "if slot not in (1, 2) or slot == self.net_my_angle():",
     "if slot not in (1, 2):",
     'переписало наш угол'),
    ('разрешаем двигать чужой угол',
     "if self.net_active() and self.net_my_angle() != 1:",
     "if False and self.net_active():",
     'сдвинул чужой угол'),
    ('убираем правило: по сети видно только своё поле',
     "if self.game['mode'] == 'net':\n"
     "            # по сети у каждого одно своё поле",
     "if self.game['mode'] == 'zzz-net':\n"
     "            # по сети у каждого одно своё поле",
     'виден флот соперника'),
    ('показываем флот соперника целиком',
     "            return fld is self.FL\n"
     "        if self.game['phase'] == 'place1':",
     "            return True\n"
     "        if self.game['phase'] == 'place1':",
     'виден флот соперника'),
    ('не прячем элементы управления соперника',
     "                w.visible = not net or i == mine",
     "                w.visible = True",
     'ползунки углов видны неверно'),
    ('прячем и свои элементы управления',
     "                w.visible = not net or i == mine",
     "                w.visible = False",
     'ползунки углов видны неверно'),
]


def run_test():
    env = dict(os.environ, PYTHONIOENCODING='utf-8')
    p = subprocess.run([sys.executable, TEST], cwd=ROOT, env=env,
                       capture_output=True, text=True, encoding='utf-8',
                       errors='replace')
    return p.stdout + p.stderr


def read_source():
    """-> (текст с LF, использовать CRLF при записи)."""
    with open(GAME, 'rb') as fd:
        raw = fd.read()
    return raw.decode('utf-8').replace('\r\n', '\n'), b'\r\n' in raw


def write_source(text, crlf):
    data = text.replace('\n', '\r\n') if crlf else text
    with open(GAME, 'wb') as fd:
        fd.write(data.encode('utf-8'))


def main():
    original, crlf = read_source()
    print('исходный код сохранён, начнём ломать')
    bad = 0
    try:
        for name, was, now, expect in CASES:
            if was not in original:
                print('  ПРОПУСК  %s: не нашёл фрагмент кода' % name)
                bad += 1
                continue
            write_source(original.replace(was, now, 1), crlf)
            out = run_test()
            caught = expect in out
            print('  %s  %s' % ('ОТЛОВИЛ ' if caught else 'НЕ ЗАМЕТИЛ',
                                name))
            if not caught:
                bad += 1
                for line in out.splitlines():
                    if 'ОШИБКА' in line:
                        print('        ' + line.strip()[:90])
    finally:
        write_source(original, crlf)
    if bad:
        print('\nИТОГ: %d проверок оказались бесполезными' % bad)
        return 1
    print('\nИТОГ: все проверки ловят старый код. Исходник восстановлен.')
    return 0


if __name__ == '__main__':
    sys.exit(main())