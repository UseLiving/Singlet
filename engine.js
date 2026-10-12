// ======== singlet engine: hashing, circuits, a real statevector simulator, a noise model, rarity, art ========
var SHOTS=1024;
function sha256(msg){var K=[],H=[],p=2,c=0;while(c<64){var ok=true;for(var d=2;d*d<=p;d++)if(p%d===0){ok=false;break}if(ok){K.push(Math.floor((Math.cbrt(p)%1)*4294967296)>>>0);if(c<8)H.push(Math.floor((Math.sqrt(p)%1)*4294967296)>>>0);c++}p++}
 var l=msg.length,words=((l+9+63)>>6)<<4,w=new Uint32Array(words),i;for(i=0;i<l;i++)w[i>>2]|=msg[i]<<(24-(i&3)*8);w[l>>2]|=0x80<<(24-(l&3)*8);w[words-1]=(l*8)>>>0;w[words-2]=Math.floor(l*8/4294967296);
 var W=new Uint32Array(64),a,b,c2,d2,e,f,g,h,t,o;for(o=0;o<words;o+=16){for(t=0;t<16;t++)W[t]=w[o+t];for(t=16;t<64;t++){var x=W[t-15],y=W[t-2],s0=(x>>>7|x<<25)^(x>>>18|x<<14)^(x>>>3),s1=(y>>>17|y<<15)^(y>>>19|y<<13)^(y>>>10);W[t]=(W[t-16]+s0+W[t-7]+s1)>>>0}
  a=H[0];b=H[1];c2=H[2];d2=H[3];e=H[4];f=H[5];g=H[6];h=H[7];for(t=0;t<64;t++){var S1=(e>>>6|e<<26)^(e>>>11|e<<21)^(e>>>25|e<<7),ch=(e&f)^(~e&g),t1=(h+S1+ch+K[t]+W[t])>>>0,S0=(a>>>2|a<<30)^(a>>>13|a<<19)^(a>>>22|a<<10),mj=(a&b)^(a&c2)^(b&c2),t2=(S0+mj)>>>0;h=g;g=f;f=e;e=(d2+t1)>>>0;d2=c2;c2=b;b=a;a=(t1+t2)>>>0}
  H[0]=(H[0]+a)>>>0;H[1]=(H[1]+b)>>>0;H[2]=(H[2]+c2)>>>0;H[3]=(H[3]+d2)>>>0;H[4]=(H[4]+e)>>>0;H[5]=(H[5]+f)>>>0;H[6]=(H[6]+g)>>>0;H[7]=(H[7]+h)>>>0}
 var out=new Uint8Array(32);for(i=0;i<8;i++){out[i*4]=H[i]>>>24;out[i*4+1]=H[i]>>>16&255;out[i*4+2]=H[i]>>>8&255;out[i*4+3]=H[i]&255}return out}
function utf8(s){return new TextEncoder().encode(s)}
function hex(b){var s='';for(var i=0;i<b.length;i++)s+=(b[i]<16?'0':'')+b[i].toString(16);return s}
function xoshiro(a,b,c,d){return function(){var t=b<<9,r=b*5;r=(r<<7|r>>>25)*9;c^=a;d^=b;b^=c;a^=d;c^=t;d=d<<11|d>>>21;return(r>>>0)/4294967296}}
function rngFrom(str){var h=sha256(utf8(str)),dv=new DataView(h.buffer,h.byteOffset,32);return xoshiro(dv.getUint32(0),dv.getUint32(4),dv.getUint32(8),dv.getUint32(12))}
var EDITIONS=[
 {id:'cold',name:'Cold start',layers:3,noise:.45,glitch:.01,cap:128,blurb:'A well-chilled chip. Low noise, so results stay close to the ideal and rare ones are very rare.'},
 {id:'deep',name:'Deep dive',layers:6,noise:1,glitch:.02,cap:128,blurb:'Six layers of entanglement. More gates, more ways for the noise to add up.'},
 {id:'warm',name:'Warm chip',layers:3,noise:2.2,glitch:.04,cap:128,blurb:'The fridge is struggling. Noise is more than double and stuck qubits are twice as likely.'},
 {id:'ring',name:'Ring parity',layers:4,ring:true,noise:1,glitch:.02,cap:128,blurb:'Every qubit is tied to its neighbour in a closed ring before each layer.'},
 {id:'sparse',name:'Sparse lattice',layers:2,noise:.8,glitch:.015,cap:128,blurb:'Two shallow layers. Few gates, sharp peaks in the result.'},
 {id:'storm',name:'Storm',layers:4,noise:3,glitch:.12,cap:64,blurb:'Three times the noise and one run in eight has a stuck qubit. Hardest to predict, hardest to find.'}];
function edition(id){for(var i=0;i<EDITIONS.length;i++)if(EDITIONS[i].id===id)return EDITIONS[i];return null}
var DEFAULT_ED={id:'',name:'Standard',layers:3,noise:1,glitch:.02,ring:false};
function circuitKey(o){return o.kind==='p'?['sgl1','p',o.n,o.walletA,o.walletB,o.msgA,o.msgB,o.invite].join('|'):['sgl1','r',o.n,o.wallet,o.edition||'-',o.prev||'-',o.msg].join('|')}
function buildCircuit(o){var n=o.n,ed=edition(o.edition)||DEFAULT_ED,rng=rngFrom('circuit|'+circuitKey(o)),g=[],half=n>>1,q,L;function ang(){return rng()*6.283185307179586}
 for(q=0;q<n;q++){g.push({g:'ry',q:q,a:ang()});g.push({g:'rz',q:q,a:ang()})}
 for(L=0;L<ed.layers;L++){for(q=L%2;q+1<n;q+=2)g.push({g:'cx',c:q,t:q+1});if(ed.ring)g.push({g:'cx',c:n-1,t:0});var st=1+Math.floor(rng()*(n-1));for(q=0;q<n;q+=2)g.push({g:'cz',c:q,t:(q+st)%n===q?(q+1)%n:(q+st)%n});if(o.kind==='p')for(q=0;q<half;q++)g.push({g:'cx',c:q,t:q+half});for(q=0;q<n;q++){g.push({g:'ry',q:q,a:ang()});g.push({g:'rz',q:q,a:ang()})}}
 for(q=0;q<n;q++)g.push({g:'rx',q:q,a:ang()});return g}
function simulate(gates,n){var N=1<<n,re=new Float64Array(N),im=new Float64Array(N),k,i;re[0]=1;
 for(k=0;k<gates.length;k++){var G=gates[k],m=1<<(G.q||0);
  if(G.g==='ry'){var c=Math.cos(G.a/2),s=Math.sin(G.a/2);for(i=0;i<N;i++)if(!(i&m)){var j=i|m,ar=re[i],ai=im[i],br=re[j],bi=im[j];re[i]=c*ar-s*br;im[i]=c*ai-s*bi;re[j]=s*ar+c*br;im[j]=s*ai+c*bi}}
  else if(G.g==='rz'){var cc=Math.cos(G.a/2),ss=Math.sin(G.a/2);for(i=0;i<N;i++){var r=re[i],x=im[i];if(i&m){re[i]=r*cc-x*ss;im[i]=r*ss+x*cc}else{re[i]=r*cc+x*ss;im[i]=-r*ss+x*cc}}}
  else if(G.g==='rx'){var c3=Math.cos(G.a/2),s3=Math.sin(G.a/2);for(i=0;i<N;i++)if(!(i&m)){var j2=i|m,a2=re[i],a3=im[i],b2=re[j2],b3=im[j2];re[i]=c3*a2+s3*b3;im[i]=c3*a3-s3*b2;re[j2]=s3*a3+c3*b2;im[j2]=-s3*a2+c3*b3}}
  else if(G.g==='cx'){var cm=1<<G.c,tm=1<<G.t;for(i=0;i<N;i++)if((i&cm)&&!(i&tm)){var j3=i|tm,tr=re[i],ti=im[i];re[i]=re[j3];im[i]=im[j3];re[j3]=tr;im[j3]=ti}}
  else if(G.g==='cz'){var m1=1<<G.c,m2=1<<G.t;for(i=0;i<N;i++)if((i&m1)&&(i&m2)){re[i]=-re[i];im[i]=-im[i]}}
  else if(G.g==='h'){var is=Math.SQRT1_2;for(i=0;i<N;i++)if(!(i&m)){var j4=i|m,a4=re[i],a5=im[i],b4=re[j4],b5=im[j4];re[i]=(a4+b4)*is;im[i]=(a5+b5)*is;re[j4]=(a4-b4)*is;im[j4]=(a5-b5)*is}}}
 var p=new Float64Array(N);for(i=0;i<N;i++)p[i]=re[i]*re[i]+im[i]*im[i];return p}
function noiseOf(ed,gates){var m=ed.noise,ge=.0011*m;return {dep:1-Math.pow(1-ge,gates),eps:Math.min(.08,.011*m),relax:Math.min(.1,.018*m),glitch:ed.glitch}}
function measure(p,n,gates,seedStr,edId,shots,nm){shots=shots||SHOTS;var ed=edition(edId)||DEFAULT_ED;if(nm!=null)ed={noise:nm,glitch:0};var nz=noiseOf(ed,gates),rng=rngFrom('shots|'+seedStr),N=1<<n,cdf=new Float64Array(N),acc=0,i;for(i=0;i<N;i++){acc+=p[i];cdf[i]=acc}
 var stuck=null;if(rng()<nz.glitch)stuck={q:Math.floor(rng()*n),v:rng()<.5?0:1};var counts=new Uint16Array(N);
 for(var s=0;s<shots;s++){var x,u=rng()*acc;if(rng()<nz.dep)x=Math.floor(rng()*N);else{var lo=0,hi=N-1;while(lo<hi){var mid=(lo+hi)>>1;if(cdf[mid]<u)lo=mid+1;else hi=mid}x=lo;
   for(var q=0;q<n;q++){if((x>>q&1)&&rng()<nz.relax)x&=~(1<<q)}}
  for(var b=0;b<n;b++)if(rng()<nz.eps)x^=1<<b;if(stuck){x=stuck.v?x|1<<stuck.q:x&~(1<<stuck.q)}counts[x]++}
 return {counts:counts,stuck:stuck,noise:nz}}
function metrics(p,counts,n,shots,stuck){shots=shots||SHOTS;var N=1<<n,tvd=0,H=0,Hi=0,i,c;for(i=0;i<N;i++){c=counts[i]/shots;tvd+=Math.abs(c-p[i]);if(c>0)H-=c*Math.log2(c);if(p[i]>0)Hi-=p[i]*Math.log2(p[i])}
 var top=[];for(i=0;i<N;i++)if(counts[i])top.push(i);top.sort(function(a,b){return counts[b]-counts[a]||a-b});return {tvd:tvd/2,entropy:H,idealEntropy:Hi,top:top.slice(0,12),distinct:top.length,glitched:!!stuck}}
function pctOf(score,table){if(!table||!table.length)return null;var n=table.length-1;if(score<=table[0])return 0;if(score>=table[n])return 100;var lo=0,hi=n;while(hi-lo>1){var m=(lo+hi)>>1;if(table[m]<=score)lo=m;else hi=m}var f=(score-table[lo])/((table[hi]-table[lo])||1);return (lo+f)*100/n}
var TIERS=[{id:'common',name:'Common',min:0},{id:'uncommon',name:'Uncommon',min:55},{id:'rare',name:'Rare',min:85},{id:'epic',name:'Epic',min:97},{id:'legendary',name:'Legendary',min:99.7}];
function tierOf(pct,glitched){if(glitched)return {id:'glitched',name:'Glitched'};var t=TIERS[0];for(var i=0;i<TIERS.length;i++)if(pct>=TIERS[i].min)t=TIERS[i];return t}
var CAL={};
function runCircuit(o,seedStr){var gates=buildCircuit(o),p=simulate(gates,o.n),ms=measure(p,o.n,gates.length,seedStr,o.edition,SHOTS),m=metrics(p,ms.counts,o.n,SHOTS,ms.stuck),tbl=(CAL[(o.edition||'std')+':'+o.n]||null),pc=pctOf(m.tvd,tbl);m.percentile=pc;m.tier=tierOf(pc==null?0:pc,m.glitched);return {gates:gates,p:p,counts:ms.counts,stuck:ms.stuck,noise:ms.noise,m:m}}
function bits(i,n){var s='';for(var q=n-1;q>=0;q--)s+=(i>>q&1)?'1':'0';return s}
function artRot(seed){return sha256(utf8(seed||'x'))[0]/256*6.283185307179586}
function drawArt(cx,S,r,opt){opt=opt||{};var n=r.n||Math.round(Math.log2(r.counts.length)),N=1<<n,counts=r.counts,p=r.p,mx=1,mp=1e-9,i;for(i=0;i<N;i++){if(counts[i]>mx)mx=counts[i];if(p[i]>mp)mp=p[i]}
 var rot=artRot(r.seed),c=S/2,r0=S*.2,red=opt.red||'#E0404F',white=opt.white||'#EDEDED';cx.save();cx.fillStyle='#000';cx.fillRect(0,0,S,S);cx.lineCap='butt';
 var lw=Math.max(1,6.283*r0/N*.62);for(i=0;i<N;i++){var a=rot+6.283185307179586*i/N,len=r0+Math.pow(counts[i]/mx,.8)*S*.27,al=counts[i]?.1+.9*Math.pow(counts[i]/mx,1.15):.035;cx.strokeStyle=red;cx.globalAlpha=al;cx.lineWidth=lw;cx.beginPath();cx.moveTo(c+Math.cos(a)*r0,c+Math.sin(a)*r0);cx.lineTo(c+Math.cos(a)*len,c+Math.sin(a)*len);cx.stroke()}
 if(opt.hi!=null&&opt.hi>=0&&opt.hi<N){var a4=rot+6.283185307179586*opt.hi/N,l4=Math.max(r0,r0+Math.pow(counts[opt.hi]/mx,.8)*S*.27)+S*.03;cx.globalAlpha=1;cx.strokeStyle=white;cx.lineWidth=Math.max(2,lw*1.8);cx.beginPath();cx.moveTo(c+Math.cos(a4)*r0*.88,c+Math.sin(a4)*r0*.88);cx.lineTo(c+Math.cos(a4)*l4,c+Math.sin(a4)*l4);cx.stroke()}
 cx.globalAlpha=1;var top=[];for(i=0;i<N;i++)if(counts[i])top.push(i);top.sort(function(a,b){return counts[b]-counts[a]||a-b});top=top.slice(0,12).sort(function(a,b){return a-b});
 cx.strokeStyle=white;cx.globalAlpha=.35;cx.lineWidth=Math.max(1,S/400);cx.beginPath();top.forEach(function(k,j){var a=rot+6.283185307179586*k/N,len=r0+Math.pow(counts[k]/mx,.8)*S*.27,x=c+Math.cos(a)*len,y=c+Math.sin(a)*len;if(j)cx.lineTo(x,y);else cx.moveTo(x,y)});cx.closePath();cx.stroke();cx.globalAlpha=1;cx.fillStyle=white;
 top.forEach(function(k){var a=rot+6.283185307179586*k/N,len=r0+Math.pow(counts[k]/mx,.8)*S*.27;cx.beginPath();cx.arc(c+Math.cos(a)*len,c+Math.sin(a)*len,Math.max(1.5,S/150),0,6.283);cx.fill()});
 cx.fillStyle=red;for(i=0;i<N;i++){var a2=rot+6.283185307179586*i/N,rr=r0*.74;cx.globalAlpha=.9;cx.beginPath();cx.arc(c+Math.cos(a2)*rr,c+Math.sin(a2)*rr,Math.max(.8,Math.sqrt(p[i]/mp)*S/110),0,6.283);cx.fill()}
 cx.globalAlpha=1;if(r.stuck){cx.strokeStyle=white;cx.lineWidth=Math.max(2,S/130);var a3=rot+6.283185307179586*(r.stuck.q/n);cx.beginPath();cx.arc(c,c,S*.475,a3,a3+.55);cx.stroke()}
 cx.strokeStyle=red;cx.globalAlpha=.5;cx.lineWidth=Math.max(1,S/500);cx.beginPath();cx.arc(c,c,S*.495,0,6.283);cx.stroke();cx.restore()}
