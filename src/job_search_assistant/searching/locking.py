"""OS-released lock prevents overlapping manual and scheduled search runs."""
from contextlib import contextmanager
import os


@contextmanager
def run_lock(path):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a+b') as stream:
        stream.write(b'0'); stream.flush(); stream.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            raise ValueError('Another search is running; wait for it to finish') from None
        try: yield
        finally:
            stream.seek(0)
            if os.name=='nt': msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
            else: fcntl.flock(stream,fcntl.LOCK_UN)
