"""Cancellable Edge TTS worker, with an offline Windows SAPI fallback."""
import asyncio
import json
import sys
from pathlib import Path


async def online_speech(text, lang, output, available=None):
    import edge_tts
    voices = ['zh-CN-XiaoshuangNeural','zh-CN-XiaoyiNeural'] if lang=='zh' else ['en-US-AnaNeural']
    try:
        if available is None:available = {v['ShortName'] for v in await asyncio.wait_for(edge_tts.list_voices(),timeout=4)}
        voices = [voice for voice in voices if voice in available]
    except Exception:
        pass  # A failed catalogue lookup must not prevent a direct synthesis attempt.
    mp3 = output.with_suffix('.mp3')
    for voice in voices:
        try:
            await asyncio.wait_for(edge_tts.Communicate(text,voice,connect_timeout=6,receive_timeout=12).save(str(mp3)),timeout=16)
            if mp3.stat().st_size > 0:
                return True
        except Exception:
            pass
        mp3.unlink(missing_ok=True)
    return False


def local_speech(text, lang, output):
    import pyttsx3
    engine = pyttsx3.init('sapi5')
    voices = engine.getProperty('voices')
    matches = [v for v in voices if
               (('ZH-' in v.id.upper() or 'Chinese' in v.name or 'Huihui' in v.name)
                if lang=='zh' else ('EN-' in v.id.upper() or 'English' in v.name))]
    if not matches:
        raise RuntimeError('Install an offline voice for the selected language')
    engine.setProperty('voice',matches[0].id)
    engine.setProperty('rate',175)
    engine.save_to_file(text,str(output))
    engine.runAndWait()

def synthesize(text, lang, output, available=None):
    try:
        success=asyncio.run(online_speech(text,lang,output,available))
    except Exception:
        success=False
    if not success:
        local_speech(text,lang,output)


if __name__ == '__main__':
    with open(sys.argv[1],encoding='utf-8') as source:
        data = json.load(source)
    synthesize(data['text'],data['lang'],Path(sys.argv[2]),data.get('voices'))
