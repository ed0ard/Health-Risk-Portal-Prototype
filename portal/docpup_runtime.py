"""Public model metadata caching only; no prompts, audio or participant data cached here."""
import json
import os
import threading
import time
from pathlib import Path
from functools import lru_cache
from django.conf import settings

DEFAULT_MODEL = 'spark-x2.6:4b-q8_0'
MODEL_REPO = 'XHToken/Spark-X2.6-4B-GGUF'
MODEL_REVISION = '9d716770ac7477776de5f891f70cdf98b003a5cd'
MODEL_FILE = 'Spark-X2.6-4B-Q8_0.gguf'
MODEL_SHA256 = '145c2aa606820663f26ad530b8fc141ed885e2e9ca29f9be7c3bfe8931d58b81'
TOKENIZER_REPO = 'XHToken/Spark-X2.6-4B'
TOKENIZER_REVISION = '64ca8f2a295b8ceb2757b9d4749a6558c4759e5b'
OUTPUT_TOKENS = 700
BRIEF_SCHEMA = {'type':'object','properties':{'text':{'type':'string'}},'required':['text'],'additionalProperties':False}

def model_name():
    return os.environ.get('DOCPUP_MODEL', DEFAULT_MODEL)

def tokenizer_path(root=None):
    return Path(os.environ.get('DOCPUP_TOKENIZER', str(Path(root or settings.BASE_DIR)/'data/docpup/spark/tokenizer.json')))

_voices=None
_voices_until=0
_voice_lock=threading.Lock()

def voice_catalog():
    """Cache public voice names, not synthesized speech or submitted text."""
    global _voices,_voices_until
    with _voice_lock:
        if time.monotonic()<_voices_until:return _voices
        try:
            import asyncio,edge_tts
            async def fetch():return await asyncio.wait_for(edge_tts.list_voices(),timeout=4)
            _voices=[v['ShortName'] for v in asyncio.run(fetch())]
            _voices_until=time.monotonic()+3600
        except Exception:
            _voices=None;_voices_until=time.monotonic()+30
        return _voices

@lru_cache(maxsize=2)
def tokenizer(path):
    from tokenizers import Tokenizer
    return Tokenizer.from_file(path)

def tokens(text):
    path=tokenizer_path()
    if path.is_file():return len(tokenizer(str(path)).encode(text,add_special_tokens=False).ids)
    # A byte-count upper bound keeps installations without tokenizer metadata safe.
    return len(text.encode('utf-8'))

def context_size():
    import psutil
    return 8192 if psutil.virtual_memory().total>=14*2**30 else 4096

def fits(prompt,payload,event):
    content=json.dumps(payload,ensure_ascii=False,default=str,separators=(',',':'))
    schema=json.dumps(getattr(event,'output_schema',BRIEF_SCHEMA),ensure_ascii=False)
    # Only the invariant prompt/schema count is reused, scoped to this operation.
    key=(prompt,schema)
    if getattr(event,'token_budget_key',None)!=key:
        event.token_budget_key=key
        event.token_budget_overhead=tokens(prompt)+tokens(schema)+256+OUTPUT_TOKENS
    return tokens(content)+event.token_budget_overhead<=context_size()
