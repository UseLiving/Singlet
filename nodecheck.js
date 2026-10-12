// independent run of the engine in Node: prints a digest of the shots for a given run
const fs=require('fs');const src=fs.readFileSync(__dirname+'/../src/engine.js','utf8');const cal=JSON.parse(fs.readFileSync(__dirname+'/../src/cal.json','utf8'));
const Q=new Function(src+';CAL=arguments[0];return {runCircuit,sha256,utf8,hex}')(cal);
const o=JSON.parse(process.argv[2]),seed=process.argv[3],r=Q.runCircuit(o,seed);
console.log(JSON.stringify({digest:Q.hex(Q.sha256(Q.utf8(Array.from(r.counts).join(',')))),tvd:r.m.tvd,tier:r.m.tier.id,pct:r.m.percentile,gates:r.gates.length,stuck:r.stuck}));
