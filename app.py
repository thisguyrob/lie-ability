import logging
import os
import threading
import webbrowser
import tkinter as tk

LAUNCH_MODE = os.environ.get("LAUNCH_MODE", "main")

werkzeug_log = logging.getLogger("werkzeug")
if LAUNCH_MODE == "debug":
    logging.basicConfig(level=logging.DEBUG)
elif LAUNCH_MODE == "dev":
    werkzeug_log.setLevel(logging.INFO)
else:
    werkzeug_log.setLevel(logging.ERROR)

from server import create_app, socketio

flask_app = create_app()


def on_start():
    webbrowser.open("http://localhost:6767/main/")
    webbrowser.open("http://localhost:6767/players/")


server_thread = threading.Thread(
    target=lambda: socketio.run(flask_app, port=6767, use_reloader=False, debug=LAUNCH_MODE == "debug"),
    daemon=True,
)
server_thread.start()

root = tk.Tk()
root.title("Lie-Ability")
root.geometry("300x150")
root.resizable(False, False)

tk.Label(root, text="Server running at localhost:6767", fg="gray").pack(pady=(20, 8))
tk.Button(root, text="START", command=on_start, width=20, height=2).pack()

root.mainloop()
