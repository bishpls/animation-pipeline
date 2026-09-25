# Region specs: each region = list of clauses. clause: ids=[drawable ids] or parts=[exact part chain] / pre=[part-chain prefix],
# optional box=(umin,umax,vmin,vmax) and absu=(min,max) in face-normalised coords (u=(x-face_cx)/faceW, v=(y-chin_y)/faceH, y up)
INF=99
R={}
R['Hiyori']=dict(face='ArtMesh51', regions={
 'face':[dict(ids=['ArtMesh51'])],
 'eyes':[dict(parts=['目','目>目玉'])], 'brows':[dict(parts=['まゆ毛'])], 'mouth':[dict(parts=['口'])], 'nose':[dict(parts=['鼻'])],
 'front_hair':[dict(parts=['前髪'])], 'side_hair':[dict(pre=['横髪'])], 'back_hair':[dict(parts=['後ろ髪'])], 'hair_tails':[dict(pre=['後ろ髪>'])],
 'ears':[dict(parts=['耳'])],
 'neck':[dict(ids=['ArtMesh67'])],
 'collar':[dict(ids=['ArtMesh96','ArtMesh97','ArtMesh98'])],
 'neckwear':[dict(ids=['ArtMesh93','ArtMesh94','ArtMesh95'])],
 'shoulders':[dict(ids=['ArtMesh99'],absu=(0.4,INF),box=(-INF,INF,-0.6,-0.1))],
 'upper_arms':[dict(ids=['ArtMesh68','ArtMesh69','ArtMesh72','ArtMesh75'])],
 'chest':[dict(ids=['ArtMesh99'],absu=(0,0.45),box=(-INF,INF,-1.0,-0.4))],
 'waist':[dict(ids=['ArtMesh99'],box=(-INF,INF,-1.8,-1.3))],
 'skirt_hem':[dict(ids=['ArtMesh100'])],
 'legs':[dict(ids=['ArtMesh101','ArtMesh102','ArtMesh103','ArtMesh104','ArtMesh105','ArtMesh106'])],
})
R['Haru']=dict(face='D_PSD_30', regions={
 'face':[dict(ids=['D_PSD_30'])],
 'eyes':[dict(parts=['目','目玉'])], 'brows':[dict(parts=['まゆ毛'])], 'mouth':[dict(parts=['口'])], 'nose':[dict(parts=['鼻'])],
 'front_hair':[dict(parts=['前髪'])], 'side_hair':[dict(parts=['横髪'])], 'back_hair':[dict(parts=['後ろ髪'])],
 'ears':[dict(parts=['耳'])],
 'neck':[dict(ids=['D_PSD_07'],box=(-INF,INF,-0.3,INF))],
 'collar':[dict(ids=['D_PSD_16'],box=(-INF,INF,-0.5,INF)),dict(ids=['D_PSD_15'],box=(-INF,INF,-0.6,INF))],
 'neckwear':[dict(ids=['D_PSD_05','D_PSD_06','D_PSD_24','D_PSD_25','D_PSD_26','D_PSD_27'])],
 'shoulders':[dict(ids=['D_PSD_14'],absu=(0.45,INF),box=(-INF,INF,-0.55,INF))],
 'upper_arms':[dict(ids=['D_PSD_09','D_PSD_12'])],
 'chest':[dict(ids=['D_PSD_14'],absu=(0,0.6),box=(-INF,INF,-1.1,-0.4))],
 'waist':[dict(ids=['D_PSD_14'],box=(-INF,INF,-1.6,-1.2))],
 'skirt_hem':[dict(ids=['D_PSD_02'])],
 'legs':[dict(ids=['D_PSD_00','D_PSD_01'])],
})
R['Mao']=dict(face='ArtMesh278', regions={
 'face':[dict(ids=['ArtMesh278'])],
 'eyes':[dict(parts=['目','目>目玉'])], 'brows':[dict(parts=['眉毛'])], 'mouth':[dict(parts=['口'])], 'nose':[dict(parts=['鼻'])],
 'front_hair':[dict(parts=['前髪'])], 'side_hair':[dict(parts=['横髪'])], 'back_hair':[dict(parts=['後ろ髪'])],
 'ears':[dict(parts=['耳'])], 'hat':[dict(parts=['帽子'])],
 'neck':[dict(ids=['ArtMesh285'])],
 'collar':[dict(ids=['ArtMesh118','ArtMesh134','ArtMesh137'])],
 'neckwear':[dict(ids=['ArtMesh284','ArtMesh283','ArtMesh282','ArtMesh124','ArtMesh125'])],
 'shoulders':[dict(ids=['ArtMesh119','ArtMesh201'],absu=(0.75,INF),box=(-INF,INF,-0.9,-0.2))],
 'upper_arms':[dict(ids=['ArtMesh180','ArtMesh205'])],
 'chest':[dict(ids=['ArtMesh135'],absu=(0,0.45),box=(-INF,INF,-1.2,-0.4))],
 'waist':[dict(ids=['ArtMesh135'],box=(-INF,INF,-2.3,-1.8))],
 'skirt_hem':[dict(ids=['ArtMesh121','ArtMesh122'],box=(-INF,INF,-INF,-2.4))],
 'legs':[dict(ids=['ArtMesh145','ArtMesh199','ArtMesh146','ArtMesh147','ArtMesh144','ArtMesh197'])],
})
R['Natori']=dict(face='ArtMesh73', regions={
 'face':[dict(ids=['ArtMesh73'])],
 'eyes':[dict(parts=['頭>右目','頭>左目'])], 'brows':[dict(parts=['頭>まゆ毛'])], 'mouth':[dict(parts=['頭>口'])], 'nose':[dict(parts=['頭>鼻'])],
 'front_hair':[dict(parts=['前髪'])], 'back_hair':[dict(parts=['後ろ髪'])],
 'ears':[dict(ids=['ArtMesh74','ArtMesh75'])], 'glasses':[dict(parts=['メガネ'])],
 'neck':[dict(ids=['ArtMesh87'])],
 'collar':[dict(ids=['ArtMesh88','ArtMesh76'])],
 'neckwear':[dict(ids=['ArtMesh85'])],
 'shoulders':[dict(ids=['ArtMesh79','ArtMesh80'],absu=(0.75,INF),box=(-INF,INF,-0.8,-0.2))],
 'upper_arms':[dict(ids=['ArtMesh113','ArtMesh105'])],
 'chest':[dict(ids=['ArtMesh79','ArtMesh80','ArtMesh86','ArtMesh84'],absu=(0,0.6),box=(-INF,INF,-1.5,-0.6))],
 'waist':[dict(ids=['ArtMesh84','ArtMesh79','ArtMesh80'],box=(-INF,INF,-2.7,-2.2))],
 'skirt_hem':[dict(ids=['ArtMesh81','ArtMesh82'],box=(-INF,INF,-INF,-3.5)),dict(ids=['ArtMesh101'],box=(-INF,INF,-INF,-4.5))],
 'legs':[dict(ids=['ArtMesh98','ArtMesh99'])],
})
HEAD=['face','eyes','brows','mouth','nose','front_hair','side_hair','back_hair','ears']
BODY=['neck','collar','neckwear','shoulders','upper_arms','chest','waist','skirt_hem','legs']
