"""Public model metadata caching only; no prompts, audio or participant data cached here."""
import json
import threading
import time
from pathlib import Path
from functools import lru_cache
from django.conf import settings

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
    path=Path(settings.BASE_DIR)/'data/docpup/qwen-tokenizer/tokenizer.json'
    if path.is_file():return len(tokenizer(str(path)).encode(text,add_special_tokens=False).ids)
    # A byte-count upper bound keeps installations without tokenizer metadata safe.
    return len(text.encode('utf-8'))

def context_size():
    import psutil
    return 4096 if psutil.virtual_memory().total>=14*2**30 else 2048

def fits(prompt,payload,event):
    content=json.dumps(payload,ensure_ascii=False,default=str,separators=(',',':'))
    schema=json.dumps(getattr(event,'output_schema','json'),ensure_ascii=False)
    # Only the invariant prompt/schema count is reused, scoped to this operation.
    key=(prompt,schema)
    if getattr(event,'token_budget_key',None)!=key:
        event.token_budget_key=key
        event.token_budget_overhead=tokens(prompt)+tokens(schema)+256+700
    return tokens(content)+event.token_budget_overhead<=context_size()
