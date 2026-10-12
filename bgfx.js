// ======== life: the background field, sound and achievements ========
var BGX={cv:null,cx:null,P:[],R:[],mx:-999,my:-999,w:0,h:0,dpr:1,on:false,frames:0,collapsed:0,scrollV:0,lastY:0,amb:0};
function bgSize(){var cv=BGX.cv;BGX.dpr=Math.min(1.5,window.devicePixelRatio||1);BGX.w=innerWidth;BGX.h=innerHeight;cv.width=Math.floor(BGX.w*BGX.dpr);cv.height=Math.floor(BGX.h*BGX.dpr)}
function bgSpawn(){var n=Math.max(18,Math.min(54,Math.round(BGX.w*BGX.h/30000))),P=[],rg=rngFrom('bg|'+BGX.w+'x'+BGX.h);for(var i=0;i<n;i++)P.push({x:rg()*BGX.w,y:rg()*BGX.h,vx:(rg()-.5)*.5,vy:(rg()-.5)*.5,r:1.2+rg()*1.8,f:0,ph:rg()*6.28});BGX.P=P}
function bgRipple(x,y,a){BGX.R.push({x:x,y:y,r:4,a:a||.4});if(BGX.R.length>24)BGX.R.shift()}
function bgCollapse(p){p.f=1;bgRipple(p.x,p.y,.5);bgRipple(BGX.w-p.x,p.y,.5);p.x=Math.random()*BGX.w;p.y=Math.random()*BGX.h;p.vx=(Math.random()-.5)*.6;p.vy=(Math.random()-.5)*.6;BGX.collapsed++;try{localStorage.setItem('singlet_bg',String(BGX.collapsed))}catch(e){}bgHud();if(BGX.collapsed===25)unlock('popper');sfx('tick')}
function bgHud(){var e=$('bgHud');if(e)e.textContent=BGX.collapsed?fmt(BGX.collapsed)+' particles collapsed by you':''}
function bgFrame(dt){var cx=BGX.cx,w=BGX.w,h=BGX.h,P=BGX.P,i,p;cx.setTransform(BGX.dpr,0,0,BGX.dpr,0,0);cx.fillStyle='rgba(0,0,0,'+(BGX.on?.22:1)+')';cx.fillRect(0,0,w,h);
 if(BGX.on){BGX.amb-=dt;if(BGX.amb<=0){BGX.amb=2600+Math.random()*2400;bgRipple(Math.random()*w,Math.random()*h,.16)}}
 cx.lineWidth=1.2;for(i=BGX.R.length-1;i>=0;i--){var R=BGX.R[i];R.r+=BGX.on?1.8:0;R.a-=BGX.on?.006:0;if(R.a<=0){BGX.R.splice(i,1);continue}cx.strokeStyle='rgba(224,64,79,'+R.a+')';cx.beginPath();cx.arc(R.x,R.y,R.r,0,6.283);cx.stroke()}
 var sv=BGX.scrollV*.04;BGX.scrollV*=.9;
 for(i=0;i<P.length;i++){p=P[i];if(BGX.on){p.vx+=(Math.random()-.5)*.012;p.vy+=(Math.random()-.5)*.012+sv*.02;p.vx*=.995;p.vy*=.995;var sp=Math.hypot(p.vx,p.vy);if(sp>.7){p.vx*=.7/sp;p.vy*=.7/sp}p.x+=p.vx;p.y+=p.vy;if(p.x<-10)p.x=w+10;if(p.x>w+10)p.x=-10;if(p.y<-10)p.y=h+10;if(p.y>h+10)p.y=-10}
  var tx=w-p.x,ty=p.y;cx.strokeStyle='rgba(224,64,79,.04)';cx.beginPath();cx.moveTo(p.x,p.y);cx.lineTo(tx,ty);cx.stroke();
  var d=Math.hypot(BGX.mx-p.x,BGX.my-p.y),d2=Math.hypot(BGX.mx-tx,BGX.my-ty);
  if(BGX.on&&(d<30||d2<30)){bgCollapse(p);continue}
  if(d<170){cx.strokeStyle='rgba(242,96,107,'+(1-d/170)*.45+')';cx.beginPath();cx.moveTo(BGX.mx,BGX.my);cx.lineTo(p.x,p.y);cx.stroke()}
  if(d2<170){cx.strokeStyle='rgba(242,96,107,'+(1-d2/170)*.3+')';cx.beginPath();cx.moveTo(BGX.mx,BGX.my);cx.lineTo(tx,ty);cx.stroke()}
  if(p.f>0)p.f=Math.max(0,p.f-.03);var tw=.5+.5*Math.sin(p.ph+BGX.frames*.02),al=.28+.3*tw+p.f*.6;cx.fillStyle='rgba(242,96,107,'+al+')';cx.beginPath();cx.arc(p.x,p.y,p.r+p.f*5,0,6.283);cx.fill();cx.fillStyle='rgba(224,64,79,'+(al*.7)+')';cx.beginPath();cx.arc(tx,ty,p.r+p.f*5,0,6.283);cx.fill()}
 BGX.frames++}
function bgLoop(t){if(!BGX.on)return;var dt=Math.min(64,t-(BGX.last||t));BGX.last=t;if(!document.hidden)bgFrame(dt);requestAnimationFrame(bgLoop)}
function bgInit(){var cv=$('bg');if(!cv||!cv.getContext)return;BGX.cv=cv;BGX.cx=cv.getContext('2d');try{BGX.collapsed=+localStorage.getItem('singlet_bg')||0}catch(e){}bgSize();bgSpawn();bgHud();
 addEventListener('resize',function(){clearTimeout(BGX.rt);BGX.rt=setTimeout(function(){bgSize();bgSpawn();if(!BGX.on)bgFrame(0)},150)});
 addEventListener('pointermove',function(e){BGX.mx=e.clientX;BGX.my=e.clientY},{passive:true});document.addEventListener('pointerleave',function(){BGX.mx=-999;BGX.my=-999});
 document.addEventListener('pointerdown',function(e){if(e.target.closest&&e.target.closest('a,button,input,select,textarea,summary,canvas,label,[tabindex],.modal,.mbox'))return;bgRipple(e.clientX,e.clientY,.5)});
 addEventListener('scroll',function(){var y=scrollY;BGX.scrollV=Math.max(-60,Math.min(60,y-BGX.lastY));BGX.lastY=y},{passive:true});
 if(reduced()){BGX.on=false;bgFrame(0)}else{BGX.on=true;requestAnimationFrame(bgLoop)}}
// ---- sound (off until you turn it on)
var SND={on:false,ctx:null};
function sndInit(){try{SND.on=localStorage.getItem('singlet_snd')==='1'}catch(e){}var b=$('sndBtn');if(b){b.textContent=SND.on?'Sound on':'Sound off';b.setAttribute('aria-pressed',String(SND.on));b.onclick=function(){SND.on=!SND.on;try{localStorage.setItem('singlet_snd',SND.on?'1':'0')}catch(e){}b.textContent=SND.on?'Sound on':'Sound off';b.setAttribute('aria-pressed',String(SND.on));sfx('tick')}}}
function sndCtx(){if(!SND.ctx){var A=window.AudioContext||window.webkitAudioContext;if(!A)return null;try{SND.ctx=new A()}catch(e){return null}}try{if(SND.ctx.state==='suspended')SND.ctx.resume()}catch(e){}return SND.ctx}
function beep(f,d,type,g,slide){if(!SND.on)return;var c=sndCtx();if(!c)return;try{var o=c.createOscillator(),G=c.createGain(),t=c.currentTime;o.type=type||'sine';o.frequency.setValueAtTime(f,t);if(slide)o.frequency.exponentialRampToValueAtTime(slide,t+d);G.gain.setValueAtTime(g||.05,t);G.gain.exponentialRampToValueAtTime(.0001,t+d);o.connect(G);G.connect(c.destination);o.start(t);o.stop(t+d);SND.plays=(SND.plays||0)+1}catch(e){}}
function sfx(k){if(k==='measure')beep(520,.09,'triangle',.05,260);else if(k==='collapse')beep(880,.55,'sine',.06,110);else if(k==='ach'){beep(660,.12,'square',.03);setTimeout(function(){beep(990,.18,'square',.03)},110)}else if(k==='tick')beep(1200,.03,'square',.02)}
// ---- achievements (kept on this device)
var ACH_DEFS=[['first','First collapse','Run anything once.'],['ten','Ten runs','Collapse ten messages.'],['rare','Rare find','Get a Rare or better result.'],['glitch','Glitched','Get a run with a stuck qubit.'],['pair','Spooky action','Entangle with another wallet.'],['bell','Perfect agreement','Measure 1,000 Bell pairs in the lab.'],['slit','Wave and particle','Fire 1,000 particles at the slits both watched and unwatched.'],['game','Called it','Score 8 or more in Guess the qubit.'],['tourist','Tourist','Open the Hall of rarity.'],['mechanic','Mechanic','Run the system check.'],['popper','Popper','Collapse 25 particles in the background.']],ACH={};
function achLoad(){try{var r=JSON.parse(localStorage.getItem('singlet_ach')||'null');ACH={};if(r&&typeof r==='object')ACH_DEFS.forEach(function(d){if(+r[d[0]]>0)ACH[d[0]]=+r[d[0]]});ACH._runs=Math.max(0,Math.min(1e6,+(r&&r._runs)||0))}catch(e){ACH={_runs:0}}}
function achSave(){try{localStorage.setItem('singlet_ach',JSON.stringify(ACH))}catch(e){}}
function unlock(id){if(ACH[id])return false;var d=ACH_DEFS.filter(function(x){return x[0]===id})[0];if(!d)return false;ACH[id]=Date.now();achSave();toast('Achievement: '+d[1]);sfx('ach');return true}
function achRun(out){ACH._runs=(ACH._runs||0)+1;achSave();unlock('first');if(ACH._runs>=10)unlock('ten');if(out){var t=out.m.tier.id;if(t==='rare'||t==='epic'||t==='legendary')unlock('rare');if(out.m.glitched)unlock('glitch')}}
