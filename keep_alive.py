import logging
import os
import socket
from threading import Thread

from flask import Flask

logger = logging.getLogger("keep_alive")
app = Flask("keep_alive")


@app.route("/")
def index():
    return "OK", 200


def find_available_port(start_port: int, max_attempts: int = 20) -> int:
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("0.0.0.0", port))
                return port
            except OSError:
                continue
    raise OSError("Не удалось найти свободный порт для keep-alive сервера")


def run() -> None:
    port = int(os.getenv("PORT", "8080"))
    try:
        available_port = find_available_port(port)
        if available_port != port:
            logger.warning("Порт %s уже занят; keep-alive сервер запущен на %s", port, available_port)
        app.run(host="0.0.0.0", port=available_port, debug=False, use_reloader=False)
    except OSError as exc:
        if exc.errno in {98, 10048}:
            logger.warning("Порт %s уже занят; keep-alive сервер не запущен.", port)
        else:
            raise


def start() -> None:
    thread = Thread(target=run, daemon=True)
    thread.start()
