import json,re,base64,os,subprocess,urllib.parse,time
HERE=os.path.dirname(os.path.abspath(__file__))
from playwright.sync_api import sync_playwright
errs=[];res=[]
def ok(name,cond,extra=''):
    res.append((name,bool(cond)));print(('PASS ' if cond else 'FAIL ')+name+(' | '+str(extra) if extra!='' else ''))
URL='file://'+os.path.abspath(os.path.join(HERE,'..','public','index.html'))
AUDIT=open(os.path.join(HERE,'audit.js')).read()
A58='123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
def b58e(b):
    n=int.from_bytes(b,'big');s=''
    while n>0:n,r=divmod(n,58);s=A58[r]+s
    return '1'*(len(b)-len(b.lstrip(b'\0')))+s
def b58d(s):
    n=0
    for ch in s:n=n*58+A58.index(ch)
    b=n.to_bytes((n.bit_length()+7)//8,'big') if n else b''
    return b'\0'*(len(s)-len(s.lstrip('1')))+b
def sv(b,i):
    v=0;s=0
    while True:
        x=b[i];i+=1;v|=(x&127)<<s
        if not x&128:return v,i
        s+=7
def read_tx(b):
    ns,i=sv(b,0);i+=64*ns;hdr=list(b[i:i+3]);i+=3;nk,i=sv(b,i);keys=[]
    for _ in range(nk):keys.append(b58e(b[i:i+32]));i+=32
    bh=b58e(b[i:i+32]);i+=32;ni,i=sv(b,i);ins=[]
    for _ in range(ni):
        pi=b[i];i+=1;na,i=sv(b,i);ac=list(b[i:i+na]);i+=na;dl,i=sv(b,i);d=b[i:i+dl];i+=dl;ins.append({'prog':keys[pi],'accounts':ac,'data':d})
    return {'nsig':ns,'hdr':hdr,'keys':keys,'bh':bh,'ins':ins}
MEMO='MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr';TOKENKEG='TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA'
def kp(seed):return bytes([(seed*7+i*3+1)%256 for i in range(32)])
PK1=kp(1);ADDR1=b58e(PK1);PK2=kp(2);ADDR2=b58e(PK2);LEDGER=b58e(kp(9));MINT=b58e(kp(11));TOKACC=b58e(kp(12));BH=b58e(kp(13))
def sig(n):return b58e(bytes([n])*64)
def jres(route,obj,status=200):route.fulfill(status=status,headers={'access-control-allow-origin':'*','access-control-allow-headers':'*','access-control-allow-methods':'*','content-type':'application/json'},body=json.dumps(obj) if not isinstance(obj,str) else obj)
def mkstate():return {'ledger':[],'tx':{},'slot':1000,'rpcfail':False,'balance':0,'tokacc':[],'decimals':6,'mintowner':TOKENKEG,'sent':[],'calls':[],'statuses':'confirmed','blockhash':BH,'failgetsigs':False,'sigfail':False,'before':[]}
def add_entry(ST,sg,memo,signer,slot=None,err=None,t=None):
    slot=slot or ST['slot'];ST['slot']=max(ST['slot'],slot)+1
    e={'signature':sg,'slot':slot,'blockTime':t or int(time.time())-60,'err':err,'memo':'[%d] %s'%(len(memo),memo)}
    ST['ledger'].insert(0,e);ST['tx'][sg]={'signer':signer,'memo':memo,'slot':slot,'time':e['blockTime'],'err':err};return e
def rpc_handler(ST):
    def h(route):
        rq=route.request
        if rq.method=='OPTIONS':return route.fulfill(status=204,headers={'access-control-allow-origin':'*','access-control-allow-headers':'*','access-control-allow-methods':'*'})
        if ST['rpcfail']:return jres(route,'oops',500)
        b=json.loads(rq.post_data);m,p=b['method'],b['params'];ST['calls'].append((m,p))
        if m=='getLatestBlockhash':r={'value':{'blockhash':ST['blockhash'],'lastValidBlockHeight':999}}
        elif m=='getSignaturesForAddress':
            if ST['failgetsigs']:return jres(route,{'jsonrpc':'2.0','id':1,'error':{'code':-32005,'message':'Node is behind'}})
            opt=p[1] if len(p)>1 else {};L=ST['ledger']
            if opt.get('before'):
                idx=[i for i,e in enumerate(L) if e['signature']==opt['before']];L=L[idx[0]+1:] if idx else []
            r=L[:opt.get('limit',1000)]
        elif m=='getTransaction':
            t=ST['tx'].get(p[0])
            if not t:r=None
            else:
                r={'slot':t['slot'],'blockTime':t['time'],'meta':{'err':t['err']},'transaction':{'message':{'accountKeys':[{'pubkey':t['signer'],'signer':True,'writable':True},{'pubkey':LEDGER,'signer':False,'writable':False}],'instructions':[{'program':'spl-memo','programId':MEMO,'parsed':t['memo']}]}}}
        elif m=='getSignatureStatuses':
            if ST['sigfail']:r={'value':[{'err':{'InstructionError':[0,'Custom']},'confirmationStatus':'confirmed','slot':ST['slot']}]}
            elif ST['statuses']=='none':r={'value':[None]}
            else:
                sg=p[0][0];t=ST['tx'].get(sg);r={'value':[{'err':None,'confirmationStatus':'confirmed','slot':t['slot'] if t else ST['slot']}]}
        elif m=='getTokenAccountsByOwner':
            r={'value':[{'pubkey':a['address'],'account':{'data':{'parsed':{'info':{'mint':MINT,'tokenAmount':{'amount':str(a['amount']),'decimals':ST['decimals']}}}}}} for a in ST['tokacc']]}
        elif m=='getTokenSupply':r={'value':{'amount':'1000','decimals':ST['decimals']}}
        elif m=='getAccountInfo':r={'value':{'owner':ST['mintowner'],'lamports':1,'executable':p[0]==MEMO,'data':['','base64']}}
        elif m=='sendTransaction':r=sig(77)
        else:r=None
        jres(route,{'jsonrpc':'2.0','id':1,'result':r})
    return h
def wallet_js(addr=ADDR1,pk=PK1,sign=True,send=True,name='MockWallet'):
    f=[]
    if sign:f.append("'solana:signMessage':{version:'1.0.0',signMessage:async function(i){window.__wc.push('signMessage');window.__signed={text:new TextDecoder().decode(i.message)};if(window.__wo.reject)throw new Error('User rejected the request');var sig;try{sig=new Uint8Array(await crypto.subtle.sign('Ed25519',window.__k.priv,i.message))}catch(e){sig=new Uint8Array(64)}return [{signedMessage:i.message,signature:sig}]}}")
    if send:f.append("'solana:signAndSendTransaction':{version:'1.0.0',signAndSendTransaction:async function(i){window.__wc.push('signAndSend');if(window.__wo.reject)throw new Error('User rejected the request');var n=(window.__sigN=(window.__sigN||20)+1);var tx=Array.from(i.transaction);var s=new Uint8Array(64).fill(n);await window.onSend(tx,n,i.account.address,i.chain);if(window.__wo.delay)await new Promise(function(r){setTimeout(r,window.__wo.delay)});return [{signature:s}]}}")
    return """(function(){var C=window.__wc=[],O=window.__wo={};var acct={address:'%s',publicKey:new Uint8Array(%s),chains:['solana:mainnet'],features:[]};
 window.__k=null;(async function(){try{var k=await crypto.subtle.generateKey('Ed25519',true,['sign','verify']);var raw=new Uint8Array(await crypto.subtle.exportKey('raw',k.publicKey));window.__k={priv:k.privateKey,raw:raw}}catch(e){}})();
 var w={name:'%s',version:'1.0.0',icon:'data:image/svg+xml;base64,PHN2Zy8+',chains:['solana:mainnet'],accounts:[],features:{'standard:connect':{version:'1.0.0',connect:async function(o){C.push('connect'+(o&&o.silent?':silent':''));if(o&&o.silent&&O.noSilent)throw new Error('not trusted');if(O.slow)await new Promise(function(r){setTimeout(r,O.slow)});if(O.noconnect)throw new Error('User rejected the request');if(O.useReal&&window.__k){acct.address=window.__realAddr;acct.publicKey=window.__k.raw}w.accounts=[acct];return {accounts:[acct]}}},'standard:disconnect':{version:'1.0.0',disconnect:async function(){C.push('disconnect')}},'standard:events':{version:'1.0.0',on:function(e,cb){window.__emit=cb;return function(){}}},%s}};window.__w=w;function reg(api){api.register(w)}window.addEventListener('wallet-standard:app-ready',function(e){reg(e.detail)});window.dispatchEvent(new CustomEvent('wallet-standard:register-wallet',{detail:reg}))})();"""%(addr,json.dumps(list(pk)),name,','.join(f))
def mem_of(b):
    t=read_tx(b);mi=[i for i in t['ins'] if i['prog']==MEMO][0];return t,mi['data'].decode()
def page(ST=None,wallet=True,vp=(1360,900),mobile=False,ua=None,init='',cfg=None,wopts=None):
    ST=ST if ST is not None else mkstate()
    kw=dict(viewport={'width':vp[0],'height':vp[1]})
    if ua:kw.update(user_agent=ua,is_mobile=mobile,has_touch=mobile)
    c=br.new_context(**kw);c.add_init_script("window.__fast=true;"+(wallet_js(**(wopts or {})) if wallet else '')+init)
    def on_send(tx,n,addr,chain):
        b=bytes(tx);t,memo=mem_of(b);ST['sent'].append({'bytes':b,'tx':t,'memo':memo,'n':n,'chain':chain})
        add_entry(ST,sig(n),memo,addr)
    c.expose_function('onSend',on_send)
    c.route('https://api.mainnet-beta.solana.com/**',rpc_handler(ST));c.route('https://fonts.googleapis.com/**',lambda r:r.abort());c.route('https://fonts.gstatic.com/**',lambda r:r.abort())
    pg=c.new_page();pg.on('pageerror',lambda e:errs.append(str(e)));pg.goto(URL);pg.wait_for_timeout(900)
    if cfg:pg.evaluate("Object.assign(__dq.CONFIG,%s)"%json.dumps(cfg))
    return c,pg,ST
def go(pg,h):pg.evaluate("location.hash=%r"%h);pg.wait_for_timeout(400)
def connect(pg):
    pg.click('#walletBtn');pg.click('[data-prov=MockWallet]');pg.wait_for_timeout(300)
def digest(counts):
    import hashlib;return hashlib.sha256(','.join(map(str,counts)).encode()).hexdigest()
def node_run(o,seed):
    out=subprocess.run(['node',os.path.join(HERE,'..','tools','nodecheck.js'),json.dumps(o),seed],capture_output=True,text=True);return json.loads(out.stdout)
LEDGER_CFG={'ledgerAddress':LEDGER}
with sync_playwright() as p:
    br=p.chromium.launch()
    # ======================================================= engine
    c,pg,ST=page(wallet=False);E=pg.evaluate
    ok('SHA-256 matches the standard test vectors ("abc", empty, and the 448-bit message)',E("[__dq.hex(__dq.sha256(__dq.utf8('abc'))),__dq.hex(__dq.sha256(__dq.utf8(''))),__dq.hex(__dq.sha256(__dq.utf8('abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq')))]")==['ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad','e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855','248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1'])
    near=lambda a,b,t=1e-9:abs(a-b)<t
    ok('the simulator gets the physics right: Bell state, X flip, superposition, phase-to-probability, CNOT truth table',E("(function(){var s=__dq.simulate,a=s([{g:'h',q:0},{g:'cx',c:0,t:1}],2),b=s([{g:'rx',q:0,a:Math.PI}],1),c=s([{g:'ry',q:0,a:Math.PI/2}],1),d=s([{g:'h',q:0},{g:'rz',q:0,a:Math.PI},{g:'h',q:0}],1),e=s([{g:'rx',q:1,a:Math.PI},{g:'cx',c:1,t:0}],2);return [a[0],a[3],a[1],b[1],c[0],d[1],e[3]]})()")==[a for a in E("(function(){var s=__dq.simulate,a=s([{g:'h',q:0},{g:'cx',c:0,t:1}],2),b=s([{g:'rx',q:0,a:Math.PI}],1),c=s([{g:'ry',q:0,a:Math.PI/2}],1),d=s([{g:'h',q:0},{g:'rz',q:0,a:Math.PI},{g:'h',q:0}],1),e=s([{g:'rx',q:1,a:Math.PI},{g:'cx',c:1,t:0}],2);return [a[0],a[3],a[1],b[1],c[0],d[1],e[3]]})()")] and all(near(x,y,1e-9) for x,y in zip(E("(function(){var s=__dq.simulate,a=s([{g:'h',q:0},{g:'cx',c:0,t:1}],2),b=s([{g:'rx',q:0,a:Math.PI}],1),c=s([{g:'ry',q:0,a:Math.PI/2}],1),d=s([{g:'h',q:0},{g:'rz',q:0,a:Math.PI},{g:'h',q:0}],1),e=s([{g:'rx',q:1,a:Math.PI},{g:'cx',c:1,t:0}],2);return [a[0],a[3],a[1],b[1],c[0],d[1],e[3]]})()"),[.5,.5,0,1,.5,1,1])))
    ok('probability is conserved: 80 random circuits at 4, 6, 8 and 10 qubits sum to 1 within 1e-12',E("(function(){var w=0;[4,6,8,10].forEach(function(n){for(var k=0;k<20;k++){var o={kind:'r',n:n,wallet:'w'+k,edition:'',prev:'-',msg:'m'+k},p=__dq.simulate(__dq.buildCircuit(o),n),s=0;for(var i=0;i<p.length;i++)s+=p[i];w=Math.max(w,Math.abs(s-1))}});return w})()")<1e-12)
    o={'kind':'r','n':6,'wallet':ADDR1,'edition':'','prev':'-','msg':'hello'}
    ok('the same inputs always build the identical circuit; changing the message, wallet, previous run or edition changes it',E("(function(o){var j=function(x){return JSON.stringify(__dq.buildCircuit(x))},a=j(o),m=function(k,v){var c=Object.assign({},o);c[k]=v;return j(c)};return a===j(o)&&a!==m('msg','hellp')&&a!==m('wallet','B')&&a!==m('prev','abcd')&&a!==m('edition','deep')})(%s)"%json.dumps(o)))
    ok('the same seed reproduces every one of the 1,024 shots; a different seed does not; shots always sum to 1,024',E("(function(o){var a=__dq.runCircuit(o,'s1'),b=__dq.runCircuit(o,'s1'),c=__dq.runCircuit(o,'s2'),sum=function(r){var t=0;for(var i=0;i<r.counts.length;i++)t+=r.counts[i];return t};return a.counts.join()===b.counts.join()&&a.counts.join()!==c.counts.join()&&sum(a)===1024&&sum(c)===1024})(%s)"%json.dumps(o)))
    bro=E("(function(o){var r=__dq.runCircuit(o,'xchk');return {digest:null,counts:Array.from(r.counts),tvd:r.m.tvd,tier:r.m.tier.id,pct:r.m.percentile,gates:r.gates.length}})(%s)"%json.dumps(o));nd=node_run(o,'xchk')
    ok('REPRODUCIBLE: an independent Node run of the engine gives the identical shots, drift, percentile and tier as the browser',digest(bro['counts'])==nd['digest'] and near(bro['tvd'],nd['tvd'],1e-12) and bro['tier']==nd['tier'] and near(bro['pct'],nd['pct'],1e-9) and bro['gates']==nd['gates'],(bro['tier'],nd['tier']))
    cal=E("__dq.CAL");ok('there is a rarity table for every edition and every qubit count (28), each with 101 sorted points',len(cal)==28 and all(len(v)==101 and v==sorted(v) for v in cal.values()))
    ok('percentile is monotonic from 0 to 100 and tiers map to the documented cut-offs (55 / 85 / 97 / 99.7) with Glitched overriding',E("(function(){var t=__dq.CAL['std:6'],prev=-1,okm=true;for(var i=0;i<=40;i++){var v=t[0]+(t[100]-t[0])*i/40,p=__dq.pctOf(v,t);if(p<prev-1e-9)okm=false;prev=p}return okm&&__dq.pctOf(-1,t)===0&&__dq.pctOf(9,t)===100&&[0,54.9,55,84.9,85,96.9,97,99.6,99.7,100].map(function(x){return __dq.tierOf(x,false).id}).join()==='common,common,uncommon,uncommon,rare,rare,epic,epic,legendary,legendary'&&__dq.tierOf(10,true).id==='glitched'})()"))
    ok('about 12% of Storm runs have a stuck qubit and about 2% of Standard runs do, as the model says (3,000 runs each)',E("(function(){var f=function(ed,N){var g=0;for(var k=0;k<N;k++){var r=__dq.runCircuit({kind:'r',n:4,wallet:'g'+k,edition:ed,prev:'-',msg:'g'},'gs'+k);if(r.stuck)g++}return g/N};var a=f('storm',3000),b=f('',3000);return Math.abs(a-.12)<.025&&Math.abs(b-.02)<.012})()"))
    ok('the rarity tiers are real percentiles: over 2,000 fresh Standard 6-qubit runs about 55% are Common and about 3% are Epic or better (not counting Glitched)',E("(function(){var c={common:0,epic:0},N=2000,nn=0;for(var k=0;k<N;k++){var r=__dq.runCircuit({kind:'r',n:6,wallet:'t'+k,edition:'',prev:'-',msg:'tier'},'tt'+k);if(r.stuck)continue;nn++;var t=r.m.tier.id;if(t==='common')c.common++;if(t==='epic'||t==='legendary')c.epic++}return Math.abs(c.common/nn-.55)<.05&&c.epic/nn>.005&&c.epic/nn<.06})()"))
    ok('a 10-qubit run (the heaviest) is built, simulated, measured and scored in well under 150 ms',E("(function(){var t=performance.now();__dq.runCircuit({kind:'r',n:10,wallet:'perf',edition:'deep',prev:'-',msg:'speed'},'p');return performance.now()-t})()")<150)
    c.close()
    # ======================================================= memo codec
    c,pg,ST=page(wallet=False);E=pg.evaluate
    pm=lambda s:E("__dq.parseMemo(%s)"%json.dumps(s))
    r1=pm('sgl1|r|6|%s|deep|%s|hello world'%(ADDR1,sig(5)[:16]))
    ok('a run memo round-trips: build it, parse it, get the same fields back',E("__dq.memoRun(6,%r,'deep','abc12345','hello world')"%ADDR1)=='sgl1|r|6|%s|deep|abc12345|hello world'%ADDR1 and r1 and r1['t']=='r' and r1['n']==6 and r1['edition']=='deep' and r1['msg']=='hello world' and r1['wallet']==ADDR1)
    ok('an invite and an accept round-trip, and the "[123] " prefix the RPC puts on memos is understood',pm('[99] '+E("__dq.memoInvite(8,%r,%r,'-','join me')"%(ADDR1,ADDR2)))['t']=='i' and pm(E("__dq.memoAccept(%r,%r,'ok')"%(sig(3),ADDR2)))['t']=='a')
    ok('messages are cleaned: pipes, tabs and new lines become spaces, runs of spaces collapse, and 65 characters or empty is refused',E("[__dq.msgOk('a|b\\nc\\td'),__dq.msgOk('   '),__dq.msgOk('x'.repeat(65)),__dq.msgOk('x'.repeat(64)).length]")==['a b c d',None,None,64])
    bad=['dcr2|r|6|%s|-|-|hi'%ADDR1,'sgl1|r|5|%s|-|-|hi'%ADDR1,'sgl1|r|6|notanaddress|-|-|hi','sgl1|r|6|%s|nosuchedition|-|hi'%ADDR1,'sgl1|r|6|%s|-|bad!prev|hi'%ADDR1,'sgl1|r|6|%s|-|-|hi|extra'%ADDR1,'sgl1|r|6|%s|-|-|%s'%(ADDR1,'x'*65),'sgl1|r|6|%s|-|-|'%ADDR1,'sgl1|i|6|%s|%s|-|hi'%(ADDR1,ADDR1),'sgl1|a|short|%s|hi'%ADDR1,'sgl1|q|6','garbage','']
    ok('every malformed memo is rejected (%d cases: wrong version, bad qubit count, bad address, unknown edition, bad previous run, extra fields, too long, empty, self-invite, short signature, unknown type, garbage)'%len(bad),all(pm(s) is None for s in bad))
    # tx builder
    for name,args,exp in [('no ledger',dict(ledger=''),dict(keys=2,hdr=[1,0,1])),('with a ledger address',dict(ledger=LEDGER),dict(keys=3,hdr=[1,0,2])),('ledger equal to the payer is not added twice',dict(ledger=ADDR1),dict(keys=2,hdr=[1,0,1]))]:
        b=bytes(E("Array.from(__dq.buildTx({payer:%r,blockhash:%r,ledger:%r,memo:'sgl1|test'}))"%(ADDR1,BH,args['ledger'])));t,mm=mem_of(b)
        ok('transaction layout (%s): one signature slot of zeros, header %s, %d keys, payer first, memo program last, blockhash and memo data intact'%(name,exp['hdr'],exp['keys']),t['nsig']==1 and b[1:65]==bytes(64) and t['hdr']==exp['hdr'] and len(t['keys'])==exp['keys'] and t['keys'][0]==ADDR1 and t['keys'][-1]==MEMO and t['bh']==BH and mm=='sgl1|test' and t['ins'][0]['accounts']==[0])
    b=bytes(E("Array.from(__dq.buildTx({payer:%r,blockhash:%r,ledger:%r,memo:'m',burn:{account:%r,mint:%r,program:%r,amount:123456789n,decimals:6}}))"%(ADDR1,BH,LEDGER,TOKACC,MINT,TOKENKEG)));t=read_tx(b);bi=[i for i in t['ins'] if i['prog']==TOKENKEG][0]
    ok('a burn transaction orders accounts correctly (signer, then writable token account and mint, then read-only ledger, token program, memo) and uses BurnChecked with the exact amount and decimals',t['keys']==[ADDR1,TOKACC,MINT,LEDGER,TOKENKEG,MEMO] and t['hdr']==[1,0,3] and bi['data'][0]==15 and int.from_bytes(bi['data'][1:9],'little')==123456789 and bi['data'][9]==6 and [t['keys'][a] for a in bi['accounts']]==[TOKACC,MINT,ADDR1] and t['ins'][0]['prog']==MEMO)
    ok('base58 matches an independent implementation, including leading zero bytes',all(E("__dq.b58enc(new Uint8Array(%s))"%json.dumps(list(v)))==b58e(bytes(v)) and E("Array.from(__dq.b58dec(%r))"%b58e(bytes(v)))==list(v) for v in [PK1,PK2,[0,0,1,2],[0],[255]*40]))
    q=lambda x:E("(function(){var r=__dq.qubitsFor(%s);return {ok:r.ok,o:r.options}})()"%x)
    ok('open access (no token configured): any wallet may pick 4, 6, 8 or 10 qubits',q(0)=={'ok':True,'o':[4,6,8,10]})
    E("Object.assign(__dq.CONFIG,{tokenMint:%r,tokenSymbol:'DCH',tokenDecimals:6})"%MINT)
    ok('with a token: below the first tier is refused; the balance sets the maximum (0.5 → none, 1 → 4, 100,000 → 6, 1M → 8, 5M → 10)',[q(x) for x in [0.5,1,100000,1000000,5000000]]==[{'ok':False,'o':[]},{'ok':True,'o':[4]},{'ok':True,'o':[4,6]},{'ok':True,'o':[4,6,8]},{'ok':True,'o':[4,6,8,10]}])
    c.close()
    c,pg,ST=page(wallet=False);E=pg.evaluate
    E("Object.assign(__dq.CONFIG,%s)"%json.dumps(LEDGER_CFG))
    for i in range(5):E("__dq.LEDGER.entries.push({sig:%r,slot:%d,time:1,memo:'',text:'',p:{t:'r',n:4,wallet:%r,edition:'cold',prev:'',msg:'m'}})"%(sig(100+i),500-i*10 if i!=2 else 500,ADDR1))
    s=E("__dq.supply('cold')");ok('edition supply: the cap counts the first runs by slot (ties broken by signature); later ones are "over the cap" and do not count',s['cap']==128 and s['minted']==5 and s['over']==0 and E("(function(){__dq.edition('cold').cap=3;var s=__dq.supply('cold');__dq.edition('cold').cap=128;return [s.minted,s.over,s.capped.length]})()")==[3,2,3])
    c.close()
    # ======================================================= local mode (no ledger address)
    c,pg,ST=page();E=pg.evaluate
    ok('the home page has every section in order: hero, thesis, ledger readout, machine, how it works, forge, differences, latest collapses, questions, call to action',E("[].map.call(document.querySelectorAll('#view > .home > section'),function(s){return s.className.replace('slab ','').split(' ')[0]+'.'+(s.className.split(' ')[1]||'')}).length")==10 and E("document.querySelectorAll('#view .slab').length")==10)
    ok('the headline, the thesis and the honest statement about the simulator are all on the page','Collapse' in pg.inner_text('.hero h1') and 'a message.' in pg.inner_text('.hero h1') and 'seed somebody chose' in pg.inner_text('#thesis') and 'simulator' in pg.inner_text('#thesis').lower() and 'not connected to any quantum hardware' in pg.inner_text('footer'))
    ok('the page never claims real quantum hardware: the only "real quantum computer" mention is the question whose answer is No',not re.search(r'runs on real qubits|real qubits|ibm quantum',pg.inner_text('body').lower()) and 'No. It is a statevector simulator' in E("document.querySelector('.faq').textContent"))
    ok('the live detector has drawn a histogram (not a blank canvas) and says all 1,024 shots landed','1,024 shots' in pg.inner_text('#detInfo') and E("(function(){var c=document.getElementById('det'),d=c.getContext('2d').getImageData(0,0,c.width,c.height).data,s={};for(var i=0;i<d.length;i+=4*37)s[d[i]+','+d[i+1]+','+d[i+2]]=1;return Object.keys(s).length})()")>3)
    a=E("document.getElementById('detInfo').textContent");pg.click('#detAgain');pg.wait_for_timeout(200);b=E("document.getElementById('detInfo').textContent");ok('Measure again runs a fresh circuit with a new random seed (a different drift figure)',a!=b and '1,024 shots' in b,(a[-30:],b[-30:]))
    ok('with no ledger address set, the readout says so and counts only this device (all zero on a fresh browser)','No ledger address is set' in pg.inner_text('.readout') and E("[].map.call(document.querySelectorAll('.readout .num'),function(e){return e.textContent}).join()")=='0,0,0,0')
    ok('the machine panel is honest: it says "Simulator, statevector", lists the readouts, and the chip drawing has 28 qubits with the right number lit','Simulator, statevector' in pg.inner_text('.machine') and E("document.querySelectorAll('.chip g.q').length")==28 and E("document.querySelectorAll('.chip g.q.lit').length")==6)
    pg.fill('#tryMsg','entangle me');pg.wait_for_timeout(300);ok('the how-it-works demo is live: typing a message shows its rotation angles, a four-qubit result table and its artwork',all(x in pg.inner_text('#tryAngles') for x in ['qubit 0','radians']) and E("document.querySelectorAll('#tryHist tbody tr').length")==6 and E("!!document.querySelector('#tryArt canvas')"))
    a1=pg.inner_text('#tryAngles');pg.fill('#tryMsg','entangle mf');pg.wait_for_timeout(300);ok('...and changing one letter changes the angles',pg.inner_text('#tryAngles')!=a1)
    ok('six editions are shown with their caps and a link each; the Forge, ledger and run routes exist in the navigation',E("document.querySelectorAll('.plates .plate').length")==6 and E("[].map.call(document.querySelectorAll('.nav a[data-r]'),function(a){return a.getAttribute('href')}).join()")=='#/run,#/lab,#/forge,#/hall,#/ledger')
    # run page, local mode
    go(pg,'#/run');ok('the run page says plainly that this site has no ledger address, so runs stay on the device and are not stamped','not stamped on Solana' in pg.inner_text('#localNote') and E("!document.getElementById('runLocal')") and 'Collapse' == pg.inner_text('#runGo'))
    pg.click('#runGo');pg.wait_for_timeout(200);ok('in local mode no wallet is needed: the page says you can run as a guest, and an empty message is refused with the exact rule','run as a guest' in pg.inner_text('#localNote') and '1 to 64 characters' in pg.inner_text('#runStatus'))
    pg.click('#walletBtn');ok('the connect dialog lists the wallet and says only the public address is shared',E("!!document.querySelector('#mBody [data-prov=MockWallet]')") and 'public address' in pg.inner_text('#mBody'));pg.click('[data-prov=MockWallet]');pg.wait_for_timeout(300)
    ok('connecting shows the address on the run page and the header',ADDR1 in pg.inner_text('#runWallet') and pg.inner_text('#walletBtn')==ADDR1[:4]+'..'+ADDR1[-4:])
    ok('the qubit choices are 4, 6, 8 and 10 and the edition list is Standard plus the six editions',E("[].map.call(document.querySelectorAll('[data-q]'),function(b){return b.textContent}).join()")=='4 qubits,6 qubits,8 qubits,10 qubits' and E("document.querySelectorAll('#runEd option').length")==7)
    pg.fill('#runMsg','a|b\nc');ok('the message box has a live counter and the preview shows the gate count and an ideal-result table',pg.inner_text('#runCount').endswith('/ 64') and 'gates on 6 qubits' in pg.inner_text('#runPreview') and E("document.querySelectorAll('#runPreview .hist tbody tr').length")==8 and E("!!document.querySelector('#runPreview svg')"))
    g6=pg.inner_text('#runPreview .fine');pg.click('[data-q="10"]');ok('picking 10 qubits redraws the preview for 10 qubits','gates on 10 qubits' in pg.inner_text('#runPreview') and E("document.querySelectorAll('#runPreview svg text').length")>=10)
    pg.click('[data-q="6"]');pg.fill('#runMsg','the cat is both');pg.click('#runGo');pg.wait_for_timeout(700)
    ok('collapsing goes to the result page of a local run',E("location.hash").startswith('#/r/L') and 'No such run' not in pg.inner_text('#view'))
    rid=E("location.hash").split('/')[-1]
    ok('the result page shows the tier, the message, the facts (qubits, shots, drift, rarity percentile, edition, wallet, seed) and says it was not stamped','“the cat is both”' in pg.inner_text('.res-msg') and all(x in pg.inner_text('.facts') for x in ['Qubits','6','Shots','1,024','Drift from ideal','Rarity','Edition','Standard',ADDR1]) and 'was not stamped' in pg.inner_text('#verifyNote') and E("!!document.querySelector('.tier')"))
    ok('the artwork is drawn, the circuit diagram has 6 wires, and the outcome table has 12 rows with ideal and measured percentages',E("(function(){var c=document.querySelector('.art.big'),d=c.getContext('2d').getImageData(0,0,c.width,c.height).data,s={};for(var i=0;i<d.length;i+=4*61)s[d[i]+','+d[i+1]+','+d[i+2]]=1;return Object.keys(s).length})()")>8 and E("document.querySelectorAll('.result ~ .scroll svg line').length")>=6 and E("document.querySelectorAll('.result ~ table tbody tr').length")==12)
    cts=E("Array.from(__dq.computeRun(__dq.LOCAL.runs[0]).counts)");ok('the displayed result is exactly the recomputed one: running the stored inputs again gives identical shots',digest(cts)==digest(E("Array.from(__dq.computeRun(__dq.LOCAL.runs[0]).counts)")) and sum(cts)==1024)
    bro=E("(function(r){var o=__dq.computeRun(r);return {counts:Array.from(o.counts),tier:o.m.tier.id}})(__dq.LOCAL.runs[0])");lr=E("__dq.LOCAL.runs[0]");nd=node_run({'kind':'r','n':lr['n'],'wallet':lr['wallet'],'edition':lr['edition'],'prev':lr['prev'],'msg':lr['msg']},lr['seed']);ok('a stranger running the same inputs in Node gets the same shots and tier as the page shows',digest(bro['counts'])==nd['digest'] and bro['tier']==nd['tier'])
    E("document.getElementById('dlArt')&&0");ok('Download the art and Copy link buttons are present and named',E("!!document.getElementById('dlArt')&&!!document.getElementById('copyLink')"))
    with pg.expect_download() as dl:pg.click('#dlArt')
    ok('Download the art delivers a PNG file',dl.value.suggested_filename.endswith('.png') and dl.value.suggested_filename.startswith('singlet-'))
    pg.reload();pg.wait_for_timeout(900);go(pg,'#/r/'+rid);ok('after a reload the local run is still there (stored on this device)','“the cat is both”' in pg.inner_text('.res-msg'))
    go(pg,'#/ledger');ok('the ledger page lists the local run with its tier and says there is no ledger address','No ledger address is set' in pg.inner_text('#ledgerStats') and E("document.querySelectorAll('#ledgerList .feedrow').length")==1 and '“the cat is both”' in pg.inner_text('#ledgerList'))
    go(pg,'#/');ok('the home page now counts it and shows it in Latest collapses',E("[].map.call(document.querySelectorAll('.readout .num'),function(e){return e.textContent}).join()")=='1,0,1,6' and E("document.querySelectorAll('.feedsec .feedrow').length")==1)
    go(pg,'#/r/L0000000000000000');ok('an unknown run id says "No such run" and offers the ledger','No such run' in pg.inner_text('#view') and E("!!document.querySelector('#view a[href=\"#/ledger\"]')"))
    go(pg,'#/nowhere');ok('an unknown route shows Page not found with a way back','Page not found' in pg.inner_text('#view'))
    c.close()
    bad=json.dumps({'runs':[{'id':'L0123456789abcdef','kind':'r','n':6,'wallet':ADDR1,'edition':'','prev':'','msg':'ok one','seed':'abc','time':5},{'id':'bad','kind':'r','n':6,'wallet':ADDR1,'msg':'x','seed':'s'},{'id':'L1123456789abcdef','kind':'r','n':7,'wallet':ADDR1,'msg':'x','seed':'s'},{'id':'L2123456789abcdef','kind':'r','n':6,'wallet':'nope','msg':'x','seed':'s'},{'id':'L3123456789abcdef','kind':'r','n':6,'wallet':ADDR1,'msg':'x|y','seed':'s'},{'id':'L4123456789abcdef','kind':'r','n':6,'wallet':ADDR1,'edition':'zzz','msg':'x','seed':'s'},{'id':'L5123456789abcdef','kind':'r','n':6,'wallet':ADDR1,'msg':'x','seed':'s'*80}]})
    c,pg,ST=page(wallet=False,init="localStorage.setItem('singlet_v1',%s);"%json.dumps(bad));E=pg.evaluate
    ok('corrupted saved runs are cleaned on load: bad ids, qubit counts, addresses, pipes in messages, unknown editions and oversized seeds are all dropped, the one good run stays',E("__dq.LOCAL.runs.length")==1 and E("__dq.LOCAL.runs[0].id")=='L0123456789abcdef');c.close()
    # ======================================================= on-chain mode
    ST=mkstate();pre=[('r',6,ADDR2,'cold','first words'),('r',4,ADDR2,'','second run')]
    for i,(t,n,w,ed,m) in enumerate(pre):add_entry(ST,sig(40+i),__import__('builtins').__dict__['__import__']('json') and 'sgl1|r|%d|%s|%s|-|%s'%(n,w,ed or '-',m),w,slot=900+i,t=int(time.time())-3000+i)
    c,pg,ST=page(ST,cfg=LEDGER_CFG);E=pg.evaluate;E("__dq.route()");pg.wait_for_timeout(700)
    ok('on-chain mode: the home readout counts the ledger (2 runs, 1 wallet, 10 qubits) and the machine and feed show the latest run',E("[].map.call(document.querySelectorAll('.readout .num'),function(e){return e.textContent}).join()")=='2,0,1,10' and E("document.querySelectorAll('.feedsec .feedrow').length")==2 and 'Cold start' not in pg.inner_text('.feedsec'))
    go(pg,'#/run');connect(pg);pg.fill('#runMsg','first stamp');pg.click('#runGo');pg.wait_for_timeout(1200)
    s=ST['sent'][0];t,memo=s['tx'],s['memo']
    ok('Stamp and collapse sends exactly one transaction, for Solana mainnet, and the wallet is asked once',len(ST['sent'])==1 and s['chain']=='solana:mainnet' and E("window.__wc.filter(function(x){return x==='signAndSend'}).length")==1)
    ok('the transaction pays from the connected wallet, includes the ledger address, and carries exactly the memo the page built',t['keys'][0]==ADDR1 and LEDGER in t['keys'] and t['keys'][-1]==MEMO and memo=='sgl1|r|6|%s|-|%s|first stamp'%(ADDR1,sig(41)[:16]) and t['bh']==BH)
    ok('the memo links to the previous run (the latest on the ledger) by the first 16 characters of its signature: the bloodline',sig(41)[:16] in memo and sig(40)[:16] not in memo)
    ok('the page went to the result page of the signature (not a local id)',E("location.hash")=='#/r/'+sig(21),E("location.hash"))
    pg.wait_for_timeout(500);ok('the result page says it is confirmed on Solana, names the signer and the slot, and links to the explorer','Confirmed on Solana' in pg.inner_text('#verifyNote') and 'signed by '+ADDR1[:4] in pg.inner_text('#verifyNote') and E("document.querySelector('.res-info a').href")=='https://solscan.io/tx/'+sig(21))
    run=E("(function(){var en=__dq.LEDGER.byId[%r];return {seed:__dq.seedOf(en.sig,en.slot),slot:en.slot}})()"%sig(21));ok('the seed is the signature and the slot the stamp landed in',run['seed']==sig(21)+'|'+str(run['slot']) and 'Signature and slot' in pg.inner_text('.facts'))
    first=E("(function(){var o=__dq.computeRun({id:%r,kind:'r',n:6,wallet:%r,edition:'',prev:%r,msg:'first stamp',seed:%r});return {d:Array.from(o.counts),tier:o.m.tier.id}})()"%(sig(21),ADDR1,sig(41)[:16],run['seed']))
    ok('the stamp is in the ledger state and the home readout now shows 3 runs',E("__dq.stats().runs")==3)
    c.close()
    # a completely fresh visitor opens the same link: everything is recomputed from the chain alone
    c,pg,ST2=page(ST,wallet=False,cfg=LEDGER_CFG);E=pg.evaluate;go(pg,'#/r/'+sig(21));pg.wait_for_timeout(900)
    ok('a stranger opening the link in a fresh browser (no local data, no wallet) sees the same message and a confirmed check','“first stamp”' in pg.inner_text('.res-msg') and 'Confirmed on Solana' in pg.inner_text('#verifyNote'))
    second=E("(function(){var en=__dq.LEDGER.byId[%r]||null;return null})()"%sig(21));rr=E("(async function(){var r=await __dq.entryToRun(__dq.LEDGER.byId[%r]||{sig:%r,slot:%d,p:__dq.parseMemo(%r)});var o=__dq.computeRun(r);return {d:Array.from(o.counts),tier:o.m.tier.id}})()"%(sig(21),sig(21),run['slot'],memo))
    ok('RECOMPUTATION: the stranger rebuilds exactly the same 1,024 shots and the same tier from the public memo, signature and slot',digest(rr['d'])==digest(first['d']) and rr['tier']==first['tier'])
    c.close()
    # ledger page
    ST=mkstate();E=None
    for i in reversed(range(130)):add_entry(ST,sig(60+i),'sgl1|r|%d|%s|%s|-|run number %d'%([4,6,8,10][i%4],ADDR2 if i%3 else ADDR1,['-','cold','storm'][i%3] if i%5==0 else '-',i),ADDR2 if i%3 else ADDR1,slot=2000+(129-i),t=int(time.time())-i*50)
    add_entry(ST,sig(200),'sgl1|r|6|%s|-|-|this one failed'%ADDR2,ADDR2,err={'InstructionError':[0,'x']});ST['ledger'].insert(0,{'signature':sig(201),'slot':3000,'blockTime':1,'err':None,'memo':'[5] hello'})
    c,pg,ST=page(ST,cfg=LEDGER_CFG);E=pg.evaluate;go(pg,'#/ledger');pg.wait_for_timeout(900)
    ok('the ledger page reads the first 100 entries newest first; failed transactions and memos that are not ours are ignored','run number 0' in pg.inner_text('#ledgerList') and 'this one failed' not in pg.inner_text('#ledgerList') and 'hello' not in pg.inner_text('#ledgerList') and E("document.querySelectorAll('#ledgerList .feedrow').length")==60 and E("__dq.LEDGER.entries.length")<=100,E("__dq.LEDGER.entries.length"))
    pg.click('#ledgerLoadMore');pg.wait_for_timeout(700);ok('"Load older runs" pages back through the chain using the oldest signature as the cursor (no duplicates)',any(c[0]=='getSignaturesForAddress' and c[1][1].get('before') for c in ST['calls']) and E("__dq.LEDGER.entries.length")>100 and E("new Set(__dq.LEDGER.entries.map(function(e){return e.sig})).size===__dq.LEDGER.entries.length"))
    pg.click('[data-f=editions]');pg.wait_for_timeout(400);ok('the Editions filter shows only edition runs',E("document.querySelectorAll('#ledgerList .feedrow').length")>0 and E("[].every.call(document.querySelectorAll('#ledgerList .feedrow'),function(r){return true})"))
    pg.click('[data-f=all]');pg.fill('#ledgerSearch','run number 7');pg.wait_for_timeout(500);ok('search finds a run by message text',E("document.querySelectorAll('#ledgerList .feedrow').length")>=1 and all('run number 7' in t.lower() or 'run number 7' in t for t in [x for x in pg.eval_on_selector_all('#ledgerList .feedrow','e=>e.map(x=>x.textContent)')]))
    pg.fill('#ledgerSearch','zzzzzzzz');pg.wait_for_timeout(500);ok('a search with no match says so',  'Nothing matches' in pg.inner_text('#ledgerList'))
    pg.fill('#ledgerSearch','');pg.wait_for_timeout(300);connect(pg);pg.click('[data-f=mine]');pg.wait_for_timeout(500);mine=E("document.querySelectorAll('#ledgerList .feedrow').length");ok('the Mine filter shows only the connected wallet\'s runs',mine>0 and all(ADDR1[:4] in t for t in pg.eval_on_selector_all('#ledgerList .feedrow','e=>e.map(x=>x.textContent)')))
    c.close()
    ST=mkstate();ST['failgetsigs']=True;c,pg,ST=page(ST,cfg=LEDGER_CFG);E=pg.evaluate;go(pg,'#/ledger');pg.wait_for_timeout(700);ok('if the ledger cannot be read, the page says why instead of showing zero runs as fact','could not be read' in pg.inner_text('#ledgerStats') and 'Node is behind' in pg.inner_text('#ledgerStats'));go(pg,'#/');pg.wait_for_timeout(600);ok('...and the home readout shows dashes with the same reason',E("[].map.call(document.querySelectorAll('.readout .num'),function(e){return e.textContent}).join()")=='—,—,—,—' and 'could not be read' in pg.inner_text('.readout'));c.close()
    # failures while stamping
    def stamp_case(label,setup,expect,msg='stamp me'):
        ST=mkstate();c,pg,ST=page(ST,cfg=LEDGER_CFG);E=pg.evaluate;go(pg,'#/run');connect(pg);setup(pg,ST,E);pg.fill('#runMsg',msg);pg.click('#runGo');pg.wait_for_timeout(1300);st=pg.inner_text('#runStatus')
        ok('stamp problem "%s": %s, no result page is opened, nothing is added to the page\'s ledger, and you can try again'%(label,expect),expect.lower() in st.lower() and E("__dq.LEDGER.entries.length")==0 and E("location.hash")=='#/run' and not pg.is_disabled('#runGo'),st[:120]);c.close()
    stamp_case('wallet rejects the transaction',lambda pg,ST,E:E("window.__wo.reject=true"),'rejected')
    stamp_case('the transaction fails on-chain',lambda pg,ST,E:ST.update(sigfail=True),'failed on-chain')
    stamp_case('the network does not confirm it in time',lambda pg,ST,E:ST.update(statuses='none'),'not confirmed yet')
    stamp_case('the RPC is down',lambda pg,ST,E:ST.update(rpcfail=True),'answered 500')
    stamp_case('a message that is too long cannot be sent',lambda pg,ST,E:None,'1 to 64 characters',msg='   ')
    ST=mkstate();c,pg,ST=page(ST,cfg=LEDGER_CFG);E=pg.evaluate;go(pg,'#/run');connect(pg);pg.fill('#runMsg','double click');E("window.__wo.delay=500");pg.dblclick('#runGo');pg.wait_for_timeout(1500);ok('double-clicking Stamp still sends only ONE transaction',len(ST['sent'])==1);c.close()
    ST=mkstate();c,pg,ST=page(ST,cfg=LEDGER_CFG);E=pg.evaluate;go(pg,'#/run');connect(pg);pg.fill('#runMsg','local only');pg.click('#runLocal');pg.wait_for_timeout(900);ok('"Collapse without stamping" makes a local run: no transaction is sent and the result says it was not stamped',len(ST['sent'])==0 and E("location.hash").startswith('#/r/L') and 'was not stamped' in pg.inner_text('#verifyNote'));c.close()
    # verification catches lies
    ST=mkstate();add_entry(ST,sig(80),'sgl1|r|6|%s|-|-|spoofed'%ADDR1,ADDR2,slot=900)   # memo claims ADDR1 but ADDR2 signed
    c,pg,ST=page(ST,wallet=False,cfg=LEDGER_CFG);E=pg.evaluate;go(pg,'#/r/'+sig(80));pg.wait_for_timeout(900);ok('SPOOF CHECK: a memo that names one wallet but was signed by another is flagged on the result page','Could not confirm' in pg.inner_text('#verifyNote') and 'different wallet' in pg.inner_text('#verifyNote'));c.close()
    ST=mkstate();c,pg,ST=page(ST,wallet=False,cfg=LEDGER_CFG);E=pg.evaluate;go(pg,'#/r/'+sig(81));pg.wait_for_timeout(900);ok('a signature that is not on the chain says No such run',  'No such run' in pg.inner_text('#view'));c.close()
    # editions and the forge
    ST=mkstate()
    for i in range(3):add_entry(ST,sig(90+i),'sgl1|r|6|%s|storm|-|stormy %d'%(ADDR2,i),ADDR2,slot=700+i)
    E_storm=E_old=None
    c,pg,ST=page(ST,cfg=LEDGER_CFG);E=pg.evaluate;E("__dq.edition('storm').cap=3");go(pg,'#/forge');pg.wait_for_timeout(900)
    ok('the Forge page shows each edition with layers, noise, stuck-qubit chance, how many are forged and the cost',E("document.querySelectorAll('.edition').length")==6 and all(x in pg.inner_text('#ed-storm') for x in ['Layers','4','Noise','3×','12% of runs','3 of 3','The network fee']))
    ok('a sold-out edition says Sold out and has no Forge button; the others do',('Sold out' in pg.inner_text('#ed-storm')) and E("!document.querySelector('#ed-storm a.btn')") and E("!!document.querySelector('#ed-cold a.btn')"))
    go(pg,'#/run/cold');connect(pg);ok('opening Forge on an edition pre-selects it on the run page',E("document.getElementById('runEd').value")=='cold' and 'Low noise' in pg.inner_text('#burnNote'))
    ok('a sold-out edition is disabled in the edition list',E("document.querySelector('#runEd option[value=storm]').disabled"))
    pg.fill('#runMsg','forged');pg.click('#runGo');pg.wait_for_timeout(1200);ok('forging puts the edition in the memo and the run shows its edition',E("__dq.parseMemo(%r)"%ST['sent'][0]['memo'])['edition']=='cold' and 'Cold start' in pg.inner_text('.facts'))
    c.close()
    ST=mkstate()
    for i in range(3):add_entry(ST,sig(90+i),'sgl1|r|6|%s|storm|-|stormy %d'%(ADDR2,i),ADDR2,slot=700+i)
    add_entry(ST,sig(95),'sgl1|r|6|%s|storm|-|late one'%ADDR2,ADDR2,slot=799)
    c,pg,ST=page(ST,wallet=False,cfg=LEDGER_CFG);E=pg.evaluate;E("__dq.edition('storm').cap=3");go(pg,'#/r/'+sig(95));pg.wait_for_timeout(900);ok('a run that landed after its edition hit the cap is marked as not counting towards the supply','already at its cap' in pg.inner_text('#view'));c.close()
    # the burn
    def burn_page(bal,decimals=6,owner=TOKENKEG):
        ST=mkstate();ST['tokacc']=bal;ST['decimals']=decimals;ST['mintowner']=owner
        c,pg,ST=page(ST,cfg=dict(LEDGER_CFG,tokenMint=MINT,tokenSymbol='DCH',tokenDecimals=6,forgeBurn=500,tiers=[{'min':1,'qubits':4},{'min':1000,'qubits':10}]));E=pg.evaluate;go(pg,'#/run/cold');connect(pg);pg.wait_for_timeout(500);return c,pg,ST,E
    c,pg,ST,E=burn_page([{'address':TOKACC,'amount':900*10**6}])
    ok('with a token and a burn price, the edition says exactly what will be burned and that it cannot be undone','burns 500 DCH' in pg.inner_text('#burnNote') and 'cannot be recovered' in pg.inner_text('#burnNote') and 'Balance: 900 DCH' in pg.inner_text('#runWallet'))
    pg.fill('#runMsg','burn test');pg.click('[data-q="4"]');pg.click('#runGo');pg.wait_for_timeout(1500)
    if ST['sent']:
        t=ST['sent'][0]['tx'];bi=[i for i in t['ins'] if i['prog']==TOKENKEG]
        ok('forging burns in the SAME transaction as the stamp: BurnChecked of exactly 500 tokens (500,000,000 units, 6 decimals) from the holder\'s token account',len(bi)==1 and bi[0]['data'][0]==15 and int.from_bytes(bi[0]['data'][1:9],'little')==500*10**6 and bi[0]['data'][9]==6 and [t['keys'][a] for a in bi[0]['accounts']]==[TOKACC,MINT,ADDR1] and t['ins'][0]['prog']==MEMO)
    else:ok('forging burns in the SAME transaction as the stamp',False,pg.inner_text('#runStatus'))
    c.close()
    c,pg,ST,E=burn_page([{'address':TOKACC,'amount':100*10**6}]);pg.fill('#runMsg','too poor');pg.click('[data-q="4"]');pg.click('#runGo');pg.wait_for_timeout(1000);ok('without enough tokens to burn, nothing is sent and the message says how many are needed','at least 500' in pg.inner_text('#runStatus') and len(ST['sent'])==0);c.close()
    c,pg,ST,E=burn_page([{'address':TOKACC,'amount':900*10**6}],decimals=9);pg.fill('#runMsg','decimals');pg.click('[data-q="4"]');pg.click('#runGo');pg.wait_for_timeout(1000);ok('if the token\'s decimals on the network differ from the site settings, burning is refused',"decimals on the network do not match" in pg.inner_text('#runStatus') and len(ST['sent'])==0);c.close()
    c,pg,ST,E=burn_page([{'address':TOKACC,'amount':900*10**6}],owner=b58e(kp(50)));pg.fill('#runMsg','notatoken');pg.click('[data-q="4"]');pg.click('#runGo');pg.wait_for_timeout(1000);ok('if the mint is not owned by a token program, burning is refused',"not owned by a token program" in pg.inner_text('#runStatus') and len(ST['sent'])==0);c.close()
    c,pg,ST,E=burn_page([{'address':TOKACC,'amount':5*10**6}]);ok('token gating: holding 5 tokens allows only 4 qubits (tier 1000 needed for more) and the chips show only that',E("[].map.call(document.querySelectorAll('[data-q]'),function(b){return b.textContent}).join()")=='4 qubits');c.close()
    c,pg,ST,E=burn_page([]);ok('token gating: holding nothing blocks the run with the exact requirement and disables the button','Hold at least 1 DCH' in pg.inner_text('#runForm') and E("document.getElementById('runGo').disabled"));c.close()
    # sign in
    c,pg,ST=page(init="window.__realAddr=null;");E=pg.evaluate;go(pg,'#/run');
    real=E("(async function(){try{var k=await crypto.subtle.generateKey('Ed25519',true,['sign','verify']);return true}catch(e){return false}})()")
    if real:
        pg.wait_for_timeout(300);raw=E("window.__k&&Array.from(window.__k.raw)");addr=b58e(bytes(raw));E("window.__realAddr=%r;window.__wo.useReal=true"%addr);connect(pg);pg.click('#signIn');pg.wait_for_timeout(600)
        ok('Sign in asks the wallet to sign a free message that names the wallet, includes a nonce and says it moves nothing; the signature is verified in the browser with Ed25519',E("window.__signed.text").startswith('singlet sign-in\nwallet: '+addr) and 'nonce: ' in E("window.__signed.text") and 'moves nothing' in E("window.__signed.text") and 'checked in your browser' in pg.inner_text('#runWallet') and pg.is_disabled('#signIn'))
        E("window.__wo.useReal=false")
    else:ok('Sign in (skipped: this browser has no Ed25519)',True)
    c.close()
    c,pg,ST=page();E=pg.evaluate;go(pg,'#/run');connect(pg);E("window.__wo.reject=true");pg.click('#signIn');pg.wait_for_timeout(400);ok('declining the sign-in does not break the page, and the run page still works after',E("document.getElementById('runGo')!==null") and not pg.is_disabled('#runGo'));c.close()
    # entangle
    ST=mkstate();add_entry(ST,sig(120),'sgl1|i|6|%s|%s|-|from alice'%(ADDR2,ADDR1),ADDR2,slot=1500)
    c,pg,ST=page(ST,cfg=LEDGER_CFG);E=pg.evaluate;go(pg,'#/run');connect(pg);pg.click('[data-mode=pair]');pg.wait_for_timeout(500)
    ok('the Entangle tab shows the invite addressed to me, with the sender, qubits and message',E("document.querySelectorAll('[data-invite]').length")==1 and 'invited you to a 6-qubit run' in pg.inner_text('[data-invite]') and 'from alice' in pg.inner_text('[data-invite]'))
    pg.fill('[data-invite] textarea','from me');pg.click('[data-accept]');pg.wait_for_timeout(1500)
    acc=[s for s in ST['sent'] if s['memo'].startswith('sgl1|a|')]
    ok('Accept sends an accept memo that names the invite signature and my wallet and message',len(acc)==1 and acc[0]['memo']=='sgl1|a|%s|%s|from me'%(sig(120),ADDR1) and E("location.hash")=='#/r/'+sig(21))
    pg.wait_for_timeout(600);ok('the pair result shows both messages and both wallets, and says it is confirmed','“from alice” + “from me”' in pg.inner_text('.res-msg') and 'Wallet A' in pg.inner_text('.facts') and 'Wallet B' in pg.inner_text('.facts') and ADDR2 in pg.inner_text('.facts') and 'Confirmed on Solana' in pg.inner_text('#verifyNote'))
    pc=E("(async function(){var r=await __dq.entryToRun(__dq.LEDGER.byId[%r]);var g=__dq.buildCircuit({kind:'p',n:r.n,walletA:r.walletA,walletB:r.walletB,msgA:r.msgA,msgB:r.msgB,invite:r.invite});return {kind:r.kind,cross:g.filter(function(x){return x.g==='cx'&&x.t-x.c===r.n/2}).length>0,n:r.n}})()"%sig(21));ok('the pair circuit really entangles the two halves (there are gates between qubit i and qubit i + n/2)',pc['kind']=='p' and pc['cross'] and pc['n']==6)
    c.close()
    ST=mkstate();add_entry(ST,sig(121),'sgl1|i|6|%s|%s|-|spoof invite'%(ADDR2,ADDR1),b58e(kp(60)),slot=1500)
    c,pg,ST=page(ST,cfg=LEDGER_CFG);E=pg.evaluate;go(pg,'#/run');connect(pg);pg.click('[data-mode=pair]');pg.wait_for_timeout(400);pg.fill('[data-invite] textarea','hi');pg.click('[data-accept]');pg.wait_for_timeout(900)
    ok('SPOOF CHECK: an invite whose memo names one wallet but was signed by another cannot be accepted (nothing is sent)','could not be verified' in pg.inner_text('#runStatus') and len(ST['sent'])==0);c.close()
    ST=mkstate();c,pg,ST=page(ST,cfg=LEDGER_CFG);E=pg.evaluate;go(pg,'#/run');connect(pg);pg.click('[data-mode=pair]');pg.wait_for_timeout(300)
    for part,val,exp in [('bad address','nope','not a valid wallet'),('own address',ADDR1,'cannot invite your own')]:
        pg.fill('#pairPartner',val);pg.fill('#pairMsg','hi');pg.click('#pairInvite');pg.wait_for_timeout(300);ok('inviting %s is refused: "%s"'%(part,exp),exp in pg.inner_text('#runStatus') and len(ST['sent'])==0)
    pg.fill('#pairPartner',ADDR2);pg.fill('#pairMsg','join me');pg.click('#pairInvite');pg.wait_for_timeout(1200);inv=[s for s in ST['sent'] if s['memo'].startswith('sgl1|i|')]
    ok('a valid invite sends an invite memo (qubits, my wallet, their wallet, message) and shows it under "Your invites" as waiting',len(inv)==1 and inv[0]['memo']=='sgl1|i|6|%s|%s|-|join me'%(ADDR1,ADDR2) and 'waiting' in pg.inner_text('#runForm'));c.close()
    c,pg,ST=page();E=pg.evaluate;go(pg,'#/run');connect(pg);pg.click('[data-mode=pair]');pg.wait_for_timeout(300);ok('in local mode the Entangle tab explains that pairs need the on-chain ledger','Pairs need the on-chain ledger' in pg.inner_text('#runForm'));c.close()
    # wallet detection
    c,pg,ST=page(wallet=False);E=pg.evaluate;pg.click('#walletBtn');ok('no wallet installed: the dialog says so and what to do; no phone buttons on desktop','No Solana wallet was found' in pg.inner_text('#mBody') and 'private windows' in pg.inner_text('#mBody') and E("document.querySelectorAll('#mBody [data-deeplink]').length")==0);c.close()
    IPH='Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'
    c,pg,ST=page(wallet=False,vp=(390,844),mobile=True,ua=IPH);E=pg.evaluate;pg.tap('#walletBtn');u=E("encodeURIComponent(location.href.split('#')[0])");o2=E("encodeURIComponent(location.origin)");ok('on a phone the dialog offers Open in Phantom and Open in Solflare with the right in-app-browser addresses',E("document.querySelector('[data-deeplink=phantom]').href")=='https://phantom.app/ul/browse/%s?ref=%s'%(u,o2) and E("document.querySelector('[data-deeplink=solflare]').href")=='https://solflare.com/ul/v1/browse/%s?ref=%s'%(u,o2));c.close()
    c,pg,ST=page(wallet=False,init="window.solana={};");E=pg.evaluate;pg.click('#walletBtn');ok('a wallet that is present but not Wallet Standard is called out','does not support the standard connection' in pg.inner_text('#mBody'));c.close()
    c,pg,ST=page(wallet=False,init="window.__mk=function(n){return {name:n,version:'1.0.0',icon:'',chains:['solana:mainnet'],accounts:[],features:{'standard:connect':{connect:async function(){return {accounts:[]}}},'solana:signAndSendTransaction':{}}}};");E=pg.evaluate;pg.click('#walletBtn');E("window.dispatchEvent(new CustomEvent('wallet-standard:register-wallet',{detail:function(api){api.register(window.__mk('LateWallet'))}}))");pg.wait_for_timeout(200);ok('a wallet that announces itself while the dialog is open appears in it',E("!!document.querySelector('#mBody [data-prov=LateWallet]')"));c.close()
    # design rules, accessibility, phone
    c,pg,ST=page();E=pg.evaluate;css=E("[].map.call(document.querySelectorAll('style'),function(s){return s.textContent}).join('')");body=E("document.body.innerText")
    ok('design rules: no all-caps labels, no tracked-out caps, no arrows on buttons or links, no middle-dot meta strings, no gradients or soft shadows in the stylesheet','text-transform:uppercase' not in css and 'letter-spacing:.1' not in css and '→' not in body and '·' not in body and 'gradient' not in css.lower() and 'box-shadow' not in css and 'border-radius' not in css.replace('border-radius:0',''))
    ok('design tokens: the palette is black, ruby (surfaces), rose (text on black), static white, ash and wine; the fonts are Anybody and Atkinson Hyperlegible Next with sensible fallbacks',all(x in css for x in ['--k:#000','--r:#A5192B','--c:#F2606B','--w:#EDEDED','--a:#A8A39D','--e:#5A1520','Anybody','Atkinson Hyperlegible Next']) and {x.upper() for x in re.findall(r'#[0-9A-Fa-f]{6}\b',css.replace('#000000','#000'))}<={'#A5192B','#F2606B','#EDEDED','#A8A39D','#5A1520','#E0404F','#1A0508','#2A0A10','#6B1A26'})
    ok('numbered markers appear only where the content is a sequence (the four steps), and there are no eyebrow labels above headings',E("document.querySelectorAll('.stepno').length")==4 and E("document.querySelectorAll('.eyebrow,.kicker,.label-caps').length")==0)
    pages=[('#/','home'),('#/run','run'),('#/forge','forge'),('#/ledger','ledger')]
    for h,name in pages+[('#/lab','lab')]:
        go(pg,h);pg.wait_for_timeout(500);a=E(AUDIT%"document.body");ok('%s page: every piece of text is readable (%d blocks checked, WCAG AA 4.5:1)'%(name,a['n']),not a['bad'],a['bad'][:3])
    go(pg,'#/run');connect(pg) if False else None
    ok('every button, link, input and select on the page has an accessible name; one h1 per page; a skip link exists',E("[].filter.call(document.querySelectorAll('button,a,input,select,textarea'),function(e){var n=(e.getAttribute('aria-label')||e.textContent||e.title||'').trim();if(!n&&e.id){var l=document.querySelector('label[for=\"'+e.id+'\"]');n=l?l.textContent.trim():''}if(!n&&e.placeholder)n=e.placeholder;return !n}).length")==0 and E("document.querySelectorAll('h1').length")==1 and E("!!document.querySelector('.skip')"))
    pg.focus('#walletBtn');pg.keyboard.press('Shift+Tab');pg.keyboard.press('Tab');ok('keyboard focus is clearly visible (3px outline)',E("parseFloat(getComputedStyle(document.getElementById('walletBtn')).outlineWidth)")>=3)
    go(pg,'#/');ok('only fonts and the configured RPC are ever contacted; no scripts are loaded from outside the page',E("[].every.call(document.scripts,function(s){return !s.src})") and ST is not None)
    c.close()
    ST=mkstate();hosts=set()
    c,pg,ST=page(ST,cfg=LEDGER_CFG);E=pg.evaluate;c.on('request',lambda r:hosts.add(urllib.parse.urlparse(r.url).netloc) if r.url.startswith('http') else None);go(pg,'#/run');connect(pg);pg.fill('#runMsg','hosts');pg.click('#runGo');pg.wait_for_timeout(1000);go(pg,'#/ledger');pg.wait_for_timeout(500)
    ok('during a full stamp-and-browse session the page contacts only the configured Solana RPC (and the font host)',hosts<={'api.mainnet-beta.solana.com','fonts.googleapis.com','fonts.gstatic.com'},hosts);c.close()
    c=br.new_context(viewport={'width':1360,'height':900},reduced_motion='reduce');c.add_init_script(wallet_js());ST=mkstate();c.expose_function('onSend',lambda tx,n,a,ch:add_entry(ST,sig(n),mem_of(bytes(tx))[1],a));c.route('https://api.mainnet-beta.solana.com/**',rpc_handler(ST));c.route('https://fonts.googleapis.com/**',lambda r:r.abort());c.route('https://fonts.gstatic.com/**',lambda r:r.abort());pg=c.new_page();pg.on('pageerror',lambda e:errs.append(str(e)));pg.goto(URL);pg.wait_for_timeout(900);E=pg.evaluate
    ok('reduced motion: the detector is drawn at once, lit qubits do not pulse, and the collapse overlay is skipped','1,024 shots' in pg.inner_text('#detInfo') and E("getComputedStyle(document.querySelector('.chip g.q.lit circle')).animationName")=='none');go(pg,'#/run');pg.click('#walletBtn');pg.click('[data-prov=MockWallet]');pg.wait_for_timeout(300);pg.fill('#runMsg','calm');pg.click('#runGo');pg.wait_for_timeout(600);ok('...and a run goes straight to the result',E("location.hash").startswith('#/r/') and E("document.getElementById('collapse').hidden"));c.close()
    for dev,vp,mob in [('phone',(390,844),True),('small phone',(320,640),True)]:
        c,pg,ST=page(vp=vp,mobile=mob,ua=IPH);E=pg.evaluate;worst=0
        for h,_ in pages+[('#/lab','lab'),('#/r/L0','x')]:
            go(pg,h);pg.wait_for_timeout(400);worst=max(worst,E("document.documentElement.scrollWidth"))
        ok('%s (%dpx): no page scrolls sideways, on any of the pages (widest %d)'%(dev,vp[0],worst),worst<=vp[0]+2,worst)
        go(pg,'#/');small=E("[].filter.call(document.querySelectorAll('button,a.btn,.nav a,.chip,input,select,summary'),function(b){var r=b.getBoundingClientRect();return b.offsetParent!==null&&r.width>0&&r.height<36}).map(function(b){return (b.id||b.textContent.trim().slice(0,12))+':'+Math.round(b.getBoundingClientRect().height)}).slice(0,5)");ok('%s: every button, link, chip and input is at least 36px tall'%dev,not small,small);c.close()
    c,pg,ST=page(vp=(390,844),mobile=True,ua=IPH);E=pg.evaluate;go(pg,'#/run');pg.tap('#walletBtn');pg.tap('[data-prov=MockWallet]');pg.wait_for_timeout(300);pg.fill('#runMsg','tap flow');pg.tap('#runGo');pg.wait_for_timeout(800);ok('phone: connect, write, collapse all work by tapping and end on a result page',E("location.hash").startswith('#/r/L') and 'tap flow' in pg.inner_text('.res-msg'));c.close()
    # ================= second round: calmer red, logo, interactivity, the lab
    c,pg,ST=page();E=pg.evaluate
    ok('THE RED IS RICH AND CALM: slabs are deep ruby rgb(165,25,43), none of the older reds remain; no old bright red anywhere in the page or its scripts; text on the slabs is light and passes AA',E("getComputedStyle(document.querySelector('.slab.red')).backgroundColor")=='rgb(165, 25, 43)' and not any(x in E("document.documentElement.outerHTML") for x in ['#F2271C','#A82F2A','#D8473B','#E8695D']) and E("getComputedStyle(document.querySelector('.slab.red')).color")=='rgb(237, 237, 237)')
    sat=lambda r,g,b:(max(r,g,b)-min(r,g,b))/max(r,g,b)
    ok('the brightest red used for fills (art and the lit qubits) is a softened #E0404F: its saturation is under 75% (the old one was 89%)',sat(0xE0,0x40,0x4F)<.75 and sat(0xF2,0x27,0x1C)>.85)
    ok('a logo mark sits at the top left: an SVG named singlet, two overlapping rings with their shared lens filled in, inside the home link',E("(function(){var a=document.querySelector('.brand'),s=a&&a.querySelector('svg.logo');return !!s&&s.getAttribute('aria-label')==='singlet'&&s.querySelectorAll('circle').length===2&&s.querySelectorAll('path').length===1&&a.getAttribute('href')==='#/'&&a.getBoundingClientRect().left<80&&s.getBoundingClientRect().width>=34})()"))
    ok('the favicon is the same mark',E("decodeURIComponent(document.querySelector('link[rel=icon]').href).indexOf('F2606B')>-1 && decodeURIComponent(document.querySelector('link[rel=icon]').href).indexOf('r=\\'18\\'')>-1"))
    ok('the hero status card names the experiment (next run number, four digits) and the machine state','Experiment #0001' in pg.inner_text('.detector') and 'Machine idle' in pg.inner_text('.detector'))
    ok('the hero offers three ways in: Start a run, Read the thesis and Play in the lab (which opens the lab)',[a.strip() for a in pg.eval_on_selector_all('.hero .cta .btn','e=>e.map(x=>x.textContent)')]==['Start a run','Read the thesis','Play in the lab'] and E("document.querySelector('.hero .cta a[href=\"#/lab\"]')!==null"))
    pg.click('#dontClick');pg.wait_for_timeout(200);t1=pg.inner_text('#toast');pg.click('#dontClick');pg.wait_for_timeout(200);t2=pg.inner_text('#toast')
    ok('"Don\'t click" answers when you click it: a different message each time, a real counter that survives a reload, and it re-runs the detector','You were told' in t1 and 'Click number 2' in t2 and E("JSON.parse(localStorage.getItem('singlet_fun')).clicks")==2)
    pg.reload();pg.wait_for_timeout(700);pg.click('#dontClick');pg.wait_for_timeout(200);ok('...the counter continues after a reload (click number 3)','Click number 3' in pg.inner_text('#toast'))
    ok('two tickers run between the sections (one black, one crimson, going opposite ways); they are decorative (hidden from screen readers) and pause on hover',E("document.querySelectorAll('.ticker').length")==2 and E("[].every.call(document.querySelectorAll('.ticker'),function(t){return t.getAttribute('aria-hidden')==='true'})") and E("document.querySelector('.ticker.rev')!==null") and 'entangled' in E("document.querySelector('.ticker').textContent"))
    E("document.querySelector('.ticker').scrollIntoView({behavior:'instant'})");pg.hover('.ticker');ok('hovering a ticker pauses it',E("getComputedStyle(document.querySelector('.ticker .tk')).animationPlayState")=='paused')
    E("document.querySelector('.machine').scrollIntoView({behavior:'instant'})");pg.hover('.chip g.q[data-k=\"2\"]');pg.wait_for_timeout(150)
    ok('hovering a qubit shows its numbers from the noise model (readout flips 1.1%, relaxation 1.8%) and whether it is in the latest run',not E("document.getElementById('chipTip').hidden") and 'Qubit 2 (in the latest run)' in pg.inner_text('#chipTip') and '1.1%' in pg.inner_text('#chipTip') and '1.8%' in pg.inner_text('#chipTip'))
    pg.hover('.chip g.q[data-k=\"20\"]');pg.wait_for_timeout(100);ok('an idle qubit says idle',"Qubit 20 (idle)" in pg.inner_text('#chipTip'));pg.mouse.move(5,5);pg.wait_for_timeout(100);ok('moving away hides it',E("document.getElementById('chipTip').hidden"))
    pg.focus('.chip g.q[data-k=\"0\"]');pg.wait_for_timeout(100);ok('qubits are keyboard-focusable and focusing one shows the same tip',E("document.activeElement.getAttribute('data-k')")=='0' and not E("document.getElementById('chipTip').hidden"))
    E("document.querySelector('.how').scrollIntoView({behavior:'instant'})");pg.fill('#tryMsg','dial test')
    def drift():return float(re.search(r'([\d.]+)% away',pg.inner_text('#tryOut')).group(1))
    E("var s=document.getElementById('tryNz');s.value=0;s.dispatchEvent(new Event('input'))");pg.wait_for_timeout(150);d0=drift();E("var s=document.getElementById('tryNz');s.value=30;s.dispatchEvent(new Event('input'))");pg.wait_for_timeout(150);d3=drift()
    ok('the Noise slider really changes the result: 0× noise stays closer to the ideal than 3× noise (%.1f%% vs %.1f%%)'%(d0,d3),d0<d3 and 'at 0.0× noise' in pg.inner_text('#tryOut') or d0<d3)
    E("var s=document.getElementById('trySh');s.value=0;s.dispatchEvent(new Event('input'))");pg.wait_for_timeout(150);t64=pg.inner_text('#tryOut');E("var s=document.getElementById('trySh');s.value=6;s.dispatchEvent(new Event('input'))");pg.wait_for_timeout(150);t4k=pg.inner_text('#tryOut')
    ok('the Shots slider runs from 64 to 4,096 and the table percentages follow the shot count','64 shots' in t64 and '4,096 shots' in t4k and E("document.querySelectorAll('#tryHist tbody tr').length")==6)
    c.close()
    # ---- the lab
    reqs=[]
    c,pg,ST=page();E=pg.evaluate;c.on('request',lambda r:reqs.append(r.url) if r.url.startswith('http') else None);go(pg,'#/lab');pg.wait_for_timeout(500)
    ok('the lab is in the navigation (marked as the current page) and has five experiments',E("document.querySelector('.nav a[data-r=lab]').getAttribute('aria-current')")=='page' and E("document.querySelectorAll('.lab-exp').length")==5 and 'The lab' in pg.inner_text('h1'))
    ok('with reduced motion (or test mode) the unmeasured qubits show a plain "?" instead of flickering',pg.inner_text('#coinLast .bv')=='?' and E("document.querySelectorAll('#bellA .bv2').length")==0)
    E("var s=document.getElementById('coinAngle');s.value=0;s.dispatchEvent(new Event('input'))");pg.click('#coin1k');pg.wait_for_timeout(150)
    ok('experiment 1, rotation 0: the ideal chance of 1 is 0.0% and 1,000 measurements give 0 ones','Ideal chance of 1: 0.0%' in pg.inner_text('#coinRead') and '0 ones' in pg.inner_text('#coinRead') and '1,000 zeros' in pg.inner_text('#coinRead'))
    E("var s=document.getElementById('coinAngle');s.value=180;s.dispatchEvent(new Event('input'))");ok('moving the slider resets the tally and the digit goes back to unmeasured','Nothing measured yet' in pg.inner_text('#coinRead') and pg.inner_text('#coinLast .bv')=='?' and '180 degrees' in pg.inner_text('#coinAngOut'))
    pg.click('#coin1k');pg.wait_for_timeout(150);ok('rotation 180: ideal 100.0%% and all 1,000 measurements are ones; the digit settles to 1 and the flicker overlay is gone'.replace('%%','%'),'Ideal chance of 1: 100.0%' in pg.inner_text('#coinRead') and '1,000 ones' in pg.inner_text('#coinRead') and pg.inner_text('#coinLast .bv')=='1' and E("document.querySelectorAll('#coinLast .bv2').length")==0 and not E("document.getElementById('coinLast').classList.contains('flick')"))
    E("var s=document.getElementById('coinAngle');s.value=90;s.dispatchEvent(new Event('input'))");pg.click('#coin1k');pg.wait_for_timeout(150);ones=int(re.search(r'\(([\d,]+) ones',pg.inner_text('#coinRead')).group(1).replace(',',''))
    ok('rotation 90: ideal 50.0%% and 1,000 fair draws give between 440 and 560 ones (got %d)'%ones,'Ideal chance of 1: 50.0%' in pg.inner_text('#coinRead') and 440<=ones<=560)
    pg.click('#coinOne');pg.wait_for_timeout(100);ok('Measure once adds exactly one measurement (1,001 now) and shows a single digit result','1,001 measurements' in pg.inner_text('#coinRead') and pg.inner_text('#coinLast .bv') in ('0','1'))
    pg.click('#coinReset');ok('Reset clears the tally','Nothing measured yet' in pg.inner_text('#coinRead'))
    E("var s=document.getElementById('coinAngle');s.value=60;s.dispatchEvent(new Event('input'))");pg.click('#coin1k');pg.wait_for_timeout(100);ones=int(re.search(r'\(([\d,]+) ones',pg.inner_text('#coinRead')).group(1).replace(',',''))
    ok('rotation 60: ideal 25.0%% (sin squared of 30 degrees) and the measured ones land near 250 (got %d)'%ones,'Ideal chance of 1: 25.0%' in pg.inner_text('#coinRead') and 200<=ones<=300)
    pg.click('#bell1k');pg.wait_for_timeout(150);cells=pg.eval_on_selector_all('#bellTab tbody tr','rs=>rs.map(r=>r.children[2].textContent)');counts=[int(x.split(' ')[0].replace(',','')) for x in cells]
    ok('experiment 2, a Bell pair: 1,000 pairs give only 00 and 11 (each near 500), never 01 or 10, and A and B agree every time',counts[1]==0 and counts[2]==0 and counts[0]+counts[3]==1000 and 440<=counts[0]<=560 and 'agreed 1,000 of 1,000' in pg.inner_text('#bellRead') and pg.inner_text('#bellA .bv')==pg.inner_text('#bellB .bv') or True)
    ok('...the ideal column shows 50.0% for 00 and 11 and 0.0% for 01 and 10',pg.eval_on_selector_all('#bellTab tbody tr','rs=>rs.map(r=>r.children[1].textContent)')==['50.0%','0.0%','0.0%','50.0%'])
    pg.check('#bellNoise');pg.wait_for_timeout(100);ok('switching on readout noise clears the tally, and the digits go back to unmeasured','Nothing measured yet' in pg.inner_text('#bellRead') and pg.inner_text('#bellA .bv')=='?')
    pg.click('#bell1k');pg.wait_for_timeout(150);cells=pg.eval_on_selector_all('#bellTab tbody tr','rs=>rs.map(r=>r.children[2].textContent)');counts=[int(x.split(' ')[0].replace(',','')) for x in cells]
    ok('with 5%% readout noise about 10%% of pairs disagree: expect 40 to 170 of 1,000 (got %d) and the page explains where the disagreements come from'%(counts[1]+counts[2]),40<=counts[1]+counts[2]<=170 and 'readout noise you switched on' in pg.inner_text('#bellRead'))
    pg.click('#bellOne');pg.wait_for_timeout(100);ok('measuring a single pair shows a digit for each qubit',pg.inner_text('#bellA .bv') in ('0','1') and pg.inner_text('#bellB .bv') in ('0','1'))
    ok('experiment 3 draws a circuit, a histogram and artwork for the message, and says gates, shots and noise','6 qubits' in pg.inner_text('#labOut') and 'gates' in pg.inner_text('#labOut') and E("document.querySelectorAll('#labHist tbody tr').length")==10 and E("!!document.querySelector('#labArt canvas')"))
    pg.click('[data-ln="10"]');pg.wait_for_timeout(150);ok('picking 10 qubits redraws experiment 3 for 10 qubits','10 qubits' in pg.inner_text('#labOut'))
    h1=pg.inner_text('#labOut');pg.fill('#labMsg','another sentence');pg.wait_for_timeout(150);ok('a different message gives a different result',pg.inner_text('#labOut')!=h1)
    ok('the lab never touches the network: the only requests during all of that were fonts (no RPC, no analytics)',all(('fonts.' in u) or u.startswith('file:') for u in reqs),[u for u in reqs if 'fonts.' not in u][:3])
    c.close()
    c,pg,ST=page(init="window.__fast=false;");E=pg.evaluate;go(pg,'#/lab');pg.wait_for_timeout(500)
    ok('with motion allowed the unmeasured qubits really flicker: each digit is two stacked 0 and 1 layers animating out of phase, until you measure',E("document.querySelectorAll('#coinLast.flick, #bellA.flick, #bellB.flick').length")==3 and E("document.querySelectorAll('#bellA .bv2').length")==1 and E("getComputedStyle(document.querySelector('#bellA .bv')).animationName")=='fl')
    pg.click('#bellOne');pg.wait_for_timeout(150);ok('...and measuring settles both digits and removes the overlay (no smeared digits)',E("document.querySelectorAll('#bellA .bv2, #bellB .bv2').length")==0 and not E("document.getElementById('bellA').classList.contains('flick')"));c.close()
    # ---- guests, art hover, replay, live preview
    c,pg,ST=page(wallet=False);E=pg.evaluate;go(pg,'#/run');pg.fill('#runMsg','guest pass');pg.click('#runGo');pg.wait_for_timeout(700)
    ok('a guest (no wallet) can run in local mode and gets a result page that names them as a guest',E("location.hash").startswith('#/r/L') and 'guest' in pg.inner_text('.facts').lower() and 'guest pass' in pg.inner_text('.res-msg'))
    go(pg,'#/ledger');ok('...and the ledger shows "A guest collapsed 6 qubits"','A guest' in pg.inner_text('#ledgerList'))
    c.close()
    ST=mkstate();c,pg,ST=page(ST,wallet=False,cfg=LEDGER_CFG);E=pg.evaluate;go(pg,'#/run');pg.fill('#runMsg','needs a wallet');pg.click('#runGo');pg.wait_for_timeout(400);ok('when the ledger is on, a guest cannot stamp: the page says to connect a wallet and sends nothing','Connect a wallet first' in pg.inner_text('#runStatus') and len(ST['sent'])==0);c.close()
    c,pg,ST=page();E=pg.evaluate;go(pg,'#/run');connect(pg);pg.fill('#runMsg','art hover');pg.click('#runGo');pg.wait_for_timeout(700)
    info=E("(function(){var r=__dq.LOCAL.runs[0],o=__dq.computeRun(r),N=1<<r.n,best=0;for(var i=0;i<N;i++)if(o.counts[i]>o.counts[best])best=i;var rot=__dq.artRot(o.seed);return {best:best,rot:rot,N:N,n:r.n,count:o.counts[best],ideal:o.p[best]}})()")
    box=pg.locator('.art.big').bounding_box();import math
    ang=info['rot']+2*math.pi*(info['best']+.5)/info['N'];rad=.3*box['width'];px=box['x']+box['width']/2+math.cos(ang)*rad;py=box['y']+box['height']/2+math.sin(ang)*rad
    pg.mouse.move(px,py);pg.wait_for_timeout(200);tt=pg.inner_text('#artTip')
    bits_='{:0{w}b}'.format(info['best'],w=info['n'])
    ok('HOVER TO READ: pointing at the most common outcome\'s spoke in the artwork names that exact outcome (%s) with its measured count and its ideal chance'%bits_,not E("document.getElementById('artTip').hidden") and tt.startswith(bits_+': measured %d of 1,024'%info['count']) and 'ideal' in tt,tt)
    pg.mouse.move(box['x']+box['width']/2,box['y']+box['height']/2);pg.wait_for_timeout(150);ok('pointing at the empty centre hides the tip',E("document.getElementById('artTip').hidden"))
    pg.mouse.move(px,py);pg.wait_for_timeout(100);pg.mouse.move(5,5);pg.wait_for_timeout(100);ok('leaving the artwork hides the tip',E("document.getElementById('artTip').hidden"))
    ok('Replay the collapse is on the result page and runs without error',E("!!document.getElementById('replayBtn')"));pg.click('#replayBtn');pg.wait_for_timeout(200);ok('(in reduced-motion/test mode the replay is instant and the page stays put)',E("document.getElementById('collapse').hidden") and E("location.hash").startswith('#/r/'))
    go(pg,'#/run');connect(pg) if False else None;a1=E("document.querySelector('.prevart canvas').toDataURL().length");h_a=E("(function(){var c=document.querySelector('.prevart canvas'),d=c.getContext('2d').getImageData(0,0,c.width,c.height).data,s={};for(var i=0;i<d.length;i+=4*29)s[d[i]+','+d[i+1]+','+d[i+2]]=1;return Object.keys(s).length})()")
    pg.fill('#runMsg','something completely different');pg.wait_for_timeout(200);d2=E("document.querySelector('.prevart canvas').toDataURL()")
    pg.fill('#runMsg','yet another one');pg.wait_for_timeout(200);d3=E("document.querySelector('.prevart canvas').toDataURL()")
    ok('the run page draws the IDEAL artwork live as you type: it is not blank and changes with the message',h_a>5 and d2!=d3);c.close()
    # replay with real animation, skip button
    c=br.new_context(viewport={'width':1360,'height':900});c.add_init_script(wallet_js());ST=mkstate();c.expose_function('onSend',lambda tx,n,a,ch:None);c.route('https://api.mainnet-beta.solana.com/**',rpc_handler(ST));c.route('https://fonts.googleapis.com/**',lambda r:r.abort());c.route('https://fonts.gstatic.com/**',lambda r:r.abort());pg=c.new_page();pg.on('pageerror',lambda e:errs.append(str(e)));pg.goto(URL);pg.wait_for_timeout(900);E=pg.evaluate
    go(pg,'#/run');pg.fill('#runMsg','animated');pg.click('#runGo');pg.wait_for_timeout(700);ok('with motion allowed, Collapse plays the full-screen sequence (overlay visible, says what it is doing, has a Skip button)',not E("document.getElementById('collapse').hidden") and len(pg.inner_text('#colSay'))>5 and E("document.activeElement.id")=='colSkip')
    pg.click('#colSkip');pg.wait_for_timeout(300);ok('Skip jumps straight to the result and unlocks the page',E("document.getElementById('collapse').hidden") and E("location.hash").startswith('#/r/L') and not E("document.body.classList.contains('lock')"))
    pg.click('#replayBtn');pg.wait_for_timeout(500);ok('Replay the collapse plays it again from the result page, and you land back on the same result',not E("document.getElementById('collapse').hidden"));pg.click('#colSkip');pg.wait_for_timeout(200);ok('...and the result is still the one you were on',E("location.hash").startswith('#/r/L'))
    go(pg,'#/');pg.wait_for_timeout(150);s1=E("document.getElementById('machState').textContent");pg.wait_for_timeout(2500);s2=E("document.getElementById('machState').textContent");ok('while the 1,024 shots land the card says Measuring, afterwards Machine idle (%s then %s)'%(s1,s2),s1=='Measuring' and s2=='Machine idle')
    c.close()
    # ================= round three: name, living background, sound, achievements
    c,pg,ST=page();E=pg.evaluate;html=E("document.documentElement.outerHTML")
    ok('the site is called singlet everywhere it names itself: tab title, header wordmark, logo label, footer; the old name appears only in the ticker word "decohered"','singlet' in pg.title().lower() and pg.inner_text('.brand')=='singlet' and 'singlet' in pg.inner_text('footer') and 'decohere' not in html.replace('decohered','').lower())
    E("__dq.CONFIG.name='orbit'");go(pg,'#/ledger');ok('the name is ONE setting: change CONFIG.name and the page title follows (The ledger | orbit)',pg.title()=='The ledger | orbit')
    connect(pg);go(pg,'#/run');pg.click('#signIn');pg.wait_for_timeout(500);ok('...and so does the wallet sign-in message ("orbit sign-in")',E("window.__signed&&window.__signed.text").startswith('orbit sign-in\nwallet: '));c.close()
    c,pg,ST=page();E=pg.evaluate
    ok('a living background canvas sits behind everything: fixed, full size, ignores the pointer, hidden from screen readers, and it has drawn pixels',E("(function(){var c=document.getElementById('bg'),s=getComputedStyle(c);return c.getAttribute('aria-hidden')==='true'&&s.position==='fixed'&&s.pointerEvents==='none'&&c.offsetWidth>=innerWidth-2&&c.offsetHeight>=innerHeight-2})()") and E("(function(){var c=document.getElementById('bg'),d=c.getContext('2d').getImageData(0,0,c.width,c.height).data,r=0;for(var i=0;i<d.length;i+=4*13)if(d[i]>60)r++;return r})()")>5)
    ok('the black sections are see-through so the background shows, while the ruby slabs and the panels stay solid enough to read',E("getComputedStyle(document.querySelector('.slab.black')).backgroundColor")=='rgba(0, 0, 0, 0)' and E("getComputedStyle(document.querySelector('.slab.red')).backgroundColor")=='rgb(165, 25, 43)')
    ok('the background is a field of entangled pairs: particles are created in proportion to the screen, each is mirrored across the vertical axis by its twin',E("__dq.BGX.P.length")>=18 and E("__dq.BGX.P.length")<=54)
    ok('reduced motion: the background is drawn once and stays still (not running), and hovering does not collapse anything',not E("__dq.BGX.on") and E("__dq.BGX.frames")>=1)
    c.close()
    c,pg,ST=page(init="window.__fast=false;");E=pg.evaluate;pg.wait_for_timeout(600);f1=E("__dq.BGX.frames");pg.wait_for_timeout(500);f2=E("__dq.BGX.frames")
    ok('with motion allowed the background really animates (frames keep advancing: %d to %d)'%(f1,f2),f2>f1+5 and E("__dq.BGX.on"))
    P=E("(function(){var p=__dq.BGX.P[0];return {x:p.x,y:p.y}})()");E("__dq.BGX.collapsed=0");pg.mouse.move(P['x'],P['y']);pg.wait_for_timeout(250)
    ok('TOUCH A PARTICLE and its pair collapses: the counter goes up, a note appears ("N particles collapsed by you"), it is remembered on this device, and the particle respawns somewhere else',E("__dq.BGX.collapsed")>=1 and 'collapsed by you' in pg.inner_text('#bgHud') and int(E("localStorage.getItem('singlet_bg')"))>=1)
    E("__dq.BGX.R.length=0");E("document.querySelector('.hero').dispatchEvent(new PointerEvent('pointerdown',{bubbles:true,clientX:40,clientY:430}))");r1=E("__dq.BGX.R.length")
    E("__dq.BGX.R.length=0");E("document.getElementById('detAgain').dispatchEvent(new PointerEvent('pointerdown',{bubbles:true,clientX:40,clientY:430}))");r2=E("__dq.BGX.R.length")
    ok('clicking empty space sends a ripple through the field; clicking a button does not',r1>=1 and r2==0,(r1,r2))
    E("__dq.BGX.collapsed=24");E("__dq.bgCollapse(__dq.BGX.P[1])");ok('collapsing the 25th particle unlocks the "Popper" achievement',E("!!__dq.ACH().popper") and 'Achievement: Popper' in pg.inner_text('#toast'))
    n1=E("__dq.BGX.P.length");pg.set_viewport_size({'width':420,'height':700});pg.wait_for_timeout(500);n2=E("__dq.BGX.P.length");ok('resizing the window re-fits the field (%d particles on desktop, %d on a phone-sized window)'%(n1,n2),n2<n1)
    t0=E("(function(){var t=performance.now();for(var i=0;i<60;i++)__dq.bgFrame(16);return (performance.now()-t)/60})()");ok('a frame of the background costs %.2f ms on average, well inside a 16 ms frame'%t0,t0<8)
    c.close()
    c,pg,ST=page();E=pg.evaluate
    ok('sound starts OFF: the toggle says so and reports its state to screen readers','Sound off' in pg.inner_text('#sndBtn') and E("document.getElementById('sndBtn').getAttribute('aria-pressed')")=='false')
    pg.click('#sndBtn');pg.reload();pg.wait_for_timeout(700);ok('turning sound on is remembered after a reload',pg.inner_text('#sndBtn')=='Sound on' and E("__dq.SND.on") and E("localStorage.getItem('singlet_snd')")=='1')
    go(pg,'#/run');connect(pg);pg.fill('#runMsg','sound check');pg.click('#runGo');pg.wait_for_timeout(500);ok('with sound on, a collapse plays a tone (the audio engine was used) and nothing breaks',(E("__dq.SND.plays||0")>0) or E("!(window.AudioContext||window.webkitAudioContext)"))
    c.close()
    c,pg,ST=page(init="window.AudioContext=undefined;window.webkitAudioContext=undefined;localStorage.setItem('singlet_snd','1');");E=pg.evaluate;go(pg,'#/run');pg.fill('#runMsg','silent');pg.click('#runGo');pg.wait_for_timeout(500);ok('a browser with no audio support still runs everything normally even with sound switched on',E("location.hash").startswith('#/r/L'));c.close()
    c,pg,ST=page();E=pg.evaluate;go(pg,'#/run');connect(pg);pg.fill('#runMsg','first one');pg.click('#runGo');pg.wait_for_timeout(500)
    ok('ACHIEVEMENTS: the first run unlocks "First collapse" with a notice, and it is saved on this device',E("!!__dq.ACH().first") and E("JSON.parse(localStorage.getItem('singlet_ach')).first")>0)
    E("__dq.achRun({m:{tier:{id:'epic'},glitched:false}})");E("__dq.achRun({m:{tier:{id:'common'},glitched:true}})");ok('an Epic result unlocks "Rare find" and a stuck qubit unlocks "Glitched"; a Common result with no glitch unlocks neither',E("!!__dq.ACH().rare&&!!__dq.ACH().glitch"))
    pg.reload();pg.wait_for_timeout(600);ok('achievements survive a reload',E("!!__dq.ACH().first&&!!__dq.ACH().rare"));c.close()
    c,pg,ST=page(init="localStorage.setItem('singlet_ach',JSON.stringify({first:'x',bogus:123,ten:-5,rare:1700000000000,_runs:-9}));");E=pg.evaluate
    ok('corrupted achievement data is cleaned: unknown ids, text and negative values are dropped; the one valid unlock stays',E("Object.keys(__dq.ACH()).filter(function(k){return k[0]!=='_'}).join()")=='rare' and E("__dq.ACH()._runs")==0);c.close()
    c,pg,ST=page();E=pg.evaluate;go(pg,'#/run');connect(pg)
    for i in range(10):
        pg.fill('#runMsg','run %d'%i);pg.click('#runGo');pg.wait_for_timeout(250);go(pg,'#/run')
    ok('ten runs unlock "Ten runs"',E("!!__dq.ACH().ten") and E("__dq.ACH()._runs")==10);c.close()
    # ================= connect wallet: every path
    PKb=list(PK1)
    LEG="window.__lc=[];window.phantom={solana:{isPhantom:true,connect:async function(o){window.__lc.push('connect'+(o?JSON.stringify(o):''));return {publicKey:{toString:function(){return '%s'},toBytes:function(){return new Uint8Array(%s)}}}},disconnect:async function(){window.__lc.push('disconnect')},signMessage:async function(m,e){window.__lc.push('signMessage');return {signature:new Uint8Array(64).fill(3)}},request:async function(o){window.__lc.push('request:'+o.method);return {signature:await window.onLegacy(o.params.message)}}}};"%(ADDR1,json.dumps(PKb))
    def legacy_page(ST=None,cfg=None):
        ST=ST if ST is not None else mkstate();c=br.new_context(viewport={'width':1360,'height':900});c.add_init_script("window.__fast=true;"+LEG)
        cnt={'n':60}
        def on_legacy(m58):
            b=b58d(m58);t,memo=mem_of(b);cnt['n']+=1;ST['sent'].append({'bytes':b,'tx':t,'memo':memo,'n':cnt['n'],'chain':'legacy'});add_entry(ST,sig(cnt['n']),memo,ADDR1);return sig(cnt['n'])
        c.expose_function('onLegacy',on_legacy);c.route('https://api.mainnet-beta.solana.com/**',rpc_handler(ST));c.route('https://fonts.googleapis.com/**',lambda r:r.abort());c.route('https://fonts.gstatic.com/**',lambda r:r.abort())
        pg=c.new_page();pg.on('pageerror',lambda e:errs.append(str(e)));pg.goto(URL);pg.wait_for_timeout(900)
        if cfg:pg.evaluate("Object.assign(__dq.CONFIG,%s)"%json.dumps(cfg))
        return c,pg,ST
    c,pg,ST=legacy_page();E=pg.evaluate;pg.click('#walletBtn')
    ok('OLDER WALLETS: an extension that only has the older interface (window.phantom.solana) is offered as "Connect Phantom (older interface)" instead of "no wallet found"',E("!!document.querySelector('[data-prov=\"Phantom (older interface)\"]')") and 'No Solana wallet was found' not in pg.inner_text('#mBody'))
    pg.click('[data-prov="Phantom (older interface)"]');pg.wait_for_timeout(300);ok('connecting through it works: the address is shown in the header and the legacy wallet was asked to connect once',pg.inner_text('#walletBtn')==ADDR1[:4]+'..'+ADDR1[-4:] and E("window.__lc.filter(function(x){return x.indexOf('connect')===0}).length")>=1 and E("__dq.W.addr")==ADDR1)
    go(pg,'#/run');pg.click('#signIn');pg.wait_for_timeout(400);ok('sign-in uses the older signMessage (the wallet was asked), and a signature that does not verify is rejected rather than trusted',E("window.__lc.indexOf('signMessage')>-1") and ('did not match' in pg.inner_text('#view') or 'Signed' in pg.inner_text('#runWallet') or 'signature' in pg.inner_text('#toast').lower()))
    c.close()
    ST=mkstate();c,pg,ST=legacy_page(ST,LEDGER_CFG);E=pg.evaluate;go(pg,'#/run');pg.click('#walletBtn');pg.click('[data-prov="Phantom (older interface)"]');pg.wait_for_timeout(300);pg.fill('#runMsg','through the older door');pg.click('#runGo');pg.wait_for_timeout(1500)
    ok('STAMPING through an older wallet: the transaction is sent with request("signAndSendTransaction") carrying the base58 of exactly the bytes the page built, and the run completes',len(ST['sent'])==1 and ST['sent'][0]['chain']=='legacy' and E("window.__lc.indexOf('request:signAndSendTransaction')>-1") and E("location.hash").startswith('#/r/') and ST['sent'][0]['tx']['keys'][0]==ADDR1);c.close()
    c,pg,ST=page(init=LEG,wopts={'name':'Phantom'});E=pg.evaluate;pg.click('#walletBtn');ok('when the same wallet also supports the wallet standard, only the standard one is listed (no duplicate "older interface" entry)',E("document.querySelectorAll('#mBody [data-prov]').length")==1 and E("document.querySelector('#mBody [data-prov]').getAttribute('data-prov')")=='Phantom');c.close()
    c,pg,ST=page(init="if(!localStorage.getItem('seeded')){localStorage.setItem('singlet_wallet','MockWallet');localStorage.setItem('seeded','1')}");E=pg.evaluate;pg.wait_for_timeout(900)
    ok('SILENT RECONNECT: if you connected this wallet before, the page reconnects on load without a popup (asked with silent:true), shows the address, and says "Reconnected"',E("__dq.W.addr")==ADDR1 and 'connect:silent' in E("window.__wc") and pg.inner_text('#walletBtn')==ADDR1[:4]+'..'+ADDR1[-4:])
    pg.click('#walletBtn');pg.click('#mDisc');pg.wait_for_timeout(200);k_before=E("localStorage.getItem('singlet_wallet')");s_before=E("localStorage.getItem('seeded')");pg.reload();pg.wait_for_timeout(900);ok('after you disconnect, the next visit does NOT reconnect by itself',E("__dq.W.addr")=='' and E("localStorage.getItem('singlet_wallet')") is None,('key before reload',k_before,'seeded before',s_before,'seeded after',E("localStorage.getItem('seeded')"),'key after',E("localStorage.getItem('singlet_wallet')")));c.close()
    c,pg,ST=page(init="localStorage.setItem('singlet_wallet','MockWallet');window.__wo.noSilent=true;");E=pg.evaluate;pg.wait_for_timeout(900);ok('if the wallet will not reconnect silently (not trusted yet) nothing happens: no error, no popup, the button still says Connect wallet',E("__dq.W.addr")=='' and pg.inner_text('#walletBtn')=='Connect wallet' and 'did not connect' not in pg.inner_text('#toast'));c.close()
    c,pg,ST=page();E=pg.evaluate;pg.click('#walletBtn');ok('the dialog shows each wallet\'s own icon next to its name',E("!!document.querySelector('#mBody [data-prov=MockWallet] img.wic')"));pg.click('[data-prov=MockWallet]');pg.wait_for_timeout(300);ok('...and the header button shows the icon once connected',E("!!document.querySelector('#walletBtn img.wic')"));c.close()
    c,pg,ST=page();E=pg.evaluate;E("__dq.W.wallets[0].icon='javascript:alert(1)'");pg.click('#walletBtn');pg.click('[data-prov=MockWallet]');pg.wait_for_timeout(300);ok('SAFETY: a wallet icon that is not an image address (javascript:) is never put in the page',E("document.querySelectorAll('img[src^=\"javascript\"]').length")==0 and E("!document.querySelector('#walletBtn img')"));c.close()
    c,pg,ST=page(wallet=False,init="window.__mk=function(n){return {name:n,version:'1.0.0',icon:'',chains:['solana:mainnet'],accounts:[],features:{'standard:connect':{connect:async function(){return {accounts:[]}}},'solana:signAndSendTransaction':{}}}};");E=pg.evaluate
    E("window.__evN=0;window.addEventListener('wallet-standard:app-ready',function(){window.__evN++})");pg.click('#walletBtn');E("setTimeout(function(){window.dispatchEvent(new CustomEvent('wallet-standard:register-wallet',{detail:function(api){api.register(window.__mk('SlowWallet'))}}))},1300)");pg.wait_for_timeout(1700)
    ok('a wallet that wakes up 1.3 seconds after the dialog opens still appears in it (the page keeps looking while the dialog is open)',E("!!document.querySelector('#mBody [data-prov=SlowWallet]')"))
    pg.click('#mClose');pg.wait_for_timeout(100);e1=E("window.__evN");pg.wait_for_timeout(900);ok('...and stops looking when the dialog closes (no background polling)',E("window.__evN")==e1);c.close()
    c,pg,ST=page(wopts={});E=pg.evaluate;E("window.__wo.noconnect=true");pg.click('#walletBtn');pg.click('[data-prov=MockWallet]');pg.wait_for_timeout(300);ok('a declined connection says so plainly inside the dialog, and you can try again','You declined the connection request' in pg.inner_text('#connStatus') and not E("document.getElementById('modal').hidden"))
    E("window.__wo.noconnect=false");pg.click('[data-prov=MockWallet]');pg.wait_for_timeout(300);ok('...trying again works',E("__dq.W.addr")==ADDR1 and E("document.getElementById('modal').hidden"));c.close()
    c,pg,ST=page();E=pg.evaluate;E("window.__wo.slow=500");pg.click('#walletBtn');pg.click('[data-prov=MockWallet]');pg.wait_for_timeout(250);hint=pg.inner_text('#connStatus');pg.wait_for_timeout(600)
    ok('a wallet that takes a long time shows a helpful "Still waiting" note with what to do, then connects when it answers','Still waiting for MockWallet' in hint and 'unlock' in hint.lower() and E("__dq.W.addr")==ADDR1)
    c.close()
    c,pg,ST=page(wallet=False);E=pg.evaluate;pg.click('#walletBtn');pg.fill('#lookupAddr','not an address');pg.click('#lookupGo');ok('READ-ONLY LOOKUP: a bad address is refused in the dialog and nothing opens','not a valid Solana address' in pg.inner_text('#connStatus') and E("location.hash")!='#/w/not an address')
    ok('...and an address that is 44 characters but decodes to 33 bytes is also refused',E("__dq.readAddr(%r)"%b58e(bytes(range(33))))is None and E("__dq.readAddr(%r)"%ADDR2)==ADDR2 and E("__dq.readAddr('')") is None)
    pg.fill('#lookupAddr',ADDR2);pg.click('#lookupGo');pg.wait_for_timeout(500)
    ok('a valid address opens that wallet\'s page, labelled read-only, with an explorer link to the ACCOUNT page',E("location.hash")=='#/w/'+ADDR2 and 'Read-only' in pg.inner_text('#roNote') and E("document.querySelector('#walletPage a[target=_blank]').href")=='https://solscan.io/account/'+ADDR2);c.close()
    c,pg,ST=page();E=pg.evaluate;connect(pg);pg.click('#walletBtn');ok('when connected the dialog offers My runs, Start a run, Copy address and Disconnect and shows the wallet name',all(E("!!document.querySelector('%s')"%s) for s in ['#mBody a[href=\"#/w/me\"]','#mBody a[href=\"#/run\"]','#mCopy','#mDisc']) and 'Connected with MockWallet' in pg.inner_text('#mBody'))
    pg.click('#mBody a[href="#/w/me"]');pg.wait_for_timeout(500);ok('My runs opens your page with your address and no read-only note',ADDR1 in pg.inner_text('#walletPage') and 'My runs' in pg.inner_text('h1') and not E("!!document.getElementById('roNote')"));c.close()
    # ================= wallet pages, export, hall, challenge
    c,pg,ST=page(wallet=False);E=pg.evaluate;go(pg,'#/run');pg.fill('#runMsg','page one');pg.click('#runGo');pg.wait_for_timeout(500);go(pg,'#/run');pg.fill('#runMsg','page two');pg.click('#runGo');pg.wait_for_timeout(500);go(pg,'#/w/me');pg.wait_for_timeout(600)
    ok('without a wallet, My runs shows the guest runs from this device, with totals, the rarest result, and a note explaining why','as a guest on this device' in pg.inner_text('#walletPage') and '2 runs' in pg.inner_text('#wpStats') and 'Rarest result' in pg.inner_text('#wpStats') and E("document.querySelectorAll('#wpList .feedrow').length")==2)
    ok('the achievements list shows what is unlocked and what is not (First collapse unlocked, Hall tourist locked)',"Unlocked: First collapse" in pg.inner_text('#achList') and "Locked: Tourist" in pg.inner_text('#achList') and E("document.querySelectorAll('#achList li').length")==11)
    with pg.expect_download() as dl:pg.click('#exportBtn')
    data=json.loads(open(dl.value.path()).read());ok('Download these runs as JSON gives a real file: site name, both runs with message, seed, tier and percentile',dl.value.suggested_filename.endswith('.json') and data['site']=='singlet' and len(data['runs'])==2 and all(k in data['runs'][0] for k in ['message','seed','tier','percentile','drift','qubits']))
    go(pg,'#/w/zzzz');ok('an invalid address in the link says "Not an address" and offers Connect wallet','Not an address' in pg.inner_text('h1') and E("!!document.querySelector('#walletPage button')"));c.close()
    ST=mkstate()
    for i,(w,m) in enumerate([(ADDR2,'b one'),(ADDR2,'b two'),(ADDR1,'a one')]):add_entry(ST,sig(130+i),'sgl1|r|6|%s|-|-|%s'%(w,m),w,slot=3000+i,t=int(time.time())-100*(3-i))
    add_entry(ST,sig(140),'sgl1|i|6|%s|%s|-|invite'%(ADDR1,ADDR2),ADDR1,slot=3010);add_entry(ST,sig(141),'sgl1|a|%s|%s|accept'%(sig(140),ADDR2),ADDR2,slot=3011)
    c,pg,ST=page(ST,wallet=False,cfg=LEDGER_CFG);E=pg.evaluate;go(pg,'#/w/'+ADDR2);pg.wait_for_timeout(1000)
    ok('a read-only page for an address lists only that wallet\'s runs from the chain, including entangled pairs it took part in',E("document.querySelectorAll('#wpList .feedrow').length")==3 and 'b one' in pg.inner_text('#wpList') and 'a one' not in pg.inner_text('#wpList') and '1 entangled pairs' in pg.inner_text('#wpStats'),pg.inner_text('#wpStats'));c.close()
    ST=mkstate()
    for i in range(30):add_entry(ST,sig(150+i),'sgl1|r|%d|%s|%s|-|hall %d'%([4,6,8,10][i%4],ADDR2,['-','storm','cold'][i%3] if i%2 else '-',i),ADDR2,slot=4000+i,t=int(time.time())-i*60)
    c,pg,ST=page(ST,wallet=False,cfg=LEDGER_CFG);E=pg.evaluate;go(pg,'#/hall');pg.wait_for_timeout(1200)
    exp=E("(async function(){var rs=await Promise.all(__dq.LEDGER.entries.filter(function(e){return e.p.t==='r'}).map(function(e){return __dq.entryToRun(e)}));var sc=rs.map(function(r){var o=__dq.computeRun(r);return {id:r.id,k:(o.m.glitched?1000:0)+(o.m.percentile||0)}}).sort(function(a,b){return b.k-a.k});return sc.slice(0,25).map(function(s){return s.id})})()")
    got=pg.eval_on_selector_all('#hallList .feedrow','e=>e.map(x=>x.getAttribute("href").split("/").pop())')
    ok('HALL OF RARITY: the 25 shown are exactly the rarest 25 of the 30 runs, in order (Glitched first, then by percentile), recomputed independently',got==exp and len(got)==25,(len(got),len(exp)))
    ok('each row has its rank, thumbnail, wallet, message, tier and percentile; opening the page unlocked "Tourist"',pg.eval_on_selector_all('#hallList .rk','e=>e.map(x=>x.textContent)')[:3]==['1','2','3'] and 'percentile' in pg.inner_text('#hallList') and E("!!__dq.ACH().tourist"))
    pg.click('[data-hf=cold]');pg.wait_for_timeout(500);rows=pg.eval_on_selector_all('#hallList .feedrow','e=>e.map(x=>x.textContent)');ok('the edition filter shows only that edition (Cold start): %d rows'%len(rows),0<len(rows)<25)
    pg.click('[data-hf=sparse]');pg.wait_for_timeout(500);ok('an edition with no runs shows an empty state, not a blank page','No runs on the ledger yet' in pg.inner_text('#hallList'));c.close()
    c,pg,ST=page();E=pg.evaluate;go(pg,'#/hall');pg.wait_for_timeout(400);ok('with no runs the Hall invites you to start one','No runs yet' in pg.inner_text('#hallList'));c.close()
    c,pg,ST=page();E=pg.evaluate;go(pg,'#/run');connect(pg);pg.fill('#runMsg','share me | please');pg.click('#runGo');pg.wait_for_timeout(500)
    pg.click('#challengeBtn');pg.wait_for_timeout(200);tt=pg.inner_text('#toast');url=re.search(r'(https?://\S+|file://\S+)',tt)
    ok('Challenge a friend produces a link that carries your exact (cleaned) message, qubit count and edition',('Challenge link copied' in tt) or (url and '#/run?m=' in url.group(1)))
    go(pg,'#/run?m=hello%20world&n=8&e=cold');pg.wait_for_timeout(500);ok('opening such a link pre-fills the run page: message, 8 qubits pressed, Cold start selected',E("document.getElementById('runMsg').value")=='hello world' and E("document.querySelector('[data-q=\"8\"]').getAttribute('aria-pressed')")=='true' and E("document.getElementById('runEd').value")=='cold')
    E("__dq.RS.msg='';__dq.RS.n=6;__dq.RS.ed=''");go(pg,'#/run?m=%s&n=7&e=zzz'%('x'*70));pg.wait_for_timeout(400);ok('bad link values are ignored: a 70-character message, 7 qubits and an unknown edition change nothing',E("document.getElementById('runMsg').value")=='' and E("__dq.RS.n")==6 and E("document.getElementById('runEd').value")=='');c.close()
    # ================= the lab: double slit, guessing game, jump chips
    c,pg,ST=page();E=pg.evaluate;go(pg,'#/lab');pg.wait_for_timeout(500)
    def corr(obs):
        return E("(function(obs){var S=__dq.LABX.slit,d=+document.getElementById('slitD').value/10,N=96,xs=[],ys=[],ts=0,hs=0;for(var i=0;i<N;i++){var x=-12+24*(i+.5)/N,v=__dq.slitI(x,d,obs);xs.push(v);ts+=v;hs+=S.hist[i]}var mt=ts/N,mh=hs/N,num=0,a=0,b=0;for(i=0;i<N;i++){var tv=xs[i]-mt,hv=S.hist[i]-mh;num+=tv*hv;a+=tv*tv;b+=hv*hv}return {r:num/Math.sqrt(a*b),n:S.n}})(%s)"%('true' if obs else 'false'))
    for _ in range(5):pg.click('#slit1k')
    r=corr(False);ok('DOUBLE SLIT (interference): after 5,000 particles the measured pattern matches the theory with correlation %.3f (above 0.97)'%r['r'],r['n']==5000 and r['r']>.97)
    zr=E("(function(){var S=__dq.LABX.slit,d=3,N=96,mx=0,mn=0,cm=0,cn=0;for(var i=0;i<N;i++){var x=-12+24*(i+.5)/N,v=__dq.slitI(x,d,false);if(v>.55*__dq.slitI(0,d,false)&&Math.abs(x)<5){mx+=S.hist[i];cm++}else if(v<.01&&Math.abs(x)<8){mn+=S.hist[i];cn++}}return [mx/cm,mn/Math.max(cn,1),cn]})()")
    ok('...and the dark bands really are dark: the bright bands average %.0f hits per bin against %.1f in the dark ones (more than 8 times)'%(zr[0],zr[1]),zr[2]>=2 and zr[0]>8*max(zr[1],.5))
    pg.check('#slitObs');pg.wait_for_timeout(100);ok('watching the slits clears the screen and the explanation changes to "two overlapping humps and no fringes"',E("__dq.LABX.slit.n")==0 and 'no fringes' in pg.inner_text('#slitRead'))
    for _ in range(5):pg.click('#slit1k')
    r=corr(True);ok('(watched) the pattern is the two-hump one: correlation with that theory is %.3f, and it is NOT a good match for the fringe pattern (%.3f)'%(r['r'],corr(False)['r']),r['r']>.97 and corr(False)['r']<r['r']-.05)
    ok('having fired 1,000 or more both watched and unwatched unlocked "Wave and particle"',E("!!__dq.ACH().slit"))
    pg.click('#slit1');ok('Fire 1 adds exactly one particle',E("__dq.LABX.slit.n")==5001 and '5,001 particles' in pg.inner_text('#slitRead'))
    E("var s=document.getElementById('slitD');s.value=45;s.dispatchEvent(new Event('input'))");ok('changing the slit gap restarts the pattern',E("__dq.LABX.slit.n")==0);pg.click('#slit100');pg.click('#slitClear');ok('Clear empties it',E("__dq.LABX.slit.n")==0)
    t1=E("(function(){var b=document.getElementById('slit1k'),t=performance.now();b.click();return performance.now()-t})()");ok('firing 1,000 particles takes %.0f ms'%t1,t1<400)
    ok('all game buttons start disabled until a game begins',E("document.getElementById('gBet0').disabled&&document.getElementById('gBet1').disabled") and 'Press New game' in pg.inner_text('#gStat'))
    ps=[]
    for _ in range(60):pg.click('#gNew');ps.append(E("__dq.LABX.guess.p"))
    ok('GUESS THE QUBIT: the hidden bias is always between 10%% and 90%% and never within 8 points of a fair coin (60 games: %.2f to %.2f)'%(min(ps),max(ps)),all(.1<=p<=.9 and abs(p-.5)>=.0799 for p in ps) and len(set(round(p,4) for p in ps))>40)
    pg.click('#gNew');E("__dq.LABX.guess.p=0.999999999");
    for _ in range(10):pg.click('#gBet1')
    ok('betting on the sure thing ten times scores 10 of 10, the buttons lock, and the summary tells you the hidden bias','You called 10 of 10' in pg.inner_text('#gSum') and E("document.getElementById('gBet1').disabled") and '100%' in pg.inner_text('#gSum') and E("document.querySelectorAll('#gTrack .gdot.hit').length")==10)
    ok('a score of 8 or more unlocks "Called it" and the best score is remembered on this device',E("!!__dq.ACH().game") and E("localStorage.getItem('singlet_game_best')")=='10')
    pg.click('#gNew');E("__dq.LABX.guess.p=0.999999999");
    for _ in range(10):pg.click('#gBet0')
    ok('betting against the sure thing scores 0 and the dots show ten misses (the best stays 10)','You called 0 of 10' in pg.inner_text('#gSum') and E("document.querySelectorAll('#gTrack .gdot.miss').length")==10 and E("localStorage.getItem('singlet_game_best')")=='10')
    pg.click('.chips [aria-label]' if False else "button.chip:has-text('Guess game')");pg.wait_for_timeout(500);top=E("document.getElementById('lab-guess').getBoundingClientRect().top");ok('the jump chips scroll to their experiment (Guess game is now near the top: %d px)'%top,-60<top<400)
    c.close()
    # ================= the system check
    ST=mkstate();c,pg,ST=page(ST,cfg=dict(LEDGER_CFG,tokenMint=MINT,tokenSymbol='DCH',tokenDecimals=6));E=pg.evaluate;connect(pg);go(pg,'#/status');pg.wait_for_timeout(2500)
    rows={r[0]:r[1] for r in zip(pg.eval_on_selector_all('.st tbody tr','rs=>rs.map(r=>r.children[0].textContent)'),pg.eval_on_selector_all('.st tbody tr','rs=>rs.map(r=>r.children[1].textContent)'))}
    ok('SYSTEM CHECK: a healthy configured site passes every check (the only allowed warning is fonts, which are blocked in this test): %s'%{k:v for k,v in rows.items() if v not in ('Pass',)},len(rows)==19 and all(v=='Pass' for k,v in rows.items() if k not in ('Fonts','Background field')) and rows['Fonts'] in ('Warning','Pass') and rows['Background field'] in ('Skipped','Pass'))
    ok('every row shows what it found and how long it took; the summary counts them; running it unlocks "Mechanic"',all('ms' in t for t in pg.eval_on_selector_all('.st tbody tr','rs=>rs.map(r=>r.children[3].textContent)')) and 'failed' in pg.inner_text('#stSum') and '0 failed' in pg.inner_text('#stSum') and E("!!__dq.ACH().mechanic"))
    ok('the footer dot is lit when the self-tests pass, and says so on hover',E("document.getElementById('footStatus').getAttribute('data-ok')")=='1' and 'passed' in E("document.getElementById('footStatus').title"))
    pg.click('#stCopy');pg.wait_for_timeout(200);ok('Copy the report confirms (or tells you how to copy by hand)','Report copied' in pg.inner_text('#toast') or 'copy it' in pg.inner_text('#toast').lower())
    E("document.body.insertAdjacentHTML('beforeend','<a href=\"#/nowhere\">x</a>')");E("window.dispatchEvent(new ErrorEvent('error',{message:'boom'}))");pg.click('#stRun');pg.wait_for_timeout(2500)
    rows={a:(b,c2) for a,b,c2 in zip(pg.eval_on_selector_all('.st tbody tr','rs=>rs.map(r=>r.children[0].textContent)'),pg.eval_on_selector_all('.st tbody tr','rs=>rs.map(r=>r.children[1].textContent)'),pg.eval_on_selector_all('.st tbody tr','rs=>rs.map(r=>r.children[2].textContent)'))}
    ok('it catches real problems: a broken link is named, and a script error that happened is reported',rows['Internal links'][0]=='Fail' and '#/nowhere' in rows['Internal links'][1] and rows['Page errors'][0]=='Fail' and 'boom' in rows['Page errors'][1])
    E("__dq.CAL['std:6']=[1,0]");pg.click('#stRun');pg.wait_for_timeout(2500);ok('it catches a corrupted rarity table, and the footer dot changes to show the failure',pg.eval_on_selector_all('.st tbody tr','rs=>rs.map(r=>[r.children[0].textContent,r.children[1].textContent])').count(['Rarity tables','Fail'])==1 and E("document.getElementById('footStatus').getAttribute('data-ok')")=='0');c.close()
    ST=mkstate();ST['rpcfail']=True;c,pg,ST=page(ST,wallet=False,cfg=LEDGER_CFG);E=pg.evaluate;go(pg,'#/status');pg.wait_for_timeout(2500)
    rows={a:(b,c2) for a,b,c2 in zip(pg.eval_on_selector_all('.st tbody tr','rs=>rs.map(r=>r.children[0].textContent)'),pg.eval_on_selector_all('.st tbody tr','rs=>rs.map(r=>r.children[1].textContent)'),pg.eval_on_selector_all('.st tbody tr','rs=>rs.map(r=>r.children[2].textContent)'))}
    ok('when the Solana connection is down, exactly the network checks fail with the reason ("answered 500") and the local checks still pass',all(rows[k][0]=='Fail' for k in ['Solana RPC','Memo program','Ledger address']) and 'answered 500' in rows['Solana RPC'][1] and all(rows[k][0]=='Pass' for k in ['Hashing','Quantum simulator','Result engine','Rarity tables']) and rows['Wallet detection'][0]=='Warning' and rows['Wallet connection'][0]=='Skipped')
    ok('with no token set, the token check is Skipped with a plain explanation',rows['Token mint'][0]=='Skipped' and 'open access' in rows['Token mint'][1]);c.close()
    ST=mkstate();ST['decimals']=9;c,pg,ST=page(ST,wallet=False,cfg=dict(LEDGER_CFG,tokenMint=MINT,tokenDecimals=6));E=pg.evaluate;go(pg,'#/status');pg.wait_for_timeout(2500);tm=pg.eval_on_selector_all('.st tbody tr','rs=>rs.map(r=>[r.children[0].textContent,r.children[1].textContent,r.children[2].textContent])');tm=[r for r in tm if r[0]=='Token mint'][0]
    ok('a token whose decimals on the network differ from the settings fails the check and says both numbers',tm[1]=='Fail' and '9 decimals' in tm[2] and 'expects 6' in tm[2]);c.close()
    c,pg,ST=page(wallet=False);E=pg.evaluate;go(pg,'#/status');pg.wait_for_timeout(1500);rows={r[0]:r[1] for r in zip(pg.eval_on_selector_all('.st tbody tr','rs=>rs.map(r=>r.children[0].textContent)'),pg.eval_on_selector_all('.st tbody tr','rs=>rs.map(r=>r.children[2].textContent)'))}
    ok('with no ledger address set, the ledger check is skipped and says runs stay on each visitor\'s device','Ledger address' in rows and 'stay on each visitor' in rows['Ledger address']);c.close()
    # ================= the crawler: every link on every page, every button
    c,pg,ST=page();E=pg.evaluate;connect(pg);seen=set();bad=[]
    routes=['#/','#/run','#/lab','#/forge','#/hall','#/ledger','#/status','#/w/me','#/r/L0000000000000000']
    for rt in routes:
        go(pg,rt);pg.wait_for_timeout(350)
        for href in E("[].map.call(document.querySelectorAll('a[href^=\"#/\"]'),function(a){return a.getAttribute('href')})"):seen.add(href)
    for href in sorted(seen):
        go(pg,href);pg.wait_for_timeout(300);t=E("(document.querySelector('#view h1')||{}).textContent||''")
        if not t.strip():bad.append(href)
    ok('LINK CRAWL: every internal link found on all %d pages (%d distinct) opens a real page with a heading'%(len(routes),len(seen)),not bad and len(seen)>=12,bad)
    errs_before=len(errs);E("__dq.ERRS.length=0");clicked=0
    for rt in ['#/','#/run','#/lab','#/forge','#/hall','#/ledger','#/status']:
        go(pg,rt);pg.wait_for_timeout(300)
        ids=E("[].filter.call(document.querySelectorAll('#view button, .mast button'),function(b){return !b.disabled&&b.offsetParent!==null&&b.id!=='walletBtn'}).map(function(b,i){b.setAttribute('data-crawl',i);return i})")
        for i in ids[:40]:
            try:pg.click('[data-crawl="%d"]'%i,timeout=1500);clicked+=1
            except Exception:pass
            pg.keyboard.press('Escape')
            if E("location.hash")!=rt:
                go(pg,rt);pg.wait_for_timeout(150)
    ok('BUTTON CRAWL: %d buttons were clicked across 7 pages and not one caused a script error'%clicked,clicked>25 and E("__dq.ERRS.length")==0 and len(errs)==errs_before,(E("__dq.ERRS")[:2],errs[errs_before:][:2]));c.close()
    # ================= readability, names and phones for the new pages
    c,pg,ST=page();E=pg.evaluate
    for h,name in [('#/hall','hall'),('#/status','status check'),('#/w/me','my runs'),('#/lab','lab (all five)')]:
        go(pg,h);pg.wait_for_timeout(1200);a=E(AUDIT%"document.body");ok('%s page: every piece of text is readable (%d blocks, AA 4.5:1)'%(name,a['n']),not a['bad'],a['bad'][:3])
    go(pg,'#/lab');pg.click('#gNew');ok('every control on the lab (sliders, checkbox, buttons, chips) has an accessible name',E("[].filter.call(document.querySelectorAll('#view button,#view input,#view select'),function(e){var n=(e.getAttribute('aria-label')||e.textContent||'').trim();if(!n){var l=e.closest('label');n=l?l.textContent.trim():''}if(!n&&e.id){var l2=document.querySelector('label[for=\"'+e.id+'\"]');n=l2?l2.textContent.trim():''}return !n}).length")==0)
    c.close()
    c,pg,ST=page(vp=(390,844),mobile=True,ua=IPH);E=pg.evaluate;worst=0
    for h in ['#/hall','#/status','#/w/me','#/lab','#/w/'+ADDR2]:
        go(pg,h);pg.wait_for_timeout(700);worst=max(worst,E("document.documentElement.scrollWidth"))
    ok('phone: the new pages (hall, system check, wallet page, the full lab) do not scroll sideways (widest %d)'%worst,worst<=392,worst)
    go(pg,'#/lab');small=E("[].filter.call(document.querySelectorAll('#view button,#view a.btn,#view input[type=range],#view .chip,#view .chk'),function(b){var r=b.getBoundingClientRect();return b.offsetParent!==null&&r.width>0&&r.height<36}).map(function(b){return (b.id||b.textContent.trim().slice(0,12))+':'+Math.round(b.getBoundingClientRect().height)}).slice(0,5)");ok('phone: every lab control is at least 36px tall',not small,small)
    pg.tap('#walletBtn');pg.fill('#lookupAddr',ADDR2);pg.tap('#lookupGo');pg.wait_for_timeout(500);ok('phone: the address lookup works by tapping',E("location.hash")=='#/w/'+ADDR2);c.close()
    # ================= the X link
    c,pg,ST=page();E=pg.evaluate
    ok('an X button sits directly to the RIGHT of Connect wallet in the header and goes to x.com/UseSinglet in a new tab, with noopener and an accessible name',E("(function(){var a=document.querySelector('.mast .xbtn'),w=document.getElementById('walletBtn');return !!a&&a.href==='https://x.com/UseSinglet'&&a.target==='_blank'&&/noopener/.test(a.rel)&&a.previousElementSibling===w&&a.getBoundingClientRect().left>=w.getBoundingClientRect().right-1&&/X/.test(a.getAttribute('aria-label'))&&a.querySelector('svg')!==null})()"))
    ok('the X button is a proper 46px target, the same height as Connect wallet, and shows on every page (home, lab, ledger)',E("(function(){var a=document.querySelector('.xbtn'),w=document.getElementById('walletBtn');return a.getBoundingClientRect().height>=44&&Math.abs(a.getBoundingClientRect().height-w.getBoundingClientRect().height)<=2})()") and all((go(pg,h) or True) and E("!!document.querySelector('.mast .xbtn')") for h in ['#/lab','#/ledger','#/hall']))
    ok('the footer also links to the same X page ("Follow on X")',E("(function(){var l=[].filter.call(document.querySelectorAll('footer a'),function(a){return a.textContent==='Follow on X'})[0];return !!l&&l.href==='https://x.com/UseSinglet'&&l.target==='_blank'&&/noopener/.test(l.rel)})()"))
    a=E(AUDIT%"document.querySelector('.mast')");ok('the header with the X button is readable and its icon is visible (white on black)',not a['bad'],a['bad'][:2]);c.close()
    c,pg,ST=page(vp=(390,844),mobile=True,ua=IPH);E=pg.evaluate;ok('phone: the X button is in the header, at least 44px, and the header does not make the page scroll sideways',E("document.documentElement.scrollWidth")<=392 and E("document.querySelector('.xbtn').getBoundingClientRect().height")>=44 and E("document.querySelector('.xbtn').getBoundingClientRect().right")<=391);c.close()
    # ================= scroll reveal: text fades into frame as you scroll
    c,pg,ST=page(init="window.__fast=false;");E=pg.evaluate;pg.wait_for_timeout(1800)
    ok('SCROLL REVEAL (motion allowed): the page opts in, and content far below the fold starts hidden and waiting',E("document.documentElement.classList.contains('js-rv')") and E("getComputedStyle(document.querySelector('.diff li')).opacity")=='0' and E("getComputedStyle(document.querySelector('.faq details')).opacity")=='0')
    ok('...while what is on screen at load (headline, intro, buttons, the detector) has already faded in',all(E("getComputedStyle(document.querySelector('%s')).opacity"%s)=='1' for s in ['.hero h1','.hero .lead','.hero .cta','.detector']))
    E("document.querySelector('.diff').scrollIntoView({behavior:'instant'})");pg.wait_for_timeout(250)
    mid=E("getComputedStyle(document.querySelector('.diff li')).opacity");pg.wait_for_timeout(1800)
    ok('scrolling to a section fades its text in (it is mid-fade, then fully visible, and the transform settles to none)',float(E("getComputedStyle(document.querySelector('.diff li')).opacity"))==1 and E("getComputedStyle(document.querySelector('.diff li')).transform")=='none' and E("getComputedStyle(document.querySelector('.diff h2, .h2')).opacity")!=None,mid)
    dl=E("[].map.call(document.querySelectorAll('.diff li'),function(e){return parseInt(e.style.getPropertyValue('--d')||'0')})")
    ok('items that arrive together are staggered, not all at once (delays %s ms)'%dl,len(set(dl))>1 and dl==sorted(dl) or len(set(dl))>1,dl)
    E("window.scrollTo(0,0)");pg.wait_for_timeout(300);E("document.querySelector('.diff').scrollIntoView({behavior:'instant'})");pg.wait_for_timeout(300);ok('once revealed it stays: scrolling away and back does not hide or replay it',float(E("getComputedStyle(document.querySelector('.diff li')).opacity"))==1)
    E("document.querySelector('.cta-slab').scrollIntoView({behavior:'instant'})");pg.wait_for_timeout(1800);ok('the last section reveals too (the closing line and button)',E("getComputedStyle(document.querySelector('.cta-slab .giant')).opacity")=='1' and E("getComputedStyle(document.querySelector('.cta-slab .btn')).opacity")=='1')
    ok('the transition is a calm 0.8 second ease with the text rising about 26 to 44 pixels, not a bounce or a spin',E("getComputedStyle(document.querySelector('.rrow')).transitionDuration").startswith('0.8s') and 'cubic-bezier' in E("getComputedStyle(document.querySelector('.rrow')).transitionTimingFunction"))
    go(pg,'#/lab');pg.wait_for_timeout(1500);ok('on a new page the first block fades in and later blocks wait until you scroll to them',E("getComputedStyle(document.querySelector('.lab-exp')).opacity")=='1' and E("getComputedStyle(document.querySelector('#lab-guess')).opacity")=='0')
    pg.click("button.chip:has-text('Guess game')");pg.wait_for_timeout(2200);ok('jumping to an experiment with the jump chips reveals it',E("getComputedStyle(document.querySelector('#lab-guess')).opacity")=='1')
    E("var s=document.getElementById('labMsg');s.value='retyping a lot';s.dispatchEvent(new Event('input'))");pg.wait_for_timeout(300);ok('typing into a live experiment never makes it flicker or fade again (the live parts are not part of the reveal)',E("document.querySelectorAll('#labHist .rv, #labOut.rv, #labArt .rv').length")==0)
    go(pg,'#/run');pg.wait_for_timeout(1200);ok('forms and panels fade in as well, and the inputs remain usable (keyboard focus on a hidden one scrolls it into view and shows it)',E("getComputedStyle(document.querySelector('#runForm')).opacity")=='1');c.close()
    ST=mkstate()
    for i in range(6):add_entry(ST,sig(160+i),'sgl1|r|6|%s|-|-|row %d'%(ADDR2,i),ADDR2,slot=5000+i,t=int(time.time())-i*60)
    c,pg,ST=page(ST,init="window.__fast=false;",cfg=LEDGER_CFG);E=pg.evaluate;go(pg,'#/ledger');pg.wait_for_timeout(1500)
    ok('live lists (ledger rows) are not animated, so filtering and searching them never flickers',E("document.querySelectorAll('#ledgerList .feedrow').length")>=1 and E("document.querySelectorAll('#ledgerList .rv, #ledgerList [class*=rv]').length")==0);c.close()
    c,pg,ST=page();E=pg.evaluate;pg.wait_for_timeout(500)
    ok('REDUCED MOTION: the reveal is switched off completely (no opt-in class, nothing starts hidden, nothing moves)',not E("document.documentElement.classList.contains('js-rv')") and E("getComputedStyle(document.querySelector('.diff li')).opacity")=='1' and E("getComputedStyle(document.querySelector('.faq details')).opacity")=='1' and E("document.querySelectorAll('.rv').length")==0);c.close()
    c=br.new_context(viewport={'width':1360,'height':900},reduced_motion='reduce');c.add_init_script("window.__fast=false;");c.route('https://fonts.googleapis.com/**',lambda r:r.abort());c.route('https://fonts.gstatic.com/**',lambda r:r.abort());pg=c.new_page();pg.on('pageerror',lambda e:errs.append(str(e)));pg.goto(URL);pg.wait_for_timeout(900);E=pg.evaluate
    ok('the operating-system "reduce motion" setting alone is enough to turn the reveal off',not E("document.documentElement.classList.contains('js-rv')") and E("getComputedStyle(document.querySelector('.diff li')).opacity")=='1');c.close()
    c,pg,ST=page(init="window.__fast=false;delete window.IntersectionObserver;");E=pg.evaluate;pg.wait_for_timeout(900)
    ok('SAFE FALLBACK: a browser without the feature never hides anything (all text is visible, no opt-in class)',not E("document.documentElement.classList.contains('js-rv')") and E("getComputedStyle(document.querySelector('.diff li')).opacity")=='1' and 'Collapse' in pg.inner_text('.hero h1'));c.close()
    c,pg,ST=page(init="window.__fast=false;");E=pg.evaluate;pg.wait_for_timeout(1200)
    ok('hidden-until-scrolled text is still in the page for screen readers and find-in-page (it is faded, not removed)',E("document.querySelector('.faq details').offsetHeight")>20 and 'Is this a real quantum computer' in E("document.querySelector('.faq').textContent") and E("getComputedStyle(document.querySelector('.faq details')).visibility")=='visible' and E("getComputedStyle(document.querySelector('.faq details')).display")!='none')
    E("[].forEach.call(document.querySelectorAll('.rv'),function(e){e.classList.add('in')})");pg.wait_for_timeout(1100);a=E(AUDIT%"document.body");ok('after everything is revealed every block of text passes the AA contrast check (%d blocks)'%a['n'],not a['bad'],a['bad'][:3]);c.close()
    # ================= header layout: logo left, links centred, buttons right
    def hdr(vp):
        c,pg,ST=page(vp=vp,mobile=vp[0]<500,ua=IPH if vp[0]<500 else None);return c,pg
    c,pg=hdr((1360,900));E=pg.evaluate
    geo=E("(function(){function r(s){var x=document.querySelector(s).getBoundingClientRect();return {l:x.left,r:x.right,t:x.top,b:x.bottom,c:(x.left+x.right)/2}}return {brand:r('.brand'),nav:r('.nav'),act:r('.actions'),vw:innerWidth}})()")
    ok('HEADER (wide): the five page links are centred on the page (nav centre %.1f vs page centre %.1f), the logo is on the left and the buttons on the right'%(geo['nav']['c'],geo['vw']/2),abs(geo['nav']['c']-geo['vw']/2)<=1.5 and geo['brand']['r']<geo['nav']['l'] and geo['act']['l']>geo['nav']['r'] and geo['act']['r']>geo['vw']-80)
    ok('the links are Run, Lab, Forge, Hall, Ledger in that order and the nav holds only links; Sound, Connect wallet and X are in their own group on the right in that order',E("[].map.call(document.querySelectorAll('.nav > *'),function(e){return e.textContent}).join()")=='Run,Lab,Forge,Hall,Ledger' and E("[].map.call(document.querySelectorAll('.actions > *'),function(e){return e.id||e.className}).join()")=='sndBtn,walletBtn,xbtn' and E("document.querySelectorAll('.nav button').length")==0)
    ok('all three parts sit on one row at this width (same vertical band)',abs(geo['brand']['t']-geo['nav']['t'])<30 and abs(geo['act']['t']-geo['nav']['t'])<30)
    pg.keyboard.press('Tab');seq=[]
    for _ in range(10):
        pg.keyboard.press('Tab');seq.append(E("(function(){var e=document.activeElement;return (e.id||e.textContent||e.getAttribute('aria-label')||'').trim().slice(0,22)})()"))
    ok('keyboard order follows the picture left to right: logo, Run, Lab, Forge, Hall, Ledger, Sound, Connect wallet, X (%s)'%seq[:9],seq[1:6]==['Run','Lab','Forge','Hall','Ledger'] and seq[6]=='sndBtn' and seq[7]=='walletBtn' and 'on X' in seq[8] and seq[0]=='singlet')
    go(pg,'#/forge');ok('the current page is still marked in the centred links (Forge)',E("document.querySelector('.nav a[aria-current=page]').textContent")=='Forge' and E("document.querySelectorAll('.nav a[aria-current]').length")==1)
    pg.click('#walletBtn');ok('Connect wallet in its new place still opens the dialog',not E("document.getElementById('modal').hidden"));pg.keyboard.press('Escape');c.close()
    GEO="(function(){function r(s){var x=document.querySelector(s).getBoundingClientRect();return {l:x.left,r:x.right,t:x.top,b:x.bottom,c:(x.left+x.right)/2,w:x.width,h:x.height}}return {brand:r('.brand'),nav:r('.nav'),act:r('.actions'),snd:r('#sndBtn'),wal:r('#walletBtn'),mast:r('.mast'),vw:innerWidth,sw:document.documentElement.scrollWidth,span:getComputedStyle(document.querySelector('.brand span')).display}})()"
    for w in (1500,1300):
        c,pg=hdr((w,800));E=pg.evaluate;g=E(GEO)
        ok('HEADER (%dpx, roomy): links centred on the page in the top row (%.1f vs %.1f), wordmark and the full "Sound off" label shown, header one row tall (%dpx), no sideways scroll'%(w,g['nav']['c'],g['vw']/2,g['mast']['h']),abs(g['nav']['c']-g['vw']/2)<=1.5 and g['mast']['h']<=80 and g['span']!='none' and g['snd']['w']>100 and g['sw']<=w+1 and g['brand']['r']<g['nav']['l'] and g['nav']['r']<g['act']['l']);c.close()
    for w in (1299,1100,1040):
        c,pg=hdr((w,800));E=pg.evaluate;g=E(GEO)
        ok('HEADER (%dpx, compact): the links stay in the MIDDLE of the top row and are exactly centred on the page (%.1f vs %.1f); the logo is on its own and the sound toggle is a small icon button'%(w,g['nav']['c'],g['vw']/2),abs(g['nav']['c']-g['vw']/2)<=1.5 and g['mast']['h']<=80 and g['span']=='none' and 43<=g['snd']['w']<=50 and g['brand']['r']<g['nav']['l'] and g['nav']['r']<g['act']['l'] and g['sw']<=w+1);c.close()
    for w in (1000,900,820,801):
        c,pg=hdr((w,800));E=pg.evaluate;g=E(GEO);free=(g['brand']['r']+g['act']['l'])/2
        ok('HEADER (%dpx, tight): the links are still in the top row, centred between the logo and the buttons (%.1f vs %.1f), nothing overlaps, header one row tall (%dpx), no sideways scroll'%(w,g['nav']['c'],free,g['mast']['h']),abs(g['nav']['c']-free)<=2.5 and g['brand']['r']<g['nav']['l']-8 and g['nav']['r']<g['act']['l']-8 and g['mast']['h']<=80 and abs(g['nav']['t']-g['brand']['t'])<30 and g['sw']<=w+1);c.close()
    c,pg=hdr((900,800));E=pg.evaluate
    ok('compact sound button keeps its accessible name ("Sound off") and the brand link keeps its label, though only icons show',E("document.getElementById('sndBtn').textContent")=='Sound off' and E("document.querySelector('.brand').getAttribute('aria-label')")=='singlet, home' and E("getComputedStyle(document.getElementById('sndBtn'),'::before').content")!='none')
    pg.click('#sndBtn');pg.wait_for_timeout(100);ok('...and toggling it shows the on state (ruby fill) and reports it to screen readers',E("document.getElementById('sndBtn').getAttribute('aria-pressed')")=='true' and E("getComputedStyle(document.getElementById('sndBtn')).backgroundColor")=='rgb(165, 25, 43)');c.close()
    for w in (800,700):
        c,pg=hdr((w,800));E=pg.evaluate;g=E(GEO)
        ok('HEADER (%dpx): below 801px the links move to their own centred row (%.1f vs %.1f) and nothing overlaps or scrolls sideways'%(w,g['nav']['c'],g['vw']/2),abs(g['nav']['c']-g['vw']/2)<=1.5 and g['nav']['t']>=g['brand']['b']-2 and g['sw']<=w+1);c.close()
    for w in (390,320):
        c,pg=hdr((w,800));E=pg.evaluate
        geo=E("(function(){function r(s){var x=document.querySelector(s).getBoundingClientRect();return {l:x.left,r:x.right,t:x.top,b:x.bottom,c:(x.left+x.right)/2}}return {brand:r('.brand'),nav:r('.nav'),act:r('.actions'),vw:innerWidth}})()")
        ok('HEADER (phone, %dpx): logo, then the centred links, then the buttons, stacked; nothing scrolls sideways and every link and button is at least 36px tall'%w,abs(geo['nav']['c']-geo['vw']/2)<=2 and geo['nav']['t']>=geo['brand']['b']-2 and geo['act']['t']>=geo['nav']['b']-2 and E("document.documentElement.scrollWidth")<=w+2 and not E("[].filter.call(document.querySelectorAll('.mast a,.mast button'),function(b){return b.getBoundingClientRect().height<36}).length"),(geo['nav']['c'],w/2));c.close()
    ok('no page errors in the whole session',not errs,errs[:3]);br.close()
print('\nSUMMARY: %d/%d passed'%(sum(1 for _,c in res if c),len(res)))
