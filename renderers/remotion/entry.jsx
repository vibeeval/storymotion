import React from 'react';
import {AbsoluteFill, Audio, Composition, Sequence, interpolate, registerRoot, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';

import {applyMotion} from '../edit-motion.mjs';
import {sampleMotion} from '../template-motion.mjs';
import {compileStaged} from '../template-registry/registry.mjs';
import {parseSvg} from '../svg-tree.mjs';
import {sampleRig,rigSvg} from '../rig-motion.mjs';

const clamp={extrapolateLeft:'clamp',extrapolateRight:'clamp'};
const ease=t=>t<.5?4*t*t*t:1-Math.pow(-2*t+2,3)/2;

function CreativeVector({vector,ident,editScene,seconds}) {
  if(!editScene)throw Error('Pinned creative edit scene required');
  const svg=applyMotion(vector,ident,editScene.object_motion.concat(editScene.camera_motion),seconds-editScene.start);
  return <div style={{width:1080,height:900}} dangerouslySetInnerHTML={{__html:svg.replaceAll('href="assets/customer-image.png"',`href="${staticFile('customer-image.png')}"`).replace('class="objects"','width="1080" height="900"')}}/>;
}

function Objects({scene,profile,vector,ident,editScene,seconds}) {
  const frame=useCurrentFrame();
  const {fps}=useVideoConfig();
  const p=profile.palette;
  const progress=(delay,duration)=>ease(interpolate(frame/fps,[delay,delay+duration],[0,1],clamp));
  if(vector)return <CreativeVector vector={vector} ident={ident} editScene={editScene} seconds={seconds}/>;
  if(scene.action==='flow') {
    const xs=scene.nodes.map((_,i)=>196+i*688/(scene.nodes.length-1));
    const x=xs[scene.from_node]+(xs[scene.to_node]-xs[scene.from_node])*progress(.2,scene.end-scene.start-.4);
    return <svg viewBox="0 0 1080 900" width="1080" height="900">
      {xs.slice(0,-1).map((x,i)=><path key={'edge'+i} d={`M${x+106} 290H${xs[i+1]-106}`} stroke={p.muted} strokeWidth="5"/>)}
      {scene.nodes.map((label,i)=><g key={i}>
        <rect x={xs[i]-100} y="210" width="200" height="160" rx="12" fill={p.background} stroke={p.ink} strokeWidth="6"/>
        <foreignObject x={xs[i]-90} y="220" width="180" height="140"><div xmlns="http://www.w3.org/1999/xhtml" style={{display:'flex',alignItems:'center',justifyContent:'center',height:'100%',fontSize:32,lineHeight:1.15,textAlign:'center'}}>{label}</div></foreignObject>
      </g>)}
      <path d={`M${xs[0]} 500H${xs.at(-1)}`} stroke={p.muted} strokeWidth="5"/>
      <circle cx={x} cy="500" r="28" fill={p.accent}/>
    </svg>;
  }
  const lidY=scene.action==='reveal'?-220:scene.action==='open'?-220*progress(.2,1.25):0;
  const lockY=scene.action==='unlock'?-120*progress(.3,1.1):-90;
  const ringScale=scene.action==='reveal'?.7+.3*progress(.1,1.3):1;
  return <svg viewBox="0 0 1080 900" width="1080" height="900">
    <g fill="none" stroke={p.ink} strokeWidth="8" strokeLinejoin="round">
      <path d="M220 405H860V715H220Z" fill={p.background}/><path d="M250 742H830" stroke={p.muted} strokeWidth="3"/>
      {profile.format==='serial-2d' && <g transform={`translate(540 485) scale(${ringScale}) translate(-540 -485)`}>
        <ellipse cx="540" cy="485" rx="72" ry="94" stroke={p.accent} strokeWidth="14"/>
        <path d="M500 391L540 354L580 391L540 426Z" fill={p.accent}/>
      </g>}
      <g transform={`translate(0 ${lidY})`}><path d="M205 345H875V422H205Z" fill={p.background}/><path d="M225 366H855" stroke={p.muted} strokeWidth="3"/></g>
      {scene.action==='unlock' && <g transform={`translate(0 ${lockY})`}><rect x="501" y="396" width="78" height="112" rx="12" fill={p.accent}/><path d="M516 393V369A24 24 0 0 1 564 369V393"/></g>}
    </g>
  </svg>;
}

function RigVisual({brief,profile,definition,edit_plan}) {
  const frame=useCurrentFrame();const {fps}=useVideoConfig();
  const seconds=frame/fps,mode=edit_plan.rig_mode;
  let svg=rigSvg(definition,profile.palette,sampleRig(brief.rig,seconds),mode);
  const opening=svg.indexOf('>')+1;svg=svg.slice(0,opening)+'<g id="rig-camera">'+svg.slice(opening,-6)+'</g></svg>';
  if(mode==='serial-courier'){
    const scene=edit_plan.scenes.find(s=>s.start<=seconds&&seconds<s.end)||edit_plan.scenes.at(-1);
    const ops=scene.camera_motion.map(op=>{const next=JSON.parse(JSON.stringify(op));const groups=next.op==='set'?[next.values]:[next.before,next.after];for(const group of groups)if(group.svgOrigin){const [x,y]=group.svgOrigin.split(' ').map(Number);group.svgOrigin=x+' '+(y+550);}return next;});
    svg=applyMotion(svg,'rig',ops,seconds-scene.start);
  }
  return <div style={{position:'absolute',inset:0}} dangerouslySetInnerHTML={{__html:svg}}/>;
}

const templateTags=new Set(['svg','mask','clipPath','g','rect','text','tspan','path','circle','ellipse','line','polyline','polygon','defs','filter','feGaussianBlur','feColorMatrix','feComposite']);
function TemplateGraph({scene,seconds}) {
  const compiled=React.useMemo(()=>scene.module?compileStaged(scene.spec):null,[scene]);
  function element(node,key) {
    if(node.tag==='#text')return node.text;
    if(!templateTags.has(node.tag))throw Error('Unsupported template node');
    const attrs=Object.fromEntries(Object.entries(node.attrs).map(([k,v])=>[k.startsWith('aria-')||k.startsWith('data-')?k:k.replace(/-([a-z])/g,(_,c)=>c.toUpperCase()),v]));
    const raw=React.createElement(node.tag,{...attrs,key},node.text===null?node.children.map(element):node.text);
    if(!node.id)return raw;
    const v=sampleMotion(node.motion,seconds);
    return <g key={key} id={node.id} transform={`translate(${v.x} ${v.y}) rotate(${v.rotation}) scale(${v.scaleX} ${v.scaleY})`} opacity={v.opacity} strokeDashoffset={v.strokeDashoffset}>{raw}</g>;
  }
  if(compiled)return element(parseSvg(compiled.render(seconds)),0);
  return <svg viewBox="0 0 1080 1920" width="1080" height="1920" role="img">{scene.nodes.map(element)}</svg>;
}

function StoryMotion({brief,profile,audio_file,vectors={},edit_plan=null,rig_definition=null,template_scene=null}) {
  const {fps}=useVideoConfig();const frame=useCurrentFrame(),seconds=frame/fps;
  const p=profile.palette;
  if(brief.template_family){
    if(!template_scene||template_scene.family!==brief.template_family.id)throw Error('Pinned template scene required');
    return <AbsoluteFill style={{backgroundColor:p.background,fontFamily:'Schibsted, sans-serif'}}>
      <style>{`@font-face{font-family:Schibsted;src:url('${staticFile('fonts/schibsted-grotesk-latin-ext-wght-normal.woff2')}')} @font-face{font-family:Schibsted;src:url('${staticFile('fonts/schibsted-grotesk-latin-wght-normal.woff2')}');unicode-range:U+000D,U+0020-007E,U+00A0-00AC,U+00AE-00FF,U+0102,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0300-0301,U+0303-0304,U+0308,U+0323,U+2013-2014,U+2018-201A,U+201C-201E,U+2022,U+2026,U+2032-2033,U+2039-203A,U+2044,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215} text{font-family:Schibsted,sans-serif}`}</style>
      <TemplateGraph scene={template_scene} seconds={seconds}/>
      {audio_file&&<Audio src={staticFile(audio_file)} volume={1}/>}
    </AbsoluteFill>;
  }
  const handle=profile.top_brand?{top:86,letterSpacing:5}:{bottom:profile.handle_bottom,letterSpacing:.8};
  return <AbsoluteFill style={{backgroundColor:p.background,color:p.ink,fontFamily:'Schibsted, sans-serif',overflow:'hidden'}}>
    <style>{`@font-face{font-family:Schibsted;src:url('${staticFile('fonts/schibsted-grotesk-latin-ext-wght-normal.woff2')}')} @font-face{font-family:Schibsted;src:url('${staticFile('fonts/schibsted-grotesk-latin-wght-normal.woff2')}');unicode-range:U+000D,U+0020-007E,U+00A0-00AC,U+00AE-00FF,U+0102,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0300-0301,U+0303-0304,U+0308,U+0323,U+2013-2014,U+2018-201A,U+201C-201E,U+2022,U+2026,U+2032-2033,U+2039-203A,U+2044,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215} *{box-sizing:border-box}`}</style>
    {brief.scenes.map((scene,i)=><Sequence key={scene.id} from={Math.ceil(scene.start*fps-1e-8)} durationInFrames={Math.ceil(scene.end*fps-1e-8)-Math.ceil(scene.start*fps-1e-8)}>
      <h1 style={{position:'absolute',left:88,top:240,width:900,margin:0,fontSize:profile.title_size,fontWeight:650,lineHeight:1.08,letterSpacing:-3.7}}>{scene.heading}</h1>
      <div style={{position:'absolute',left:0,top:550,width:1080,height:900}}><Objects scene={scene} profile={profile} vector={vectors['s'+i]} ident={'s'+i} editScene={edit_plan?.scenes[i]} seconds={seconds}/></div>
    </Sequence>)}
    {brief.rig && <RigVisual brief={brief} profile={profile} definition={rig_definition} edit_plan={edit_plan}/>}
    {brief.cues.map((cue,i)=><Sequence key={i} from={Math.ceil(cue.start*fps-1e-8)} durationInFrames={Math.ceil(cue.end*fps-1e-8)-Math.ceil(cue.start*fps-1e-8)}>
      <div style={{position:'absolute',left:86,top:profile.subtitle_top,width:profile.subtitle_width,height:128,display:'flex',alignItems:'center',justifyContent:'center',textAlign:'center',fontSize:profile.subtitle_size,fontWeight:550,lineHeight:1.2,letterSpacing:-.8}}>{cue.text}</div>
    </Sequence>)}
    <div style={{position:'absolute',left:profile.handle_left,...handle,fontSize:profile.handle_size,fontWeight:400,color:p.muted}}>{profile.handle}</div>
    {!audio_file && <div style={{position:'absolute',left:88,top:140,fontSize:23,color:p.ink}}>Sessiz teknik demo</div>}
    {audio_file && <Audio src={staticFile(audio_file)} volume={1}/>}
  </AbsoluteFill>;
}

const Root=()=> <Composition id="StoryMotion" component={StoryMotion} width={1080} height={1920} fps={30} durationInFrames={120}
  calculateMetadata={({props})=>({durationInFrames:Math.round(props.brief.duration*30)})}/>;
registerRoot(Root);
