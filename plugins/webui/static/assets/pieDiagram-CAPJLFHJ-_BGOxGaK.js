import{p as at}from"./chunk-JWPE2WC7-BNEtARPq.js";import{a9 as T,ac as G,ba as rt,g as nt,s as it,a as ot,b as st,t as lt,q as ct,_ as g,l as B,c as ut,M as dt,P as gt,U as pt,d as ht,z as ft,N as mt}from"./mermaid.core-CGw1xJen.js";import{p as vt}from"./cynefin-EF2NZ3EQ-BuQCKNCQ.js";import{d as Z}from"./arc-D8tzAnpd.js";import{o as xt}from"./ordinal-Cboi1Yqb.js";import"./index-8h4MIQOi.js";import"./ProjectDocument-DcUzYDgH.js";import"./init-Gi6I4Gst.js";function St(t,n){return n<t?-1:n>t?1:n>=t?0:NaN}function yt(t){return t}function wt(){var t=yt,n=St,y=null,b=T(0),l=T(G),p=T(0);function i(e){var r,s=(e=rt(e)).length,h,w,$=0,f=new Array(s),o=new Array(s),D=+b.apply(this,arguments),M=Math.min(G,Math.max(-G,l.apply(this,arguments)-D)),k,L=Math.min(Math.abs(M)/s,p.apply(this,arguments)),u=L*(M<0?-1:1),A;for(r=0;r<s;++r)(A=o[f[r]=r]=+t(e[r],r,e))>0&&($+=A);for(n!=null?f.sort(function(E,m){return n(o[E],o[m])}):y!=null&&f.sort(function(E,m){return y(e[E],e[m])}),r=0,w=$?(M-s*u)/$:0;r<s;++r,D=k)h=f[r],A=o[h],k=D+(A>0?A*w:0)+u,o[h]={data:e[h],index:r,value:A,startAngle:D,endAngle:k,padAngle:L};return o}return i.value=function(e){return arguments.length?(t=typeof e=="function"?e:T(+e),i):t},i.sortValues=function(e){return arguments.length?(n=e,y=null,i):n},i.sort=function(e){return arguments.length?(y=e,n=null,i):y},i.startAngle=function(e){return arguments.length?(b=typeof e=="function"?e:T(+e),i):b},i.endAngle=function(e){return arguments.length?(l=typeof e=="function"?e:T(+e),i):l},i.padAngle=function(e){return arguments.length?(p=typeof e=="function"?e:T(+e),i):p},i}var At=mt.pie,I={sections:new Map,showData:!1},W=I.sections,U=I.showData,Ct=structuredClone(At),$t=g(()=>structuredClone(Ct),"getConfig"),Dt=g(()=>{W=new Map,U=I.showData,ft()},"clear"),Tt=g(({label:t,value:n})=>{if(n<0)throw new Error(`"${t}" has invalid value: ${n}. Negative values are not allowed in pie charts. All slice values must be >= 0.`);W.has(t)||(W.set(t,n),B.debug(`added new section: ${t}, with value: ${n}`))},"addSection"),bt=g(()=>W,"getSections"),kt=g(t=>{U=t},"setShowData"),zt=g(()=>U,"getShowData"),J={getConfig:$t,clear:Dt,setDiagramTitle:ct,getDiagramTitle:lt,setAccTitle:st,getAccTitle:ot,setAccDescription:it,getAccDescription:nt,addSection:Tt,getSections:bt,setShowData:kt,getShowData:zt},Mt=g((t,n)=>{at(t,n),n.setShowData(t.showData),t.sections.map(n.addSection)},"populateDb"),Et={parse:g(async t=>{const n=await vt("pie",t);B.debug(n),Mt(n,J)},"parse")},Rt=g(t=>`
  .pieCircle{
    stroke: ${t.pieStrokeColor};
    stroke-width : ${t.pieStrokeWidth};
    opacity : ${t.pieOpacity};
  }
  .pieCircle.highlighted{
    scale: 1.05;
    opacity: 1;
  }
  .pieCircle.highlightedOnHover:hover{
    transition-duration: 250ms;
    scale: 1.05;
    opacity: 1;
  }
  .pieOuterCircle{
    stroke: ${t.pieOuterStrokeColor};
    stroke-width: ${t.pieOuterStrokeWidth};
    fill: none;
  }
  .pieTitleText {
    text-anchor: middle;
    font-size: ${t.pieTitleTextSize};
    fill: ${t.pieTitleTextColor};
    font-family: ${t.fontFamily};
  }
  .slice {
    font-family: ${t.fontFamily};
    fill: ${t.pieSectionTextColor};
    font-size:${t.pieSectionTextSize};
    // fill: white;
  }
  .legend text {
    fill: ${t.pieLegendTextColor};
    font-family: ${t.fontFamily};
    font-size: ${t.pieLegendTextSize};
  }
`,"getStyles"),Lt=Rt,Nt=g(t=>{const n=[...t.values()].reduce((l,p)=>l+p,0),y=[...t.entries()].map(([l,p])=>({label:l,value:p})).filter(l=>l.value/n*100>=1);return wt().value(l=>l.value).sort(null)(y)},"createPieArcs"),Pt=g((t,n,y,b)=>{B.debug(`rendering pie chart
`+t);const l=b.db,p=ut(),i=dt(l.getConfig(),p.pie),e=40,r=18,s=4,h=450,w=h,$=gt(n),f=$.append("g");f.attr("transform","translate("+w/2+","+h/2+")");const{themeVariables:o}=p;let[D]=pt(o.pieOuterStrokeWidth);D??=2;const M=i.legendPosition,k=i.textPosition,L=i.donutHole>0&&i.donutHole<=.9?i.donutHole:0,u=Math.min(w,h)/2-e,A=Z().innerRadius(L*u).outerRadius(u),E=Z().innerRadius(u*k).outerRadius(u*k),m=f.append("g");m.append("circle").attr("cx",0).attr("cy",0).attr("r",u+D/2).attr("class","pieOuterCircle");const N=l.getSections(),K=Nt(N),Q=[o.pie1,o.pie2,o.pie3,o.pie4,o.pie5,o.pie6,o.pie7,o.pie8,o.pie9,o.pie10,o.pie11,o.pie12];let _=0;N.forEach(a=>{_+=a});const V=K.filter(a=>(a.data.value/_*100).toFixed(0)!=="0"),F=xt(Q).domain([...N.keys()]);m.selectAll("mySlices").data(V).enter().append("path").attr("d",A).attr("fill",a=>F(a.data.label)).attr("class",a=>{let c="pieCircle";return i.highlightSlice==="hover"?c+=" highlightedOnHover":i.highlightSlice===a.data.label&&(c+=" highlighted"),c}),m.selectAll("mySlices").data(V).enter().append("text").text(a=>(a.data.value/_*100).toFixed(0)+"%").attr("transform",a=>"translate("+E.centroid(a)+")").style("text-anchor","middle").attr("class","slice");const Y=f.append("text").text(l.getDiagramTitle()).attr("x",0).attr("y",-400/2).attr("class","pieTitleText"),R=[...N.entries()].map(([a,c])=>({label:a,value:c})),C=f.selectAll(".legend").data(R).enter().append("g").attr("class","legend");C.append("rect").attr("width",r).attr("height",r).style("fill",a=>F(a.label)).style("stroke",a=>F(a.label)),C.append("text").attr("x",r+s).attr("y",r-s).text(a=>l.getShowData()?`${a.label} [${a.value}]`:a.label);const z=Math.max(...C.selectAll("text").nodes().map(a=>a?.getBoundingClientRect().width??0));let P=h,H=w+e;const d=r+s,O=R.length*d;switch(M){case"center":C.attr("transform",(a,c)=>{const v=d*R.length/2,x=-z/2-(r+s),S=c*d-v;return"translate("+x+","+S+")"});break;case"top":P+=O,C.attr("transform",(a,c)=>{const v=u,x=-z/2-(r+s),S=c*d-v;return`translate(${x}, ${S})`}),m.attr("transform",()=>`translate(0, ${O+d})`);break;case"bottom":P+=O,C.attr("transform",(a,c)=>{const v=-u-d,x=-z/2-(r+s),S=c*d-v;return"translate("+x+","+S+")"});break;case"left":H+=r+s+z,C.attr("transform",(a,c)=>{const v=d*R.length/2,x=-u-(r+s),S=c*d-v;return"translate("+x+","+S+")"}),m.attr("transform",()=>`translate(${z+r+s}, 0)`);break;default:H+=r+s+z,C.attr("transform",(a,c)=>{const v=d*R.length/2,x=12*r,S=c*d-v;return"translate("+x+","+S+")"});break}const j=Y.node()?.getBoundingClientRect().width??0,tt=w/2-j/2,et=w/2+j/2,q=Math.min(0,tt),X=Math.max(H,et)-q;$.attr("viewBox",`${q} 0 ${X} ${P}`),ht($,P,X,i.useMaxWidth)},"draw"),Wt={draw:Pt},jt={parser:Et,db:J,renderer:Wt,styles:Lt};export{jt as diagram};
