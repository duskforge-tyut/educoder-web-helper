import json, secrets, threading, webbrowser
from pathlib import Path
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import httpx
from educoder_cli.client import EduCoderClient
from educoder_cli.cli import _format_problem_text

BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
ROOT = Path(__file__).parent
TOKEN = secrets.token_urlsafe(32)
AUTH = None
LEVELS = {}
PROFILE = ""
VIEW = {}
LOG = ROOT.parent / 'logs' / 'file-submissions.md'

def detail(t):
    return dict(id=t.challenge.id, game=t.game.identifier, position=t.challenge.position, title=t.challenge.subject, path=t.challenge.clean_path,
                status={0:'未开始',1:'评测中',2:'通过',3:'未通过'}.get(t.game.status,str(t.game.status)),
                score=t.game.final_score, description=_format_problem_text(t.challenge.task_pass),
                output=t.last_compile_output)


def chapter_levels(c, current):
    found = {current.game.identifier: current}
    pending = [current.prev_game, current.next_game]
    warnings = []
    seen = set(found)
    while pending:
        gid = pending.pop(0)
        if not gid or str(gid) in seen:
            continue
        gid = str(gid)
        seen.add(gid)
        try:
            t = c.get_task_detail(game_identifier=gid)
        except Exception as exc:
            warnings.append('部分关卡暂时无法读取：' + str(exc))
            continue
        found[gid] = t
        pending.extend([t.prev_game, t.next_game])
    levels = sorted((detail(t) for t in found.values()), key=lambda x:x['position'])
    return levels, '；'.join(warnings)

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def reply(self, obj, status=200):
        data=json.dumps(obj,ensure_ascii=False).encode()
        self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','no-store'); self.end_headers(); self.wfile.write(data)
    def do_GET(self):
        if self.path != '/': return self.reply({'error':'页面不存在'},404)
        data=(ROOT/'index.html').read_text(encoding='utf-8').replace('__TOKEN__',TOKEN).encode()
        self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8')
        self.send_header('Cache-Control','no-store'); self.end_headers(); self.wfile.write(data)
    def do_POST(self):
        global AUTH, PROFILE
        if self.headers.get('X-TG-Token') != TOKEN: return self.reply({'error':'请刷新本地页面'},403)
        try:
            size=int(self.headers.get('Content-Length',0))
            if size>2_000_000: raise ValueError('文件过大，请选择代码源文件')
            p=json.loads(self.rfile.read(size))
            if self.path=='/api/session':
                return self.reply({'authenticated':bool(AUTH),'name':PROFILE,'view':dict(VIEW) if AUTH else {}})
            if self.path=='/api/logout':
                AUTH=None; PROFILE=''; VIEW.clear(); LEVELS.clear(); return self.reply({'ok':True})
            if self.path=='/api/login':
                with httpx.Client(timeout=30, headers={"User-Agent": BROWSER_UA}) as transport:
                    with EduCoderClient(http_client=transport) as c:
                        r=c.login(p['account'],p['password'])
                        AUTH=(r.zzud,r.autologin,r.session)
                        PROFILE=r.name or r.login
                        VIEW.clear()
                        LEVELS.clear()
                return self.reply({'name':r.name or r.login})
            if not AUTH: return self.reply({'error':'请先登录'},401)
            with httpx.Client(timeout=30, headers={"User-Agent": BROWSER_UA}) as transport:
                with EduCoderClient(*AUTH,http_client=transport) as c:
                    if self.path=='/api/courses':
                        items=[]; page=1
                        while True:
                            batch=c.get_courses(page=page,limit=50)
                            items.extend({'id':x.id,'name':x.name} for x in batch)
                            if len(batch)<50: break
                            page+=1
                        return self.reply(items)
                    c.select_course(str(p['course']))
                    if self.path=='/api/homeworks':
                        VIEW.clear(); VIEW.update(course=str(p['course']))
                        return self.reply([{'id':h.homework_id,'name':h.name,'progress':f'{h.finished_challenge_count}/{h.challenge_count}'} for h in c.get_homeworks()])
                    c.select_homework(str(p['homework']))
                    key = (str(p['course']), str(p['homework']))
                    if self.path=='/api/levels':
                        current=c.get_current_context()
                        levels, warning=chapter_levels(c, current)
                        LEVELS[key]={x['game'] for x in levels}
                        return self.reply({'levels':levels,'current':current.game.identifier,'warning':warning})
                    gid=str(p.get('game') or '')
                    if self.path in ('/api/task','/api/submit'):
                        if not gid or gid not in LEVELS.get(key,set()):
                            raise ValueError('请先加载本章关卡，再选择有效关卡')
                        c.game_identifier=gid
                    t=c.get_current_context()
                    if self.path=='/api/task':
                        VIEW.clear(); VIEW.update(course=str(p['course']),homework=str(p['homework']),game=gid)
                        return self.reply(detail(t))
                    if self.path=='/api/preview':
                        path=Path(p['path'].strip().strip('"'))
                        if not path.is_file(): raise ValueError('找不到该文件，请填写完整文件路径')
                        return self.reply({'content':path.read_text(encoding='utf-8-sig'),'name':path.name})
                    if self.path=='/api/submit':
                        if str(t.challenge.id)!=str(p['challenge']): raise ValueError('当前关卡已变化，请重新打开实训后核对')
                        if t.challenge.clean_path != p['target']: raise ValueError('目标文件已变化，请重新打开实训')
                        source=p['content']
                        if not source.strip(): raise ValueError('答案文件内容为空')
                        LOG.parent.mkdir(parents=True,exist_ok=True)
                        with LOG.open('a',encoding='utf-8') as f:
                            f.write(f'\n## {datetime.now():%Y-%m-%d %H:%M:%S}\n- 转移：提交代码到头歌（发起）\n- 来源：{p.get("source","浏览器选择文件")}\n- 目标：课堂 {p["course"]} / 实训 {p["homework"]} / 关卡 {t.challenge.subject} / {t.challenge.clean_path}\n')
                        result=c.submit(source,timeout=60)
                        return self.reply({'passed':result.get('passed'),'task':detail(result['task_detail']), 'tests':[{'expected':x.output,'actual':x.actual_output,'passed':x.result} for x in result.get('test_sets',[])]})
                    return self.reply({'error':'未知操作'},404)
        except Exception as e:
            self.reply({'error':str(e)},400)

if __name__=='__main__':
    server=HTTPServer(('127.0.0.1',8765),Handler)
    print('头歌本地助手：http://127.0.0.1:8765',flush=True)
    if '--no-browser' not in __import__('sys').argv:
        threading.Timer(0.8,lambda:webbrowser.open('http://127.0.0.1:8765')).start()
    server.serve_forever()


