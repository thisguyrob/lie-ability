from flask import Blueprint, render_template

bp = Blueprint("views", __name__)


@bp.route("/main/")
def main():
    return render_template("main.html")


@bp.route("/player/")
@bp.route("/players/")
def players():
    return render_template("player.html")
