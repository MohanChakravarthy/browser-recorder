<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NLP Test Generator</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/react/18.2.0/umd/react.production.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/react-dom/18.2.0/umd/react-dom.production.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/babel-standalone/7.23.9/babel.min.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        *{margin:0;padding:0;box-sizing:border-box}
        html,body,#root{height:100%;width:100%;overflow:hidden}
        body{background:#0a0e1a;color:#e2e8f0}
        @keyframes spin{to{transform:rotate(360deg)}}
        @keyframes pulse{0%,100%{opacity:1}50%{opacity:.5}}
        @keyframes fadeIn{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:translateY(0)}}
        @keyframes glowPulse{0%{background:rgba(34,197,94,.15)}50%{background:rgba(34,197,94,.05)}100%{background:rgba(34,197,94,0)}}
        ::-webkit-scrollbar{width:5px}
        ::-webkit-scrollbar-track{background:#0a0e1a}
        ::-webkit-scrollbar-thumb{background:#1e293b;border-radius:3px}
        input:focus,textarea:focus{border-color:#3b82f6!important;outline:none}
        button{transition:all .12s}button:hover{filter:brightness(1.1)}button:active{transform:scale(.98)}
    </style>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.44.0/min/vs/loader.min.js"></script>
</head>
<body>
<div id="root"></div>
<script type="text/babel">
const{useState,useRef,useEffect,useCallback}=React;
const WS_BASE=`ws://${window.location.hostname||'localhost'}:${window.location.port||'8000'}`;
const ICONS={pending:"○",running:"◉",success:"✓",failed:"✗",skipped:"⊘"};
const COLORS={pending:"#4b5563",running:"#f59e0b",success:"#22c55e",failed:"#ef4444",skipped:"#6b7280"};

// ─── Monaco Editor with line highlighting ────────────────
function MonacoEditor({value,highlightLine}){
    const cRef=useRef(null);
    const edRef=useRef(null);
    const monacoRef=useRef(null);
    const decoRef=useRef([]);

    useEffect(()=>{
        if(!cRef.current)return;
        require.config({paths:{vs:'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.44.0/min/vs'}});
        require(['vs/editor/editor.main'],function(monaco){
            monacoRef.current=monaco;

            if(!monaco.languages.getLanguages().find(l=>l.id==='robot')){
                monaco.languages.register({id:'robot'});
                monaco.languages.setMonarchTokensProvider('robot',{
                    tokenizer:{root:[
                        [/^\*\*\*.*\*\*\*/,'keyword.section'],
                        [/\$\{[^}]+\}/,'variable'],
                        [/\[Documentation\]|\[Setup\]|\[Teardown\]|\[Tags\]|\[Template\]/,'keyword.tag'],
                        [/#\s*FAILED:.*$/,'error-line'],
                        [/#\s*WARNING:.*$/,'warning-line'],
                        [/#\s*MANUAL.*$/,'warning-line'],
                        [/#.*$/,'comment'],
                        [/Library|Resource|Variables|Suite Setup|Suite Teardown/,'keyword.setting'],
                        [/\b(New Browser|New Page|Close Browser|Click|Fill Text|Get Text|Get Url|Get Element States|Get Element Count|Get Title|Wait For Elements State|Check Checkbox|Uncheck Checkbox|Select Options By|Hover|Keyboard Key|Type Text|Go To|Go Back|Reload|Sleep|Wait For Load State|Log|Take Screenshot)\b/,'support.function'],
                        [/\b(==|!=|\*=|contains|visible|enabled|disabled|checked|hidden)\b/,'operator'],
                        [/\b(headless=true|headless=false|chromium|firefox|webkit)\b/,'constant'],
                        [/"[^"]*"/,'string'],
                        [/'[^']*'/,'string'],
                        [/SET_AT_RUNTIME/,'constant.warning'],
                    ]}
                });
            }

            monaco.editor.defineTheme('nlp-dark',{
                base:'vs-dark',inherit:true,
                rules:[
                    {token:'keyword.section',foreground:'60a5fa',fontStyle:'bold'},
                    {token:'variable',foreground:'c084fc'},
                    {token:'keyword.tag',foreground:'f472b6'},
                    {token:'keyword.setting',foreground:'60a5fa'},
                    {token:'support.function',foreground:'34d399',fontStyle:'bold'},
                    {token:'comment',foreground:'4b5563',fontStyle:'italic'},
                    {token:'string',foreground:'fbbf24'},
                    {token:'operator',foreground:'fb923c'},
                    {token:'constant',foreground:'f472b6'},
                    {token:'constant.warning',foreground:'f59e0b',fontStyle:'italic'},
                    {token:'error-line',foreground:'fca5a5',fontStyle:'italic'},
                    {token:'warning-line',foreground:'fbbf24',fontStyle:'italic'},
                ],
                colors:{
                    'editor.background':'#080c16',
                    'editor.foreground':'#e2e8f0',
                    'editor.lineHighlightBackground':'#1e293b30',
                    'editorLineNumber.foreground':'#1e293b',
                    'editorLineNumber.activeForeground':'#475569',
                    'editor.selectionBackground':'#3b82f640',
                    'editorCursor.foreground':'#3b82f6',
                    'editorGutter.background':'#080c16',
                    'scrollbarSlider.background':'#1e293b80',
                }
            });

            edRef.current=monaco.editor.create(cRef.current,{
                value:value||'',language:'robot',theme:'nlp-dark',readOnly:true,
                minimap:{enabled:false},fontSize:13,lineHeight:22,
                fontFamily:"'JetBrains Mono','Fira Code',monospace",
                fontLigatures:true,lineNumbers:'on',scrollBeyondLastLine:false,
                renderLineHighlight:'none',automaticLayout:true,
                padding:{top:12,bottom:12},
                scrollbar:{vertical:'auto',horizontal:'auto',verticalScrollbarSize:6,horizontalScrollbarSize:6},
                overviewRulerBorder:false,hideCursorInOverviewRuler:true,contextmenu:false,wordWrap:'on',
                renderWhitespace:'none',guides:{indentation:false},
            });
        });
        return()=>{if(edRef.current){edRef.current.dispose();edRef.current=null}};
    },[]);

    // Update content
    useEffect(()=>{
        if(!edRef.current||value===undefined)return;
        const model=edRef.current.getModel();
        if(model&&model.getValue()!==value){
            model.setValue(value);
            const lc=model.getLineCount();
            edRef.current.revealLine(lc);
        }
    },[value]);

    // Highlight latest line with glow animation
    useEffect(()=>{
        if(!edRef.current||!monacoRef.current||!highlightLine||highlightLine<1)return;
        const monaco=monacoRef.current;

        // Remove old decorations
        decoRef.current=edRef.current.deltaDecorations(decoRef.current,[
            {
                range:new monaco.Range(highlightLine,1,highlightLine,1),
                options:{
                    isWholeLine:true,
                    className:'highlight-new-line',
                    glyphMarginClassName:'highlight-glyph',
                }
            }
        ]);

        edRef.current.revealLineInCenter(highlightLine);

        // Remove highlight after animation
        const timer=setTimeout(()=>{
            if(edRef.current){
                decoRef.current=edRef.current.deltaDecorations(decoRef.current,[]);
            }
        },2000);
        return()=>clearTimeout(timer);
    },[highlightLine]);

    // Inject highlight CSS once
    useEffect(()=>{
        if(document.getElementById('monaco-highlight-css'))return;
        const style=document.createElement('style');
        style.id='monaco-highlight-css';
        style.textContent=`
            .highlight-new-line{animation:glowPulse 2s ease-out forwards;border-left:2px solid #22c55e}
            .highlight-glyph{background:transparent}
        `;
        document.head.appendChild(style);
    },[]);

    return <div ref={cRef} style={{width:'100%',height:'100%'}}/>;
}

// ─── App ─────────────────────────────────────────────────
function App(){
    const[connected,setConnected]=useState(false);
    const wsRef=useRef(null);

    const[nlp,setNlp]=useState("");
    const[url,setUrl]=useState("");
    const[user,setUser]=useState("");
    const[pwd,setPwd]=useState("");
    const[showCreds,setShowCreds]=useState(false);

    const[running,setRunning]=useState(false);
    const[paused,setPaused]=useState(false);
    const[steps,setSteps]=useState([]);
    const[statuses,setStatuses]=useState([]);
    const[curStep,setCurStep]=useState(-1);
    const[status,setStatus]=useState("");

    const[ss,setSs]=useState(null);
    const[rfLines,setRfLines]=useState([]);
    const[finalScript,setFinal]=useState("");
    const[liveScript,setLive]=useState("");
    const[hlLine,setHlLine]=useState(0);
    const[result,setResult]=useState(null);
    const[copyLbl,setCopyLbl]=useState("Copy");

    // Build live preview
    useEffect(()=>{
        if(finalScript)return;
        if(!rfLines.length)return;
        const lines=[
            "*** Settings ***","Library    Browser","",
            "*** Variables ***",
            `\${BASE_URL}    ${url||'https://...'}`,
            user?"${USERNAME}    SET_AT_RUNTIME":null,
            pwd?"${PASSWORD}    SET_AT_RUNTIME":null,
            "","*** Test Cases ***","NLP Generated Test",
            `    [Documentation]    ${nlp.slice(0,80)}`,
            "    New Browser    chromium    headless=true",
            "    New Page    ${BASE_URL}","",
            ...rfLines,"","    [Teardown]    Close Browser",
        ].filter(l=>l!==null).join("\n");
        setLive(lines);

        // Calculate highlight line: header lines + current rf line
        const headerCount=lines.split("\n").length-rfLines.length-1;
        setHlLine(headerCount+rfLines.length);
    },[rfLines,finalScript,url,nlp,user,pwd]);

    // When final script arrives, highlight last meaningful line
    useEffect(()=>{
        if(!finalScript)return;
        const lines=finalScript.split("\n");
        setHlLine(lines.length-2); // line before [Teardown]
    },[finalScript]);

    const connect=useCallback(()=>{
        if(wsRef.current?.readyState===WebSocket.OPEN)return;
        const ws=new WebSocket(`${WS_BASE}/nlp-test/ws`);
        wsRef.current=ws;
        ws.onopen=()=>setConnected(true);
        ws.onclose=()=>{setConnected(false);setRunning(false)};
        ws.onerror=()=>setConnected(false);
        ws.onmessage=e=>handleMsg(JSON.parse(e.data));
    },[]);

    const send=useCallback(m=>{
        if(wsRef.current?.readyState===WebSocket.OPEN)wsRef.current.send(JSON.stringify(m));
    },[]);

    const handleMsg=useCallback(d=>{
        switch(d.type){
            case"connected":break;
            case"status":setStatus(d.message);break;
            case"steps_planned":setSteps(d.steps);setStatuses(d.steps.map(()=>"pending"));break;
            case"step_start":
                setCurStep(d.index);
                setStatuses(p=>{const n=[...p];if(d.index>=0)n[d.index]="running";return n});
                setStatus(`Step ${d.index+1}: ${d.description}`);
                break;
            case"step_complete":
                if(d.screenshot_b64)setSs(d.screenshot_b64);
                if(d.rf_line)setRfLines(p=>[...p,d.rf_line]);
                setStatuses(p=>{const n=[...p];if(d.index>=0)n[d.index]=d.status==="skipped"?"skipped":"success";return n});
                break;
            case"step_failed":
                if(d.screenshot_b64)setSs(d.screenshot_b64);
                if(d.rf_line)setRfLines(p=>[...p,`    # FAILED: ${d.error?.slice(0,80)||'unknown'}`]);
                setStatuses(p=>{const n=[...p];if(d.index>=0)n[d.index]="failed";return n});
                setStatus(`✗ Step ${d.index+1}: ${d.error}`);
                break;
            case"rf_script_complete":setFinal(d.script);setStatus("✓ Script generated!");break;
            case"execution_complete":setRunning(false);setResult(d);break;
            case"error":setStatus(`Error: ${d.message}`);setRunning(false);break;
        }
    },[]);

    useEffect(()=>{connect();return()=>wsRef.current?.close()},[connect]);

    const start=()=>{
        if(!nlp.trim()||!url.trim())return;
        setSteps([]);setStatuses([]);setCurStep(-1);setRfLines([]);
        setFinal("");setLive("");setSs(null);setResult(null);setHlLine(0);
        setRunning(true);setPaused(false);
        send({type:"start",nlp_input:nlp.trim(),start_url:url.trim(),username:user.trim(),password:pwd.trim()});
    };

    const ok=nlp.trim()&&url.trim()&&connected&&!running;
    const script=finalScript||liveScript;

    return(
    <div style={S.box}>
        {/* Header */}
        <div style={S.hdr}>
            <div style={S.hdrL}>
                <div style={S.logo}>⚡</div>
                <h1 style={S.h1}>NLP Test Generator</h1>
                <div style={{...S.dot,background:connected?'#22c55e':'#ef4444'}}/>
            </div>
            <div style={S.hdrR}>
                {result&&<>
                    <span style={{...S.pill,background:'#052e16',color:'#4ade80'}}>{result.passed}✓</span>
                    {result.failed>0&&<span style={{...S.pill,background:'#2a0a0a',color:'#fca5a5'}}>{result.failed}✗</span>}
                </>}
            </div>
        </div>

        {/* Inputs */}
        <div style={S.inputs}>
            <div style={S.row}>
                <div style={{flex:1}}>
                    <label style={S.lbl}>Target URL</label>
                    <input style={S.inp} placeholder="https://your-app.com" value={url} onChange={e=>setUrl(e.target.value)} disabled={running}/>
                </div>
                <button style={{...S.credBtn,color:showCreds?'#3b82f6':'#4b5563'}} onClick={()=>setShowCreds(!showCreds)}>
                    🔑 {showCreds?'Hide':'Credentials'}
                </button>
            </div>

            {showCreds&&(
                <div style={{...S.row,animation:'fadeIn .2s ease'}}>
                    <div style={{flex:1}}>
                        <label style={S.lbl}>Username / Email</label>
                        <input style={S.inp} placeholder="user@example.com" value={user} onChange={e=>setUser(e.target.value)} disabled={running} autoComplete="off"/>
                    </div>
                    <div style={{flex:1}}>
                        <label style={S.lbl}>Password</label>
                        <input style={S.inp} type="password" placeholder="••••••••" value={pwd} onChange={e=>setPwd(e.target.value)} disabled={running} autoComplete="new-password"/>
                    </div>
                    <div style={S.lock}>🔒 Never sent to AI logs</div>
                </div>
            )}

            <div style={S.row}>
                <div style={{flex:1}}>
                    <label style={S.lbl}>Test Description</label>
                    <input style={S.inp} placeholder='e.g. "Login with credentials, go to orders, create new order with qty 5, verify success"'
                        value={nlp} onChange={e=>setNlp(e.target.value)} disabled={running}
                        onKeyDown={e=>e.key==="Enter"&&ok&&start()}/>
                </div>
                <div style={S.btns}>
                    {!running?(
                        <button style={{...S.btn,...S.btnGo,opacity:ok?1:.4}} onClick={start} disabled={!ok}>▶ Generate</button>
                    ):(<>
                        <button style={{...S.btn,...S.btnW}} onClick={()=>{send({type:paused?"resume":"pause"});setPaused(!paused)}}>{paused?"▶":"⏸"}</button>
                        <button style={{...S.btn,...S.btnD}} onClick={()=>{send({type:"stop"});setRunning(false);setPaused(false)}}>■</button>
                    </>)}
                </div>
            </div>
        </div>

        {/* Split */}
        <div style={S.split}>
            {/* Left */}
            <div style={S.left}>
                <div style={S.ssBox}>
                    {ss?<img src={`data:image/png;base64,${ss}`} alt="" style={S.ssImg}/>
                    :<div style={S.ph}><div style={{fontSize:44,opacity:.12}}>🌐</div><div style={S.phT}>Browser preview</div></div>}
                </div>

                {status&&<div style={S.stat}>{running&&<span style={S.spin}/>}{status}</div>}

                {steps.length>0&&(
                    <div style={S.stWrap}>
                        <div style={S.stHead}>Steps {statuses.filter(s=>s==="success"||s==="skipped").length}/{steps.length}</div>
                        <div style={S.stList}>
                            {steps.map((s,i)=>(
                                <div key={i} style={{...S.stRow,borderLeftColor:COLORS[statuses[i]]||COLORS.pending,background:curStep===i?'#111827':'transparent',animation:statuses[i]==="running"?"pulse 1.5s infinite":"none"}}>
                                    <span style={{...S.stIco,color:COLORS[statuses[i]]}}>{ICONS[statuses[i]]||ICONS.pending}</span>
                                    <span style={S.stAct}>{s.action}</span>
                                    <span style={S.stDsc}>{s.description}</span>
                                    {statuses[i]==="failed"&&<button style={S.retry} onClick={()=>{send({type:"retry_step",step_index:i});setStatuses(p=>{const n=[...p];n[i]="running";return n})}}>↻</button>}
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </div>

            <div style={S.div}/>

            {/* Right — Monaco */}
            <div style={S.right}>
                <div style={S.cHead}>
                    <span style={S.cTitle}>{finalScript?'✓ Generated .robot':rfLines.length?`Building... (${rfLines.length} lines)`:'RF Browser Code'}</span>
                    <div style={{display:'flex',gap:4}}>
                        {script&&<>
                            <button style={S.cBtn} onClick={()=>{navigator.clipboard.writeText(script);setCopyLbl("✓");setTimeout(()=>setCopyLbl("Copy"),2000)}}>{copyLbl}</button>
                            <button style={S.cBtn} onClick={()=>{const a=document.createElement("a");a.href=URL.createObjectURL(new Blob([script],{type:"text/plain"}));a.download=`test_${Date.now()}.robot`;a.click()}}>↓ .robot</button>
                        </>}
                    </div>
                </div>
                <div style={S.monaco}>
                    {script?<MonacoEditor value={script} highlightLine={hlLine}/>
                    :<div style={S.ph}><div style={{fontFamily:"'JetBrains Mono'",fontSize:28,opacity:.08}}>{"{ }"}</div><div style={S.phT}>Code builds here as steps execute</div></div>}
                </div>
            </div>
        </div>
    </div>
    );
}

const S={
    box:{width:'100%',height:'100vh',display:'flex',flexDirection:'column',background:'#0a0e1a',fontFamily:"'Inter',sans-serif",overflow:'hidden'},
    hdr:{display:'flex',alignItems:'center',justifyContent:'space-between',padding:'7px 16px',borderBottom:'1px solid #151b2e',flexShrink:0,background:'#0d1220'},
    hdrL:{display:'flex',alignItems:'center',gap:10},
    hdrR:{display:'flex',gap:6},
    logo:{fontSize:15,width:26,height:26,display:'flex',alignItems:'center',justifyContent:'center',background:'linear-gradient(135deg,#3b82f6,#8b5cf6)',borderRadius:6},
    h1:{fontSize:13,fontWeight:700,color:'#f1f5f9',fontFamily:"'JetBrains Mono',monospace",letterSpacing:'-.02em'},
    dot:{width:7,height:7,borderRadius:'50%'},
    pill:{fontSize:11,padding:'2px 8px',borderRadius:99,fontWeight:600,fontFamily:"'JetBrains Mono',monospace"},

    inputs:{padding:'8px 16px',borderBottom:'1px solid #151b2e',flexShrink:0,display:'flex',flexDirection:'column',gap:7,background:'#0d1220'},
    row:{display:'flex',gap:8,alignItems:'flex-end'},
    lbl:{display:'block',fontSize:9,color:'#4b5563',marginBottom:2,fontWeight:700,textTransform:'uppercase',letterSpacing:'.08em'},
    inp:{width:'100%',padding:'6px 10px',fontSize:12,background:'#111827',border:'1px solid #1e293b',borderRadius:4,color:'#e2e8f0',fontFamily:"'Inter',sans-serif"},
    credBtn:{background:'none',border:'1px solid #1e293b',borderRadius:4,padding:'6px 10px',fontSize:11,cursor:'pointer',fontFamily:"'Inter',sans-serif",whiteSpace:'nowrap',flexShrink:0},
    lock:{fontSize:9,color:'#22c55e',whiteSpace:'nowrap',padding:'0 0 5px 0',flexShrink:0,fontWeight:700},
    btns:{display:'flex',gap:4,flexShrink:0},
    btn:{padding:'6px 14px',fontSize:12,fontWeight:600,border:'none',borderRadius:4,cursor:'pointer',fontFamily:"'JetBrains Mono',monospace",whiteSpace:'nowrap'},
    btnGo:{background:'linear-gradient(135deg,#3b82f6,#2563eb)',color:'#fff',minWidth:100},
    btnW:{background:'#f59e0b',color:'#000',minWidth:32},
    btnD:{background:'#ef4444',color:'#fff',minWidth:32},

    split:{flex:1,display:'flex',overflow:'hidden',minHeight:0},
    div:{width:1,background:'#151b2e',flexShrink:0},

    left:{flex:'0 0 58%',display:'flex',flexDirection:'column',overflow:'hidden'},
    ssBox:{flex:'0 0 42%',padding:8,display:'flex',alignItems:'center',justifyContent:'center',background:'#070a14',borderBottom:'1px solid #151b2e',overflow:'hidden'},
    ssImg:{maxWidth:'100%',maxHeight:'100%',objectFit:'contain',borderRadius:3,border:'1px solid #1e293b'},
    ph:{textAlign:'center',display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'center',height:'100%',gap:4},
    phT:{fontSize:11,color:'#1e293b'},
    stat:{padding:'5px 12px',fontSize:10,color:'#94a3b8',background:'#111827',borderBottom:'1px solid #1e293b',display:'flex',alignItems:'center',gap:6,flexShrink:0,fontFamily:"'JetBrains Mono',monospace",lineHeight:1.4},
    spin:{display:'inline-block',width:9,height:9,border:'2px solid #1e293b',borderTopColor:'#3b82f6',borderRadius:'50%',animation:'spin .7s linear infinite',flexShrink:0},

    stWrap:{flex:1,display:'flex',flexDirection:'column',overflow:'hidden'},
    stHead:{padding:'5px 12px',fontSize:9,fontWeight:700,color:'#4b5563',textTransform:'uppercase',letterSpacing:'.06em',borderBottom:'1px solid #151b2e',flexShrink:0,fontFamily:"'JetBrains Mono',monospace"},
    stList:{flex:1,overflowY:'auto',padding:'1px 0'},
    stRow:{display:'flex',alignItems:'center',gap:7,padding:'3px 12px',borderLeft:'3px solid transparent'},
    stIco:{fontSize:11,fontWeight:700,width:13,textAlign:'center',flexShrink:0,fontFamily:"'JetBrains Mono',monospace"},
    stAct:{fontSize:8,fontWeight:700,color:'#3b82f6',textTransform:'uppercase',flexShrink:0,letterSpacing:'.04em',fontFamily:"'JetBrains Mono',monospace",minWidth:52},
    stDsc:{fontSize:11,color:'#cbd5e1',whiteSpace:'nowrap',overflow:'hidden',textOverflow:'ellipsis',flex:1,minWidth:0},
    retry:{background:'none',border:'1px solid #374151',color:'#f59e0b',fontSize:12,cursor:'pointer',borderRadius:3,padding:'0 5px',flexShrink:0},

    right:{flex:'0 0 42%',display:'flex',flexDirection:'column',overflow:'hidden'},
    cHead:{display:'flex',alignItems:'center',justifyContent:'space-between',padding:'5px 12px',borderBottom:'1px solid #151b2e',flexShrink:0,background:'#0d1220'},
    cTitle:{fontSize:9,fontWeight:700,color:'#4b5563',textTransform:'uppercase',letterSpacing:'.06em',fontFamily:"'JetBrains Mono',monospace"},
    cBtn:{background:'#111827',border:'1px solid #1e293b',color:'#94a3b8',fontSize:9,padding:'2px 7px',borderRadius:3,cursor:'pointer',fontFamily:"'JetBrains Mono',monospace"},
    monaco:{flex:1,overflow:'hidden',background:'#080c16'},
};

ReactDOM.createRoot(document.getElementById("root")).render(<App/>);
</script>
</body>
</html>
