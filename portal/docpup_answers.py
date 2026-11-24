"""Typed form extraction. Missing information is never equivalent to a negative answer."""
import math
import re
import unicodedata
from datetime import date
from .catalog import FIELDS

OUTPUT_SCHEMA = {'type':'object','properties':{
    'answers':{'type':'array','items':{'type':'object','properties':{
        'key':{'type':'string'},'status':{'type':'string','enum':['answered','not_given','uncertain']},
        'value':{'type':['number','string','boolean','array','null'],'items':{'type':'string'}},
        'confidence':{'type':'number'},'evidence':{'type':'string'}},
        'required':['key','status','value','confidence','evidence'],'additionalProperties':False}},
    'question':{'type':'string'}},'required':['answers','question'],'additionalProperties':False}
UNKNOWN = re.compile(r'not\s+(?:given|provided|stated|specified|known|available)|unknown|unspecified|未(?:提供|说明|知|给出|填写)|不(?:知道|清楚|详)|无资料|缺失',re.I)

def normal(value):
    return re.sub(r'[\s，,。.!！?？:：;；"“”\-–—]+','',unicodedata.normalize('NFKC',str(value))).casefold()

def descriptors(kind, keys, extras=(), lang='en'):
    fields={f.key:{'key':f.key,'question':f.zh if lang=='zh' else f.en,
        'type':'choice' if f.choices else 'number','min':f.lo,'max':f.hi,'step':f.step,
        'options':[{'value':str(i),'label':pair[lang=='zh'],'aliases':list(pair)} for i,pair in enumerate(f.choices)]}
        for f in FIELDS[kind]}
    # Additional UI fields are suggestions only; this API never saves them to the database.
    for item in extras[:80]:
        key=str(item.get('key',''))
        if key in fields or not re.fullmatch(r'[\w-]{1,100}',key) or re.search('password|csrf|token|secret',key,re.I):continue
        typ=item.get('type')
        if typ not in {'text','number','choice','boolean','multichoice','date'}:continue
        fields[key]={'key':key,'question':str(item.get('question',''))[:300],'type':typ,
                     'min':item.get('min'),'max':item.get('max'),'step':item.get('step','any'),
                     'options':[{'value':str(o.get('value',''))[:120],'label':str(o.get('label',''))[:200]} for o in item.get('options',[])[:40]]}
    return [fields[key] for key in keys if key in fields]

def normalized_value(field, value):
    typ=field['type']
    if typ=='date':
        value=date.fromisoformat(str(value)).isoformat()
        if field.get('min') and value<field['min']:raise ValueError()
        if field.get('max') and value>field['max']:raise ValueError()
        return value
    if typ=='text':
        if not isinstance(value,str) or UNKNOWN.search(value):raise ValueError()
        return re.sub(r'[*#`]+','',value).strip()[:400]
    if typ in {'choice','boolean','multichoice'}:
        def option(v):
            for o in field['options']:
                if str(v)==o['value'] or normal(v) in [normal(x) for x in [o['label'],*o.get('aliases',[])]]:return o['value']
            if typ=='boolean' and isinstance(v,bool):return 'true' if v else 'false'
            raise ValueError()
        return [option(v) for v in value] if typ=='multichoice' and isinstance(value,list) else option(value)
    value=float(quantity(field,value) if isinstance(value,str) else value)
    if not math.isfinite(value):raise ValueError()
    if field.get('min') is not None and value<float(field['min']):raise ValueError()
    if field.get('max') is not None and value>float(field['max']):raise ValueError()
    if str(field.get('step'))=='1' and not value.is_integer():raise ValueError()
    return int(value) if value.is_integer() else value

def validated(schema, result, source):
    fields={f['key']:f for f in schema};valid=[]
    source_normal = normal(source)
    source_lines = [(normal(line), bool(UNKNOWN.search(line))) for line in re.split(r'[\n。;；]',source)]
    catalog_keys = {f.key for group in FIELDS.values() for f in group}
    if not isinstance(result,dict) or not isinstance(result.get('answers',[]),list):return valid
    for item in result.get('answers',[]):
        if not isinstance(item,dict) or not isinstance(item.get('key'),str):continue
        field=fields.get(item.get('key'))
        if not field or item.get('status','answered')!='answered':continue
        try:
            evidence=str(item.get('evidence','')).strip();confidence=float(item.get('confidence',0))
            quote = normal(evidence)
            if not quote or UNKNOWN.search(evidence) or quote not in source_normal:continue
            if not math.isfinite(confidence) or not (.75 if field['type']=='text' else .70)<=confidence<=1:continue
            # Reject a quote lifted from a line explicitly marking that answer as missing.
            lines=[missing for line,missing in source_lines if quote in line]
            if lines and all(lines):continue
            value=normalized_value(field,item.get('value'))
            if value=='':continue
            if field['key'] in catalog_keys and field['type']=='choice':value=int(value)
            valid.append({'key':field['key'],'value':value})
        except (ValueError,TypeError,OverflowError):continue
    return valid

def spoken_number(text):
    """Parse spoken quantities, including colloquial 'one eighty', without guessing units."""
    text=str(text).lower().strip().rstrip('。.!！')
    text=re.sub(r'^(?:it(?: is|\'s)|i am|i\'m|my (?:height|weight) is|about|approximately)\s+','',text)
    text=re.sub(r'\s*(?:mmhg|毫米汞柱|岁|years? old)\s*$','',text).strip()
    try:return float(text)
    except ValueError:pass
    digits=dict(zip('zero one two three four five six seven eight nine'.split(),range(10)));digits['oh']=0
    small={**digits,**dict(zip('ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen'.split(),range(10,20)))}
    tens=dict(zip('twenty thirty forty fifty sixty seventy eighty ninety'.split(),range(20,100,10)))
    tokens=text.replace('-',' ').replace(',',' ').split();tokens=[t for t in tokens if t!='and']
    if not tokens:raise ValueError()
    chinese_digits={c:i for i,c in enumerate('零一二三四五六七八九')};chinese_digits.update({'〇':0,'两':2})
    if all(c in chinese_digits for c in text):return int(''.join(str(chinese_digits[c]) for c in text))
    if re.fullmatch(r'[零〇一二两三四五六七八九十百千点]+',text):
        shorthand=re.fullmatch(r'([一二两三四五六七八九])(百|千)([一二两三四五六七八九])',text)
        if shorthand:
            scale=100 if shorthand[2]=='百' else 1000
            return chinese_digits[shorthand[1]]*scale+chinese_digits[shorthand[3]]*(scale//10)
        if '点' in text:
            whole,tail=text.split('点',1)
            if not tail or not all(c in chinese_digits for c in tail):raise ValueError()
            return spoken_number(whole)+float('0.'+''.join(str(chinese_digits[c]) for c in tail))
        total=digit=0
        for c in text:
            if c in chinese_digits:digit=chinese_digits[c]
            else:total+=(digit or 1)*{'十':10,'百':100,'千':1000}[c];digit=0
        return total+digit
    if 'point' in tokens:
        index=tokens.index('point');tail=tokens[index+1:]
        if not tail or not all(t in digits for t in tail):raise ValueError()
        return spoken_number(' '.join(tokens[:index]))+float('0.'+''.join(str(digits[t]) for t in tail))
    if len(tokens)>1 and all(t in digits for t in tokens):return int(''.join(str(digits[t]) for t in tokens))
    if len(tokens)>=2 and tokens[0] in digits and tokens[1] in tens:
        return digits[tokens[0]]*100+spoken_number(' '.join(tokens[1:]))
    # Repeated tens or unrelated prose is ambiguous; let semantic interpretation handle it.
    if sum(t in tens for t in tokens)>1 and not any(t in ('hundred','thousand') for t in tokens):raise ValueError()
    for left,right in zip(tokens,tokens[1:]):
        if left in tens and right in small and small[right]>=10:raise ValueError()
        if left in small and right in small:raise ValueError()
    total=part=0
    for token in tokens:
        if token in small:part+=small[token]
        elif token in tens:part+=tens[token]
        elif token=='hundred':part=max(1,part)*100
        elif token=='thousand':total+=max(1,part)*1000;part=0
        else:raise ValueError()
    return total+part

def quantity(field, source):
    text=str(source).strip().rstrip('。.!！')
    key=field['key']
    units={
        'height':[(r'(?:centimet(?:er|re)s?|cm|厘米)',1),(r'(?:met(?:er|re)s?|米)',100),(r'(?:inches|inch|英寸)',2.54),(r'(?:feet|foot|英尺)',30.48)],
        'weight':[(r'(?:kilograms?|kilos?|kg|公斤|千克)',1),(r'(?:pounds?|lbs?|磅)',.45359237),(r'(?:斤)',.5)],
    }
    if key=='height':
        compact=re.fullmatch(r'(.+?)\s*(?:米|m)\s*([零〇一二三四五六七八九0-9]{1,2})',text,re.I)
        if compact:return spoken_number(compact[1])*100+spoken_number(compact[2])*(10 if len(compact[2])==1 else 1)
        match=re.fullmatch(r'(.+?)\s*(?:feet|foot|英尺)\s*(.+?)\s*(?:inches|inch|英寸)',text,re.I)
        if match:return round(spoken_number(match[1])*30.48+spoken_number(match[2])*2.54,3)
    for pattern,factor in units.get(key,[]):
        match=re.fullmatch(r'(.+?)\s*'+pattern,text,re.I)
        if match:return round(spoken_number(match[1])*factor,3)
    return spoken_number(text)

def direct_answer(schema, source):
    """Unambiguous single-question voice answers need no probabilistic conversion."""
    if len(schema)!=1 or UNKNOWN.search(source):return []
    field=schema[0];text=source.strip().rstrip('。.!！')
    try:
        if field['type']=='number':
            value=normalized_value(field,quantity(field,text))
        elif field['type']=='date':
            value=normalized_value(field,text)
        else:
            if field['key']=='subject' and re.fullmatch(r'[\w.@+-]{1,150}',text):return [{'key':'subject','value':text}]
            if normal(text) in {'yes','是','有','true','正确','对'}:text='Yes' if field['type']!='boolean' else True
            elif normal(text) in {'no','否','没有','false','错误','错'}:text='No' if field['type']!='boolean' else False
            value=normalized_value(field,text)
            if field['type']=='text':return []
        return [{'key':field['key'],'value':value}]
    except (ValueError,TypeError):return []
