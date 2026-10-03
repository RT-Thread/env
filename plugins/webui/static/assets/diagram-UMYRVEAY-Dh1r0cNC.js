import{p as z}from"./chunk-JWPE2WC7-BNEtARPq.js";import{_ as f,M as B,P,d as E,l as $,b as F,a as A,q as W,t as _,g as N,s as M,K as L,N as Y,z as I}from"./mermaid.core-CGw1xJen.js";import{p as K}from"./cynefin-EF2NZ3EQ-BuQCKNCQ.js";import"./index-8h4MIQOi.js";import"./ProjectDocument-DcUzYDgH.js";var O=Y.packet,b,C=(b=class{constructor(){this.packet=[],this.setAccTitle=F,this.getAccTitle=A,this.setDiagramTitle=W,this.getDiagramTitle=_,this.getAccDescription=N,this.setAccDescription=M}getConfig(){const t=B({...O,...L().packet});return t.showBits&&(t.paddingY+=10),t}getPacket(){return this.packet}pushWord(t){t.length>0&&this.packet.push(t)}clear(){I(),this.packet=[]}},f(b,"PacketDB"),b),j=1e4,q=f((e,t)=>{z(e,t);let r=-1,s=[],i=1;const{bitsPerRow:l}=t.getConfig();for(let{start:a,end:o,bits:d,label:g}of e.blocks){if(a!==void 0&&o!==void 0&&o<a)throw new Error(`Packet block ${a} - ${o} is invalid. End must be greater than start.`);if(a??=r+1,a!==r+1)throw new Error(`Packet block ${a} - ${o??a} is not contiguous. It should start from ${r+1}.`);if(d===0)throw new Error(`Packet block ${a} is invalid. Cannot have a zero bit field.`);for(o??=a+(d??1)-1,d??=o-a+1,r=o,$.debug(`Packet block ${a} - ${r} with label ${g}`);s.length<=l+1&&t.getPacket().length<j;){const[c,p]=G({start:a,end:o,bits:d,label:g},i,l);if(s.push(c),c.end+1===i*l&&(t.pushWord(s),s=[],i++),!p)break;({start:a,end:o,bits:d,label:g}=p)}}t.pushWord(s)},"populate"),G=f((e,t,r)=>{if(e.start===void 0)throw new Error("start should have been set during first phase");if(e.end===void 0)throw new Error("end should have been set during first phase");if(e.start>e.end)throw new Error(`Block start ${e.start} is greater than block end ${e.end}.`);if(e.end+1<=t*r)return[e,void 0];const s=t*r-1,i=t*r;return[{start:e.start,end:s,label:e.label,bits:s-e.start},{start:i,end:e.end,label:e.label,bits:e.end-i}]},"getNextFittingBlock"),S={parser:{yy:void 0},parse:f(async e=>{const t=await K("packet",e),r=S.parser?.yy;if(!(r instanceof C))throw new Error("parser.parser?.yy was not a PacketDB. This is due to a bug within Mermaid, please report this issue at https://github.com/mermaid-js/mermaid/issues.");$.debug(t),q(t,r)},"parse")},H=f((e,t,r,s)=>{const i=s.db,l=i.getConfig(),{rowHeight:a,paddingY:o,bitWidth:d,bitsPerRow:g}=l,c=i.getPacket(),p=i.getDiagramTitle(),m=a+o,n=m*(c.length+1)-(p?0:a),h=d*g+2,k=P(t);k.attr("viewBox",`0 0 ${h} ${n}`),E(k,n,h,l.useMaxWidth);for(const[x,u]of c.entries())U(k,u,x,l);k.append("text").text(p).attr("x",h/2).attr("y",n-m/2).attr("dominant-baseline","middle").attr("text-anchor","middle").attr("class","packetTitle")},"draw"),U=f((e,t,r,{rowHeight:s,paddingX:i,paddingY:l,bitWidth:a,bitsPerRow:o,showBits:d,bitOrder:g})=>{const c=e.append("g"),p=r*(s+l)+l,m=g==="descending";for(const n of t){const h=n.end-n.start+1,k=n.start%o,u=(m?o-k-h:k)*a+1,w=h*a-i;if(c.append("rect").attr("x",u).attr("y",p).attr("width",w).attr("height",s).attr("class","packetBlock"),c.append("text").attr("x",u+w/2).attr("y",p+s/2).attr("class","packetLabel").attr("dominant-baseline","middle").attr("text-anchor","middle").text(n.label),!d)continue;const[D,T]=m?[n.end,n.start]:[n.start,n.end],v=h===1,y=p-2;c.append("text").attr("x",u+(v?w/2:0)).attr("y",y).attr("class","packetByte start").attr("dominant-baseline","auto").attr("text-anchor",v?"middle":"start").text(D),v||c.append("text").attr("x",u+w).attr("y",y).attr("class","packetByte end").attr("dominant-baseline","auto").attr("text-anchor","end").text(T)}},"drawWord"),X={draw:H},J={byteFontSize:"10px",startByteColor:"black",endByteColor:"black",labelColor:"black",labelFontSize:"12px",titleColor:"black",titleFontSize:"14px",blockStrokeColor:"black",blockStrokeWidth:"1",blockFillColor:"#efefef"},Q=f(({packet:e}={})=>{const t=B(J,e);return`
	.packetByte {
		font-size: ${t.byteFontSize};
	}
	.packetByte.start {
		fill: ${t.startByteColor};
	}
	.packetByte.end {
		fill: ${t.endByteColor};
	}
	.packetLabel {
		fill: ${t.labelColor};
		font-size: ${t.labelFontSize};
	}
	.packetTitle {
		fill: ${t.titleColor};
		font-size: ${t.titleFontSize};
	}
	.packetBlock {
		stroke: ${t.blockStrokeColor};
		stroke-width: ${t.blockStrokeWidth};
		fill: ${t.blockFillColor};
	}
	`},"styles"),at={parser:S,get db(){return new C},renderer:X,styles:Q};export{at as diagram};
