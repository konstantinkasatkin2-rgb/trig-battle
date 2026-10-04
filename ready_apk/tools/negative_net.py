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
PORTRAIT = os.path.join(ROOT, 'ready_apk', 'tools', 'test_portrait.py')

# (что ломаем, что проверка обязана заметить)
CASES = [
    ('принимаем углы из чужого сообщения',
     "        elif kind == 'angles':\n"
     "            # Углы больше не синхронизируются",
     "        elif kind == 'angles':\n"
     "            self.sliders[0].set(msg.get('a', self.s1), exact=True)\n"
     "            # Углы больше не синхронизируются",
     'переписало наш угол'),
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
    ('показываем точку прицела соперника',
     "return point == ('P1' if self._net_my_turn() == 'player1' else 'P2')",
     "return True",
     'точки определены неверно'),
    ('рисуем обе точки прицела',
     "if self.state['P2'] is not None and self.point_is_mine('P2'):",
     "if self.state['P2'] is not None:",
     'нарисованы чужие точки'),
    ('показываем выбор точки выстрела',
     "self.btn_shot1.visible = not net",
     "self.btn_shot1.visible = True",
     'выбор чужой точки выстрела'),
    # --- книжная ориентация: проверка обязана ловить старое поведение ---
    ('рисуем холст в книжных размерах',
     "self.rotated = win_h > win_w",
     "self.rotated = False",
     'вместо 1920x1080'),
    ('не пересчитываем касание при повороте',
     "        return (self.W - 1 - pos[1], pos[0])",
     "        return pos",
     'вне холста'),
    ('убираем защиту разбора кнопок',
     "        btns = list(btns) + [None] * (8 - len(btns))",
     "        btns = list(btns)[:8]",
     'падение'),
]


def run_test():
    env = dict(os.environ, PYTHONIOENCODING='utf-8')
    out = ''
    for test in (TEST, PORTRAIT):
        p = subprocess.run([sys.executable, test], cwd=ROOT, env=env,
                           capture_output=True, text=True, encoding='utf-8',
                           errors='replace')
        out += p.stdout + p.stderr
    return out


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