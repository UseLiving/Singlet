const fs=require('fs');const src=fs.readFileSync(__dirname+'/../src/engine.js','utf8');
const Q=new Function(src+';return {simulate,buildCircuit,measure,metrics,runCircuit,sha256,utf8,hex,rngFrom,EDITIONS}')();
const near=(a,b,t=1e-12)=>Math.abs(a-b)<t;let ok=0,bad=0;const T=(n,c)=>{console.log((c?'PASS ':'FAIL ')+n);c?ok++:bad++};
let p=Q.simulate([{g:'h',q:0},{g:'cx',c:0,t:1}],2);T('Bell state: |00> and |11> each 0.5, |01> and |10> zero',near(p[0],.5)&&near(p[3],.5)&&near(p[1],0)&&near(p[2],0));
p=Q.simulate([{g:'rx',q:0,a:Math.PI}],1);T('RX(pi) flips |0> to |1>',near(p[1],1)&&near(p[0],0,1e-12));
p=Q.simulate([{g:'ry',q:0,a:Math.PI/2}],1);T('RY(pi/2) makes an even superposition',near(p[0],.5)&&near(p[1],.5));
p=Q.simulate([{g:'rz',q:0,a:1.234}],1);T('RZ alone changes no probability (|0> stays |0>)',near(p[0],1));
p=Q.simulate([{g:'h',q:0},{g:'rz',q:0,a:Math.PI},{g:'h',q:0}],1);T('H, RZ(pi), H turns |0> into |1> (phase becomes probability)',near(p[1],1,1e-12));
p=Q.simulate([{g:'h',q:0},{g:'h',q:1},{g:'cz',c:0,t:1},{g:'h',q:1}],2);T('CZ conjugated by H on the target acts as CNOT (|+>|0> -> Bell)',near(p[0],.5)&&near(p[3],.5));
p=Q.simulate([{g:'rx',q:1,a:Math.PI},{g:'cx',c:1,t:0}],2);T('CNOT with control set flips the target (|10> -> |11>)',near(p[3],1,1e-12));
p=Q.simulate([{g:'cx',c:1,t:0}],2);T('CNOT with control clear does nothing',near(p[0],1));
let worst=0;for(let n of [4,6,8,10])for(let k=0;k<40;k++){const o={kind:'r',n,wallet:'w'+k,edition:'',prev:'-',msg:'m'+k},g=Q.buildCircuit(o),pp=Q.simulate(g,n);let s=0;for(const v of pp)s+=v;worst=Math.max(worst,Math.abs(s-1))}
T('total probability stays 1 for 160 random circuits (worst error '+worst.toExponential(1)+')',worst<1e-12);
const o={kind:'r',n:6,wallet:'A',edition:'',prev:'-',msg:'hello'};
const a=JSON.stringify(Q.buildCircuit(o)),b=JSON.stringify(Q.buildCircuit(o));T('same inputs always build the identical circuit',a===b);
T('a different message builds a different circuit',a!==JSON.stringify(Q.buildCircuit(Object.assign({},o,{msg:'hellp'}))));
T('a different wallet builds a different circuit',a!==JSON.stringify(Q.buildCircuit(Object.assign({},o,{wallet:'B'}))));
T('a different previous run builds a different circuit',a!==JSON.stringify(Q.buildCircuit(Object.assign({},o,{prev:'abcd'}))));
const r1=Q.runCircuit(o,'seed-1'),r2=Q.runCircuit(o,'seed-1'),r3=Q.runCircuit(o,'seed-2');
T('the same seed reproduces every shot exactly',r1.counts.join()===r2.counts.join());
T('a different seed gives different shots',r1.counts.join()!==r3.counts.join());
T('every run has exactly 1,024 shots',[r1,r2,r3].every(r=>r.counts.reduce((x,y)=>x+y,0)===1024));
// noise model really matches the ideal distribution at zero noise
const ed0=Q.EDITIONS[0];let tv=0,K=40;for(let k=0;k<K;k++){const oo={kind:'r',n:4,wallet:'z'+k,edition:'cold',prev:'-',msg:'q'+k};const r=Q.runCircuit(oo,'s'+k);tv+=r.m.tvd}
T('statistical sanity: the cold edition at 4 qubits stays close to the ideal (mean drift '+(tv/K).toFixed(3)+' < 0.12)',tv/K<.12);
let sd=0;for(let k=0;k<40;k++){const oo={kind:'r',n:4,wallet:'z'+k,edition:'storm',prev:'-',msg:'q'+k};sd+=Q.runCircuit(oo,'s'+k).m.tvd}
T('the storm edition drifts much further (mean drift '+(sd/40).toFixed(3)+')',sd/40>tv/K*2);
// glitch frequency should be near the edition probability
let gl=0,M=3000;for(let k=0;k<M;k++){const rr=Q.runCircuit({kind:'r',n:4,wallet:'g'+k,edition:'storm',prev:'-',msg:'g'},'gs'+k);if(rr.stuck)gl++}
T('stuck-qubit glitches happen about as often as the storm edition says ('+(gl/M*100).toFixed(1)+'% vs 12%)',Math.abs(gl/M-.12)<.025);
// the tvd vs ideal when there is no noise at all
const gates=Q.buildCircuit(o),pi=Q.simulate(gates,6);const ms=Q.measure(pi,6,gates.length,'x','',1e5);let t2=0;for(let i=0;i<64;i++)t2+=Math.abs(ms.counts[i]/1e5-pi[i]);
console.log('info: 100k-shot drift of the standard noise model at 6 qubits =',(t2/2).toFixed(3));
console.log('\n'+ok+' passed, '+bad+' failed');process.exit(bad?1:0);
