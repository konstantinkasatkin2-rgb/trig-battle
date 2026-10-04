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
CARS = os.path.join(ROOT, 'ready_apk', 'tools', 'test_cars.py')
CARS = os.path.join(ROOT, 'ready_apk', 'tools', 'test_cars.py')
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
    ('рисуем только одну точку прицела',
     "        if self.state['P2'] is not None:",
     "        if self.state['P2'] is not None and False:",
     'нарисованы не обе точки'),
    ('стреляем всегда по одной и той же точке',
     "        P = self.state[self.shot_sel['p']]",
     "        P = self.state['P1' if who == 'player1' else 'P2']",
     'выстрел по P2 не попал'),
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
     "        btns = list(btns) + [None] * (9 - len(btns))",
     "        btns = list(btns)[:8]",
     'ValueError'),
    ('машинку разрешаем внутри окружности',
     "            if kind == 'car' and d < 1 - 1e-9:",
     '            if False:',
     'машинку можно поставить внутри окружности'),
    ('разрешаем закрыть жёлтый круг',
     "                if d < YELLOW_R - 1e-9:",
     '                if False:',
     'жёлтый круг можно закрыть'),
    ('машинка не разворачивается при таране',
     "            self.car_reverse(un)\n"
     "            # Столкновение раскрывает обе стороны",
     "            # Столкновение раскрывает обе стороны",
     'машинка не развернулась'),
    ('препятствие не теряет клетку от тарана',
     "            self.car_break_wall(*hit)",
     '            pass',
     'препятствие не пострадало'),
    ('машинка едет на две клетки',
     '        return dx * GRID, dy * GRID',
     '        return dx * GRID * 2, dy * GRID * 2',
     'прямой ход неверный'),
    ('касание жёлтого круга не приносит победу',
     '        if self.car_hit_yellow(nxt):',
     '        if False:',
     'партия не закончилась'),
    ('запас ходов не тратится',
     "        un['left'] = max(0, int(un.get('left', CAR_STEPS)) - 1)",
     '        pass',
     'ходы не тратятся'),

    # --- новый режим: видимость, стройка в бою, размер, курс ---
    ('показываем чужие фигуры без столкновения',
     "        if un['fld'] is fld:\n            return True",
     "        if True:\n            return True",
     'чужая стена видна на чужом поле и до столкновения'),
    ('забываем раскрыть стену при таране',
     "            hit[0]['revealed'] = True",
     '            pass',
     'стена осталась невидимой после столкновения'),
    ('разрешаем строить стену в чужой ход',
     '        if not your_turn:',
     '        if False:',
     'в чужой ход стена не ставится'),
    ('разрешаем строить на чужом поле',
     "        my = self.car_my_field()\n        return my is None or fld is my",
     '        return True',
     'правило своего поля не работает'),
    ('не тратим ход на построенную стену',
     "        self.cars_after_change()\n        # ход тратится: дальше играет соперник\n        self.game['turn'] = ('player2' if self.game['turn'] == 'player1'\n                             else 'player1')",
     '        self.cars_after_change()',
     'ход остался у построившего'),
    ('не показываем плавный ход машинки',
     "        un['anim'] = ([tuple(un['pts'][0])], pygame.time.get_ticks())",
     '        pass',
     'после хода анимации нет — движение не видно'),
    ('уменьшаем машинку до прежнего размера',
     'CAR_R = 0.105',
     'CAR_R = 0.042',
     'машинка не увеличена'),
    ('считаем занятость стены по чужому полю',
     "        if not self.car_points_ok([nxt], 'wall', un['fld']['units'],",
     "        if not self.car_points_ok([nxt], 'wall', self.FL['units'],",
     'стены слиплись'),
    ('ломаем адрес фигуры в сетевом ходу',
     "        same = [u for u in un['fld']['units'] if u['type'] == un['type']]",
     "        same = un['fld']['units']",
     'ходы разошлись'),
]


def run_test():
    env = dict(os.environ, PYTHONIOENCODING='utf-8')
    out = ''
    for test in (TEST, PORTRAIT, CARS):
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