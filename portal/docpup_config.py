"""Shared Doc Pup policy: server validated, delivered to both portal roles."""
DEFAULTS={'enabled':True,'auto_read':True,'auto_asr':True,'max_file_mb':20,'clarify_rounds':2,'file_rounds':2,'mic_seconds':20}
RANGES={'max_file_mb':(1,100),'clarify_rounds':(0,5),'file_rounds':(0,5),'mic_seconds':(5,120)}

def current(options=None):
    if options is None:
        from .models import SiteOptions
        options=SiteOptions.objects.filter(pk=1).first()
    saved=getattr(options,'docpup',{}) or {}
    result=dict(DEFAULTS)
    for key,value in saved.items():
        if key in RANGES and type(value) is int and RANGES[key][0]<=value<=RANGES[key][1]:result[key]=value
        elif key in ('enabled','auto_read','auto_asr') and type(value) is bool:result[key]=value
    return result

def parse(post):
    values={k:post.get(k)=='on' for k in ('enabled','auto_read','auto_asr')}
    for key,(low,high) in RANGES.items():
        raw=str(post.get(key,''))
        if not raw.isascii() or not raw.isdecimal():raise ValueError(key)
        value=int(raw)
        if not low<=value<=high:raise ValueError(key)
        values[key]=value
    return values
