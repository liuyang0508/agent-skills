"""Build the illustrated light-theme preview from the shared storyboard. Requires Pillow."""
from pathlib import Path
import json, math
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT=Path(__file__).resolve().parent
W,H=1280,720
BLUE='#1768ed'; INK='#172d48'; MUTED='#8594a9'; LINE='#dce7f3'
STORY=json.loads((ROOT/'storyboard.js').read_text().split('=',1)[1].strip().rstrip(';'))
def font(size, kind='body'):
    paths={'body':['/System/Library/Fonts/STHeiti Light.ttc','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'],
           'display':['/System/Library/Fonts/STHeiti Medium.ttc','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'],
           'mono':['/System/Library/Fonts/Menlo.ttc','/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf']}[kind]
    for p in paths:
        if Path(p).exists(): return ImageFont.truetype(p,size)
    raise SystemExit('Provide a local font path before exporting.')
def text(d,xy,value,size=20,color=INK,kind='body'):
    d.text(xy,value,font=font(size,kind),fill=color)
def card(image,box,blue=False):
    shadow=Image.new('RGBA',(W,H),(31,72,116,0))
    sd=ImageDraw.Draw(shadow);x1,y1,x2,y2=box
    sd.rounded_rectangle((x1,y1+15,x2,y2+15),18,fill=(31,72,116,24))
    image.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(15)))
    d=ImageDraw.Draw(image)
    d.rounded_rectangle(box,18,fill=BLUE if blue else 'white',outline=None if blue else LINE,width=1)
    return d
def lines(d,x,y,width,count=4,color='#dfe7f1',progress=1):
    for i in range(count):
        length=width*[1,.72,.86,.58][i%4]*progress
        d.rounded_rectangle((x,y+i*20,x+length,y+i*20+6),3,fill=color)
def base():
    image=Image.new('RGBA',(W,H),'#f8fafc')
    layer=Image.new('RGBA',(W,H),(199,224,255,0))
    d=ImageDraw.Draw(layer);d.ellipse((510,80,1190,650),fill=(199,224,255,115))
    image.alpha_composite(layer.filter(ImageFilter.GaussianBlur(85)))
    return image
def scene(image,index,t):
    drift=round(math.sin(t*math.pi*2)*5)
    x,y=620,185+drift
    d=ImageDraw.Draw(image)
    d.ellipse((560,128,1225,595),outline='#d8e5f5',width=1)
    d.ellipse((697,97,1108,623),outline='#e1eaf6',width=1)
    if index==0:
        d=card(image,(585,y+45,815,y+305));text(d,(611,y+73),'RAW RESULT',13,MUTED,'mono');lines(d,611,y+113,173,6)
        text(d,(835,y+146),'→',38,'#719bda')
        d=card(image,(892,y+10,1195,y+335),True);text(d,(918,y+39),'UNDERSTANDING',13,'#c9deff','mono');text(d,(918,y+82),'先明确目标',31,'white','display')
        for j,title in enumerate(['识别差异','找到依据','完成判断']):text(d,(927,y+146+j*45),'✓  '+title,22,'#eef5ff')
    elif index==1:
        for n,(label,title) in enumerate([('EXPLAIN','讲清结论'),('VERIFY','核验依据')]):
            x=585+n*310;d=card(image,(x,y+15,x+286,y+322));text(d,(x+25,y+44),label,13,BLUE,'mono');text(d,(x+25,y+86),title,32,INK,'display')
            if n==0:
                for j,hh in enumerate([36,61,78,105]):d.rounded_rectangle((x+28+j*52,y+258-hh,x+63+j*52,y+258),5,fill=['#dfeaff','#b5d1ff','#6fa4fa',BLUE][j])
            else:
                for j,word in enumerate(['原始数据','来源引用','适用限制']):text(d,(x+28,y+155+j*38),'✓  '+word,19,'#47698d')
    elif index==2:
        d=card(image,(585,y+36,873,y+309));text(d,(612,y+68),'THE ASSUMPTION',12,MUTED,'mono');text(d,(612,y+111),'有输入，',38,INK,'display');text(d,(612,y+163),'就已成功？',38,INK,'display');text(d,(612,y+242),'输入不能证明结果。',18,MUTED)
        d=card(image,(902,y+4,1196,y+331),True);text(d,(926,y+39),'THE BOUNDARY',12,'#c9deff','mono');text(d,(926,y+95),'有输入 ≠ 已执行',27,'white','display');text(d,(926,y+145),'已调用 ≠ 已成功',27,'white','display');text(d,(926,y+221),'核对实际输出与证据',20,'#e2eeff');text(d,(926,y+277),'明确标注的教学反例',15,'#c9deff')
    elif index==3:
        for n,title in enumerate(['比较两个方案','核验结论依据','改变一个假设','检查薄弱环节']):
            x=590+(n%2)*305;yy=y+30+(n//2)*153;d=card(image,(x,yy,x+277,yy+124));text(d,(x+24,yy+25),['↔','◎','△','↗'][n],31,BLUE);text(d,(x+24,yy+76),title,22,INK)
    elif index==4:
        for n,title in enumerate(['信息输入关系','+ 成功仍需独立验证','+ 来源说明已修订']):
            yy=y+24+n*97;d=card(image,(586,yy,1192,yy+78));text(d,(608,yy+28),'v1' if n==0 else 'v2',16,MUTED if n==0 else BLUE,'mono');text(d,(677,yy+25),title,23,MUTED if n==0 else BLUE)
    else:
        d=card(image,(593,y+22,1132,y+144));text(d,(618,y+49),'我懂输入，但为什么它',25,INK);text(d,(618,y+88),'不能证明成功？',25,INK)
        d=card(image,(677,y+178,1205,y+337),True);text(d,(703,y+208),'相同输入，可能尚未执行，',24,'white');text(d,(703,y+247),'也可能执行失败。',24,'white');text(d,(703,y+292),'要看调用之后的实际结果。',21,'#dcecff')
def build():
    frames=[]
    for index,step in enumerate(STORY):
        for tick in range(16):
            image=base();d=ImageDraw.Draw(image)
            text(d,(63,47),'OUTPUT PRESENTATION',14,BLUE,'mono')
            text(d,(66,149),'把结果，',68,INK,'display');text(d,(66,235),'讲明白。',68,BLUE,'display')
            text(d,(68,355),step['title'],25,INK,'display')
            desc=step['english']
            words=desc.split();rows=[];row=''
            for word in words:
                if len(row+' '+word)>29:rows.append(row);row=word
                else:row=(row+' '+word).strip()
            if row:rows.append(row)
            for j,row in enumerate(rows):text(d,(68,403+j*33),row,20,MUTED)
            text(d,(68,537),f'0{index+1} / 06',13,BLUE,'mono')
            scene(image,index,tick/16)
            d=ImageDraw.Draw(image);d.line((64,640,1216,640),fill=LINE,width=1)
            for j,item in enumerate(STORY):
                xx=64+j*194
                d.rounded_rectangle((xx,662,xx+173,694),16,fill='#e7f0ff'if j==index else '#f8fafc')
                text(d,(xx+15,672),item['label'],11,BLUE if j==index else '#8ea1ba','mono')
            frames.append(image.convert('RGB').resize((960,540),Image.Resampling.LANCZOS).quantize(colors=96,dither=Image.Dither.NONE))
    frames[0].save(ROOT/'demo.gif',save_all=True,append_images=frames[1:],duration=170,loop=0,optimize=True,disposal=2)
    frames[8].convert('RGB').save(ROOT/'cover.png')
    frames[36].convert('RGB').save('/tmp/output-presentation-light-frame.png')
    print('Exported',len(frames),'illustrated frames.')
if __name__=='__main__':build()
