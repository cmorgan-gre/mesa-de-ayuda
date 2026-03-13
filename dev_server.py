from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import subprocess
import time
import os

process = None

def start_server():
    global process
    if process:
        process.kill()
    print("Reiniciando servidor...")
    process = subprocess.Popen(["python", "app.py"])

class ChangeHandler(FileSystemEventHandler):
    def on_any_event(self, event):
        if event.src_path.endswith((".py", ".html", ".css", ".js")):
            start_server()

if __name__ == "__main__":
    start_server()

    event_handler = ChangeHandler()
    observer = Observer()
    observer.schedule(event_handler, ".", recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()

    observer.join()