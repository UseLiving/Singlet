
(function(root){function parse(s){var m=s.match(/rgba?\(([^)]+)\)/);if(!m)return null;var p=m[1].split(/[ ,\/]+/).map(parseFloat);return {r:p[0],g:p[1],b:p[2],a:p.length>3&&!isNaN(p[3])?p[3]:1}}
 function lum(c){function f(v){v/=255;return v<=.03928?v/12.92:Math.pow((v+.055)/1.055,2.4)}return .2126*f(c.r)+.7152*f(c.g)+.0722*f(c.b)}
 function blend(top,bot){var a=top.a;return {r:top.r*a+bot.r*(1-a),g:top.g*a+bot.g*(1-a),b:top.b*a+bot.b*(1-a),a:1}}
 function bgOf(el){var chain=[];for(var e=el;e&&e.nodeType===1;e=e.parentElement)chain.unshift(e);var bg={r:7,g:7,b:10,a:1};chain.forEach(function(e){var cs=getComputedStyle(e),c=parse(cs.backgroundColor);if(c&&c.a>0)bg=blend(c,bg);else if(cs.backgroundImage&&cs.backgroundImage!=='none'&&/gradient/.test(cs.backgroundImage)){var m=cs.backgroundImage.match(/rgba?\([^)]+\)/g);if(m){var cc=parse(m[m.length-1]);if(cc)bg=blend({r:cc.r,g:cc.g,b:cc.b,a:cc.a===undefined?1:cc.a},bg)}}});return bg}
 function visible(el){for(var e=el;e&&e.nodeType===1;e=e.parentElement){var cs=getComputedStyle(e);if(cs.display==='none'||cs.visibility==='hidden'||+cs.opacity<.6)return false}var r=el.getBoundingClientRect();return r.width>0&&r.height>0}
 var bad=[],n=0,w=document.createTreeWalker(root,NodeFilter.SHOW_TEXT,null);var seen=new Set();
 while(w.nextNode()){var t=w.currentNode,el=t.parentElement;if(!el||!t.textContent.trim()||seen.has(el))continue;if(el.closest('script,style,svg,canvas,option'))continue;if(el.closest('button:disabled,[disabled]'))continue;if(!visible(el))continue;seen.add(el);
  var cs=getComputedStyle(el),fg=parse(cs.color),bg=bgOf(el);if(!fg)continue;fg=blend(fg,bg);var L1=lum(fg),L2=lum(bg),ratio=(Math.max(L1,L2)+.05)/(Math.min(L1,L2)+.05),px=parseFloat(cs.fontSize),bold=+cs.fontWeight>=700,large=px>=24||(px>=18.66&&bold);n++;
  if(ratio<(large?3:4.5))bad.push({t:t.textContent.trim().slice(0,32),r:Math.round(ratio*100)/100,fg:cs.color,bg:'rgb('+Math.round(bg.r)+','+Math.round(bg.g)+','+Math.round(bg.b)+')',cls:(el.className||el.tagName)+''})}
 return {n:n,bad:bad}})(%s)
