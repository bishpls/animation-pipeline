// Export per-drawable geometry of a Cubism model under a list of parameter configs (no physics, no pose/fade).
const fs=require('fs');const S=__dirname+'/..',name=process.argv[2];
const C=require(S+'/core.cjs');
process.on("uncaughtException",e=>{console.log("ERR",String(e.stack).slice(0,500));process.exit(1)});
const CFG=[
 ['base',{}],
 ['AX+30',{ParamAngleX:30}],['AX-30',{ParamAngleX:-30}],['AX+15',{ParamAngleX:15}],
 ['AY+30',{ParamAngleY:30}],['AY-30',{ParamAngleY:-30}],['AY+15',{ParamAngleY:15}],
 ['AZ+30',{ParamAngleZ:30}],['AZ-30',{ParamAngleZ:-30}],['AZ+15',{ParamAngleZ:15}],
 ['BX+10',{ParamBodyAngleX:10}],['BX-10',{ParamBodyAngleX:-10}],['BX+5',{ParamBodyAngleX:5}],
 ['BY+10',{ParamBodyAngleY:10}],['BY-10',{ParamBodyAngleY:-10}],['BY+5',{ParamBodyAngleY:5}],
 ['BZ+10',{ParamBodyAngleZ:10}],['BZ-10',{ParamBodyAngleZ:-10}],['BZ+5',{ParamBodyAngleZ:5}],
 ['Br=1',{ParamBreath:1}],['Br=0.5',{ParamBreath:0.5}],
 ['AX+30&AZ+30',{ParamAngleX:30,ParamAngleZ:30}],
 ['AX+30&AY+30',{ParamAngleX:30,ParamAngleY:30}],
 ['AZ+30&BZ+10',{ParamAngleZ:30,ParamBodyAngleZ:10}],
 ['AX+30&BX+10',{ParamAngleX:30,ParamBodyAngleX:10}],
 ['AX-30&AZ+30',{ParamAngleX:-30,ParamAngleZ:30}],
 ['AY+30&AZ+30',{ParamAngleY:30,ParamAngleZ:30}],
 ['AX+30&BZ+10',{ParamAngleX:30,ParamBodyAngleZ:10}],
 ['BX+10&BZ+10',{ParamBodyAngleX:10,ParamBodyAngleZ:10}],
 ['AZ+30&BX+10',{ParamAngleZ:30,ParamBodyAngleX:10}],
];
setTimeout(()=>{
 const dir=S+'/cws/Samples/Resources/'+name+'/';const buf=fs.readFileSync(dir+name+'.moc3');
 const m=C.Model.fromMoc(C.Moc.fromArrayBuffer(buf.buffer.slice(buf.byteOffset,buf.byteOffset+buf.length)));
 const cdi=JSON.parse(fs.readFileSync(dir+name+'.cdi3.json'));const pname={};(cdi.Parts||[]).forEach(p=>pname[p.Id]=p.Name);
 const P=m.parameters,D=m.drawables,Pt=m.parts;
 const chain=i=>{const a=[];while(i>=0){a.unshift(pname[Pt.ids[i]]||Pt.ids[i]);i=Pt.parentIndices[i];}return a.join('>');};
 const chainIds=i=>{const a=[];while(i>=0){a.unshift(Pt.ids[i]);i=Pt.parentIndices[i];}return a.join('>');};
 const r4=a=>Array.from(a,x=>Math.round(x*1e5)/1e5);
 const snap=o=>{for(let i=0;i<P.count;i++)P.values[i]=P.defaultValues[i];for(const k in o){const i=P.ids.indexOf(k);if(i>=0)P.values[i]=o[k];}m.update();return Array.from({length:D.count},(_,d)=>r4(D.vertexPositions[d]));};
 const out={model:name,canvas:m.canvasinfo,params:{},drawables:[],configs:{}};
 P.ids.forEach((id,i)=>{if(/Angle[XYZ]$|Breath|Body/.test(id))out.params[id]={min:P.minimumValues[i],max:P.maximumValues[i],def:P.defaultValues[i],keys:Array.from(P.keyValues[i])};});
 snap({});
 for(let d=0;d<D.count;d++)out.drawables.push({id:D.ids[d],part:chain(D.parentPartIndices[d]),partIds:chainIds(D.parentPartIndices[d]),opacity:D.opacities[d],order:D.renderOrders[d],tex:D.textureIndices[d],uv:r4(D.vertexUvs[d]),idx:Array.from(D.indices[d])});
 for(const [k,o] of CFG){const pos=snap(o);out.configs[k]={params:o,pos};}
 fs.writeFileSync(__dirname+'/'+name+'.geo.json',JSON.stringify(out));
 console.log(name,'drawables',D.count,'configs',CFG.length);
},500);
