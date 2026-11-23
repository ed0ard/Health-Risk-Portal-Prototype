"""Build a manual GitHub-upload source bundle without machine state or large AI weights."""
import argparse,hashlib,json,os
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED

ROOT=Path(__file__).resolve().parents[1]
EXCLUDED={'.git','.venv','venv','.runtime','__pycache__','.pytest_cache','.mypy_cache','.ruff_cache','.cache','dist','build','node_modules','staticfiles','media','test-results','playwright-report','tests','dev_checks'}
SUFFIXES={'.pyc','.pyo','.log','.sqlite3','.db','.zip','.gguf','.onnx','.wav','.mp3','.webm','.partial','.incomplete'}
LOCAL_ONLY={'requirements-dev.txt','browser_testing.py','docpup_regression_v4.py','docpup-rig.js'}

def files():
    for directory,folders,names in os.walk(ROOT,followlinks=False):
        base=Path(directory)
        folders[:]=sorted(name for name in folders if name not in EXCLUDED and not (base/name).is_symlink() and (base/name).relative_to(ROOT).as_posix()!='data/docpup')
        for name in sorted(names):
            path=base/name
            if path.is_symlink() or path.suffix in SUFFIXES or name.startswith(('.env','~$','test')) or 'regression' in name or name.endswith('_check.py') or name in LOCAL_ONLY or '.sqlite3-' in name:continue
            if path.resolve().is_relative_to(ROOT):yield path

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'dist/health-risk-portal-source.zip');args=parser.parse_args()
    args.output.parent.mkdir(parents=True,exist_ok=True);manifest=[]
    with ZipFile(args.output,'w',ZIP_DEFLATED) as archive:
        for path in files():
            relative=path.relative_to(ROOT).as_posix()
            if path.stat().st_size>25*1024*1024:raise RuntimeError('File exceeds GitHub browser upload size: '+relative)
            blob=path.read_bytes();archive.writestr(relative,blob)
            manifest.append({'path':relative,'bytes':len(blob),'sha256':hashlib.sha256(blob).hexdigest()})
    args.output.with_suffix('.manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    for stale in args.output.parent.glob(args.output.stem+'-upload-*.zip'):stale.unlink()
    if len(manifest)>100:
        for offset in range(0,len(manifest),100):
            batch=args.output.with_name(args.output.stem+f'-upload-{offset//100+1:02}.zip')
            with ZipFile(batch,'w',ZIP_DEFLATED) as archive:
                for item in manifest[offset:offset+100]:archive.write(ROOT/item['path'],item['path'])
    print(f'Release ready: {len(manifest)} files, {args.output.stat().st_size/1024/1024:.1f} MiB. Extract and upload the contents, not the ZIP itself.')

if __name__=='__main__':main()
