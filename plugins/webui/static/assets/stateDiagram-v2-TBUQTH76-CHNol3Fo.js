import{g as ie}from"./chunk-XXDRQBXY-DzFkmq_f.js";import{s as re}from"./chunk-KQW6MTUR-B7LXZvvk.js";import{_ as p,l as b,c as $,p as ae,r as ne,u as oe,a as le,b as ce,g as he,s as de,q as ue,t as fe,Y as pe,m as U,z as Se,k as vt,B as ge,C as ye,D as me,H as Te}from"./mermaid.core-CGw1xJen.js";import{c as Ee}from"./chunk-7TKQ45FW-CIh71sFP.js";import{p as _e}from"./ProjectDocument-DcUzYDgH.js";import"./index-8h4MIQOi.js";var At=(function(){var t=p(function(V,o,f,n){for(f=f||{},n=V.length;n--;f[V[n]]=o);return f},"o"),e=[1,2],s=[1,3],a=[1,4],r=[2,4],c=[1,9],h=[1,11],u=[1,16],l=[1,17],m=[1,18],y=[1,19],_=[1,33],L=[1,20],R=[1,21],D=[1,22],S=[1,23],w=[1,24],C=[1,26],F=[1,27],I=[1,28],P=[1,29],v=[1,30],z=[1,31],at=[1,32],nt=[1,35],ot=[1,36],lt=[1,37],ct=[1,38],K=[1,34],g=[1,4,5,16,17,19,21,22,24,25,26,27,28,29,33,35,37,38,41,45,48,51,52,53,54,57],ht=[1,4,5,14,15,16,17,19,21,22,24,25,26,27,28,29,33,35,37,38,39,40,41,45,48,51,52,53,54,57],It=[4,5,16,17,19,21,22,24,25,26,27,28,29,33,35,37,38,41,45,48,51,52,53,54,57],mt={trace:p(function(){},"trace"),yy:{},symbols_:{error:2,start:3,SPACE:4,NL:5,SD:6,document:7,line:8,statement:9,classDefStatement:10,styleStatement:11,cssClassStatement:12,idStatement:13,DESCR:14,"-->":15,HIDE_EMPTY:16,scale:17,WIDTH:18,COMPOSIT_STATE:19,STRUCT_START:20,STRUCT_STOP:21,STATE_DESCR:22,AS:23,ID:24,FORK:25,JOIN:26,CHOICE:27,CONCURRENT:28,note:29,notePosition:30,NOTE_TEXT:31,direction:32,acc_title:33,acc_title_value:34,acc_descr:35,acc_descr_value:36,acc_descr_multiline_value:37,CLICK:38,STRING:39,HREF:40,classDef:41,CLASSDEF_ID:42,CLASSDEF_STYLEOPTS:43,DEFAULT:44,style:45,STYLE_IDS:46,STYLEDEF_STYLEOPTS:47,class:48,CLASSENTITY_IDS:49,STYLECLASS:50,direction_tb:51,direction_bt:52,direction_rl:53,direction_lr:54,eol:55,";":56,EDGE_STATE:57,STYLE_SEPARATOR:58,left_of:59,right_of:60,$accept:0,$end:1},terminals_:{2:"error",4:"SPACE",5:"NL",6:"SD",14:"DESCR",15:"-->",16:"HIDE_EMPTY",17:"scale",18:"WIDTH",19:"COMPOSIT_STATE",20:"STRUCT_START",21:"STRUCT_STOP",22:"STATE_DESCR",23:"AS",24:"ID",25:"FORK",26:"JOIN",27:"CHOICE",28:"CONCURRENT",29:"note",31:"NOTE_TEXT",33:"acc_title",34:"acc_title_value",35:"acc_descr",36:"acc_descr_value",37:"acc_descr_multiline_value",38:"CLICK",39:"STRING",40:"HREF",41:"classDef",42:"CLASSDEF_ID",43:"CLASSDEF_STYLEOPTS",44:"DEFAULT",45:"style",46:"STYLE_IDS",47:"STYLEDEF_STYLEOPTS",48:"class",49:"CLASSENTITY_IDS",50:"STYLECLASS",51:"direction_tb",52:"direction_bt",53:"direction_rl",54:"direction_lr",56:";",57:"EDGE_STATE",58:"STYLE_SEPARATOR",59:"left_of",60:"right_of"},productions_:[0,[3,2],[3,2],[3,2],[7,0],[7,2],[8,2],[8,1],[8,1],[9,1],[9,1],[9,1],[9,1],[9,2],[9,3],[9,4],[9,1],[9,2],[9,1],[9,4],[9,3],[9,6],[9,1],[9,1],[9,1],[9,1],[9,4],[9,4],[9,1],[9,2],[9,2],[9,1],[9,5],[9,5],[10,3],[10,3],[11,3],[12,3],[32,1],[32,1],[32,1],[32,1],[55,1],[55,1],[13,1],[13,1],[13,3],[13,3],[30,1],[30,1]],performAction:p(function(o,f,n,T,E,i,B){var d=i.length-1;switch(E){case 3:return T.setRootDoc(i[d]),i[d];case 4:this.$=[];break;case 5:i[d]!="nl"&&(i[d-1].push(i[d]),this.$=i[d-1]);break;case 6:case 7:this.$=i[d];break;case 8:this.$="nl";break;case 12:this.$=i[d];break;case 13:const Z=i[d-1];Z.description=T.trimColon(i[d]),this.$=Z;break;case 14:this.$={stmt:"relation",state1:i[d-2],state2:i[d]};break;case 15:const Tt=T.trimColon(i[d]);this.$={stmt:"relation",state1:i[d-3],state2:i[d-1],description:Tt};break;case 19:this.$={stmt:"state",id:i[d-3],type:"default",description:"",doc:i[d-1]};break;case 20:var Y=i[d],X=i[d-2].trim();if(i[d].match(":")){var ut=i[d].split(":");Y=ut[0],X=[X,ut[1]]}this.$={stmt:"state",id:Y,type:"default",description:X};break;case 21:this.$={stmt:"state",id:i[d-3],type:"default",description:i[d-5],doc:i[d-1]};break;case 22:this.$={stmt:"state",id:i[d],type:"fork"};break;case 23:this.$={stmt:"state",id:i[d],type:"join"};break;case 24:this.$={stmt:"state",id:i[d],type:"choice"};break;case 25:this.$={stmt:"state",id:T.getDividerId(),type:"divider"};break;case 26:this.$={stmt:"state",id:i[d-1].trim(),note:{position:i[d-2].trim(),text:i[d].trim()}};break;case 29:this.$=i[d].trim(),T.setAccTitle(this.$);break;case 30:case 31:this.$=i[d].trim(),T.setAccDescription(this.$);break;case 32:this.$={stmt:"click",id:i[d-3],url:i[d-2],tooltip:i[d-1]};break;case 33:this.$={stmt:"click",id:i[d-3],url:i[d-1],tooltip:""};break;case 34:case 35:this.$={stmt:"classDef",id:i[d-1].trim(),classes:i[d].trim()};break;case 36:this.$={stmt:"style",id:i[d-1].trim(),styleClass:i[d].trim()};break;case 37:this.$={stmt:"applyClass",id:i[d-1].trim(),styleClass:i[d].trim()};break;case 38:T.setDirection("TB"),this.$={stmt:"dir",value:"TB"};break;case 39:T.setDirection("BT"),this.$={stmt:"dir",value:"BT"};break;case 40:T.setDirection("RL"),this.$={stmt:"dir",value:"RL"};break;case 41:T.setDirection("LR"),this.$={stmt:"dir",value:"LR"};break;case 44:case 45:this.$={stmt:"state",id:i[d].trim(),type:"default",description:""};break;case 46:this.$={stmt:"state",id:i[d-2].trim(),classes:[i[d].trim()],type:"default",description:""};break;case 47:this.$={stmt:"state",id:i[d-2].trim(),classes:[i[d].trim()],type:"default",description:""};break}},"anonymous"),table:[{3:1,4:e,5:s,6:a},{1:[3]},{3:5,4:e,5:s,6:a},{3:6,4:e,5:s,6:a},t([1,4,5,16,17,19,22,24,25,26,27,28,29,33,35,37,38,41,45,48,51,52,53,54,57],r,{7:7}),{1:[2,1]},{1:[2,2]},{1:[2,3],4:c,5:h,8:8,9:10,10:12,11:13,12:14,13:15,16:u,17:l,19:m,22:y,24:_,25:L,26:R,27:D,28:S,29:w,32:25,33:C,35:F,37:I,38:P,41:v,45:z,48:at,51:nt,52:ot,53:lt,54:ct,57:K},t(g,[2,5]),{9:39,10:12,11:13,12:14,13:15,16:u,17:l,19:m,22:y,24:_,25:L,26:R,27:D,28:S,29:w,32:25,33:C,35:F,37:I,38:P,41:v,45:z,48:at,51:nt,52:ot,53:lt,54:ct,57:K},t(g,[2,7]),t(g,[2,8]),t(g,[2,9]),t(g,[2,10]),t(g,[2,11]),t(g,[2,12],{14:[1,40],15:[1,41]}),t(g,[2,16]),{18:[1,42]},t(g,[2,18],{20:[1,43]}),{23:[1,44]},t(g,[2,22]),t(g,[2,23]),t(g,[2,24]),t(g,[2,25]),{30:45,31:[1,46],59:[1,47],60:[1,48]},t(g,[2,28]),{34:[1,49]},{36:[1,50]},t(g,[2,31]),{13:51,24:_,57:K},{42:[1,52],44:[1,53]},{46:[1,54]},{49:[1,55]},t(ht,[2,44],{58:[1,56]}),t(ht,[2,45],{58:[1,57]}),t(g,[2,38]),t(g,[2,39]),t(g,[2,40]),t(g,[2,41]),t(g,[2,6]),t(g,[2,13]),{13:58,24:_,57:K},t(g,[2,17]),t(It,r,{7:59}),{24:[1,60]},{24:[1,61]},{23:[1,62]},{24:[2,48]},{24:[2,49]},t(g,[2,29]),t(g,[2,30]),{39:[1,63],40:[1,64]},{43:[1,65]},{43:[1,66]},{47:[1,67]},{50:[1,68]},{24:[1,69]},{24:[1,70]},t(g,[2,14],{14:[1,71]}),{4:c,5:h,8:8,9:10,10:12,11:13,12:14,13:15,16:u,17:l,19:m,21:[1,72],22:y,24:_,25:L,26:R,27:D,28:S,29:w,32:25,33:C,35:F,37:I,38:P,41:v,45:z,48:at,51:nt,52:ot,53:lt,54:ct,57:K},t(g,[2,20],{20:[1,73]}),{31:[1,74]},{24:[1,75]},{39:[1,76]},{39:[1,77]},t(g,[2,34]),t(g,[2,35]),t(g,[2,36]),t(g,[2,37]),t(ht,[2,46]),t(ht,[2,47]),t(g,[2,15]),t(g,[2,19]),t(It,r,{7:78}),t(g,[2,26]),t(g,[2,27]),{5:[1,79]},{5:[1,80]},{4:c,5:h,8:8,9:10,10:12,11:13,12:14,13:15,16:u,17:l,19:m,21:[1,81],22:y,24:_,25:L,26:R,27:D,28:S,29:w,32:25,33:C,35:F,37:I,38:P,41:v,45:z,48:at,51:nt,52:ot,53:lt,54:ct,57:K},t(g,[2,32]),t(g,[2,33]),t(g,[2,21])],defaultActions:{5:[2,1],6:[2,2],47:[2,48],48:[2,49]},parseError:p(function(o,f){if(f.recoverable)this.trace(o);else{var n=new Error(o);throw n.hash=f,n}},"parseError"),parse:p(function(o){var f=this,n=[0],T=[],E=[null],i=[],B=this.table,d="",Y=0,X=0,ut=2,Z=1,Tt=i.slice.call(arguments,1),k=Object.create(this.lexer),W={yy:{}};for(var Et in this.yy)Object.prototype.hasOwnProperty.call(this.yy,Et)&&(W.yy[Et]=this.yy[Et]);k.setInput(o,W.yy),W.yy.lexer=k,W.yy.parser=this,typeof k.yylloc>"u"&&(k.yylloc={});var _t=k.yylloc;i.push(_t);var ee=k.options&&k.options.ranges;typeof W.yy.parseError=="function"?this.parseError=W.yy.parseError:this.parseError=Object.getPrototypeOf(this).parseError;function se(N){n.length=n.length-2*N,E.length=E.length-N,i.length=i.length-N}p(se,"popStack");function Nt(){var N;return N=T.pop()||k.lex()||Z,typeof N!="number"&&(N instanceof Array&&(T=N,N=T.pop()),N=f.symbols_[N]||N),N}p(Nt,"lex");for(var x,j,O,bt,J={},ft,G,Rt,pt;;){if(j=n[n.length-1],this.defaultActions[j]?O=this.defaultActions[j]:((x===null||typeof x>"u")&&(x=Nt()),O=B[j]&&B[j][x]),typeof O>"u"||!O.length||!O[0]){var kt="";pt=[];for(ft in B[j])this.terminals_[ft]&&ft>ut&&pt.push("'"+this.terminals_[ft]+"'");k.showPosition?kt="Parse error on line "+(Y+1)+`:
`+k.showPosition()+`
Expecting `+pt.join(", ")+", got '"+(this.terminals_[x]||x)+"'":kt="Parse error on line "+(Y+1)+": Unexpected "+(x==Z?"end of input":"'"+(this.terminals_[x]||x)+"'"),this.parseError(kt,{text:k.match,token:this.terminals_[x]||x,line:k.yylineno,loc:_t,expected:pt})}if(O[0]instanceof Array&&O.length>1)throw new Error("Parse Error: multiple actions possible at state: "+j+", token: "+x);switch(O[0]){case 1:n.push(x),E.push(k.yytext),i.push(k.yylloc),n.push(O[1]),x=null,X=k.yyleng,d=k.yytext,Y=k.yylineno,_t=k.yylloc;break;case 2:if(G=this.productions_[O[1]][1],J.$=E[E.length-G],J._$={first_line:i[i.length-(G||1)].first_line,last_line:i[i.length-1].last_line,first_column:i[i.length-(G||1)].first_column,last_column:i[i.length-1].last_column},ee&&(J._$.range=[i[i.length-(G||1)].range[0],i[i.length-1].range[1]]),bt=this.performAction.apply(J,[d,X,Y,W.yy,O[1],E,i].concat(Tt)),typeof bt<"u")return bt;G&&(n=n.slice(0,-1*G*2),E=E.slice(0,-1*G),i=i.slice(0,-1*G)),n.push(this.productions_[O[1]][0]),E.push(J.$),i.push(J._$),Rt=B[n[n.length-2]][n[n.length-1]],n.push(Rt);break;case 3:return!0}}return!0},"parse")},te=(function(){var V={EOF:1,parseError:p(function(f,n){if(this.yy.parser)this.yy.parser.parseError(f,n);else throw new Error(f)},"parseError"),setInput:p(function(o,f){return this.yy=f||this.yy||{},this._input=o,this._more=this._backtrack=this.done=!1,this.yylineno=this.yyleng=0,this.yytext=this.matched=this.match="",this.conditionStack=["INITIAL"],this.yylloc={first_line:1,first_column:0,last_line:1,last_column:0},this.options.ranges&&(this.yylloc.range=[0,0]),this.offset=0,this},"setInput"),input:p(function(){var o=this._input[0];this.yytext+=o,this.yyleng++,this.offset++,this.match+=o,this.matched+=o;var f=o.match(/(?:\r\n?|\n).*/g);return f?(this.yylineno++,this.yylloc.last_line++):this.yylloc.last_column++,this.options.ranges&&this.yylloc.range[1]++,this._input=this._input.slice(1),o},"input"),unput:p(function(o){var f=o.length,n=o.split(/(?:\r\n?|\n)/g);this._input=o+this._input,this.yytext=this.yytext.substr(0,this.yytext.length-f),this.offset-=f;var T=this.match.split(/(?:\r\n?|\n)/g);this.match=this.match.substr(0,this.match.length-1),this.matched=this.matched.substr(0,this.matched.length-1),n.length-1&&(this.yylineno-=n.length-1);var E=this.yylloc.range;return this.yylloc={first_line:this.yylloc.first_line,last_line:this.yylineno+1,first_column:this.yylloc.first_column,last_column:n?(n.length===T.length?this.yylloc.first_column:0)+T[T.length-n.length].length-n[0].length:this.yylloc.first_column-f},this.options.ranges&&(this.yylloc.range=[E[0],E[0]+this.yyleng-f]),this.yyleng=this.yytext.length,this},"unput"),more:p(function(){return this._more=!0,this},"more"),reject:p(function(){if(this.options.backtrack_lexer)this._backtrack=!0;else return this.parseError("Lexical error on line "+(this.yylineno+1)+`. You can only invoke reject() in the lexer when the lexer is of the backtracking persuasion (options.backtrack_lexer = true).
`+this.showPosition(),{text:"",token:null,line:this.yylineno});return this},"reject"),less:p(function(o){this.unput(this.match.slice(o))},"less"),pastInput:p(function(){var o=this.matched.substr(0,this.matched.length-this.match.length);return(o.length>20?"...":"")+o.substr(-20).replace(/\n/g,"")},"pastInput"),upcomingInput:p(function(){var o=this.match;return o.length<20&&(o+=this._input.substr(0,20-o.length)),(o.substr(0,20)+(o.length>20?"...":"")).replace(/\n/g,"")},"upcomingInput"),showPosition:p(function(){var o=this.pastInput(),f=new Array(o.length+1).join("-");return o+this.upcomingInput()+`
`+f+"^"},"showPosition"),test_match:p(function(o,f){var n,T,E;if(this.options.backtrack_lexer&&(E={yylineno:this.yylineno,yylloc:{first_line:this.yylloc.first_line,last_line:this.last_line,first_column:this.yylloc.first_column,last_column:this.yylloc.last_column},yytext:this.yytext,match:this.match,matches:this.matches,matched:this.matched,yyleng:this.yyleng,offset:this.offset,_more:this._more,_input:this._input,yy:this.yy,conditionStack:this.conditionStack.slice(0),done:this.done},this.options.ranges&&(E.yylloc.range=this.yylloc.range.slice(0))),T=o[0].match(/(?:\r\n?|\n).*/g),T&&(this.yylineno+=T.length),this.yylloc={first_line:this.yylloc.last_line,last_line:this.yylineno+1,first_column:this.yylloc.last_column,last_column:T?T[T.length-1].length-T[T.length-1].match(/\r?\n?/)[0].length:this.yylloc.last_column+o[0].length},this.yytext+=o[0],this.match+=o[0],this.matches=o,this.yyleng=this.yytext.length,this.options.ranges&&(this.yylloc.range=[this.offset,this.offset+=this.yyleng]),this._more=!1,this._backtrack=!1,this._input=this._input.slice(o[0].length),this.matched+=o[0],n=this.performAction.call(this,this.yy,this,f,this.conditionStack[this.conditionStack.length-1]),this.done&&this._input&&(this.done=!1),n)return n;if(this._backtrack){for(var i in E)this[i]=E[i];return!1}return!1},"test_match"),next:p(function(){if(this.done)return this.EOF;this._input||(this.done=!0);var o,f,n,T;this._more||(this.yytext="",this.match="");for(var E=this._currentRules(),i=0;i<E.length;i++)if(n=this._input.match(this.rules[E[i]]),n&&(!f||n[0].length>f[0].length)){if(f=n,T=i,this.options.backtrack_lexer){if(o=this.test_match(n,E[i]),o!==!1)return o;if(this._backtrack){f=!1;continue}else return!1}else if(!this.options.flex)break}return f?(o=this.test_match(f,E[T]),o!==!1?o:!1):this._input===""?this.EOF:this.parseError("Lexical error on line "+(this.yylineno+1)+`. Unrecognized text.
`+this.showPosition(),{text:"",token:null,line:this.yylineno})},"next"),lex:p(function(){var f=this.next();return f||this.lex()},"lex"),begin:p(function(f){this.conditionStack.push(f)},"begin"),popState:p(function(){var f=this.conditionStack.length-1;return f>0?this.conditionStack.pop():this.conditionStack[0]},"popState"),_currentRules:p(function(){return this.conditionStack.length&&this.conditionStack[this.conditionStack.length-1]?this.conditions[this.conditionStack[this.conditionStack.length-1]].rules:this.conditions.INITIAL.rules},"_currentRules"),topState:p(function(f){return f=this.conditionStack.length-1-Math.abs(f||0),f>=0?this.conditionStack[f]:"INITIAL"},"topState"),pushState:p(function(f){this.begin(f)},"pushState"),stateStackSize:p(function(){return this.conditionStack.length},"stateStackSize"),options:{"case-insensitive":!0},performAction:p(function(f,n,T,E){function i(){const B=n.yytext.indexOf("%%");if(B===0)return!1;if(B>0){const d=n.yytext.slice(0,B),Y=n.yytext.slice(B);Y&&f.lexer.unput(Y),n.yytext=d}return!0}switch(p(i,"processId"),T){case 0:return 38;case 1:return 40;case 2:return 39;case 3:return 44;case 4:return 51;case 5:return 52;case 6:return 53;case 7:return 54;case 8:return 5;case 9:break;case 10:break;case 11:break;case 12:break;case 13:return this.pushState("SCALE"),17;case 14:return 18;case 15:this.popState();break;case 16:return this.begin("acc_title"),33;case 17:return this.popState(),"acc_title_value";case 18:return this.begin("acc_descr"),35;case 19:return this.popState(),"acc_descr_value";case 20:this.begin("acc_descr_multiline");break;case 21:this.popState();break;case 22:return"acc_descr_multiline_value";case 23:return this.pushState("CLASSDEF"),41;case 24:return this.popState(),this.pushState("CLASSDEFID"),"DEFAULT_CLASSDEF_ID";case 25:return this.popState(),this.pushState("CLASSDEFID"),42;case 26:return this.popState(),43;case 27:return this.pushState("CLASS"),48;case 28:return this.popState(),this.pushState("CLASS_STYLE"),49;case 29:return this.popState(),50;case 30:return this.pushState("STYLE"),45;case 31:return this.popState(),this.pushState("STYLEDEF_STYLES"),46;case 32:return this.popState(),47;case 33:return this.pushState("SCALE"),17;case 34:return 18;case 35:this.popState();break;case 36:this.pushState("STATE");break;case 37:return this.popState(),n.yytext=n.yytext.slice(0,-8).trim(),25;case 38:return this.popState(),n.yytext=n.yytext.slice(0,-8).trim(),26;case 39:return this.popState(),n.yytext=n.yytext.slice(0,-10).trim(),27;case 40:return this.popState(),n.yytext=n.yytext.slice(0,-8).trim(),25;case 41:return this.popState(),n.yytext=n.yytext.slice(0,-8).trim(),26;case 42:return this.popState(),n.yytext=n.yytext.slice(0,-10).trim(),27;case 43:return 51;case 44:return 52;case 45:return 53;case 46:return 54;case 47:this.pushState("STATE_STRING");break;case 48:return this.pushState("STATE_ID"),"AS";case 49:return i()?(this.popState(),"ID"):void 0;case 50:this.popState();break;case 51:return"STATE_DESCR";case 52:throw new Error('Error: State name must be a single word. Found: "'+n.yytext.trim()+'"');case 53:return 19;case 54:this.popState();break;case 55:return this.popState(),this.pushState("struct"),20;case 56:return this.popState(),21;case 57:break;case 58:return this.begin("NOTE"),29;case 59:return this.popState(),this.pushState("NOTE_ID"),59;case 60:return this.popState(),this.pushState("NOTE_ID"),60;case 61:this.popState(),this.pushState("FLOATING_NOTE");break;case 62:return this.popState(),this.pushState("FLOATING_NOTE_ID"),"AS";case 63:break;case 64:return"NOTE_TEXT";case 65:return i()?(this.popState(),"ID"):void 0;case 66:return i()?(this.popState(),this.pushState("NOTE_TEXT"),24):void 0;case 67:return this.popState(),n.yytext=n.yytext.substr(2).trim(),31;case 68:return this.popState(),n.yytext=n.yytext.slice(0,-8).trim(),31;case 69:return 6;case 70:return 6;case 71:return 16;case 72:return 57;case 73:return i()?24:void 0;case 74:return n.yytext=n.yytext.trim(),14;case 75:return 15;case 76:return 28;case 77:return 58;case 78:return 5;case 79:return"INVALID"}},"anonymous"),rules:[/^(?:click\b)/i,/^(?:href\b)/i,/^(?:"[^"]*")/i,/^(?:default\b)/i,/^(?:.*direction\s+TB[^\n]*)/i,/^(?:.*direction\s+BT[^\n]*)/i,/^(?:.*direction\s+RL[^\n]*)/i,/^(?:.*direction\s+LR[^\n]*)/i,/^(?:[\n]+)/i,/^(?:[\s]+)/i,/^(?:((?!\n)\s)+)/i,/^(?:#[^\n]*)/i,/^(?:%%(?!\{)[^\n]*)/i,/^(?:scale\s+)/i,/^(?:\d+)/i,/^(?:\s+width\b)/i,/^(?:accTitle\s*:\s*)/i,/^(?:(?!\n||)*[^\n]*)/i,/^(?:accDescr\s*:\s*)/i,/^(?:(?!\n||)*[^\n]*)/i,/^(?:accDescr\s*\{\s*)/i,/^(?:[\}])/i,/^(?:[^\}]*)/i,/^(?:classDef\s+)/i,/^(?:DEFAULT\s+)/i,/^(?:\w+\s+)/i,/^(?:[^\n]*)/i,/^(?:class\s+)/i,/^(?:(\w+)+((,\s*\w+)*))/i,/^(?:[^\n]*)/i,/^(?:style\s+)/i,/^(?:[\w,]+\s+)/i,/^(?:[^\n]*)/i,/^(?:scale\s+)/i,/^(?:\d+)/i,/^(?:\s+width\b)/i,/^(?:state\s+)/i,/^(?:.*<<fork>>)/i,/^(?:.*<<join>>)/i,/^(?:.*<<choice>>)/i,/^(?:.*\[\[fork\]\])/i,/^(?:.*\[\[join\]\])/i,/^(?:.*\[\[choice\]\])/i,/^(?:.*direction\s+TB[^\n]*)/i,/^(?:.*direction\s+BT[^\n]*)/i,/^(?:.*direction\s+RL[^\n]*)/i,/^(?:.*direction\s+LR[^\n]*)/i,/^(?:["])/i,/^(?:\s*as\s+)/i,/^(?:[^\n\{]*)/i,/^(?:["])/i,/^(?:[^"]*)/i,/^(?:\w+\s+\w+.*?\{)/i,/^(?:[^\n\s\{]+)/i,/^(?:\n)/i,/^(?:\{)/i,/^(?:\})/i,/^(?:[\n])/i,/^(?:note\s+)/i,/^(?:left of\b)/i,/^(?:right of\b)/i,/^(?:")/i,/^(?:\s*as\s*)/i,/^(?:["])/i,/^(?:[^"]*)/i,/^(?:[^\n]*)/i,/^(?:\s*[^:\n\s\-]+)/i,/^(?:\s*:[^:\n;]+)/i,/^(?:[\s\S]*?\n\s*end note\b)/i,/^(?:stateDiagram\s+)/i,/^(?:stateDiagram-v2\s+)/i,/^(?:hide empty description\b)/i,/^(?:\[\*\])/i,/^(?:[^:\n\s\-\{]+)/i,/^(?:\s*:(?:[^:\n;]|:[^:\n;])+)/i,/^(?:-->)/i,/^(?:--)/i,/^(?::::)/i,/^(?:$)/i,/^(?:.)/i],conditions:{LINE:{rules:[10,11,12],inclusive:!1},struct:{rules:[10,11,12,23,27,30,36,43,44,45,46,56,57,58,72,73,74,75,76,77],inclusive:!1},FLOATING_NOTE_ID:{rules:[65],inclusive:!1},FLOATING_NOTE:{rules:[62,63,64],inclusive:!1},NOTE_TEXT:{rules:[67,68],inclusive:!1},NOTE_ID:{rules:[66],inclusive:!1},NOTE:{rules:[59,60,61],inclusive:!1},STYLEDEF_STYLEOPTS:{rules:[],inclusive:!1},STYLEDEF_STYLES:{rules:[32],inclusive:!1},STYLE_IDS:{rules:[],inclusive:!1},STYLE:{rules:[31],inclusive:!1},CLASS_STYLE:{rules:[29],inclusive:!1},CLASS:{rules:[28],inclusive:!1},CLASSDEFID:{rules:[26],inclusive:!1},CLASSDEF:{rules:[24,25],inclusive:!1},acc_descr_multiline:{rules:[21,22],inclusive:!1},acc_descr:{rules:[19],inclusive:!1},acc_title:{rules:[17],inclusive:!1},SCALE:{rules:[14,15,34,35],inclusive:!1},ALIAS:{rules:[],inclusive:!1},STATE_ID:{rules:[49],inclusive:!1},STATE_STRING:{rules:[50,51],inclusive:!1},FORK_STATE:{rules:[],inclusive:!1},STATE:{rules:[10,11,12,37,38,39,40,41,42,47,48,52,53,54,55],inclusive:!1},ID:{rules:[10,11,12],inclusive:!1},INITIAL:{rules:[0,1,2,3,4,5,6,7,8,9,11,12,13,16,18,20,23,27,30,33,36,55,58,69,70,71,72,73,74,75,77,78,79],inclusive:!0}}};return V})();mt.lexer=te;function dt(){this.yy={}}return p(dt,"Parser"),dt.prototype=mt,mt.Parser=dt,new dt})();At.parser=At;var be=At,ke="TB",Gt="TB",Ot="dir",Q="state",q="root",xt="relation",ve="classDef",De="style",Ce="applyClass",it="default",Vt="divider",Mt="fill:none",Wt="fill: #333",jt="c",Ut="markdown",Ht="normal",Dt="rect",Ct="rectWithTitle",Ae="stateStart",xe="stateEnd",Lt="divider",$t="roundedWithTitle",Le="note",we="noteGroup",rt="statediagram",Ie="state",Ne=`${rt}-${Ie}`,zt="transition",Re="note",Oe="note-edge",$e=`${zt} ${Oe}`,Fe=`${rt}-${Re}`,Pe="cluster",Be=`${rt}-${Pe}`,Ye="cluster-alt",Ge=`${rt}-${Ye}`,Kt="parent",Xt="note",Ve="state",wt="----",Me=`${wt}${Xt}`,Ft=`${wt}${Kt}`,gt=new Map,M=0,Jt=0,tt=new Map,We=p((t,e,s,a)=>{if(t===Lt&&s?.id!==void 0&&tt.has(s.id)){const h=tt.get(s.id);return tt.set(e,h),h}const r=Jt++,c=a?void 0:r;return tt.set(e,c),c},"colorSlotFor");function yt(t="",e=0,s="",a=wt){const r=s!==null&&s.length>0?`${a}${s}`:"";return`${Ve}-${t}${r}-${e}`}p(yt,"stateDomId");var je=p((t,e,s,a,r,c,h,u)=>{b.trace("items",e),e.forEach(l=>{switch(l.stmt){case Q:st(t,l,s,a,r,c,h,u);break;case it:st(t,l,s,a,r,c,h,u);break;case xt:{st(t,l.state1,s,a,r,c,h,u),st(t,l.state2,s,a,r,c,h,u);const m=h==="neo",y={id:"edge"+M,start:l.state1.id,end:l.state2.id,arrowhead:"normal",arrowTypeEnd:m?"arrow_barb_neo":"arrow_barb",style:Mt,labelStyle:"",label:U.sanitizeText(l.description??"",$()),arrowheadStyle:Wt,labelpos:jt,labelType:Ut,thickness:Ht,classes:zt,look:h};r.push(y),M++}break}})},"setupDoc"),Pt=p((t,e=Gt)=>{let s=e;if(t.doc)for(const a of t.doc)a.stmt==="dir"&&(s=a.value);return s},"getDir");function et(t,e,s){if(!e.id||e.id==="</join></fork>"||e.id==="</choice>")return;e.cssClasses&&(Array.isArray(e.cssCompiledStyles)||(e.cssCompiledStyles=[]),e.cssClasses.split(" ").forEach(r=>{const c=s.get(r);c&&(e.cssCompiledStyles=[...e.cssCompiledStyles??[],...c.styles])}));const a=t.find(r=>r.id===e.id);a?Object.assign(a,e):t.push(e)}p(et,"insertOrUpdateNode");function qt(t){return t?.classes?.join(" ")??""}p(qt,"getClassesFromDbInfo");function Qt(t){return t?.styles??[]}p(Qt,"getStylesFromDbInfo");var st=p((t,e,s,a,r,c,h,u)=>{const l=e.id,m=s.get(l),y=qt(m),_=Qt(m),L=$(),R=y.trim()!==""||_.length>0;if(b.info("dataFetcher parsedItem",e,m,_),l!=="root"){let D=Dt;e.start===!0?D=Ae:e.start===!1&&(D=xe),e.type!==it&&(D=e.type),gt.get(l)||gt.set(l,{id:l,shape:D,description:U.sanitizeText(l,L),cssClasses:`${y} ${Ne}`,cssStyles:_});const S=gt.get(l);e.description&&(Array.isArray(S.description)?(S.shape=Ct,S.description.push(e.description)):S.description?.length&&S.description.length>0?(S.shape=Ct,S.description===l?S.description=[e.description]:S.description=[S.description,e.description]):(S.shape=Dt,S.description=e.description),S.description=U.sanitizeTextOrArray(S.description,L)),S.description?.length===1&&S.shape===Ct&&(S.type==="group"?S.shape=$t:S.shape=Dt),!S.type&&e.doc&&(b.info("Setting cluster for XCX",l,Pt(e)),S.type="group",S.isGroup=!0,S.dir=Pt(e),S.shape=e.type===Vt?Lt:$t,S.colorIndex=We(S.shape,l,t,R),S.cssClasses=`${S.cssClasses} ${Be} ${c?Ge:""}`);const w={labelStyle:"",shape:S.shape,label:S.description,cssClasses:S.cssClasses,cssCompiledStyles:[],cssStyles:S.cssStyles,id:l,dir:S.dir,domId:yt(l,M),type:S.type,isGroup:S.type==="group",colorIndex:S.colorIndex,padding:8,rx:10,ry:10,look:h,labelType:"markdown"};if(w.shape===Lt&&(w.label=""),t&&t.id!=="root"&&(b.trace("Setting node ",l," to be child of its parent ",t.id),w.parentId=t.id),w.centerLabel=!0,e.note){const C={labelStyle:"",shape:Le,label:e.note.text,labelType:"markdown",cssClasses:Fe,cssStyles:[],cssCompiledStyles:[],id:l+Me+"-"+M,domId:yt(l,M,Xt),type:"node",isGroup:!1,padding:L.flowchart?.padding,look:h,position:e.note.position},F=l+Ft,I={labelStyle:"",shape:we,label:e.note.text,cssClasses:S.cssClasses,cssStyles:[],id:l+Ft,domId:yt(l,M,Kt),type:"group",isGroup:!0,padding:16,look:h,position:e.note.position};M++,I.id=F,C.parentId=F,et(a,I,u),et(a,C,u),et(a,w,u);let P=l,v=C.id;e.note.position==="left of"&&(P=C.id,v=l),r.push({id:P+"-"+v,start:P,end:v,arrowhead:"none",arrowTypeEnd:"",style:Mt,labelStyle:"",classes:$e,pattern:"dashed",arrowheadStyle:Wt,labelpos:jt,labelType:Ut,thickness:Ht,look:h})}else et(a,w,u)}e.doc&&(b.trace("Adding nodes children "),je(e,e.doc,s,a,r,!c,h,u))},"dataFetcher"),Ue=p(()=>{gt.clear(),M=0,Jt=0,tt.clear()},"reset"),Zt=p((t,e=Gt)=>{if(!t.doc)return e;let s=e;for(const a of t.doc)a.stmt==="dir"&&(s=a.value);return s},"getDir"),He=p(function(t,e){return e.db.getClasses()},"getClasses"),ze=p(async function(t,e,s,a){b.info("REF0:"),b.info("Drawing state diagram (v2)",e);const{securityLevel:r,state:c,layout:h}=$();a.db.extract(a.db.getRootDocV2());const u=a.db.getData(),l=ie(e,r);u.type=a.type,u.layoutAlgorithm=ae(h),u.nodeSpacing=c?.nodeSpacing||50,u.rankSpacing=c?.rankSpacing||50,$().look==="neo"?u.markers=["barbNeo"]:u.markers=["barb"],u.diagramId=e,await ne(u,l);const y=8;try{(typeof a.db.getLinks=="function"?a.db.getLinks():new Map).forEach((L,R)=>{const D=typeof R=="string"?R:typeof R?.id=="string"?R.id:"",S=u.nodes.find(v=>v.id===D);if(!D){b.warn("⚠️ Invalid or missing stateId from key:",JSON.stringify(R));return}const w=l.node()?.querySelectorAll("g.node, g.rough-node");let C;if(w?.forEach(v=>{const z=v.textContent?.trim();(v.id===S?.domId||z===D)&&(C=v)}),!C){b.warn("⚠️ Could not find node matching text:",D);return}const F=C.parentNode;if(!F){b.warn("⚠️ Node has no parent, cannot wrap:",D);return}const I=document.createElementNS("http://www.w3.org/2000/svg","a"),P=L.url.replace(/^"+|"+$/g,"");if(I.setAttributeNS("http://www.w3.org/1999/xlink","xlink:href",P),I.setAttribute("target","_blank"),L.tooltip){const v=L.tooltip.replace(/^"+|"+$/g,"");I.setAttribute("title",v),C.setAttribute("title",v)}F.replaceChild(I,C),I.appendChild(C),b.info("🔗 Wrapped node in <a> tag for:",D,L.url)})}catch(_){b.error("❌ Error injecting clickable links:",_)}oe.insertTitle(l,"statediagramTitleText",c?.titleTopMargin??25,a.db.getDiagramTitle()),re(l,y,rt,c?.useMaxWidth??!0)},"draw"),Ke={getClasses:He,draw:ze,getDir:Zt},A={START_NODE:"[*]",START_TYPE:"start",END_NODE:"[*]",END_TYPE:"end",COLOR_KEYWORD:"color",FILL_KEYWORD:"fill",BG_FILL:"bgFill",STYLECLASS_SEP:","},Bt=p(()=>new Map,"newClassesList"),Yt=p(()=>({relations:[],states:new Map,documents:{}}),"newDoc"),St=p(t=>JSON.parse(JSON.stringify(t)),"clone"),H,Xe=(H=class{constructor(e){this.version=e,this.nodes=[],this.edges=[],this.rootDoc=[],this.classes=Bt(),this.documents={root:Yt()},this.currentDocument=this.documents.root,this.startEndCount=0,this.dividerCnt=0,this.links=new Map,this.funs=[],this.getAccTitle=le,this.setAccTitle=ce,this.getAccDescription=he,this.setAccDescription=de,this.setDiagramTitle=ue,this.getDiagramTitle=fe,this.clear(),this.setRootDoc=this.setRootDoc.bind(this),this.getDividerId=this.getDividerId.bind(this),this.setDirection=this.setDirection.bind(this),this.trimColon=this.trimColon.bind(this),this.bindFunctions=this.bindFunctions.bind(this)}extract(e){this.clear(!0);for(const r of Array.isArray(e)?e:e.doc)switch(r.stmt){case Q:this.addState(r.id.trim(),r.type,r.doc,r.description,r.note);break;case xt:this.addRelation(r.state1,r.state2,r.description);break;case ve:this.addStyleClass(r.id.trim(),r.classes);break;case De:this.handleStyleDef(r);break;case Ce:this.setCssClass(r.id.trim(),r.styleClass);break;case"click":this.addLink(r.id,r.url,r.tooltip);break}const s=this.getStates(),a=$();Ue(),st(void 0,this.getRootDocV2(),s,this.nodes,this.edges,!0,a.look,this.classes);for(const r of this.nodes)if(Array.isArray(r.label)){if(r.description=r.label.slice(1),r.isGroup&&r.description.length>0)throw new Error(`Group nodes can only have label. Remove the additional description for node [${r.id}]`);r.label=r.label[0]}}handleStyleDef(e){const s=e.id.trim().split(","),a=e.styleClass.split(",");for(const r of s){let c=this.getState(r);if(!c){const h=r.trim();this.addState(h),c=this.getState(h)}c&&(c.styles=a.map(h=>h.replace(/;/g,"")?.trim()))}}setRootDoc(e){b.info("Setting root doc",e),this.rootDoc=e,this.version===1?this.extract(e):this.extract(this.getRootDocV2())}docTranslator(e,s,a){if(s.stmt===xt){this.docTranslator(e,s.state1,!0),this.docTranslator(e,s.state2,!1);return}if(s.stmt===Q&&(s.id===A.START_NODE?(s.id=e.id+(a?"_start":"_end"),s.start=a):s.id=s.id.trim()),s.stmt!==q&&s.stmt!==Q||!s.doc)return;const r=[];let c=[];for(const h of s.doc)if(h.type===Vt){const u=St(h);u.doc=St(c),r.push(u),c=[]}else c.push(h);if(r.length>0&&c.length>0){const h={stmt:Q,id:pe(),type:"divider",doc:St(c)};r.push(St(h)),s.doc=r}s.doc.forEach(h=>this.docTranslator(s,h,!0))}getRootDocV2(){return this.docTranslator({id:q,stmt:q},{id:q,stmt:q,doc:this.rootDoc},!0),{id:q,doc:this.rootDoc}}addState(e,s=it,a=void 0,r=void 0,c=void 0,h=void 0,u=void 0,l=void 0){const m=e?.trim();if(!this.currentDocument.states.has(m))b.info("Adding state ",m,r),this.currentDocument.states.set(m,{stmt:Q,id:m,descriptions:[],type:s,doc:a,note:c,classes:[],styles:[],textStyles:[]});else{const y=this.currentDocument.states.get(m);if(!y)throw new Error(`State not found: ${m}`);y.doc||(y.doc=a),y.type||(y.type=s)}if(r&&(b.info("Setting state description",m,r),(Array.isArray(r)?r:[r]).forEach(_=>this.addDescription(m,_.trim()))),c){const y=this.currentDocument.states.get(m);if(!y)throw new Error(`State not found: ${m}`);y.note=c,y.note.text=U.sanitizeText(y.note.text,$())}h&&(b.info("Setting state classes",m,h),(Array.isArray(h)?h:[h]).forEach(_=>this.setCssClass(m,_.trim()))),u&&(b.info("Setting state styles",m,u),(Array.isArray(u)?u:[u]).forEach(_=>this.setStyle(m,_.trim()))),l&&(b.info("Setting state styles",m,u),(Array.isArray(l)?l:[l]).forEach(_=>this.setTextStyle(m,_.trim())))}clear(e){this.nodes=[],this.edges=[],this.funs=[this.setupToolTips.bind(this)],this.documents={root:Yt()},this.currentDocument=this.documents.root,this.startEndCount=0,this.classes=Bt(),e||(this.links=new Map,Se())}getState(e){return this.currentDocument.states.get(e)}getStates(){return this.currentDocument.states}logDocuments(){b.info("Documents = ",this.documents)}getRelations(){return this.currentDocument.relations}addLink(e,s,a){this.links.set(e,{url:s,tooltip:a}),b.warn("Adding link",e,s,a)}getLinks(){return this.links}startIdIfNeeded(e=""){return e===A.START_NODE?(this.startEndCount++,`${A.START_TYPE}${this.startEndCount}`):e}startTypeIfNeeded(e="",s=it){return e===A.START_NODE?A.START_TYPE:s}endIdIfNeeded(e=""){return e===A.END_NODE?(this.startEndCount++,`${A.END_TYPE}${this.startEndCount}`):e}endTypeIfNeeded(e="",s=it){return e===A.END_NODE?A.END_TYPE:s}addRelationObjs(e,s,a=""){const r=this.startIdIfNeeded(e.id.trim()),c=this.startTypeIfNeeded(e.id.trim(),e.type),h=this.startIdIfNeeded(s.id.trim()),u=this.startTypeIfNeeded(s.id.trim(),s.type);this.addState(r,c,e.doc,e.description,e.note,e.classes,e.styles,e.textStyles),this.addState(h,u,s.doc,s.description,s.note,s.classes,s.styles,s.textStyles),this.currentDocument.relations.push({id1:r,id2:h,relationTitle:U.sanitizeText(a,$())})}addRelation(e,s,a){if(typeof e=="object"&&typeof s=="object")this.addRelationObjs(e,s,a);else if(typeof e=="string"&&typeof s=="string"){const r=this.startIdIfNeeded(e.trim()),c=this.startTypeIfNeeded(e),h=this.endIdIfNeeded(s.trim()),u=this.endTypeIfNeeded(s);this.addState(r,c),this.addState(h,u),this.currentDocument.relations.push({id1:r,id2:h,relationTitle:a?U.sanitizeText(a,$()):void 0})}}addDescription(e,s){const a=this.currentDocument.states.get(e),r=s.startsWith(":")?s.replace(":","").trim():s;a?.descriptions?.push(U.sanitizeText(r,$()))}cleanupLabel(e){return e.startsWith(":")?e.slice(2).trim():e.trim()}getDividerId(){return this.dividerCnt++,`divider-id-${this.dividerCnt}`}addStyleClass(e,s=""){this.classes.has(e)||this.classes.set(e,{id:e,styles:[],textStyles:[]});const a=this.classes.get(e);s&&a&&s.split(A.STYLECLASS_SEP).forEach(r=>{const c=r.replace(/([^;]*);/,"$1").trim();if(RegExp(A.COLOR_KEYWORD).exec(r)){const u=c.replace(A.FILL_KEYWORD,A.BG_FILL).replace(A.COLOR_KEYWORD,A.FILL_KEYWORD);a.textStyles.push(u)}a.styles.push(c)})}getClasses(){return this.classes}setupToolTips(e){const s=Ee();vt(e).select("svg").selectAll("g.node, g.rough-node").on("mouseover",c=>{const h=vt(c.currentTarget),u=h.attr("title");if(u===null)return;const l=c.currentTarget?.getBoundingClientRect();s.transition().duration(200).style("opacity",".9"),s.style("left",window.scrollX+l.left+(l.right-l.left)/2+"px").style("top",window.scrollY+l.bottom+"px"),s.html(_e.sanitize(u)),h.classed("hover",!0)}).on("mouseout",c=>{s.transition().duration(500).style("opacity",0),vt(c.currentTarget).classed("hover",!1)})}setCssClass(e,s){e.split(",").forEach(a=>{let r=this.getState(a);if(!r){const c=a.trim();this.addState(c),r=this.getState(c)}r?.classes?.push(s)})}setStyle(e,s){this.getState(e)?.styles?.push(s)}setTextStyle(e,s){this.getState(e)?.textStyles?.push(s)}bindFunctions(e){this.funs.forEach(s=>{s(e)})}getDirectionStatement(){return this.rootDoc.find(e=>e.stmt===Ot)}getDirection(){return this.getDirectionStatement()?.value??ke}setDirection(e){const s=this.getDirectionStatement();s?s.value=e:this.rootDoc.unshift({stmt:Ot,value:e})}trimColon(e){return e.startsWith(":")?e.slice(1).trim():e.trim()}getData(){const e=$();for(const s of this.nodes)s.wrappingWidth??=e.state?.wrappingWidth,s.isGroup||(s.minWidth??=e.state?.minNodeWidth);return{nodes:this.nodes,edges:this.edges,other:{},config:e,direction:Zt(this.getRootDocV2())}}getConfig(){return $().state}},p(H,"StateDB"),H.relationType={AGGREGATION:0,EXTENSION:1,COMPOSITION:2,DEPENDENCY:3},H),Je=p(t=>{const{theme:e,bkgColorArray:s,borderColorArray:a}=t;if(!ge(e,a))return"";const r=ye(t.look),c=me(s);let h="";for(let u=0;u<Te(a);u++){const l=a[u],m=c?`fill: ${s[u%s.length]};`:"",y=`[data-look="${r}"][data-color-id="color-${u}"]`;h+=`

    /* The title strip: \`rect.outer\` spans the whole composite and \`rect.inner\` covers
       the body, so what stays visible of \`outer\` is the band behind the label. */
    ${y}.statediagram-cluster rect.outer {
      stroke: ${l};
      ${m}
    }

    ${y}.statediagram-cluster rect.inner {
      stroke: ${l};
    }

    /* Concurrency regions. Siblings of one composite share a slot, so a divided composite
       reads as one thing split into parts rather than as several composites. */
    ${y}.statediagram-cluster rect.divider {
      stroke: ${l};
      ${m}
    }

    /* handDrawn draws the same container as roughjs shapes rather than plain rects, so it
       needs its own rules. \`roundedWithTitle\` and \`divider\` name those groups \`outer\`,
       \`inner\` and \`divider\` to match the classic branch, which is what lets these
       discriminate -- a bare \`.statediagram-cluster path\` rule reached the body as well and
       tinted the whole composite, losing \`compositeBackground\` and diverging from what
       classic and neo do.

       roughjs emits two paths per shape and marks them: the filled shape carries
       \`stroke="none"\` and the sketched outline carries \`fill="none"\`. Splitting on that is
       what keeps \`fill\` off the outline -- a rough outline is open squiggles, not a closed
       region, so filling it produces smears -- and keeps \`stroke\` off the fill shape, which
       would otherwise gain an edge it was drawn without. */
    ${y}.statediagram-cluster .outer path[stroke='none'] {
      ${m}
    }

    ${y}.statediagram-cluster .outer path[fill='none'] {
      stroke: ${l};
    }

    /* No \`.inner\` rule on purpose. The body shape is left entirely alone under handDrawn,
       where a rect's \`inner\` counterpart cannot be recoloured safely: roughjs draws a
       hachure fill as *stroked* lines, so its fill paths carry \`fill="none"\` exactly like
       the outline and no selector separates them. An \`.inner\` stroke rule therefore
       repainted the hatching of every alt composite in the palette colour instead of
       leaving it on \`altBackground\`. The container still reads as palette-coloured: the
       \`outer\` shape spans the whole composite, so its outline already frames the body. */

    /* Regions split the same way, which is why \`divider\` fills solid rather than taking
       roughjs's default hachure -- see the note on that call. Hatched, both of its paths
       carried \`fill="none"\` and these two rules degenerated: the tint matched nothing and
       the border rule repainted the hatching. */
    ${y}.statediagram-cluster .divider path[stroke='none'] {
      ${m}
    }

    ${y}.statediagram-cluster .divider path[fill='none'] {
      stroke: ${l};
    }
    `}return h},"genColor"),qe=p(t=>`
${Je(t)}
defs [id$="-barbEnd"] {
    fill: ${t.transitionColor};
    stroke: ${t.transitionColor};
  }
g.stateGroup text {
  fill: ${t.nodeBorder};
  stroke: none;
  font-size: 10px;
}
g.stateGroup text {
  fill: ${t.textColor};
  stroke: none;
  font-size: 10px;

}
g.stateGroup .state-title {
  font-weight: bolder;
  fill: ${t.stateLabelColor};
}

g.stateGroup rect {
  fill: ${t.mainBkg};
  stroke: ${t.nodeBorder};
}

g.stateGroup line {
  stroke: ${t.lineColor};
  stroke-width: ${t.strokeWidth||1};
}

.transition {
  stroke: ${t.transitionColor};
  stroke-width: ${t.strokeWidth||1};
  fill: none;
}

.stateGroup .composit {
  fill: ${t.background};
  border-bottom: 1px
}

.stateGroup .alt-composit {
  fill: #e0e0e0;
  border-bottom: 1px
}

.state-note {
  stroke: ${t.noteBorderColor};
  fill: ${t.noteBkgColor};

  text {
    fill: ${t.noteTextColor};
    stroke: none;
    font-size: 10px;
  }
}

.stateLabel .box {
  stroke: none;
  stroke-width: 0;
  fill: ${t.mainBkg};
  opacity: 0.5;
}

.edgeLabel .label rect {
  fill: ${t.labelBackgroundColor};
  opacity: 0.5;
}
.edgeLabel {
  background-color: ${t.edgeLabelBackground};
  p {
    background-color: ${t.edgeLabelBackground};
  }
  rect {
    opacity: 0.5;
    background-color: ${t.edgeLabelBackground};
    fill: ${t.edgeLabelBackground};
  }
  text-align: center;
}
.edgeLabel .label text {
  fill: ${t.transitionLabelColor||t.tertiaryTextColor};
}
.label div .edgeLabel {
  color: ${t.transitionLabelColor||t.tertiaryTextColor};
}

.stateLabel text {
  fill: ${t.stateLabelColor};
  font-size: 10px;
  font-weight: bold;
}

.node circle.state-start {
  fill: ${t.specialStateColor};
  stroke: ${t.specialStateColor};
}

.node .fork-join {
  fill: ${t.specialStateColor};
  stroke: ${t.specialStateColor};
}

.node circle.state-end {
  fill: ${t.innerEndBackground};
  stroke: ${t.background};
  stroke-width: 1.5
}
.end-state-inner {
  fill: ${t.compositeBackground||t.background};
  // stroke: ${t.background};
  stroke-width: 1.5
}

.node rect {
  fill: ${t.stateBkg||t.mainBkg};
  stroke: ${t.stateBorder||t.nodeBorder};
  stroke-width: ${t.strokeWidth||1}px;
}
.node polygon {
  fill: ${t.mainBkg};
  stroke: ${t.stateBorder||t.nodeBorder};;
  stroke-width: ${t.strokeWidth||1}px;
}
[id$="-barbEnd"] {
  fill: ${t.lineColor};
}

.statediagram-cluster rect {
  fill: ${t.compositeTitleBackground};
  stroke: ${t.stateBorder||t.nodeBorder};
  stroke-width: ${t.strokeWidth||1}px;
}

.cluster-label, .nodeLabel {
  color: ${t.stateLabelColor};
  // line-height: 1;
}

.statediagram-cluster rect.outer {
  rx: 5px;
  ry: 5px;
}
.statediagram-state .divider {
  stroke: ${t.stateBorder||t.nodeBorder};
}

.statediagram-state .title-state {
  rx: 5px;
  ry: 5px;
}
.statediagram-cluster.statediagram-cluster .inner {
  fill: ${t.compositeBackground||t.background};
}
.statediagram-cluster.statediagram-cluster-alt .inner {
  fill: ${t.altBackground?t.altBackground:"#efefef"};
}

.statediagram-cluster .inner {
  rx:0;
  ry:0;
}

.statediagram-state rect.basic {
  rx: 5px;
  ry: 5px;
}
.statediagram-state rect.divider {
  stroke-dasharray: 10,10;
  fill: ${t.altBackground?t.altBackground:"#efefef"};
}

.note-edge {
  stroke-dasharray: 5;
}

.statediagram-note rect {
  fill: ${t.noteBkgColor};
  stroke: ${t.noteBorderColor};
  stroke-width: 1px;
  rx: 0;
  ry: 0;
}
.statediagram-note rect {
  fill: ${t.noteBkgColor};
  stroke: ${t.noteBorderColor};
  stroke-width: 1px;
  rx: 0;
  ry: 0;
}

.statediagram-note text {
  fill: ${t.noteTextColor};
}

.statediagram-note .nodeLabel {
  color: ${t.noteTextColor};
}
.statediagram .edgeLabel {
  color: red; // ${t.noteTextColor};
}

[id$="-dependencyStart"], [id$="-dependencyEnd"] {
  fill: ${t.lineColor};
  stroke: ${t.lineColor};
  stroke-width: ${t.strokeWidth||1};
}

.statediagramTitleText {
  text-anchor: middle;
  font-size: 18px;
  fill: ${t.textColor};
}

[data-look="neo"].statediagram-cluster rect {
  fill: ${t.mainBkg};
  stroke: ${t.useGradient?"url("+t.svgId+"-gradient)":t.stateBorder||t.nodeBorder};
  stroke-width: ${t.strokeWidth??1};
}
[data-look="neo"].statediagram-cluster rect.outer {
  rx: ${t.radius}px;
  ry: ${t.radius}px;
  filter: ${t.dropShadow?t.dropShadow.replace("url(#drop-shadow)",`url(${t.svgId}-drop-shadow)`):"none"}
}
`,"getStyles"),Qe=qe,as={parser:be,get db(){return new Xe(2)},renderer:Ke,styles:Qe,init:p(t=>{t.state||(t.state={}),t.state.arrowMarkerAbsolute=t.arrowMarkerAbsolute},"init")};export{as as diagram};
