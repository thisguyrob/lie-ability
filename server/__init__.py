import threading
from flask import Flask
from flask_socketio import SocketIO

socketio = SocketIO(cors_allowed_origins="*", async_mode="threading")
game_state_lock = threading.Lock()

_initialized = False


def create_app():
    global _initialized
    app = Flask(__name__, template_folder="../templates", static_folder="../static")

    if not _initialized:
        _initialized = True
        socketio.init_app(app)

        from .events import register_events
        register_events(socketio)

        from .timers import start_tick_loop
        start_tick_loop(socketio)
    else:
        # Second call (e.g. from test_game_flow's app fixture): bind the new
        # Flask app to the already-running SocketIO server without replacing it.
        app.extensions['socketio'] = socketio

    from .routes import bp as routes_bp
    app.register_blueprint(routes_bp)

    from .views import bp as views_bp
    app.register_blueprint(views_bp)

    from .db import init_db
    init_db()

    return app
