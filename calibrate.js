const fs=require('fs');const src=fs.readFileSync(__dirname+'/../src/engine.js','utf8');
const Q=new Function(src+';return {sha256,utf8,hex,rngFrom,buildCircuit,simulate,measure,metrics,EDITIONS,runCircuit,CAL,SHOTS}')();
// sanity: SHA-256 vectors
const t=(s)=>Q.hex(Q.sha256(Q.utf8(s)));
console.log('abc ',t('abc')==='ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad');
console.log('empty',t('')==='e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855');
console.log('long ',t('abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq')==='248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1');
const ids=['std',...Q.EDITIONS.map(e=>e.id)],ns=[4,6,8,10],M=+process.argv[2]||1200,out={};
let t0=Date.now();
for(const id of ids)for(const n of ns){const arr=[];for(let k=0;k<M;k++){const o={kind:'r',n,wallet:'CAL'+k%97,edition:id==='std'?'':id,prev:'-',msg:'cal message '+k};const r=Q.runCircuit(o,'cal-seed-'+id+'-'+n+'-'+k);arr.push(r.m.tvd)}arr.sort((a,b)=>a-b);const q=[];for(let i=0;i<=100;i++){q.push(+arr[Math.min(arr.length-1,Math.round(i/100*(arr.length-1)))].toFixed(5))}out[id+':'+n]=q}
console.log('calibrated',Object.keys(out).length,'tables in',((Date.now()-t0)/1000).toFixed(1),'s');
fs.writeFileSync(__dirname+'/../src/cal.json',JSON.stringify(out));
console.log('sample std:6 quantiles p0,p55,p85,p97,p100:',[0,55,85,97,100].map(i=>out['std:6'][i]).join(' | '));
console.log('sample storm:10:',[0,55,85,97,100].map(i=>out['storm:10'][i]).join(' | '));
