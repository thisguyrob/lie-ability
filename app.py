import threading
import webbrowser
import tkinter as tk
from flask import Flask, render_template_string

flask_app = Flask(__name__)

MAIN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Main</title>
</head>
<body>
  <h1>HELLO</h1>
</body>
</html>"""

PLAYERS_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Players</title>
</head>
<body>
  <h1>WORLD</h1>
</body>
</html>"""


@flask_app.route("/main/")
def main():
    return render_template_string(MAIN_HTML)


@flask_app.route("/players/")
def players():
    return render_template_string(PLAYERS_HTML)


def on_start():
    webbrowser.open("http://localhost:6767/main/")
    webbrowser.open("http://localhost:6767/players/")


import logging
import os

LAUNCH_MODE = os.environ.get("LAUNCH_MODE", "main")

werkzeug_log = logging.getLogger("werkzeug")
if LAUNCH_MODE == "debug":
    logging.basicConfig(level=logging.DEBUG)
elif LAUNCH_MODE == "dev":
    werkzeug_log.setLevel(logging.INFO)
else:
    werkzeug_log.setLevel(logging.ERROR)

flask_debug = LAUNCH_MODE == "debug"

server_thread = threading.Thread(
    target=lambda: flask_app.run(port=6767, use_reloader=False, debug=flask_debug),
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
