"""
NLP Test Generator v3 — Adaptive Agent Architecture
AI sees page → decides → acts → sees result → repeats
No blind pre-planning. Handles SSO, multi-step login, dynamic pages.
"""
import asyncio,base64,concurrent.futures,glob,json,os,re,subprocess,tempfile,traceback,uuid
from datetime import datetime
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from fastapi import FastAPI,WebSocket,WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse,HTMLResponse
from ai_service import AIService
from playwright_parser import assemble_robot_file,playwright_to_rf
load_dotenv()

app=FastAPI(title="NLP Test Generator",version="3.0.0")
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_credentials=True,allow_methods=["*"],allow_headers=["*"])

CLI=os.getenv("PLAYWRIGHT_CLI_PATH","playwright-cli")
WS_DIR=Path(os.getenv("NLP_WORKSPACE",os.path.join(tempfile.gettempdir(),"nlp-test-ws")))
OUT_DIR=Path("./generated_tests")
WS_DIR.mkdir(parents=True,exist_ok=True)
OUT_DIR.mkdir(parents=True,exist_ok=True)
ai=AIService()
_pool=concurrent.futures.ThreadPoolExecutor(max_workers=4)

MAX_ACTIONS=35
MAX_CONSECUTIVE_FAILS=3
EXECUTION_TIMEOUT=300  # 5 minutes

# ─── Helpers ──────────────────────────────────────────────

async def cli(cmd,session="default",cwd="",timeout=30.0):
    full=f"{CLI} -s={session} {cmd}"
    wd=cwd or str(WS_DIR)
    print(f"  [CLI] {full}")
    def _r():
        try:
            r=subprocess.run(full,shell=True,capture_output=True,cwd=wd,timeout=timeout,encoding="utf-8",errors="replace")
            return r.stdout,r.stderr,r.returncode
        except subprocess.TimeoutExpired: return "","Timeout",-1
        except Exception as e: return "",str(e),-1
    loop=asyncio.get_event_loop()
    out,err,rc=await loop.run_in_executor(_pool,_r)
    if out.strip(): print(f"  [out] {out[:300]}")
    if err.strip(): print(f"  [err] {err[:150]}")
    snap=None
    for l in out.split("\n"):
        m=re.search(r"(\.playwright-cli[/\\][^\s\)\]]+\.yml)",l)
        if m: snap=os.path.join(wd,m.group(1))
    shot=None
    for l in out.split("\n"):
        m=re.search(r"(\.playwright-cli[/\\][^\s\)\]]+\.png)",l)
        if m: shot=os.path.join(wd,m.group(1))
    return {"stdout":out,"stderr":err,"rc":rc,"snap":snap,"shot":shot}

def readf(p):
    try:
        with open(p,"r",encoding="utf-8",errors="replace") as f: return f.read()
    except: return ""

def latest(d,pat):
    fs=sorted(glob.glob(os.path.join(d,pat)),key=os.path.getmtime,reverse=True)
    return fs[0] if fs else None

def b64(p):
    try:
        with open(p,"rb") as f: return base64.b64encode(f.read()).decode()
    except: return None

def extract_pw(out):
    for l in out.strip().split("\n"):
        l=l.strip()
        if l.startswith("await page.") or l.startswith("page."): return l
    return None

def is_ref(r):
    if not r: return False
    s=str(r).strip().lower()
    return s not in ("null","none","","undefined")

# ─── Credential Manager ──────────────────────────────────

class Creds:
    def __init__(self,user="",pwd="",url=""):
        self.user=user; self.pwd=pwd; self.url=url
    def mask(self,t):
        if self.pwd and self.pwd in t: t=t.replace(self.pwd,"${PASSWORD}")
        if self.user and self.user in t: t=t.replace(self.user,"${USERNAME}")
        return t
    def unmask(self,t):
        t=t.replace("${USERNAME}",self.user) if self.user else t
        t=t.replace("${PASSWORD}",self.pwd) if self.pwd else t
        return t
    def rf_vars(self):
        v={}
        if self.user: v["USERNAME"]="SET_AT_RUNTIME"
        if self.pwd: v["PASSWORD"]="SET_AT_RUNTIME"
        return v

# ─── Agent Orchestrator ──────────────────────────────────

class Agent:
    def __init__(self,sid,ws,creds):
        self.sid=sid; self.ws=ws; self.creds=creds
        self.wd=str(WS_DIR/sid)
        self.cli_dir=os.path.join(self.wd,".playwright-cli")
        self.stopped=False; self.paused=False
        self.history=[]; self.rf_lines=[]; self.last_ss=None
        os.makedirs(self.wd,exist_ok=True)

    async def send(self,m):
        try: await self.ws.send_json(m)
        except: pass

    async def screenshot(self):
        r=await cli("screenshot",self.sid,self.wd)
        p=r["shot"] or latest(self.cli_dir,"*.png")
        s=b64(p) if p else None
        if s: self.last_ss=s
        return s

    async def snapshot(self):
        r=await cli("snapshot",self.sid,self.wd)
        p=r["snap"] or latest(self.cli_dir,"*.yml")
        return readf(p) if p else ""

    async def execute_action(self,decision):
        """Execute a single action decided by the AI agent."""
        action=decision.get("action","")
        ref=decision.get("ref","")
        value=decision.get("value","")
        desc=decision.get("description","")

        try:
            if action=="wait":
                dur=float(value or "2")
                await asyncio.sleep(dur)
                return {"ok":True,"rf":f"    Sleep    {dur}s","pw":f"page.waitForTimeout({int(dur*1000)})"}

            if action in ("assert_text","assert_visible","assert_url"):
                hint=decision.get("locator_hint","")
                if action=="assert_visible":
                    loc=hint or f"ref={ref}"
                    rf=f"    Get Element States    {loc}    contains    visible"
                elif action=="assert_text":
                    loc=hint or f"ref={ref}"
                    rf=f"    Get Text    {loc}    *=    {self.creds.mask(value)}"
                elif action=="assert_url":
                    rf=f"    Get Url    *=    {self.creds.mask(value)}"
                return {"ok":True,"rf":rf,"pw":f"// {desc}"}

            # Interactive actions
            if not is_ref(ref):
                return {"ok":False,"error":f"Invalid element ref: {ref}","rf":"","pw":""}

            if action=="fill":
                real_val=self.creds.unmask(value) if value else ""
                if not real_val:
                    return {"ok":False,"error":"Fill action requires a value","rf":"","pw":""}
                r=await cli(f'fill {ref} "{real_val}"',self.sid,self.wd)
            elif action=="press_key":
                r=await cli(f"press {value or 'Enter'}",self.sid,self.wd)
            elif action=="click":
                r=await cli(f"click {ref}",self.sid,self.wd)
            else:
                r=await cli(f"{action} {ref}",self.sid,self.wd)

            if r["rc"] not in (0,None):
                err=r["stderr"].strip() or r["stdout"].strip()
                return {"ok":False,"error":err[:200],"rf":"","pw":""}

            # Smart wait based on action type
            if action=="click":
                desc_low=desc.lower()
                if any(w in desc_low for w in ["login","sign in","submit","next","continue","confirm","save","create","delete"]):
                    await asyncio.sleep(2.0)
                else:
                    await asyncio.sleep(0.8)
            elif action=="fill":
                await asyncio.sleep(0.2)

            # Extract playwright_code → RF
            pw=extract_pw(r["stdout"])
            if pw:
                clean=pw.lstrip("await ").lstrip()
                if clean.startswith("await "): clean=clean[6:]
                rf=playwright_to_rf(clean)
            else:
                hint=decision.get("locator_hint","")
                if action=="click":
                    rf=f"    Click    {hint or f'ref={ref}'}"
                elif action=="fill":
                    rf=f"    Fill Text    {hint or f'ref={ref}'}    {self.creds.mask(value)}"
                elif action=="press_key":
                    rf=f"    Keyboard Key    {value}"
                else:
                    rf=f"    # {action} on {hint or ref}"

            rf=self.creds.mask(rf)
            pw=self.creds.mask(pw or "")
            return {"ok":True,"rf":rf,"pw":pw}

        except Exception as e:
            return {"ok":False,"error":self.creds.mask(str(e))[:200],"rf":"","pw":""}

    async def run(self,goal,url):
        import time
        start_time=time.time()
        try:
            # ── Open browser ──────────────────────
            await self.send({"type":"status","message":"Opening browser..."})
            r=await cli(f"open {url}",self.sid,self.wd)
            if r["rc"] not in (0,None):
                await self.send({"type":"error","message":f"Browser failed: {r['stderr'][:200]}"})
                return

            await asyncio.sleep(2.5)

            # Verify page loaded
            snap=await self.snapshot()
            if not snap.strip():
                await asyncio.sleep(2)
                snap=await self.snapshot()
                if not snap.strip():
                    await self.send({"type":"error","message":"Page failed to load. Check URL."})
                    return

            ss=await self.screenshot()
            await self.send({"type":"browser_ready","screenshot_b64":ss})

            # ── Agent loop ────────────────────────
            consec_fails=0
            action_index=0

            for _ in range(MAX_ACTIONS):
                if self.stopped: break
                while self.paused and not self.stopped: await asyncio.sleep(0.3)
                if time.time()-start_time > EXECUTION_TIMEOUT:
                    await self.send({"type":"status","message":"Execution timeout (5 min). Stopping."})
                    break

                # 1. Snapshot current page
                await self.send({"type":"thinking","message":"AI analyzing page..."})
                snap=await self.snapshot()
                if not snap.strip():
                    await asyncio.sleep(1.5)
                    snap=await self.snapshot()
                if not snap.strip():
                    await self.send({"type":"error","message":"Lost connection to page"})
                    break

                # 2. AI decides next action
                decision=await ai.decide_next_action(
                    goal=goal, snapshot=self.creds.mask(snap),
                    history=self.history,
                    username=self.creds.user, password=self.creds.pwd,
                )

                status=decision.get("status","action")
                desc=self.creds.mask(decision.get("description",""))
                reasoning=self.creds.mask(decision.get("reasoning",""))
                action_type=decision.get("action","")

                # 3. Goal achieved
                if status=="goal_achieved":
                    await self.send({"type":"goal_achieved","message":reasoning or "Goal accomplished!"})
                    print(f"\n[✓ GOAL ACHIEVED] {reasoning}")
                    break

                # 4. Stuck
                if status=="stuck":
                    await self.send({"type":"action_stuck","index":action_index,"description":desc,"reasoning":reasoning})
                    print(f"\n[✗ STUCK] {reasoning}")
                    break

                # 5. Execute action
                await self.send({"type":"action_start","index":action_index,"action":action_type,"description":desc,"reasoning":reasoning})
                print(f"\n[Action {action_index+1}] {action_type}: {desc}")

                result=await self.execute_action(decision)

                if result["ok"]:
                    consec_fails=0
                    self.rf_lines.append(result["rf"])
                    self.history.append({"action":action_type,"description":desc,"status":"success"})

                    # Screenshot for visual actions
                    ss_b64=self.last_ss
                    if action_type not in ("wait","fill","press_key"):
                        ss_b64=await self.screenshot()

                    await self.send({
                        "type":"action_complete","index":action_index,
                        "rf_line":result["rf"],"playwright_code":result["pw"],
                        "screenshot_b64":ss_b64,
                    })
                    print(f"  ✓ {result['rf'].strip()}")
                else:
                    consec_fails+=1
                    self.history.append({"action":action_type,"description":desc,"status":"failed","error":result["error"]})

                    ss_b64=await self.screenshot()
                    await self.send({
                        "type":"action_failed","index":action_index,
                        "error":result["error"],"screenshot_b64":ss_b64,
                    })
                    print(f"  ✗ {result['error']}")

                    if consec_fails>=MAX_CONSECUTIVE_FAILS:
                        await self.send({"type":"status","message":f"Stopped: {MAX_CONSECUTIVE_FAILS} consecutive failures"})
                        print(f"\n[STOPPED] {MAX_CONSECUTIVE_FAILS} consecutive failures")
                        break

                action_index+=1
                await asyncio.sleep(0.3)

            # ── Generate .robot file ──────────────
            passed=sum(1 for h in self.history if h["status"]=="success")
            failed=sum(1 for h in self.history if h["status"]=="failed")

            if self.rf_lines:
                name=re.sub(r"[^\w\s]","",goal)[:60].strip().title()
                script=assemble_robot_file(
                    test_name=name,
                    test_description=self.creds.mask(goal),
                    base_url=url,
                    rf_lines=[l for l in self.rf_lines if not l.startswith("    #")],  # skip comments
                    variables=self.creds.rf_vars(),
                )
                script=self.creds.mask(script)

                ts=datetime.now().strftime("%Y%m%d_%H%M%S")
                fn=f"test_{ts}.robot"
                fp=OUT_DIR/fn
                with open(fp,"w",encoding="utf-8") as f: f.write(script)

                await self.send({"type":"rf_script_complete","script":script,"filename":fn})

            await self.send({"type":"execution_complete","total":len(self.history),"passed":passed,"failed":failed})
            print(f"\n[Done] {passed}✓ {failed}✗ — {len(self.rf_lines)} RF lines")
            await cli("close",self.sid,self.wd)

        except Exception as e:
            print(f"\n[Error]\n{traceback.format_exc()}")
            await self.send({"type":"error","message":self.creds.mask(str(e))})

# ─── WebSocket ────────────────────────────────────────────

@app.websocket("/nlp-test/ws")
async def ws_ep(websocket:WebSocket):
    await websocket.accept()
    sid=str(uuid.uuid4())[:8]
    agent=None; task=None
    await websocket.send_json({"type":"connected","session_id":sid})
    print(f"\n[WS] {sid} connected")
    try:
        while True:
            d=await websocket.receive_json()
            t=d.get("type")
            if t=="start":
                nlp=d.get("nlp_input","").strip()
                url=d.get("start_url","").strip()
                usr=d.get("username","").strip()
                pwd=d.get("password","").strip()
                if not nlp or not url:
                    await websocket.send_json({"type":"error","message":"URL and description required"})
                    continue
                print(f"\n[Start] {url}\n[Goal] {nlp}")
                creds=Creds(usr,pwd,url)
                agent=Agent(sid,websocket,creds)
                task=asyncio.create_task(agent.run(nlp,url))
            elif t=="pause" and agent: agent.paused=True; await websocket.send_json({"type":"status","message":"Paused"})
            elif t=="resume" and agent: agent.paused=False; await websocket.send_json({"type":"status","message":"Resumed"})
            elif t=="stop" and agent:
                agent.stopped=True
                if task: task.cancel()
                await websocket.send_json({"type":"status","message":"Stopped"})
    except WebSocketDisconnect:
        print(f"[WS] {sid} disconnected")
        if agent: agent.stopped=True; await cli("close",sid,str(WS_DIR/sid))
    except: print(f"[WS Error] {traceback.format_exc()}")

# ─── REST ─────────────────────────────────────────────────

@app.get("/api/generated-tests")
async def list_t():
    fs=sorted(OUT_DIR.glob("*.robot"),key=os.path.getmtime,reverse=True)
    return [{"filename":f.name,"created":datetime.fromtimestamp(f.stat().st_mtime).isoformat()} for f in fs]

@app.get("/api/generated-tests/{fn}")
async def dl(fn:str):
    p=OUT_DIR/fn
    return FileResponse(p,filename=fn) if p.exists() else {"error":"Not found"}

@app.get("/api/health")
async def health():
    ok=False;v="?"
    try:
        r=subprocess.run(f"{CLI} --version",shell=True,capture_output=True,encoding="utf-8",timeout=10)
        ok=r.returncode==0; v=r.stdout.strip() if ok else "not found"
    except: pass
    return {"status":"ok" if ok else "degraded","cli":v,"ai":ai.provider_display}

@app.get("/")
async def ui():
    p=Path(__file__).parent/"index.html"
    return HTMLResponse(p.read_text(encoding="utf-8")) if p.exists() else HTMLResponse("<h2>index.html not found</h2>")

if __name__=="__main__":
    import uvicorn
    h,p=os.getenv("HOST","0.0.0.0"),int(os.getenv("PORT","8000"))
    print(f"\n{'='*45}\n  NLP Test Generator v3 (Adaptive Agent)\n  AI: {ai.provider_display}\n  http://{h}:{p}\n{'='*45}\n")
    uvicorn.run("app:app",host=h,port=p,reload=True)
    
