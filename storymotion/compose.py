from .local_state import private_directory, write_private
from . import __version__
from .account_packs import capability, load_pack, validate_render_profile
"""Small deterministic HyperFrames scene vocabulary; no claim of arbitrary story generation."""
import html
import json
import shutil
from pathlib import Path
from .security import write_json,WorkflowError,file_hash


def esc(text):
    return html.escape(str(text), quote=True)


def creative_objects(profile, suffix, scene, *, with_plan=False):
    """Owned vector geometry and seekable part motion; never model HTML/assets."""
    p=profile['palette'];ink=p['ink'];bg=p['background'];accent=p['accent'];muted=p['muted']
    a=scene['action'];start=scene['start'];length=scene['end']-start;operations=[]
    def set_part(part,values):operations.append({'op':'set','target':part,'values':values})
    def move(part,before,after,delay=.25,duration=None):
        operations.append({'op':'tween','target':part,'before':before,'after':after,'offset':delay,
                           'duration':duration or min(1.6,length-.6),'ease':'cubic-in-out'})
    family=load_pack(profile['id'])['visual_family']
    if family=='approval-conveyor':
        shape=f'''<path d="M100 600H980M100 630H980" stroke="{muted}" stroke-width="5"/>
        <g fill="none" stroke="{muted}" stroke-width="5"><circle cx="150" cy="615" r="35"/><circle cx="930" cy="615" r="35"/></g>
        <path d="M580 550V650M550 650H610" stroke="{ink}" stroke-width="12"/>
        <g id="{suffix}-gate"><path d="M580 550V300" stroke="{accent}" stroke-width="20" stroke-linecap="round"/><circle cx="580" cy="550" r="16" fill="{ink}"/></g>
        <g id="{suffix}-paper"><path d="M130 350H255L295 390V555H130Z" fill="{bg}" stroke="{ink}" stroke-width="7"/><path d="M255 350V390H295M155 425H266M155 460H245M155 495H220" fill="none" stroke="{ink}" stroke-width="6"/>
        <g id="{suffix}-receipt"><circle cx="252" cy="517" r="32" fill="{bg}" stroke="{accent}" stroke-width="6"/><path d="M235 517L247 529L270 502" fill="none" stroke="{accent}" stroke-width="7"/></g></g>
        <path id="{suffix}-reuse" d="M805 280C805 170 360 170 360 310" fill="none" stroke="{muted}" stroke-width="6" stroke-dasharray="12 10"/>
        <circle id="{suffix}-token" cx="360" cy="260" r="18" fill="{accent}"/>'''
        set_part('receipt',{'opacity':0 if a=='request-route' else 1});set_part('reuse',{'opacity':1 if a=='receipt-reuse' else 0});set_part('token',{'opacity':1 if a=='receipt-reuse' else 0})
        if a=='request-route':move('paper',{'x':0},{'x':260})
        elif a=='approval-gate':
            set_part('paper',{'x':260});move('gate',{'rotation':0,'svgOrigin':'580 550'},{'rotation':-85,'svgOrigin':'580 550'},.2,.8)
            move('paper',{'x':260},{'x':620},1.1,min(1.6,length-1.3))
            move('receipt',{'opacity':0},{'opacity':1},length-.5,.3)
        else:
            set_part('paper',{'x':620});set_part('gate',{'rotation':-85,'svgOrigin':'580 550'})
            move('token',{'x':0,'y':0},{'x':445,'y':20})
    elif family=='hinged-box':
        shape=f'''<path d="M235 470H845V710H235Z" fill="{bg}" stroke="{ink}" stroke-width="8"/>
        <path d="M260 740H840" stroke="{muted}" stroke-width="4"/>
        <g id="{suffix}-lid"><path d="M220 408H850V468H220Z" fill="{bg}" stroke="{ink}" stroke-width="8"/><path d="M250 432H810" stroke="{muted}" stroke-width="3"/></g>
        <circle cx="820" cy="450" r="17" fill="{bg}" stroke="{ink}" stroke-width="7"/>
        <g id="{suffix}-latch"><path d="M280 500V448H320V428" fill="none" stroke="{accent}" stroke-width="15" stroke-linecap="round"/><circle cx="280" cy="500" r="12" fill="{ink}"/></g>
        <path id="{suffix}-contact" d="M308 412V390M295 401L280 389M323 400L340 388" stroke="{accent}" stroke-width="4"/>
        <path d="M785 486H812V510" fill="none" stroke="{muted}" stroke-width="4"/>'''
        set_part('contact',{'opacity':0})
        if a=='latch-release':move('latch',{'rotation':0,'svgOrigin':'280 500'},{'rotation':-55,'svgOrigin':'280 500'})
        else:
            set_part('latch',{'rotation':-55,'svgOrigin':'280 500'})
            if a=='lid-rise':move('lid',{'rotation':0,'svgOrigin':'820 450'},{'rotation':28,'svgOrigin':'820 450'})
            else:set_part('lid',{'rotation':28,'svgOrigin':'820 450'})
    elif family=='possibility-branches':
        index=['familiar-moment','inner-sentence','two-explanations','distinguish-question','observe-cue'].index(a)
        shape=f'''<path d="M100 720H975M455 720V825M895 720V825" stroke="{muted}" stroke-width="7"/>
        <g data-character-id="{esc(scene['character_id'])}"><circle cx="240" cy="250" r="60" fill="{bg}" stroke="{ink}" stroke-width="7"/>
        <path d="M225 248H232M260 248H267M236 278Q247 282 257 278" fill="none" stroke="{ink}" stroke-width="4"/>
        <path d="M170 340Q240 308 310 340L340 600H150Z" fill="{accent}" fill-opacity=".2" stroke="{ink}" stroke-width="7"/>
        <path d="M190 598V720M285 598V720M295 390L430 470L530 460" fill="none" stroke="{ink}" stroke-width="9" stroke-linecap="round"/></g>
        <g id="{suffix}-phone"><rect x="550" y="500" width="142" height="210" rx="20" fill="{bg}" stroke="{ink}" stroke-width="7"/><path d="M585 523H657M604 688H638" stroke="{muted}" stroke-width="4"/><path d="M576 555H664V610H601L580 625V610H576Z" fill="none" stroke="{ink}" stroke-width="5"/><circle cx="600" cy="584" r="4" fill="{muted}"/><circle cx="620" cy="584" r="4" fill="{muted}"/></g>
        <g id="{suffix}-thought"><path d="M390 220Q390 145 495 145Q600 145 600 220Q600 285 490 285L405 315L425 274Q390 260 390 220Z" fill="{bg}" stroke="{muted}" stroke-width="5"/><text x="495" y="242" text-anchor="middle" fill="{ink}" font-size="68">?</text></g>
        <g id="{suffix}-possibilities" fill="none" stroke="{muted}" stroke-width="5"><path d="M640 340L765 225M640 340L765 425"/><rect x="770" y="130" width="170" height="130" rx="9"/><path d="M770 168H940M808 118V145M900 118V145M805 195H830M858 195H884M805 225H830"/><circle cx="855" cy="410" r="58"/><path d="M855 371V410L881 425"/><text x="855" y="302" text-anchor="middle" fill="{muted}" stroke="none" font-size="27">Yoğunluk?</text><text x="855" y="505" text-anchor="middle" fill="{muted}" stroke="none" font-size="27">Ritim?</text></g>
        <circle id="{suffix}-clue" cx="620" cy="585" r="83" fill="none" stroke="{accent}" stroke-width="5" stroke-dasharray="7 8"/>'''
        set_part('thought',{'opacity':1 if index==1 else 0});set_part('possibilities',{'opacity':1 if index>=2 else 0});set_part('clue',{'opacity':1 if index==3 else 0})
        if index==0:move('phone',{'x':0,'y':0},{'x':-90,'y':-130})
        elif index<4:set_part('phone',{'x':-90,'y':-130})
        else:move('phone',{'x':-90,'y':-130},{'x':0,'y':0})
        if index==3:set_part('clue',{'x':-90,'y':-130})
    else:
        shape=f'''<path d="M650 100H940V370H650ZM795 100V370M650 235H940" fill="none" stroke="{muted}" stroke-width="4" opacity=".5"/>
        <path d="M420 680H980M480 680V840M925 680V840" stroke="{ink}" stroke-width="8"/>
        <g data-character-id="{esc(scene['character_id'])}"><circle cx="245" cy="235" r="60" fill="{bg}" stroke="{ink}" stroke-width="7"/>
        <path d="M215 213Q245 175 288 213M230 245H235M260 245H265" fill="none" stroke="{ink}" stroke-width="5"/>
        <path d="M180 325L245 300L310 325L340 620H155Z" fill="{ink}" stroke="{ink}" stroke-width="7"/><path d="M245 311V610M224 313L245 350L266 313" fill="none" stroke="{bg}" stroke-width="4"/>
        <path d="M180 620L165 840M300 620L325 840M305 380L440 470L520 500" fill="none" stroke="{ink}" stroke-width="9" stroke-linecap="round"/></g>
        <g id="{suffix}-envelope"><path d="M500 480H786L800 494V660H500Z" fill="{ink}" stroke="{bg}" stroke-width="5"/><path d="M500 480L650 578L786 480M500 660L601 549M800 660L701 548" fill="none" stroke="{bg}" stroke-width="4"/><path d="M786 480V494H800" fill="none" stroke="{accent}" stroke-width="7"/><circle id="{suffix}-nick" cx="790" cy="489" r="32" fill="none" stroke="{accent}" stroke-width="4"/></g>'''
        set_part('nick',{'opacity':0 if a=='envelope-place' else 1})
        if a=='envelope-place':move('envelope',{'x':-90,'y':-150},{'x':0,'y':0})
        elif a=='envelope-inspect':move('envelope',{'x':0,'y':0},{'x':-60,'y':-150})
        else:set_part('envelope',{'x':-60,'y':-150})
    if scene['camera']=='push-in':move('camera',{'scale':1,'svgOrigin':'540 450'},{'scale':1.08,'svgOrigin':'540 450'},.1,length-.2)
    elif scene['camera']=='follow-object':move('camera',{'x':0},{'x':45},.1,length-.2)
    svg=f'<svg class="objects" viewBox="0 0 1080 900" data-visual-family="{esc(family)}" data-object-id="{esc(scene["object_id"])}" aria-label="{esc(scene["information"])}"><g id="{suffix}-camera">{shape}</g></svg>'
    result=(svg,motion_program(suffix,start,operations))
    return (*result,operations) if with_plan else result


def motion_program(suffix,start,operations):
    js=[]
    for op in operations:
        target='#'+suffix+'-'+op['target']
        if op['op']=='set':js.append(f"gsap.set({json.dumps(target)},{json.dumps(op['values'])});")
        else:
            after=dict(op['after'],duration=op['duration'],ease='power2.inOut')
            js.append(f"tl.fromTo({json.dumps(target)},{json.dumps(op['before'])},{json.dumps(after)},{start+op['offset']});")
    return js


def objects(profile, suffix, action,scene=None):
    p = profile['palette']
    if action=='flow':
        nodes=scene['nodes'];xs=[196+i*688/(len(nodes)-1) for i in range(len(nodes))]
        shapes=[]
        for i,(label,x) in enumerate(zip(nodes,xs)):
            shapes.append(f'<rect x="{x-100}" y="210" width="200" height="160" rx="12" fill="{p["background"]}" stroke="{p["ink"]}" stroke-width="6"/><foreignObject x="{x-90}" y="220" width="180" height="140"><div xmlns="http://www.w3.org/1999/xhtml" style="display:flex;align-items:center;justify-content:center;width:100%;height:100%;font-size:32px;line-height:1.15;text-align:center;color:{p["ink"]}">{esc(label)}</div></foreignObject>')
        lines=''.join(f'<path d="M{x+106} 290H{xs[i+1]-106}" stroke="{p["muted"]}" stroke-width="5"/>' for i,x in enumerate(xs[:-1]))
        line=f'<path d="M{xs[0]} 500H{xs[-1]}" fill="none" stroke="{p["muted"]}" stroke-width="5"/>'
        token=f'<circle id="{suffix}-token" cx="0" cy="500" r="28" fill="{p["accent"]}"/>'
        return f'<svg class="objects" viewBox="0 0 1080 900" aria-label="{esc(" → ".join(nodes))}">{lines}{"".join(shapes)}{line}{token}</svg>',False
    ring = profile['format'] == 'serial-2d'
    return f'''<svg class="objects" viewBox="0 0 1080 900" aria-label="Kutu, kilit ve kapak">
      <g fill="none" stroke="{p['ink']}" stroke-width="8" stroke-linejoin="round">
      <path d="M220 405H860V715H220Z" fill="{p['background']}"/>
      <path d="M250 742H830" stroke="{p['muted']}" stroke-width="3"/>
      <g id="{suffix}-ring"><ellipse cx="540" cy="485" rx="72" ry="94" stroke="{p['accent']}" stroke-width="14"/>
      <path d="M500 391L540 354L580 391L540 426Z" fill="{p['accent']}"/></g>
      <g id="{suffix}-lid"><path d="M205 345H875V422H205Z" fill="{p['background']}"/>
      <path d="M225 366H855" stroke="{p['muted']}" stroke-width="3"/></g>
      <g id="{suffix}-lock"><rect x="501" y="396" width="78" height="112" rx="12" fill="{p['accent']}"/>
      <path d="M516 393V369A24 24 0 0 1 564 369V393"/></g></g></svg>''', ring


def build(payload, out, package_root):
    if payload['brief'].get('template_family'):
        from .template_families import build as build_template
        return build_template(payload,out,package_root)
    validate_render_profile(payload['profile'])
    out = Path(out)
    private_directory(out)
    profile, brief = payload['profile'], payload['brief']
    p, d = profile['palette'], brief['duration']
    assets = out / 'assets'
    shutil.copytree(package_root / 'vendor', assets, dirs_exist_ok=True)
    rig_markup=''
    if brief.get('rig'):
        from .rig_assets import stage_rig_assets
        from .rig_render import hf_markup
        stage_rig_assets(payload['edit_plan']['rig_assets'],out,package_root)
        write_json(out/'rig.json',brief['rig'])
        rig_markup=hf_markup(brief['rig'],p)
        opening=rig_markup.index('>')+1
        rig_markup=rig_markup[:opening]+'<g id="rig-camera">'+rig_markup[opening:-6]+'</g></svg>'
        rig_markup=f'<div class="clip" data-start="0" data-duration="{d}" data-track-index="4">{rig_markup}</div>'
    if brief.get('scene_plan'):write_json(out/'manual-plan.json',brief['scene_plan'])
    if brief.get('raster'):
        from .raster_revision import pinned_path
        from .raster_io import validate_normalized
        a=brief['raster']['asset'];source=Path(payload['raster_source']);validate_normalized(source,a['sha256'],a['width'],a['height'])
        target=pinned_path(out,'assets/customer-image.png');shutil.copyfile(source,target)
        write_json(out/'raster.json',brief['raster'])
    from .edit_plan import verify_staged_assets
    verify_staged_assets(payload,out)
    scenes, js = [], []
    for i, scene in enumerate(brief['scenes']):
        ident = 's' + str(i)
        if brief.get('creative'):
            compiled=payload['edit_plan']['scenes'][i]
            svg=compiled['vector'];js.extend(motion_program(ident,scene['start'],compiled['object_motion']+compiled['camera_motion']));ring=False
            if brief.get('rig') and capability(brief['brand'], 'rig_mode')=='serial-courier':
                from .rig_revision import rig_camera_program
                js.append(rig_camera_program(compiled))
        else:svg, ring = objects(profile, ident, scene['action'],scene)
        scenes.append(f'''<section id="{ident}" class="clip scene" data-start="{scene['start']}" data-duration="{scene['end']-scene['start']}" data-track-index="1">
          <h1>{esc(scene['heading'])}</h1>{svg}</section>''')
        start = scene['start']
        action = scene['action']
        if brief.get('creative'):continue
        if action=='flow':
            nodes=scene['nodes'];xs=[196+n*688/(len(nodes)-1) for n in range(len(nodes))]
            js.append(f"tl.fromTo('#{ident}-token',{{x:{xs[scene['from_node']]}}},{{x:{xs[scene['to_node']]},duration:{scene['end']-start-.4},ease:'power2.inOut'}},{start+.2});")
            continue
        js.append(f"gsap.set('#{ident}-ring',{{opacity:{1 if ring else 0}}});")
        if action in {'open', 'reveal'}:
            js.append(f"gsap.set('#{ident}-lock',{{y:-90,opacity:0}});")
        if action == 'unlock':
            js.append(f"tl.fromTo('#{ident}-lock',{{y:0}},{{y:-120,duration:1.1,ease:'power2.inOut'}},{start+.3});")
        elif action == 'open':
            js.append(f"tl.fromTo('#{ident}-lid',{{y:0}},{{y:-220,duration:1.25,ease:'power2.inOut'}},{start+.2});")
        else:
            js.append(f"gsap.set('#{ident}-lid',{{y:-220}});tl.fromTo('#{ident}-ring',{{scale:.7,transformOrigin:'540px 485px'}},{{scale:1,duration:1.3,ease:'power2.out'}},{start+.1});")
    captions = ''.join(f'''<div id="cue{i}" class="clip cue" data-start="{c['start']}" data-duration="{c['end']-c['start']}" data-track-index="2"><span>{esc(c['text'])}</span></div>''' for i,c in enumerate(brief['cues']))
    audio = ''
    if brief.get('rig'):
        from .rig_render import hf_program
        js.append(hf_program(brief['rig']))
    if brief.get('audio'):
        source = Path(payload['audio_source'])
        target = assets / ('narration' + source.suffix.lower())
        shutil.copy2(source, target)
        audio = f'<audio id="narration" class="clip" src="assets/{target.name}" data-start="0" data-duration="{payload["audio_duration"]}" data-track-index="3" data-volume="1"></audio>'
    brand_css = 'top:86px;letter-spacing:5px' if profile['top_brand'] else f"bottom:{profile['handle_bottom']}px;letter-spacing:.8px"
    demo = '<div class="demo">Sessiz teknik demo</div>' if not audio else ''
    markup = f'''<!doctype html><html lang="{esc(brief.get('language','tr'))}"><head><meta charset="utf-8"><title>{esc(brief['title'])}</title>
      <script src="assets/gsap.min.js"></script><style>
      @font-face{{font-family:Schibsted;src:url('assets/fonts/schibsted-grotesk-latin-ext-wght-normal.woff2')}}
      @font-face{{font-family:Schibsted;src:url('assets/fonts/schibsted-grotesk-latin-wght-normal.woff2');unicode-range:U+000D,U+0020-007E,U+00A0-00AC,U+00AE-00FF,U+0102,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0300-0301,U+0303-0304,U+0308,U+0323,U+2013-2014,U+2018-201A,U+201C-201E,U+2022,U+2026,U+2032-2033,U+2039-203A,U+2044,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215}}
      *{{box-sizing:border-box}}html,body{{margin:0;width:100%;height:100%;overflow:hidden;background:{p['background']};font-family:Schibsted,sans-serif;color:{p['ink']}}}
      #root{{position:relative;width:100%;height:100%;overflow:hidden}}.scene,.clip{{position:absolute;inset:0;overflow:hidden}}.scene-inner{{position:absolute;inset:0}}
      h1{{position:absolute;left:88px;top:240px;width:900px;margin:0;font-size:{profile['title_size']}px;font-weight:650;line-height:1.08;letter-spacing:-3.7px}}
      .objects{{position:absolute;left:0;top:550px;width:1080px;height:900px}}
      .cue{{left:86px;top:{profile['subtitle_top']}px;width:{profile['subtitle_width']}px;height:128px;display:flex;align-items:center;justify-content:center;text-align:center;font-size:{profile['subtitle_size']}px;font-weight:550;line-height:1.2;letter-spacing:-.8px}}
      .cue span{{white-space:pre-line}}.handle{{position:absolute;left:{profile['handle_left']}px;{brand_css};font-size:{profile['handle_size']}px;font-weight:400;color:{p['muted']};opacity:1;min-width:1px;min-height:1em}}
      .demo{{position:absolute;left:88px;top:140px;font-size:23px;color:{p['ink']}}}
      </style></head><body><div id="root" data-composition-id="root" data-width="1080" data-height="1920" data-duration="{d}" data-fps="30">
      {''.join(scenes)}{rig_markup}{captions}{audio}<div class="handle">{esc(profile['handle'])}</div>{demo}</div><script>
      const tl=gsap.timeline({{paused:true}});{''.join(js)}window.__timelines['root']=tl;
      </script></body></html>'''
    write_private(out / 'index.html',markup)
    write_json(out/'hyperframes.json', {'$schema':'https://hyperframes.heygen.com/schema/hyperframes.json','paths':{'assets':'assets','blocks':'compositions'}})
    write_json(out/'index.motion.json', {'duration':d, 'assertions':[{'kind':'appearsBy','selector':'.handle','bySec':.1}]})
    write_json(out/'timeline.json', {'alignment':brief['alignment'], 'duration':d,'playback_rate':1,'scenes':brief['scenes'],'cues':brief['cues']})
    cover = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1080 1920"><rect width="1080" height="1920" fill="{p['background']}"/><foreignObject x="88" y="280" width="900" height="500"><div xmlns="http://www.w3.org/1999/xhtml" style="font-family:Schibsted,sans-serif;color:{p['ink']};font-size:86px;font-weight:650;line-height:1.1">{esc(brief['title'])}</div></foreignObject><path d="M88 830H720" stroke="{p['accent']}" stroke-width="14"/><path d="M250 1050H830V1350H250ZM235 1020H845V1080H235Z" fill="none" stroke="{p['ink']}" stroke-width="9"/><text x="88" y="1748" font-family="sans-serif" fill="{p['muted']}" font-size="27">{esc(profile['handle'])}</text></svg>'''
    if brief.get('creative'):
        # The same authored subject appears on the cover; no generic box substitute.
        if brief.get('scene_plan'):
            from .scene_plan import compile_scene
            subject,_=compile_scene(brief['scenes'][0],brief['scene_plan']['scenes'][0],profile,'cover',brief)
        elif brief.get('raster'):
            from .raster_view import compile_view
            subject,_=compile_view(brief['scenes'][0],brief['raster']['views'][0],brief['raster']['asset'],profile,'cover')
        else:subject,_=creative_objects(profile,'cover',brief['scenes'][0])
        subject=subject.replace('class="objects"','x="0" y="760" width="1080" height="900"')
        cover=f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1080 1920"><rect width="1080" height="1920" fill="{p['background']}"/><foreignObject x="88" y="280" width="900" height="500"><div xmlns="http://www.w3.org/1999/xhtml" style="font-family:Schibsted,sans-serif;color:{p['ink']};font-size:86px;font-weight:650;line-height:1.1">{esc(brief['title'])}</div></foreignObject>{subject}<text x="88" y="1748" font-family="sans-serif" fill="{p['muted']}" font-size="27">{esc(profile['handle'])}</text></svg>'''
    write_private(out/'cover.svg',cover)
    write_private(out/'cover.html',markup.split('<body>')[0].replace('<title>', '<title>Kapak — ').replace('</head>','<style>body>svg{width:100vw;height:100vh;display:block}</style></head>')+'<body>'+cover+'</body></html>')
    write_private(out/'caption.txt',brief['caption']+'\n')
    def stamp(t):
        ms=round(t*1000); return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'
    write_private(out/'subtitles.srt','\n\n'.join(f'{i+1}\n{stamp(c["start"])} --> {stamp(c["end"])}\n{c["text"]}' for i,c in enumerate(brief['cues']))+'\n')
    write_private(out/'BRIEF.md','# '+brief['title']+'\n\n'+brief['brief']+'\n\n'+brief['script']+f'\n\nGenerated by StoryMotion {__version__} (local deterministic templates, no model call).\n')
    if brief.get('production_notes'):
        with (out/'BRIEF.md').open('a') as f:f.write('\nPlanning notes (not automatic visual changes):\n'+json.dumps(brief['production_notes'],ensure_ascii=False,indent=2)+'\n')
    write_json(out/'profile.json',profile)
    return (['rig.json'] if brief.get('rig') else [])+(['manual-plan.json'] if brief.get('scene_plan') else [])+(['raster.json'] if brief.get('raster') else [])+['index.html','hyperframes.json','index.motion.json','timeline.json','cover.svg','cover.html','caption.txt','subtitles.srt','BRIEF.md','profile.json']+[x.relative_to(out).as_posix() for x in sorted(assets.rglob('*')) if x.is_file()]
