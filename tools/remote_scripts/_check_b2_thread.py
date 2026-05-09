import threading
import torch
import datetime as dt
print(f'now_utc={dt.datetime.now(dt.timezone.utc).isoformat()}')
print(f'active_threads={threading.active_count()}')
for t in threading.enumerate():
    print(f'  {t.name}  alive={t.is_alive()}  daemon={t.daemon}')
print(f'VRAM_MB={torch.cuda.memory_allocated()//(1024*1024) if torch.cuda.is_available() else 0}')
b2t = None
for t in threading.enumerate():
    if t.name == 'b2-smoke10-bg':
        b2t = t
        break
print(f'b2 thread alive: {b2t.is_alive() if b2t else "NOT FOUND"}')
