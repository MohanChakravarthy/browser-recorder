<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>NLP Test Generator</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/react/18.2.0/umd/react.production.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/react-dom/18.2.0/umd/react-dom.production.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/babel-standalone/7.23.9/babel.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.44.0/min/vs/loader.min.js"></script>
<style>
*{margin:0;padding:0;box-sizing:border-box}
html,body,#root{height:100%;overflow:hidden}
body{background:#080c18;color:#e2e8f0;font-family:'Inter',sans-serif}
@keyframes spin{to{transform:rotate(360deg)}}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
@keyframes slideUp{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}
@keyframes glowLine{0%{background:rgba(34,197,94,.18)}100%{background:transparent}}
::-webkit-scrollbar{width:4px}::-webkit-scrollbar-track{background:transparent}::-webkit-scrollbar-thumb{background:#1e293b;border-radius:2px}
input:focus{border-color:#3b82f6!important;outline:none}
button{cursor:pointer;transition:all .1s}button:active{transform:scale(.97)}
</style>
</head>
<body><div id="root"></div>
<script type="text/babel">
const{useState,useRef,useEffect,useCallback}=React;
const WS=`ws://${location.hostname||'localhost'}:${location.port||'8000'}/nlp-test/ws`;

function Editor({value,hlLine}){
    const cRef=useRef(),edRef=useRef(),mRef=useRef(),decRef=useRef([]);
    useEffect(()=>{
        if(!cRef.current)return;
        require.config({paths:{vs:'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.44.0/min/vs'}});
        require(['vs/editor/editor.main'],m=>{
            mRef.current=m;
            if(!m.languages.getLanguages().find(l=>l.id==='robot')){
                m.languages.register({id:'robot'});
                m.languages.setMonarchTokensProvider('robot',{tokenizer:{root:[
                    [/^\*\*\*.*\*\*\*/,'kw'],[/\$\{[^}]+\}/,'var'],[/\[(Documentation|Setup|Teardown|Tags)\]/,'tag'],
                    [/#\s*FAILED.*/,'err'],[/#.*/,'cmt'],
                    [/\b(Library|Resource|Variables)\b/,'kw'],
                    [/\b(New Browser|New Page|Close Browser|Click|Fill Text|Get Text|Get Url|Get Element States|Get Element Count|Get Title|Wait For Elements State|Check Checkbox|Uncheck Checkbox|Select Options By|Hover|Keyboard Key|Type Text|Go To|Sleep|Log|Take Screenshot|Reload)\b/,'fn'],
                    [/\b(==|!=|\*=|contains|visible|enabled|disabled|checked|hidden)\b/,'op'],
                    [/\b(headless=true|chromium|firefox|webkit)\b/,'const'],
                    [/"[^"]*"/,'str'],[/'[^']*'/,'str'],[/SET_AT_RUNTIME/,'warn'],
                ]}});
            }
            m.editor.defineTheme('t',{base:'vs-dark',inherit:true,
                rules:[{token:'kw',foreground:'60a5fa',fontStyle:'bold'},{token:'var',foreground:'c084fc'},{token:'tag',foreground:'f472b6'},{token:'fn',foreground:'34d399',fontStyle:'bold'},{token:'cmt',foreground:'374151',fontStyle:'italic'},{token:'str',foreground:'fbbf24'},{token:'op',foreground:'fb923c'},{token:'const',foreground:'f472b6'},{token:'err',foreground:'fca5a5',fontStyle:'italic'},{token:'warn',foreground:'f59e0b',fontStyle:'italic'}],
                colors:{'editor.background':'#060a14','editor.foreground':'#e2e8f0','editor.lineHighlightBackground':'#ffffff06','editorLineNumber.foreground':'#1a2030','editorLineNumber.activeForeground':'#3b4860','editor.selectionBackground':'#3b82f630','editorCursor.foreground':'#3b82f6','editorGutter.background':'#060a14','scrollbarSlider.background':'#1e293b60'}
            });
            edRef.current=m.editor.create(cRef.current,{
                value:value||'',language:'robot',theme:'t',readOnly:true,minimap:{enabled:false},
                fontSize:13,lineHeight:21,fontFamily:"'JetBrains Mono',monospace",fontLigatures:true,
                lineNumbers:'on',scrollBeyondLastLine:false,renderLineHighlight:'none',
                automaticLayout:true,padding:{top:10,bottom:10},
                scrollbar:{vertical:'auto',verticalScrollbarSize:4},
                overviewRulerBorder:false,contextmenu:false,wordWrap:'on',
                guides:{indentation:false},renderWhitespace:'none',
            });
        });
        return()=>{edRef.current?.dispose()};
    },[]);

    useEffect(()=>{
        if(!edRef.current||!value)return;
        const m=edRef.current.getModel();
        if(m&&m.getValue()!==value){m.setValue(value);edRef.current.revealLine(m.getLineCount())}
    },[value]);

    useEffect(()=>{
        if(!edRef.current||!mRef.current||!hlLine)return;
        const mn=mRef.current;
        decRef.current=edRef.current.deltaDecorations(decRef.current,[{
            range:new mn.Range(hlLine,1,hlLine,1),
            options:{isWholeLine:true,className:'hl-line'}
        }]);
        edRef.current.revealLineInCenter(hlLine);
        const t=setTimeout(()=>{if(edRef.current)decRef.current=edRef.current.deltaDecorations(decRef.current,[])},2200);
        return()=>clearTimeout(t);
    },[hlLine]);

    useEffect(()=>{
        if(document.getElementById('hl-css'))return;
        const s=document.createElement('style');s.id='hl-css';
        s.textContent='.hl-line{animation:glowLine 2s ease-out forwards;border-left:2px solid #22c55e}';
        document.head.appendChild(s);
    },[]);
    return <div ref={cRef} style={{width:'100%',height:'100%'}}/>;
}

function App(){
    const[conn,setConn]=useState(false);
    const ws=useRef(null);
    const[url,setUrl]=useState("");const[nlp,setNlp]=useState("");
    const[user,setUser]=useState("");const[pwd,setPwd]=useState("");const[showCred,setShowCred]=useState(false);
    const[running,setRunning]=useState(false);const[paused,setPaused]=useState(false);
    const[actions,setActions]=useState([]);  // {index,action,description,reasoning,status,error,rf_line}
    const[thinking,setThinking]=useState("");
    const[status,setStatus]=useState("");
    const[ss,setSs]=useState(null);
    const[rfLines,setRfLines]=useState([]);
    const[script,setScript]=useState("");
    const[live,setLive]=useState("");
    const[hl,setHl]=useState(0);
    const[result,setResult]=useState(null);
    const[copyLbl,setCopy]=useState("Copy");
    const actRef=useRef(null);

    // Build live preview
    useEffect(()=>{
        if(script||!rfLines.length)return;
        const ls=["*** Settings ***","Library    Browser","",
            "*** Variables ***",`\${BASE_URL}    ${url||'...'}`,
            user?"${USERNAME}    SET_AT_RUNTIME":null,
            pwd?"${PASSWORD}    SET_AT_RUNTIME":null,
            "","*** Test Cases ***","NLP Generated Test",
            `    [Documentation]    ${nlp.slice(0,80)}`,
            "    New Browser    chromium    headless=true",
            "    New Page    ${BASE_URL}","",
            ...rfLines,"","    [Teardown]    Close Browser"
        ].filter(l=>l!==null).join("\n");
        setLive(ls);
        setHl(ls.split("\n").length-2);
    },[rfLines,script]);

    useEffect(()=>{if(script)setHl(script.split("\n").length-2)},[script]);
    useEffect(()=>{actRef.current?.scrollTo({top:actRef.current.scrollHeight,behavior:'smooth'})},[actions]);

    const connect=useCallback(()=>{
        const w=new WebSocket(WS);ws.current=w;
        w.onopen=()=>setConn(true);w.onclose=()=>{setConn(false);setRunning(false)};
        w.onerror=()=>setConn(false);
        w.onmessage=e=>{
            const d=JSON.parse(e.data);
            switch(d.type){
                case"connected":break;
                case"status":setStatus(d.message);setThinking("");break;
                case"thinking":setThinking(d.message);break;
                case"browser_ready":if(d.screenshot_b64)setSs(d.screenshot_b64);setStatus("Browser ready");setThinking("");break;
                case"action_start":
                    setThinking("");
                    setActions(p=>[...p,{index:d.index,action:d.action,description:d.description,reasoning:d.reasoning,status:"running"}]);
                    setStatus(`Action ${d.index+1}: ${d.description}`);
                    break;
                case"action_complete":
                    if(d.screenshot_b64)setSs(d.screenshot_b64);
                    if(d.rf_line)setRfLines(p=>[...p,d.rf_line]);
                    setActions(p=>p.map(a=>a.index===d.index?{...a,status:"success",rf_line:d.rf_line}:a));
                    break;
                case"action_failed":
                    if(d.screenshot_b64)setSs(d.screenshot_b64);
                    setActions(p=>p.map(a=>a.index===d.index?{...a,status:"failed",error:d.error}:a));
                    setStatus(`✗ ${d.error}`);
                    break;
                case"action_stuck":
                    setActions(p=>[...p,{index:d.index||p.length,action:"stuck",description:d.description||"Cannot proceed",reasoning:d.reasoning,status:"failed"}]);
                    setStatus(`Stuck: ${d.reasoning}`);setRunning(false);setThinking("");
                    break;
                case"goal_achieved":
                    setStatus(`✓ ${d.message}`);setThinking("");
                    break;
                case"rf_script_complete":setScript(d.script);setThinking("");break;
                case"execution_complete":setRunning(false);setResult(d);setThinking("");break;
                case"error":setStatus(`Error: ${d.message}`);setRunning(false);setThinking("");break;
            }
        };
    },[]);
    useEffect(()=>{connect();return()=>ws.current?.close()},[connect]);

    const send=m=>{if(ws.current?.readyState===1)ws.current.send(JSON.stringify(m))};
    const start=()=>{
        if(!nlp.trim()||!url.trim())return;
        setActions([]);setRfLines([]);setScript("");setLive("");setSs(null);setResult(null);setHl(0);setThinking("");setStatus("");
        setRunning(true);setPaused(false);
        send({type:"start",nlp_input:nlp.trim(),start_url:url.trim(),username:user.trim(),password:pwd.trim()});
    };
    const ok=nlp.trim()&&url.trim()&&conn&&!running;
    const display=script||live;

    const IC={pending:"○",running:"◉",success:"✓",failed:"✗"};
    const CC={pending:"#4b5563",running:"#f59e0b",success:"#22c55e",failed:"#ef4444"};

    return(
    <div style={{width:'100%',height:'100vh',display:'flex',flexDirection:'column',background:'#080c18',overflow:'hidden'}}>
        {/* Header */}
        <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',padding:'6px 14px',borderBottom:'1px solid #111827',background:'#0a0f1c',flexShrink:0}}>
            <div style={{display:'flex',alignItems:'center',gap:8}}>
                <div style={{fontSize:14,width:24,height:24,display:'flex',alignItems:'center',justifyContent:'center',background:'linear-gradient(135deg,#3b82f6,#8b5cf6)',borderRadius:5}}>⚡</div>
                <span style={{fontSize:13,fontWeight:700,fontFamily:"'JetBrains Mono'",color:'#f1f5f9'}}>NLP Test Generator</span>
                <div style={{width:6,height:6,borderRadius:'50%',background:conn?'#22c55e':'#ef4444'}}/>
                <span style={{fontSize:9,color:'#4b5563',fontFamily:"'JetBrains Mono'"}}>v3 adaptive</span>
            </div>
            {result&&<div style={{display:'flex',gap:5}}>
                <span style={{fontSize:10,padding:'1px 8px',borderRadius:99,background:'#052e16',color:'#4ade80',fontFamily:"'JetBrains Mono'",fontWeight:600}}>{result.passed}✓</span>
                {result.failed>0&&<span style={{fontSize:10,padding:'1px 8px',borderRadius:99,background:'#2a0a0a',color:'#fca5a5',fontFamily:"'JetBrains Mono'",fontWeight:600}}>{result.failed}✗</span>}
            </div>}
        </div>

        {/* Inputs */}
        <div style={{padding:'8px 14px',borderBottom:'1px solid #111827',background:'#0a0f1c',flexShrink:0,display:'flex',flexDirection:'column',gap:6}}>
            <div style={{display:'flex',gap:8,alignItems:'flex-end'}}>
                <div style={{flex:1}}>
                    <label style={{fontSize:8,color:'#374151',fontWeight:700,textTransform:'uppercase',letterSpacing:'.1em',display:'block',marginBottom:2}}>URL</label>
                    <input style={{width:'100%',padding:'5px 8px',fontSize:12,background:'#0f1629',border:'1px solid #1e293b',borderRadius:4,color:'#e2e8f0',fontFamily:'Inter'}} placeholder="https://app.example.com" value={url} onChange={e=>setUrl(e.target.value)} disabled={running}/>
                </div>
                <button onClick={()=>setShowCred(!showCred)} style={{background:'none',border:'1px solid #1e293b',borderRadius:4,padding:'5px 8px',fontSize:10,color:showCred?'#3b82f6':'#374151',fontFamily:'Inter',whiteSpace:'nowrap'}}>🔑 {showCred?'Hide':'Creds'}</button>
            </div>
            {showCred&&<div style={{display:'flex',gap:8,alignItems:'flex-end',animation:'slideUp .2s'}}>
                <div style={{flex:1}}><label style={{fontSize:8,color:'#374151',fontWeight:700,textTransform:'uppercase',letterSpacing:'.1em',display:'block',marginBottom:2}}>Username</label>
                <input style={{width:'100%',padding:'5px 8px',fontSize:12,background:'#0f1629',border:'1px solid #1e293b',borderRadius:4,color:'#e2e8f0'}} placeholder="user@example.com" value={user} onChange={e=>setUser(e.target.value)} disabled={running} autoComplete="off"/></div>
                <div style={{flex:1}}><label style={{fontSize:8,color:'#374151',fontWeight:700,textTransform:'uppercase',letterSpacing:'.1em',display:'block',marginBottom:2}}>Password</label>
                <input type="password" style={{width:'100%',padding:'5px 8px',fontSize:12,background:'#0f1629',border:'1px solid #1e293b',borderRadius:4,color:'#e2e8f0'}} placeholder="••••••" value={pwd} onChange={e=>setPwd(e.target.value)} disabled={running} autoComplete="new-password"/></div>
                <span style={{fontSize:8,color:'#166534',fontWeight:700,whiteSpace:'nowrap',paddingBottom:4}}>🔒 Masked from AI</span>
            </div>}
            <div style={{display:'flex',gap:8,alignItems:'flex-end'}}>
                <div style={{flex:1}}>
                    <label style={{fontSize:8,color:'#374151',fontWeight:700,textTransform:'uppercase',letterSpacing:'.1em',display:'block',marginBottom:2}}>Test Goal</label>
                    <input style={{width:'100%',padding:'5px 8px',fontSize:12,background:'#0f1629',border:'1px solid #1e293b',borderRadius:4,color:'#e2e8f0',fontFamily:'Inter'}}
                        placeholder='e.g. "Login, go to Orders, create new order with qty 5, verify success"'
                        value={nlp} onChange={e=>setNlp(e.target.value)} disabled={running} onKeyDown={e=>e.key==='Enter'&&ok&&start()}/>
                </div>
                {!running?
                    <button onClick={start} disabled={!ok} style={{padding:'5px 16px',fontSize:12,fontWeight:600,border:'none',borderRadius:4,background:'linear-gradient(135deg,#3b82f6,#2563eb)',color:'#fff',fontFamily:"'JetBrains Mono'",opacity:ok?1:.4,minWidth:90}}>▶ Generate</button>
                :<div style={{display:'flex',gap:3}}>
                    <button onClick={()=>{send({type:paused?'resume':'pause'});setPaused(!paused)}} style={{padding:'5px 10px',fontSize:12,border:'none',borderRadius:4,background:'#f59e0b',color:'#000',fontFamily:"'JetBrains Mono'",fontWeight:600}}>{paused?'▶':'⏸'}</button>
                    <button onClick={()=>{send({type:'stop'});setRunning(false)}} style={{padding:'5px 10px',fontSize:12,border:'none',borderRadius:4,background:'#ef4444',color:'#fff',fontFamily:"'JetBrains Mono'",fontWeight:600}}>■</button>
                </div>}
            </div>
        </div>

        {/* Main */}
        <div style={{flex:1,display:'flex',overflow:'hidden',minHeight:0}}>
            {/* Left 58% */}
            <div style={{flex:'0 0 58%',display:'flex',flexDirection:'column',overflow:'hidden'}}>
                {/* Screenshot */}
                <div style={{flex:'0 0 40%',padding:8,display:'flex',alignItems:'center',justifyContent:'center',background:'#060a12',borderBottom:'1px solid #111827',overflow:'hidden'}}>
                    {ss?<img src={`data:image/png;base64,${ss}`} style={{maxWidth:'100%',maxHeight:'100%',objectFit:'contain',borderRadius:3,border:'1px solid #111827'}}/>
                    :<div style={{textAlign:'center',opacity:.15}}><div style={{fontSize:40}}>🌐</div><div style={{fontSize:10,marginTop:4}}>Browser</div></div>}
                </div>

                {/* Status + Thinking */}
                {(status||thinking)&&<div style={{padding:'4px 12px',fontSize:10,background:'#0d1220',borderBottom:'1px solid #111827',display:'flex',alignItems:'center',gap:6,fontFamily:"'JetBrains Mono'",color:thinking?'#f59e0b':'#64748b',flexShrink:0}}>
                    {(running||thinking)&&<span style={{display:'inline-block',width:8,height:8,border:'2px solid #1e293b',borderTopColor:thinking?'#f59e0b':'#3b82f6',borderRadius:'50%',animation:'spin .6s linear infinite',flexShrink:0}}/>}
                    <span>{thinking||status}</span>
                </div>}

                {/* Actions List */}
                <div style={{flex:1,display:'flex',flexDirection:'column',overflow:'hidden'}}>
                    <div style={{padding:'4px 12px',fontSize:8,fontWeight:700,color:'#1e293b',textTransform:'uppercase',letterSpacing:'.08em',borderBottom:'1px solid #111827',flexShrink:0,fontFamily:"'JetBrains Mono'"}}>
                        Actions {actions.filter(a=>a.status==='success').length}/{actions.length}
                    </div>
                    <div ref={actRef} style={{flex:1,overflowY:'auto',padding:'2px 0'}}>
                        {actions.map((a,i)=>(
                            <div key={i} style={{display:'flex',alignItems:'flex-start',gap:7,padding:'3px 12px',borderLeft:`3px solid ${CC[a.status]||CC.pending}`,animation:'slideUp .25s ease',background:a.status==='running'?'#111827':'transparent'}}>
                                <span style={{fontSize:11,fontWeight:700,color:CC[a.status],fontFamily:"'JetBrains Mono'",flexShrink:0,width:13,textAlign:'center',marginTop:1,animation:a.status==='running'?'pulse 1s infinite':'none'}}>{IC[a.status]||IC.pending}</span>
                                <div style={{flex:1,minWidth:0}}>
                                    <div style={{display:'flex',alignItems:'baseline',gap:6}}>
                                        <span style={{fontSize:8,fontWeight:700,color:'#3b82f6',textTransform:'uppercase',fontFamily:"'JetBrains Mono'",flexShrink:0}}>{a.action}</span>
                                        <span style={{fontSize:11,color:'#cbd5e1',whiteSpace:'nowrap',overflow:'hidden',textOverflow:'ellipsis'}}>{a.description}</span>
                                    </div>
                                    {a.reasoning&&a.status==='running'&&<div style={{fontSize:9,color:'#4b5563',marginTop:1,fontStyle:'italic'}}>{a.reasoning}</div>}
                                    {a.error&&<div style={{fontSize:9,color:'#fca5a5',marginTop:1}}>✗ {a.error}</div>}
                                </div>
                            </div>
                        ))}
                        {actions.length===0&&!running&&<div style={{padding:20,textAlign:'center',color:'#1e293b',fontSize:11}}>Actions appear here as the AI executes</div>}
                    </div>
                </div>
            </div>

            <div style={{width:1,background:'#111827',flexShrink:0}}/>

            {/* Right 42% — Monaco */}
            <div style={{flex:'0 0 42%',display:'flex',flexDirection:'column',overflow:'hidden'}}>
                <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',padding:'4px 12px',borderBottom:'1px solid #111827',background:'#0a0f1c',flexShrink:0}}>
                    <span style={{fontSize:8,fontWeight:700,color:'#1e293b',textTransform:'uppercase',letterSpacing:'.06em',fontFamily:"'JetBrains Mono'"}}>{script?'✓ Generated':'RF Code'}</span>
                    {display&&<div style={{display:'flex',gap:3}}>
                        <button onClick={()=>{navigator.clipboard.writeText(display);setCopy('✓');setTimeout(()=>setCopy('Copy'),1500)}} style={{background:'#0f1629',border:'1px solid #1e293b',color:'#64748b',fontSize:9,padding:'2px 6px',borderRadius:3,fontFamily:"'JetBrains Mono'"}}>{copyLbl}</button>
                        <button onClick={()=>{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([display]));a.download=`test_${Date.now()}.robot`;a.click()}} style={{background:'#0f1629',border:'1px solid #1e293b',color:'#64748b',fontSize:9,padding:'2px 6px',borderRadius:3,fontFamily:"'JetBrains Mono'"}}>↓</button>
                    </div>}
                </div>
                <div style={{flex:1,overflow:'hidden',background:'#060a14'}}>
                    {display?<Editor value={display} hlLine={hl}/>
                    :<div style={{display:'flex',alignItems:'center',justifyContent:'center',height:'100%',color:'#111827',fontSize:10}}>Code builds here live</div>}
                </div>
            </div>
        </div>
    </div>);
}
ReactDOM.createRoot(document.getElementById('root')).render(<App/>);
</script>
</body></html>
