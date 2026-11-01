"""Three bounded MG adaptations, with original layouts, vectors and labels.

Adapted numerical techniques: MG07 area-preserving merge, MG09 detented
rotation/inscribed fit, MG20 palette-grid blitting. Copyright (c) 2026
Vincentwei1021, MIT; full notice in vendor/notices/mg-styles-15-MIT.txt.
No source film, character, bitmap, font, soundtrack or prompt is included.
"""
import copy
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAMILIES = {
    'liquid-merge': {'name': 'Akışkan birleşme', 'kind': 'drops',
        'description': 'Ağırlıklı damlalar tek kütlede birleşir, bekler ve tekrar ayrılır.',
        'palette': {'background': '#F5EDFF', 'ink': '#29153C', 'muted': '#665174', 'accent': '#8B32D6'}},
    'bauhaus-modules': {'name': 'Bauhaus modülleri', 'kind': 'modules',
        'description': 'Geometrik hücreler kademeli dönerek, sığarak ve zıt yönlerde kayarak düzen değiştirir.',
        'palette': {'background': '#F4F0E5', 'ink': '#202521', 'muted': '#615E53', 'accent': '#BC3A28'}},
    'pixel-journey': {'name': 'Piksel yolculuğu', 'kind': 'waypoints',
        'description': 'Özgün piksel motifleri açılır; kareye oturan işaret belirlenen durakları adımlayarak izler.',
        'palette': {'background': '#17273D', 'ink': '#EEF5E4', 'muted': '#B6C5C3', 'accent': '#FFD16A'}},
}
OPTIONAL = {'liquid-merge': {'softness'}, 'bauhaus-modules': {'turns', 'stagger'}, 'pixel-journey': {'step_fps'}}
SHAPES = ('disc', 'bars', 'arch', 'quarters')
MOTIFS = {
    # Original 8x8 bitmaps for this product. Not the source film's sprites.
    'drop': ('00011000','00011000','00111100','01111110','01111110','11111111','01111110','00111100'),
    'leaf': ('00000011','00001111','00011110','00111110','01111100','01111000','11100000','10000000'),
    'sun': ('10011001','01011010','00111100','11111111','11111111','00111100','01011010','10011001'),
    'cube': ('00011000','01111110','11111111','11100111','11100111','01111110','00111100','00011000'),
}


def adaptation(key):
    if key not in FAMILIES:
        from .development_templates import adaptation as original_adaptation
        return original_adaptation(key)
    records = json.loads((ROOT / 'catalog/style-adapters.json').read_text())['adapters']
    return copy.deepcopy(next(r for r in records if r['family_id'] == key)['provenance'])


def implemented_sources(key):
    value = adaptation(key)
    return [value['source_item_id']] if value else []


def validate_parameters(family, p, fields, text, fit_lines, finite, invalid):
    """Strict finite inputs; no source code, paths or media from the caller."""
    kind = FAMILIES[family]['kind']; items = p[kind]
    if not isinstance(items, list) or not 2 <= len(items) <= 4:
        invalid(kind + ': 2–4 öğe gerekli')
    for item in items:
        extra = 'amount' if family == 'liquid-merge' else 'shape' if family == 'bauhaus-modules' else 'motif'
        fields(item, {'label', extra}); item['label'] = text(item['label'], 'etiket', 60)
        fit_lines(item['label'], 370, 36, 28, 3)
        if extra == 'amount': item['amount'] = finite(item['amount'], 'damla ağırlığı', 1, 1000)
        elif extra == 'shape' and (not isinstance(item['shape'], str) or item['shape'] not in SHAPES):
            invalid('geometri disc/bars/arch/quarters olmalı')
        elif extra == 'motif' and (not isinstance(item['motif'], str) or item['motif'] not in MOTIFS):
            invalid('motif drop/leaf/sun/cube olmalı')
    if family == 'liquid-merge': p['softness'] = finite(p.get('softness', 14), 'birleşme yumuşaklığı', 8, 24)
    elif family == 'bauhaus-modules':
        turns = p.get('turns', 1)
        if type(turns) is not int or not 1 <= turns <= 3: invalid('dönüş sayısı 1–3 tam sayı olmalı')
        p['turns'] = turns; p['stagger'] = finite(p.get('stagger', .06), 'modül aralığı', 0, .12)
    else:
        fps = p.get('step_fps', 10)
        if type(fps) is not int or not 6 <= fps <= 15: invalid('piksel adımı 6–15 tam sayı olmalı')
        p['step_fps'] = fps


def smooth(x):
    x = max(0, min(1, x))
    return x*x*(3-2*x)


def sampled_motion(function, duration, tween, fps=30):
    """Finite frame samples; both engines evaluate the same numeric scene data."""
    frames = round(duration*fps)
    def value(t): return {k: round(v, 7) for k, v in function(t).items()}
    values = [value(i/fps) for i in range(frames+1)]
    return [tween(i/fps, 1/fps, values[i], values[i+1], 'none') for i in range(frames)]


def liquid_state(p, seconds):
    """MG07 scene's mergeK and sqrt(sum(r²)) adapted to a bounded SVG union.

    Residual and merged areas conserve sum(r²) throughout. This is graphic
    choreography, not a physical fluid simulation or a numerical data chart.
    """
    u = seconds/p['duration']; weights = [v['amount'] for v in p['drops']]
    radii = [48+40*math.sqrt(v/max(weights)) for v in weights]
    merges = [0] + [smooth((u-(.10+i*.075))/.25)*(1-smooth((u-.72)/.22)) for i in range(1, len(radii))]
    center_radius = math.sqrt(radii[0]**2+sum(r*r*m for r, m in zip(radii[1:], merges[1:])))
    return radii, merges, center_radius


def liquid(p, palette, node, group, label, tween):
    d=p['duration']; ink=palette['ink']; muted=palette['muted']; accent=palette['accent']
    out=[node('defs', {}, [node('filter', {'id':'lm-goo', 'x':'-50%', 'y':'-50%', 'width':'200%', 'height':'200%', 'color-interpolation-filters':'sRGB'}, [
        node('feGaussianBlur', {'in':'SourceGraphic','stdDeviation':p['softness'],'result':'blur'}),
        node('feColorMatrix', {'in':'blur','mode':'matrix','values':'1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 20 -8','result':'union'}),
        node('feComposite', {'in':'SourceGraphic','in2':'union','operator':'atop'})])])]
    positions=[(540,920),(235,740),(845,740),(845,1090)]
    base,_,_=liquid_state(p,0); shapes=[]
    for i,(item,radius) in enumerate(zip(p['drops'],base)):
        x,y=positions[i]
        def state(t, i=i, radius=radius, x=x, y=y):
            _,merges,central=liquid_state(p,t)
            if i==0:return {'scaleX':central/radius,'scaleY':central/radius,'x':0,'y':0}
            m=merges[i]; scale=math.sqrt(max(0,1-m))
            return {'scaleX':scale,'scaleY':scale,'x':(540-x)*m,'y':(920-y)*m}
        shapes.append(group([node('circle',{'cx':0,'cy':0,'r':round(radius,6),'fill':accent,
            'data-liquid-weight':item['amount'],'data-liquid-base-radius':radius})],x=x,y=y,ident=f'lm-drop-{i}',motion=sampled_motion(state,d,tween)))
    out.append(node('g', {'filter':'url(#lm-goo)'}, shapes))
    # Three timed phase words make the causal merge / hold / split explicit.
    for i,(word,start,end) in enumerate([('AYRI',0,.30),('BİRLİKTE',.30,.72),('YENİDEN AYRI',.72,1)]):
        motion=[] if start==0 else [tween(d*start,0,{'opacity':0},{'opacity':1},'none')]
        motion.append(tween(d*end,0,{'opacity':1},{'opacity':0},'none'))
        out.append(label(word,540,575,860,muted,28,28,1,anchor='middle',ident=f'lm-phase-{i}',motion=motion))
    for i,item in enumerate(p['drops']):
        x=105+(i%2)*455;y=1285+(i//2)*145
        out += [node('circle',{'cx':x+9,'cy':y-10,'r':8,'fill':accent}),
                label(item['label'],x+35,y,370,ink,36,28,3)]
    return out


def detent_angle(u, turns):
    """MG09 12 detents per quarter turn; dwell then ease each 7.5° step."""
    x=max(0,min(1,u))*12*turns; k=min(12*turns,math.floor(x+1e-9)); f=x-k
    return 7.5*(k+smooth(max(0,min(1,(f-.35)/.65))))


def inscribed_scale(angle):
    theta=math.radians(angle)
    return 1/(abs(math.cos(theta))+abs(math.sin(theta)))


def bauhaus(p, palette, node, group, label, tween):
    d=p['duration']; ink=palette['ink']; accent=palette['accent']; bg=palette['background']; muted=palette['muted']; out=[]
    colors=[accent,'#D5A521','#244E72',ink]
    for i,item in enumerate(p['modules']):
        x=310+(i%2)*460;y=705+(i//2)*480; c=colors[i]; shape=item['shape']; pieces=[]
        if shape=='disc':
            pieces=[node('circle',{'cx':0,'cy':0,'r':123,'fill':c}),node('path',{'d':'M0 -123A123 123 0 0 1 0 123Z','fill':ink if i!=3 else accent}),node('circle',{'cx':0,'cy':0,'r':23,'fill':bg})]
        elif shape=='bars':
            pieces=[node('rect',{'x':-120,'y':-120+j*64,'width':240,'height':40,'fill':c if j%2==0 else ink}) for j in range(4)]
        elif shape=='arch':
            pieces=[node('path',{'d':'M-123 123V0A123 123 0 0 1 123 0V123H65V0A65 65 0 0 0 -65 0V123Z','fill':c}),node('circle',{'cx':0,'cy':78,'r':27,'fill':ink})]
        else:
            pieces=[node('path',{'d':'M0 0V-123A123 123 0 0 1 123 0Z','fill':c}),node('path',{'d':'M0 0V123A123 123 0 0 1 -123 0Z','fill':ink}),node('rect',{'x':-123,'y':-123,'width':88,'height':88,'fill':'#D5A521'})]
        def state(t,i=i):
            u=t/d; phase=max(0,min(1,(u-.08-i*p['stagger'])/.57)); angle=detent_angle(phase,p['turns'])*(1 if i%2==0 else -1)
            scale=inscribed_scale(angle); slide=(1 if i%2==0 else -1)*36*smooth((u-.72)/.12)*(1-smooth((u-.88)/.10))
            return {'rotation':angle,'scaleX':scale,'scaleY':scale,'x':slide}
        out.append(node('rect',{'x':x-174,'y':y-166,'width':348,'height':332,'fill':'none','stroke':muted,'stroke-width':2}))
        out.append(group(pieces,x,y,ident=f'bm-tile-{i}',motion=sampled_motion(state,d,tween)))
        out.append(label(item['label'],x-185,y+215,370,ink,36,28,3))
    return out


def bitmap(rows, x, y, size, color, node):
    """Palette-mask blit from MG20, expressed as editable SVG pixel rectangles."""
    return [node('rect',{'x':x+col*size,'y':y+row*size,'width':size,'height':size,'fill':color})
            for row,line in enumerate(rows) for col,value in enumerate(line) if value=='1']


def pixel_position(p, seconds):
    points=[(4,5),(22,5),(22,16),(4,16)][:len(p['waypoints'])]
    # The cursor moves only in whole grid cells, on the selected fixed cadence.
    quantized=math.floor(max(0,seconds)*p['step_fps']+1e-8)/p['step_fps']
    u=max(0,min(1,(quantized/p['duration']-.12)/.72)); distance=u*(len(points)-1)
    index=min(len(points)-2,math.floor(distance)); f=distance-index; a=points[index]; b=points[index+1]
    return (round(a[0]+(b[0]-a[0])*f),round(a[1]+(b[1]-a[1])*f))


def pixel(p,palette,node,group,label,tween):
    d=p['duration']; out=[]; ink=palette['ink']; accent=palette['accent']; muted=palette['muted']; cell=28;ox=120;oy=600
    points=[(4,5),(22,5),(22,16),(4,16)][:len(p['waypoints'])]
    for row in range(22):
        for col in range(30):
            if (row+col)%2==0:out.append(node('rect',{'x':ox+col*cell,'y':oy+row*cell,'width':cell,'height':cell,'fill':muted,'opacity':.055,'shape-rendering':'crispEdges'}))
    route='M'+'L'.join(f'{ox+x*cell} {oy+y*cell}' for x,y in points)
    out.append(node('path',{'d':route,'fill':'none','stroke':muted,'stroke-width':8,'stroke-dasharray':'7 21','shape-rendering':'crispEdges'}))
    for i,(item,(x,y)) in enumerate(zip(p['waypoints'],points)):
        start=d*(.02+i*.14)
        pixels=bitmap(MOTIFS[item['motif']],-48,-48,12,accent,node)
        pixels.append(node('rect',{'x':-62,'y':-62,'width':124,'height':124,'fill':'none','stroke':ink,'stroke-width':3}))
        out.append(group(pixels,x=ox+x*cell,y=oy+y*cell,ident=f'pj-motif-{i}',motion=[tween(start,0,{'opacity':0},{'opacity':1},'none')]))
        lx=105+(i%2)*455;ly=1300+(i//2)*145
        out.append(label(str(i+1),lx,ly,30,accent,30,30,1))
        out.append(label(item['label'],lx+35,ly,370,ink,36,28,3))
    moves=[];previous=pixel_position(p,0)
    for frame in range(1,math.ceil(d*p['step_fps'])+1):
        seconds=min(d,frame/p['step_fps']);point=pixel_position(p,seconds)
        if point!=previous:
            moves.append(tween(seconds,0,{'x':(previous[0]-4)*cell,'y':(previous[1]-5)*cell},{'x':(point[0]-4)*cell,'y':(point[1]-5)*cell},'none'))
        previous=point
    cursor=[node('path',{'d':'M-14 -23H14V-14H23V14H14V23H-14V14H-23V-14H-14Z','fill':ink,'stroke':palette['background'],'stroke-width':4,'shape-rendering':'crispEdges'})]
    out.append(group(cursor,x=ox+4*cell,y=oy+5*cell,ident='pj-cursor',motion=moves))
    return out


def compile_nodes(family,p,palette,node,group,label,tween):
    return {'liquid-merge':liquid,'bauhaus-modules':bauhaus,'pixel-journey':pixel}[family](p,palette,node,group,label,tween)
