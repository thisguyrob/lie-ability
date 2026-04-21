import socket

from flask import Blueprint, render_template

bp = Blueprint("views", __name__)


def _local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "localhost"


@bp.route("/main/")
def main():
    return render_template("main/index.html", local_ip=_local_ip())


@bp.route("/player/")
@bp.route("/players/")
def players():
    return render_template("player/index.html")


@bp.route("/preview/")
def preview():
    return render_template("preview/index.html")
