import json
import os
HERE=os.path.dirname(os.path.abspath(__file__))
rd=lambda f:open(os.path.join(HERE,f)).read()
cal=rd('cal.json')
cfg='''var CONFIG={
  name:'{{NAME}}',                            // the site name: change it here and the whole site follows
  // Where the page reads and writes Solana data. For a real launch use your own RPC provider.
  rpc:'https://api.mainnet-beta.solana.com',
  network:'mainnet',                         // 'mainnet' or 'devnet'
  explorer:'https://solscan.io/tx/',
  // Every stamp transaction includes this address, which is how the ledger lists all runs.
  // Leave it empty for local mode: runs stay on the visitor's device and nothing is stamped.
  ledgerAddress:'',
  // Optional token. Leave tokenMint empty for open access (anyone with a wallet picks 4 to 10 qubits).
  tokenMint:'',tokenSymbol:'',tokenDecimals:6,
  tiers:[{min:1,qubits:4},{min:100000,qubits:6},{min:1000000,qubits:8},{min:5000000,qubits:10}],
  forgeBurn:0,                               // whole tokens burned in the same transaction when forging an edition
  openQubits:[4,6,8,10],maxMessage:64,
  x:'https://x.com/UseSinglet'              // shown in the footer when set
};
'''
parts=[cfg,rd('engine.js'),'CAL='+cal+';',rd('chain.js'),rd('bgfx.js'),rd('app.js'),rd('views.js'),rd('views2.js'),rd('views3.js'),rd('views4.js')]
tail='''
(function(){var f=$('footLinks');f.appendChild(h('a',{href:'#/status',id:'footStatus','data-ok':'',text:'System check'}));f.appendChild(document.createTextNode(' '));f.appendChild(h('a',{href:'#/hall',text:'Hall of rarity'}));if(CONFIG.x){f.appendChild(document.createTextNode(' '));f.appendChild(h('a',{href:CONFIG.x,target:'_blank',rel:'noopener noreferrer',text:'Follow on X'}))}lightCheck()})();
window.__dq={CONFIG:CONFIG,W:W,LEDGER:LEDGER,LOCAL:LOCAL,RS:RS,runCircuit:runCircuit,computeRun:computeRun,buildCircuit:buildCircuit,simulate:simulate,parseMemo:parseMemo,memoRun:memoRun,memoInvite:memoInvite,memoAccept:memoAccept,buildTx:buildTx,readTx:readTx,supply:supply,stats:stats,qubitsFor:qubitsFor,msgOk:msgOk,clean:clean,b58enc:b58enc,b58dec:b58dec,sha256:sha256,hex:hex,utf8:utf8,edition:edition,EDITIONS:EDITIONS,route:route,verifyEntry:verifyEntry,entryToRun:entryToRun,ledgerLoad:ledgerLoad,ledgerLoadAll:ledgerLoadAll,pctOf:pctOf,artRot:artRot,LABX:LABX,RV:RV,bgCollapse:bgCollapse,bgFrame:bgFrame,achRun:achRun,slitI:slitI,CHECKS:CHECKS,lightCheck:lightCheck,ACH:function(){return ACH},ACH_DEFS:ACH_DEFS,BGX:BGX,SND:SND,unlock:unlock,legacyList:legacyList,readAddr:readAddr,wAuto:wAuto,ERRS:ERRS,CAL:CAL,tierOf:tierOf,drawArt:drawArt,measure:measure,metrics:metrics,seedOf:seedOf,wsSolana:wsSolana,SHOTS:SHOTS,burnInfo:burnInfo,stamp:stamp,wBalance:wBalance,rngFrom:rngFrom,DEFAULT_ED:DEFAULT_ED,noiseOf:noiseOf};
init();
'''
js='\n'.join(parts)+tail
BRAND='singlet'
html=(rd('head.html')+'<script>(function(){\'use strict\';\n'+js+'\n})();</script></body></html>\n').replace('{{NAME}}',BRAND)
open(os.path.join(HERE,'..','public','index.html'),'w').write(html)
print('built',len(html),'bytes')
