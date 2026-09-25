const fs=require('fs');const S=__dirname+'/..';const C=require(S+'/core.cjs');
setTimeout(()=>{for(const [name,part] of [['Hiyori','目玉'],['Haru','目玉'],['Mao','目玉'],['Natori','右目']]){
 const dir=S+'/cws/Samples/Resources/'+name+'/';const buf=fs.readFileSync(dir+name+'.moc3');
 const m=C.Model.fromMoc(C.Moc.fromArrayBuffer(buf.buffer.slice(buf.byteOffset,buf.byteOffset+buf.length)));
 const cdi=JSON.parse(fs.readFileSync(dir+name+'.cdi3.json'));const pn={};(cdi.Parts||[]).forEach(p=>pn[p.Id]=p.Name);
 const P=m.parameters,D=m.drawables;const set=(o)=>{for(let i=0;i<P.count;i++)P.values[i]=P.defaultValues[i];for(const k in o)P.values[P.ids.indexOf(k)]=o[k];m.update();
  let sx=0,n=0;for(let d=0;d<D.count;d++){if((pn[m.parts.ids[D.parentPartIndices[d]]]||'')!==part)continue;const v=D.vertexPositions[d];for(let j=0;j<v.length;j+=2){sx+=v[j];n++;}}return sx/n;};
 const b=set({});console.log(name,'EyeBallX=+1 iris dx',(set({ParamEyeBallX:1})-b).toFixed(4),' EyeBallY=+1 iris dy?',(()=>{return 'n/a'})());}},500);
