#!/usr/bin/env python3
"""One-root local lifecycle. Reads .env without logging secrets."""
from pathlib import Path
import os, shutil, signal, socket, subprocess, sys, time
from urllib.parse import urlsplit
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parents[1]
LOCAL=ROOT/'.local'; RUN=LOCAL/'run'; LOG=LOCAL/'logs'; PY=ROOT/'.venv/bin/python'

def environment():
    # Bootstrap via the project's interpreter even when invoked by npm/system Python.
    from dotenv import dotenv_values
    env=dict(os.environ)
    env.update({k:v for k,v in dotenv_values(ROOT/'.env').items() if v is not None})
    if not env.get('DATABASE_URL'): raise SystemExit('DATABASE_URL is missing. Copy .env.example to .env; see README.md.')
    env.setdefault('BACKEND_PORT','8010'); env.setdefault('FRONTEND_PORT','5190')
    env.setdefault('STORAGE_PATH',str(LOCAL/'storage'))
    env.setdefault('ALLOWED_ORIGINS',f"http://localhost:{env['FRONTEND_PORT']},http://127.0.0.1:{env['FRONTEND_PORT']}")
    env['BACKEND_URL']=f"http://127.0.0.1:{env['BACKEND_PORT']}"
    env['PYTHONDONTWRITEBYTECODE']='1'
    return env

def alive(pid):
    try: os.kill(pid,0);return True
    except ProcessLookupError:return False

def matches(pid, cwd, marker):
    args=subprocess.run(['ps','-p',str(pid),'-o','command='],capture_output=True,text=True).stdout
    if marker not in args:return False
    if sys.platform=='darwin':
        info=subprocess.run(['lsof','-a','-p',str(pid),'-d','cwd','-Fn'],capture_output=True,text=True).stdout.splitlines()
        return 'n'+str(cwd) in info
    try:return Path(f'/proc/{pid}/cwd').resolve()==cwd
    except OSError:return False

def db(env):
    parsed=urlsplit(env['DATABASE_URL'])
    if parsed.hostname not in ('127.0.0.1','localhost','::1'):
        if env.get('ALLOW_REMOTE_DATABASE')!='true': raise SystemExit('Remote DB startup is disabled. Set ALLOW_REMOTE_DATABASE=true only for an intended development database. Startup executes schema SQL.')
        print('Using configured external PostgreSQL (credentials hidden).');return
    port=parsed.port or 5432
    with socket.socket() as s:
        if s.connect_ex(('127.0.0.1',port))==0: print(f'Using local PostgreSQL on port {port}.');return
    pg_bin=env.get('LOCAL_PG_BIN'); pg_data=env.get('LOCAL_PG_DATA')
    if pg_bin and pg_data:
        subprocess.run([str(Path(pg_bin)/'pg_ctl'),'-D',pg_data,'-l',str(LOG/'postgres.log'),'-w','start'],check=True,env=env)
        # This cluster may be shared with another local project. stop never stops it.
        return
    if shutil.which('docker') and env.get('LOCAL_DATABASE_MODE')=='docker':
        subprocess.run(['docker','compose','up','-d','--wait','db'],cwd=ROOT,env=env,check=True);return
    raise SystemExit(f'PostgreSQL is unavailable on {port}. Start your PostgreSQL service, configure LOCAL_PG_BIN/LOCAL_PG_DATA, or use docker compose up -d --wait db.')

def launch(name, command, cwd, port, path, env, marker):
    pidfile=RUN/(name+'.pid')
    if pidfile.exists():
        pid=int(pidfile.read_text())
        if alive(pid) and matches(pid,cwd,marker):print(name+': already running');return
        pidfile.unlink(missing_ok=True)
    with socket.socket() as s:
        if s.connect_ex(('127.0.0.1',port))==0:raise SystemExit(f'Port {port} is occupied; no unrelated process was stopped.')
    with (LOG/(name+'.log')).open('ab') as log:
        p=subprocess.Popen(command,cwd=cwd,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    pidfile.write_text(str(p.pid))
    for _ in range(120):
        if p.poll() is not None:raise SystemExit(name+' exited. See '+str(LOG/(name+'.log')))
        try:
            with urlopen(f'http://127.0.0.1:{port}{path}',timeout=1) as r:
                if r.status==200:print(f'{name}: http://localhost:{port}');return
        except OSError:time.sleep(.2)
    raise SystemExit(name+' is not ready. See logs.')

def start(env, single=False):
    db(env)
    if single:env['FRONTEND_DIST']=str(ROOT/'apps/frontend/dist')
    launch('backend',[str(PY),'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',env['BACKEND_PORT']],ROOT/'apps/backend',int(env['BACKEND_PORT']),'/health',env,'uvicorn app.main:app')
    if not single:
        node=shutil.which('node')
        if not node:raise SystemExit('Node.js 22.12+ is required.')
        launch('frontend',[node,str(ROOT/'node_modules/vite/bin/vite.js'),'--host','127.0.0.1','--port',env['FRONTEND_PORT'],'--strictPort'],ROOT/'apps/frontend',int(env['FRONTEND_PORT']),'/',env,'vite/bin/vite.js')
    print(f"API docs: http://localhost:{env['BACKEND_PORT']}/docs")

def stop():
    for name,cwd,marker in [('frontend',ROOT/'apps/frontend','vite/bin/vite.js'),('backend',ROOT/'apps/backend','uvicorn app.main:app')]:
        f=RUN/(name+'.pid')
        if not f.exists():continue
        pid=int(f.read_text())
        if alive(pid):
            if not matches(pid,cwd,marker):raise SystemExit('PID identity changed; refusing to stop '+name)
            os.killpg(pid,signal.SIGTERM)
            for _ in range(50):
                if not alive(pid):break
                time.sleep(.1)
        f.unlink(missing_ok=True)
    print('App stopped. PostgreSQL and persistent data are retained (the cluster may be shared).')

def main():
    for p in (RUN,LOG):p.mkdir(parents=True,exist_ok=True)
    action=sys.argv[1] if len(sys.argv)>1 else 'start'
    if action=='stop':stop();return
    env=environment()
    if action in ('start','serve-build'):start(env,action=='serve-build')
    elif action=='db':db(env)
    elif action=='status':
        for name,port,path in [('frontend',env['FRONTEND_PORT'],'/'),('backend',env['BACKEND_PORT'],'/health')]:
            try:
                with urlopen(f'http://127.0.0.1:{port}{path}',timeout=2) as r:print(name+': HTTP '+str(r.status))
            except OSError:print(name+': stopped')
    else:raise SystemExit('Usage: dev.py start|stop|status|db|serve-build')
if __name__=='__main__':
    if Path(sys.executable).parent!=PY.parent and os.environ.get('WALLPANELS_DEV_BOOTSTRAPPED')!='1':
        if not PY.exists():raise SystemExit('Run npm run setup first (Python 3.12 required).')
        os.environ['WALLPANELS_DEV_BOOTSTRAPPED']='1';os.execv(str(PY),[str(PY),str(Path(__file__).resolve()),*sys.argv[1:]])
    main()
