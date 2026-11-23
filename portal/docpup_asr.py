"""Cancellable, offline ASR worker. Its output lives in a task temporary directory."""
import os
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django
django.setup()
from portal.docpup import transcribe

if __name__=='__main__':
    Path(sys.argv[3]).write_text(transcribe(sys.argv[1],sys.argv[2],max_seconds=int(sys.argv[4]) if len(sys.argv)>4 else 600),encoding='utf-8')
