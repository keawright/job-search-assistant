"""Scheduled entry point: hidden window, private logs, no credentials in task args."""
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime
from pathlib import Path
import os
import traceback

from job_search_assistant.searching.engine import run_search

if __name__=='__main__':
    root=Path(__file__).resolve().parent.parent
    logs=root/'.job-search-assistant-private/search/logs'; logs.mkdir(parents=True,exist_ok=True)
    os.chdir(root)
    with (logs/f'morning-{datetime.now():%Y%m%d-%H%M%S-%f}.log').open('x',encoding='utf-8') as log:
        with redirect_stdout(log), redirect_stderr(log):
            try: run_search(root,max_assessments=20)
            except Exception:
                traceback.print_exc()
                raise SystemExit(1)
