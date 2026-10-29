"""Owned short-lived metadata target; newline/EOF or 30 s ends it normally."""
import json
import os
import sys
import threading

stop=threading.Event()
worker=threading.Thread(target=lambda:stop.wait(30))
worker.start()
def read_stop():
    sys.stdin.readline()
    stop.set()
threading.Thread(target=read_stop,daemon=True).start()
print(json.dumps(dict(pid=os.getpid(),worker_tid=worker.native_id)),flush=True)
stop.wait(30)
stop.set()
worker.join(2)
