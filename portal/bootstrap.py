"""One startup pipeline: required models, local services, database and portal."""
import argparse,hashlib,json,os,subprocess,sys,time,zipfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import requests
from .docpup_runtime import (DEFAULT_MODEL, MODEL_REPO, MODEL_REVISION, MODEL_FILE, MODEL_SHA256,
    TOKENIZER_REPO, TOKENIZER_REVISION, model_name, tokenizer_path)

ROOT=Path(__file__).resolve().parents[1]
SERVICE='http://127.0.0.1:11434'

def sha256(path):
    digest=hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()


def download_spark():
    root=ROOT/'data/docpup/spark'
    root.mkdir(parents=True,exist_ok=True)
    name=MODEL_FILE
    meta=requests.get(f'https://huggingface.co/api/models/{MODEL_REPO}/tree/{MODEL_REVISION}',timeout=30)
    meta.raise_for_status()
    entry=next(x for x in meta.json() if x['path']==name)
    size=entry['size']; expected=MODEL_SHA256
    if entry['lfs']['oid']!=expected:raise RuntimeError('Unexpected model hash in repository metadata')
    destination=root/name
    parts=root/'parts';parts.mkdir(exist_ok=True)
    block=16*1024*1024
    def part(index):
        start=index*block;end=min(size,start+block)-1
        path=parts/str(index)
        if path.exists() and path.stat().st_size==end-start+1:return path
        for attempt in range(8):
            try:
                offset=path.stat().st_size if path.exists() else 0
                if offset==end-start+1:return path
                resume=start+offset
                url=f'https://huggingface.co/{MODEL_REPO}/resolve/{MODEL_REVISION}/{name}?part={index}'
                with requests.get(url+f'&offset={offset}',headers={'Range':f'bytes={resume}-{end}'},stream=True,timeout=(20,60)) as response:
                    response.raise_for_status()
                    if response.status_code!=206 or not response.headers.get('Content-Range','').startswith(f'bytes {resume}-{end}/'):
                        raise ValueError('Invalid range response')
                    with path.open('ab') as output:
                        for chunk in response.iter_content(1024*1024):output.write(chunk)
                if path.stat().st_size!=end-start+1:raise ValueError('Incomplete range')
                return path
            except Exception:
                if attempt==7:raise
                time.sleep(min(10,attempt+1))
    count=(size+block-1)//block
    with ThreadPoolExecutor(max_workers=8) as pool:
        for n,future in enumerate(as_completed([pool.submit(part,i) for i in range(count)]),1):
            future.result()
            if n%10==0 or n==count:print(f'{n}/{count} chunks',flush=True)
    digest=hashlib.sha256()
    temporary=root/(name+'.partial')
    with temporary.open('wb') as output:
        for index in range(count):
            with (parts/str(index)).open('rb') as source:
                while chunk:=source.read(1024*1024):output.write(chunk);digest.update(chunk)
    if digest.hexdigest()!=expected:raise ValueError('SHA256 mismatch')
    temporary.replace(destination)
    for index in range(count):(parts/str(index)).unlink()
    parts.rmdir()
    print('Model downloaded and SHA-256 verified.',flush=True)


def service_ready():
    try:return requests.get(SERVICE+'/api/version',timeout=2).ok
    except requests.RequestException:return False

def download_runtime(archive):
    url='https://github.com/ollama/ollama/releases/latest/download/ollama-windows-amd64.zip'
    for attempt in range(6):
        try:
            offset=archive.stat().st_size if archive.exists() else 0
            if offset and zipfile.is_zipfile(archive):return
            with requests.get(url,headers={'Range':f'bytes={offset}-'} if offset else {},stream=True,timeout=(20,60)) as response:
                response.raise_for_status()
                with archive.open('ab' if offset and response.status_code==206 else 'wb') as output:
                    for chunk in response.iter_content(1024*1024):output.write(chunk)
            if not zipfile.is_zipfile(archive):raise RuntimeError('Incomplete runtime archive')
            return
        except (requests.RequestException,RuntimeError):
            if attempt==5:raise
            time.sleep(min(attempt+1,5))

def ensure_assistant():
    model_root=ROOT/'data/docpup';runtime=ROOT/'.runtime/docpup'
    runtime.mkdir(parents=True,exist_ok=True);model_root.mkdir(parents=True,exist_ok=True)
    os.environ.setdefault('HF_HOME',str(model_root/'hf-cache'))
    from huggingface_hub import snapshot_download,hf_hub_download
    tokenizer=tokenizer_path(ROOT)
    if not tokenizer.is_file():
        print('Preparing Spark tokenizer...',flush=True)
        downloaded=Path(hf_hub_download(TOKENIZER_REPO,'tokenizer.json',revision=TOKENIZER_REVISION,local_dir=tokenizer.parent))
        if downloaded!=tokenizer:
            import shutil
            shutil.copyfile(downloaded,tokenizer)
    asr=model_root/'whisper-small'
    if not all((asr/name).is_file() for name in ('model.bin','config.json','tokenizer.json','vocabulary.txt')):
        print('Preparing local speech recognition...',flush=True)
        snapshot_download('Systran/faster-whisper-small',local_dir=asr)
    executable=runtime/'ollama.exe'
    if not service_ready():
        if not executable.is_file():
            if os.name!='nt':raise RuntimeError('Start a local Ollama service on port 11434 before running on this OS.')
            print('Downloading local model runtime...',flush=True)
            archive=runtime/'ollama.zip';download_runtime(archive)
            with zipfile.ZipFile(archive) as package:
                if any(not (runtime/name).resolve().is_relative_to(runtime.resolve()) for name in package.namelist()):raise RuntimeError('Unsafe runtime archive path')
                package.extractall(runtime)
        environment=dict(os.environ,OLLAMA_HOST='127.0.0.1:11434',OLLAMA_MODELS=str(model_root/'ollama'),OLLAMA_NUM_PARALLEL='1',OLLAMA_MAX_LOADED_MODELS='1',OLLAMA_CONTEXT_LENGTH='8192')
        with (runtime/'server.log').open('ab') as output,(runtime/'server-error.log').open('ab') as error:
            subprocess.Popen([str(executable),'serve'],env=environment,stdout=output,stderr=error,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        for _ in range(40):
            if service_ready():break
            time.sleep(.5)
        else:raise RuntimeError('Ollama startup failed; see .runtime/docpup/server-error.log')
    version=requests.get(SERVICE+'/api/version',timeout=5);version.raise_for_status()
    import re,shutil
    numbers=re.match(r'(\d+)\.(\d+)\.(\d+)',version.json().get('version',''))
    if not numbers or tuple(map(int,numbers.groups()))<(0,34,1):
        raise RuntimeError('Spark requires Ollama >= 0.34.1; upgrade the local Ollama runtime and restart it.')
    model=model_name()
    response=requests.get(SERVICE+'/api/tags',timeout=10);response.raise_for_status()
    if any(row['name']==model for row in response.json().get('models',[])):
        if model==DEFAULT_MODEL:
            info=requests.post(SERVICE+'/api/show',json={'model':model},timeout=10);info.raise_for_status()
            details=info.json().get('details',{})
            if details.get('family')!='spark2_5' or details.get('quantization_level')!='Q8_0' or MODEL_SHA256 not in info.json().get('modelfile',''):
                raise RuntimeError('The Spark alias points to the wrong architecture or quantization. Reimport the official Q8_0 GGUF.')
        return
    if model!=DEFAULT_MODEL:raise RuntimeError('Install the requested custom model before startup: '+model)
    weight=model_root/'spark'/MODEL_FILE
    if not weight.is_file() or sha256(weight)!=MODEL_SHA256:
        print('Preparing official Spark-X2.6-4B Q8_0 (resumable download)...',flush=True)
        download_spark()
    command=str(executable) if executable.is_file() else shutil.which('ollama')
    if not command:raise RuntimeError('Install the Ollama CLI to import '+str(weight))
    modelfile=runtime/'Modelfile'
    modelfile.write_text('FROM '+json.dumps(weight.as_posix(),ensure_ascii=False)+'\nPARAMETER num_ctx 8192\n',encoding='utf-8')
    environment=dict(os.environ,OLLAMA_HOST='127.0.0.1:11434')
    subprocess.run([command,'create',model,'-f',str(modelfile)],check=True,cwd=ROOT,env=environment)


def main():
    parser=argparse.ArgumentParser(description='Initialize and start the complete health portal, including Doc Pup.')
    parser.add_argument('--prepare',action='store_true',help='Install/initialize everything without starting the web server')
    parser.add_argument('--check',action='store_true',help='Check the installed Python application')
    args=parser.parse_args()
    os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
    os.environ.setdefault('PYTHONDONTWRITEBYTECODE','1');sys.dont_write_bytecode=True
    import django
    django.setup()
    from django.core.management import call_command
    call_command('check')
    if args.check:return
    call_command('migrate',interactive=False)
    files=['table_baseline.xlsx','table_hbp.xlsx','table_depre.xlsx','table_psqi.xlsx','LoginData/User.xlsx','LoginData/Admin.xlsx']
    demo=os.environ.get('HEALTH_IMPORT_DEMO','1')!='0' and all((ROOT/'data/source'/name).is_file() for name in files)
    call_command('health_setup',import_data=demo)
    if all((ROOT/f'data/source/model/model_{i}.pkl').is_file() for i in (1,2,3)):call_command('import_source_models')
    if args.prepare:ensure_assistant();print('Complete installation ready. Run start-site.cmd to open the portal.');return
    call_command('health_serve')

if __name__=='__main__':
    try:main()
    except (RuntimeError,requests.RequestException,subprocess.CalledProcessError) as error:
        print('Startup failed: '+str(error),file=sys.stderr);raise SystemExit(1)
