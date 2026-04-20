from __future__ import annotations

from flask_socketio import emit

from server import game_state_lock, socketio
from server.game import active_players, get_game, sanitize_state


def register_events(sio) -> None:

    @sio.on("connect")
    def on_connect():
        game = get_game()
        emit("game_state", sanitize_state(game))

    @sio.on("disconnect")
    def on_disconnect():
        game = get_game()
        # Identify player by their stored sid — clients must emit "identify"
        # after connecting so we know which UUID maps to this socket.
        # Until then, disconnection is a no-op.
        pass

    @sio.on("identify")
    def on_identify(data):
        player_id = (data or {}).get("player_id", "")
        game = get_game()
        with game_state_lock:
            player = game.players.get(player_id)
            if not player:
                return
            player.connected = True
        emit("game_state", sanitize_state(game), broadcast=True)

    @sio.on("player_disconnect")
    def on_player_disconnect(data):
        player_id = (data or {}).get("player_id", "")
        game = get_game()
        with game_state_lock:
            player = game.players.get(player_id)
            if not player:
                return
            player.connected = False

            # If active picker went MIA during category_pick, auto-pick
            if game.phase == "category_pick":
                from server.game import current_picker
                picker = current_picker(game)
                if picker and picker.player_id == player_id:
                    from server.db import get_categories
                    import random
                    cats = get_categories(game.included_groups)
                    if cats:
                        chosen = random.choice(cats)
                        from server.routes import _do_setup_turn
                        _do_setup_turn(game, chosen["id"], chosen["name"])

        socketio.emit("game_state", sanitize_state(game))
