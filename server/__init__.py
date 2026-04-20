import threading
from flask import Flask
from flask_socketio import SocketIO

socketio = SocketIO(cors_allowed_origins="*", async_mode="threading")
game_state_lock = threading.Lock()


def create_app():
    app = Flask(__name__, template_folder="../templates", static_folder="../static")

    socketio.init_app(app)

    from .routes import bp as routes_bp
    app.register_blueprint(routes_bp)

    from .views import bp as views_bp
    app.register_blueprint(views_bp)

    from .events import register_events
    register_events(socketio)

    from .db import init_db
    init_db()

    from .timers import start_tick_loop
    start_tick_loop(socketio)

    return app
