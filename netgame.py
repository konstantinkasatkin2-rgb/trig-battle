# -*- coding: utf-8 -*-
"""
Игра по локальной сети: хост + клиент.

Два способа связи, оба работают без интернета и без сервера:

1. **По коду из пяти символов** (например `00AA0`).
   Хост каждые полсекунды рассылает UDP-маячок в локальную сеть:
       `TB1|<код>|<порт>`
   Клиент рассылает запрос и слушает маячки. Увидевший маячок с нужным
   кодом берёт адрес отправителя (это и есть IP хоста) и подключается.
   Пятизначный код, а не IP, потому что адрес на телефоне неудобно вводить
   руками, а код можно продиктовать.

2. **По IP** — для случая, когда в сети запрещён широковещательный трафик
   или устройства соединены напрямую.

Транспорт — TCP, сообщения — JSON по одному в строке. Все операции, способные
заблокировать интерфейс (ожидание соперника, соединение), выполняются в
отдельных потоках: игра опрашивает состояние раз в кадр и не подвисает.

Синхронизация игры держится на двух простых правилах, из-за чего не нужен
сервер-арбитр:

* бой ведёт авторитет хоста: он решает, чей сейчас ход;
* попадание/промах каждый считает у себя по СВОЕМУ флоту и получает
  одинаковый результат, поэтому расхождений быть не может.

Только стандартная библиотека — модуль должен работать на Android.
"""

import json
import os
import queue
import random
import socket
import threading
import time

# Порты по умолчанию. TCP — игра, UDP — маячки и поиск по коду.
DEFAULT_TCP_PORT = 38383
DEFAULT_UDP_PORT = 38384

# Алфавит кода без неоднозначных символов: нет 0/O, 1/I, 2/Z.
CODE_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
CODE_LENGTH = 5

BEACON_PREFIX = 'TB1'
CONNECT_TIMEOUT = 6.0
SEND_TIMEOUT = 4.0
RECV_BUFFER = 8192


class NetError(Exception):
    """Ошибка сети, показываемая игроку как есть."""


def make_code():
    """Случайный пятизначный код вроде `K7P3M`."""
    return ''.join(random.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def normalize_code(text):
    """Приводит ввод кода к верхнему регистру без лишних символов."""
    return ''.join(ch for ch in (text or '').upper() if ch.isalnum())[:CODE_LENGTH]


# Перевод причин отказа сокета: игроку нужны слова, а не «timed out».
_ERROR_TEXT = (
    ('timed out', 'превышено время ожидания'),
    ('Connection refused', 'порт закрыт'),
    ('Network is unreachable', 'сеть недоступна'),
    ('No route to host', 'нет маршрута к узлу'),
    ('Permission denied', 'нет прав доступа'),
    ('Address already in use', 'порт уже занят'),
)


def _ru_error(exc):
    """Человеческое объяснение ошибки сокета."""
    text = str(exc)
    for needle, human in _ERROR_TEXT:
        if needle in text:
            return human
    return text


def local_ip(target='8.8.8.8'):
    """Локальный IP для показания хосту.

    Никогда не отправляет пакет: соединение с UDP-«чёрной дырой» только
    выбирает сетевой интерфейс через маршрут по умолчанию.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.settimeout(0.5)
        sock.connect((target, 80))
        return sock.getsockname()[0]
    except OSError:
        return '127.0.0.1'
    finally:
        sock.close()


class _Peer(object):
    """Общая часть хоста и клиента: сокет, приём в потоке, очередь."""

    def __init__(self, sock, nick):
        self.sock = sock
        self.nick = nick
        self.peer_addr = sock.getpeername()[:2] if sock else None
        self.inbox = queue.Queue()
        self.connected = False
        self.error = None
        self.closed = False
        self._send_lock = threading.Lock()
        self._rx = None

    # ---------------- приём ----------------
    def start_receiving(self):
        self._rx = threading.Thread(target=self._reader, daemon=True)
        self._rx.start()

    def _reader(self):
        buf = b''
        try:
            while not self.closed:
                chunk = self.sock.recv(RECV_BUFFER)
                if not chunk:
                    break
                buf += chunk
                while b'\n' in buf:
                    line, _, buf = buf.partition(b'\n')
                    self._on_line(line)
        except OSError:
            pass
        finally:
            self.connected = False
            self.inbox.put({'t': 'disconnect'})

    def _on_line(self, line):
        line = line.strip()
        if not line:
            return
        try:
            msg = json.loads(line.decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            return
        if isinstance(msg, dict):
            self.inbox.put(msg)

    def poll(self):
        """Забрать накопившиеся сообщения (вызывается каждый кадр)."""
        out = []
        while True:
            try:
                out.append(self.inbox.get_nowait())
            except queue.Empty:
                return out

    # ---------------- отправка ----------------
    def send(self, msg):
        if self.closed or self.sock is None:
            return False
        data = (json.dumps(msg, ensure_ascii=False) + '\n').encode('utf-8')
        try:
            with self._send_lock:
                self.sock.sendall(data)
            return True
        except OSError as e:
            self.error = 'Соединение прервано: %s' % e
            self.connected = False
            return False

    def close(self):
        self.closed = True
        for sock in (self.sock, getattr(self, '_udp', None)):
            if sock is None:
                continue
            try:
                sock.close()
            except OSError:
                pass
        self.sock = None


class HostServer(_Peer):
    """Хост: ждёт соперника, рассылает маячки с кодом."""

    def __init__(self, nick, tcp_port=DEFAULT_TCP_PORT,
                 udp_port=DEFAULT_UDP_PORT, code=None):
        try:
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(('0.0.0.0', tcp_port))
            server.listen(1)
            server.settimeout(0.3)
        except OSError as e:
            raise NetError("Не удалось занять порт %d: %s" % (tcp_port, _ru_error(e)))
        self._server = server
        self.tcp_port = tcp_port
        self.udp_port = udp_port
        self.code = (code or make_code()).upper()
        self.waiting = True
        self._beacon_stop = threading.Event()
        self._udp = None
        super().__init__(None, nick)

    def start_beacon(self):
        """Маячок: код -> IP. Рассылаем во все интерфейсы раз в 0.5 с."""
        try:
            udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            udp.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            udp.bind(('0.0.0.0', self.udp_port))
            self._udp = udp
        except OSError as e:
            raise NetError("Не удалось запустить поиск по коду: %s" % _ru_error(e))

        beacon = ('%s|%s|%d' % (BEACON_PREFIX, self.code, self.tcp_port))
        blob = beacon.encode('ascii')
        targets = [('255.255.255.255', self.udp_port),
                   ('127.0.0.1', self.udp_port)]

        def loop():
            while not self._beacon_stop.is_set() and not self.closed:
                for addr in targets:
                    try:
                        self._udp.sendto(blob, addr)
                    except OSError:
                        pass
                self._beacon_stop.wait(0.5)

        threading.Thread(target=loop, daemon=True).start()

    def try_accept(self):
        """Проверяет, не подключился ли соперник. Вызывается каждый кадр."""
        if not self.waiting:
            return True
        try:
            conn, addr = self._server.accept()
        except (socket.timeout, OSError):
            return False
        conn.settimeout(None)
        self.waiting = False
        self.sock = conn
        self.peer_addr = addr
        self.connected = True
        self.start_receiving()
        self.send({'t': 'hello', 'nick': self.nick, 'code': self.code})
        # Прекращаем маячок: соперник нашёлся, дальше играем по TCP.
        self._beacon_stop.set()
        return True

    def close(self):
        self._beacon_stop.set()
        srv = getattr(self, '_server', None)
        if srv is not None:
            try:
                srv.close()
            except OSError:
                pass
        super().close()


class Client(_Peer):
    """Клиент: подключается по IP или находит хоста по коду."""

    def __init__(self, nick):
        self.status = 'idle'          # idle | searching | connecting | ready
        self.status_text = ''
        self.found_ip = None
        self._stop = threading.Event()
        self._udp = None
        super().__init__(None, nick)

    def connect_ip(self, ip, tcp_port=DEFAULT_TCP_PORT, timeout=CONNECT_TIMEOUT):
        ip = (ip or '').strip()
        if not ip:
            raise NetError('Введите IP-адрес хоста')
        self.status = 'connecting'
        self.status_text = 'Подключение к %s...' % ip
        try:
            sock = socket.create_connection((ip, tcp_port), timeout=timeout)
        except OSError as e:
            self.status = 'idle'
            raise NetError('Не удалось подключиться к %s:%d — %s'
                           % (ip, tcp_port, _ru_error(e)))
        sock.settimeout(None)
        self.sock = sock
        self.connected = True
        self.status = 'ready'
        self.status_text = 'Соединение установлено'
        self.start_receiving()
        self.send({'t': 'hello', 'nick': self.nick})
        return True

    def search_code(self, code, udp_port=DEFAULT_UDP_PORT):
        """Ищет хост по коду в фоне; ход игры не блокируется."""
        code = normalize_code(code)
        if len(code) != CODE_LENGTH:
            raise NetError('Код состоит из %d символов' % CODE_LENGTH)
        self.status = 'searching'
        self.status_text = 'Ищу хост с кодом %s...' % code
        threading.Thread(target=self._search, args=(code, udp_port),
                         daemon=True).start()
        return True

    def _search(self, code, udp_port):
        try:
            udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            udp.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            udp.bind(('0.0.0.0', udp_port))
            udp.settimeout(0.5)
            self._udp = udp
        except OSError as e:
            self.status = 'idle'
            self.status_text = 'Поиск не запустился: %s' % e
            return

        query = ('%s?|%s' % (BEACON_PREFIX, self.nick)).encode('utf-8')
        for addr in (('255.255.255.255', udp_port), ('127.0.0.1', udp_port)):
            try:
                udp.sendto(query, addr)
            except OSError:
                pass

        deadline = time.time() + 45.0
        while not self._stop.is_set() and time.time() < deadline:
            try:
                data, addr = udp.recvfrom(RECV_BUFFER)
            except socket.timeout:
                # повторяем запрос: маячок мог пройти мимо
                try:
                    udp.sendto(query, ('255.255.255.255', udp_port))
                except OSError:
                    pass
                continue
            except OSError:
                break
            parts = data.decode('utf-8', 'replace').split('|')
            if len(parts) != 3 or parts[0] != BEACON_PREFIX:
                continue
            if normalize_code(parts[1]) != code:
                continue
            host_ip = addr[0]
            port = int(parts[2] or DEFAULT_TCP_PORT)
            self.found_ip = host_ip
            self.status_text = 'Нашёл хост %s, подключаюсь...' % host_ip
            try:
                sock = socket.create_connection((host_ip, port),
                                                timeout=CONNECT_TIMEOUT)
            except OSError as e:
                self.status_text = 'Хост не ответил: %s' % e
                continue
            sock.settimeout(None)
            self.sock = sock
            self.connected = True
            self.status = 'ready'
            self.status_text = 'Соединение с %s' % host_ip
            self.start_receiving()
            self.send({'t': 'hello', 'nick': self.nick})
            return
        if self.status == 'searching':
            self.status_text = 'Хост с кодом %s не найден. Проверьте, что ' \
                               'оба устройства в одной сети' % code

    def cancel_search(self):
        self._stop.set()
        udp = self._udp
        self._udp = None
        if udp is not None:
            try:
                udp.close()
            except OSError:
                pass
        if self.status == 'searching':
            self.status = 'idle'
            self.status_text = 'Поиск отменён'

    def close(self):
        self._stop.set()
        super().close()


# ---------------- формат флота ----------------
# Юнит в игре — это словарь с полями type/size/dir/pts/hits/fld/visible.
# По сети передаём всё, кроме fld (это ссылка на локальное поле) и hits
# (отметки о попаданиях считаются у каждого свои). Раньше передавались
# только точки, и принимающая сторона падала с KeyError: 'type' на
# отрисовке чужого флота.
def encode_fleet(units):
    """Флот -> список [тип, размер, направление, [[x, y], ...]]."""
    out = []
    for un in units:
        out.append([str(un.get('type', 'ship')),
                    int(un.get('size', len(un.get('pts', [])))),
                    int(un.get('dir', 0)),
                    [[round(float(p[0]), 6), round(float(p[1]), 6)]
                     for p in un.get('pts', [])]])
    return out


def decode_fleet(payload):
    """Обратное преобразование.

    Возвращает готовые юниты; поле `fld` проставляет принимающая сторона
    (указатель на её собственное поле соперника).
    """
    units = []
    for item in payload or []:
        try:
            utype, size, dir_idx, pts = item
        except (TypeError, ValueError):
            continue
        points = [(float(p[0]), float(p[1])) for p in pts]
        if not points:
            continue
        units.append({'type': str(utype),
                      'size': int(size) or len(points),
                      'dir': int(dir_idx),
                      'pts': points,
                      'hits': set(),
                      'visible': True,
                      'fld': None})
    return units


if __name__ == '__main__':
    print('код примера:', make_code())
    print('локальный IP:', local_ip())
