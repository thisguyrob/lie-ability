from pathlib import Path
from flask import Blueprint, send_from_directory

bp = Blueprint("views", __name__)

ROOT = Path(__file__).parent.parent
MAIN_DIR = ROOT / "lie-ability-main-view"
PLAYERS_DIR = ROOT / "lie-ability-players-view"


@bp.route("/main/")
@bp.route("/main/<path:filename>")
def main(filename="index.html"):
    return send_from_directory(MAIN_DIR, filename)


@bp.route("/players/")
@bp.route("/players/<path:filename>")
def players(filename="index.html"):
    return send_from_directory(PLAYERS_DIR, filename)
