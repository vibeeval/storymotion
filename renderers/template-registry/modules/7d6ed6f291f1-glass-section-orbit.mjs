import{base,result,number,choice,pair,metadata,context,lerp,rect,circle,line,txt,page,fmt,DEFAULT,fail}from'./09764466d2b7-common.mjs';
export const ID='glass-section-orbit',SOURCE_ID='source-lemo-style-glass-product',DEFAULT_PALETTE=DEFAULT;
export const METADATA=metadata('Saydam kabuk kesiti','shell_section','technical-cutaway','bounded shell orbit / clipped wall section / one Snell interface at a marked cap normal','technical heading / large cutaway / measured ray notes');
export const PARAMETER_SCHEMA={shell_geometry:{enum:['cylinder','capsule']},outer_radius:[100,190],height:[320,520],wall_thickness:[8,28],light_angles:[-70,70],section_depth:[.2,.8],orbit_degrees:[10,65],ior:[1.1,1.6]};
function numericLabels(p){return txt('Duvar '+p.wall_thickness+' birim',90,1430,900,35,p.palette.ink,1)+txt('Kırılma indisi '+p.ior,90,1490,900,35,p.palette.ink,1);}
export function validateSpec(spec){const p=base(spec,ID,['shell_geometry','outer_radius','height','wall_thickness','light_angles','section_depth'],['orbit_degrees','ior']),r=spec.parameters;p.shell_geometry=choice(r.shell_geometry,'shell_geometry',['cylinder','capsule']);for(const[k,a,b,d]of[['outer_radius',100,190],['height',320,520],['wall_thickness',8,28],['section_depth',.2,.8],['orbit_degrees',10,65,32],['ior',1.1,1.6,1.4]])p[k]=number(Object.hasOwn(r,k)?r[k]:d,k,a,b);p.light_angles=pair(r.light_angles,'light_angles',-70,70);if(Math.abs(p.light_angles[1]-p.light_angles[0])<5)fail('light sweep must span five degrees');if(p.wall_thickness>=p.outer_radius*.3)fail('wall must retain hollow center');numericLabels(p);return result(ID,p);}
export function capRay({cx,top,outer,inner,incident,ior}){
 const refracted=Math.asin(Math.sin(incident)/ior),dx=Math.sin(refracted),dy=Math.cos(refracted),entry={x:cx,y:top-outer.ry};
 // First intersection of the transmitted ray with the actual drawn inner cap.
 const A=(dx/inner.rx)**2+(dy/inner.ry)**2,B=-2*outer.ry*dy/inner.ry**2,C=(outer.ry/inner.ry)**2-1,discriminant=B*B-4*A*C;
 if(discriminant<=0)fail('cap ray does not intersect inner boundary');
 const distance=(-B-Math.sqrt(discriminant))/(2*A);
 if(!(distance>0&&Number.isFinite(distance)))fail('invalid cap wall segment');
 return {entry,inside:{x:entry.x+dx*distance,y:entry.y+dy*distance},
  start:{x:entry.x-Math.sin(incident)*145,y:entry.y-Math.cos(incident)*145},
  inward_normal:{x:0,y:1},inside_distance:distance,surface:'outer-cap-ellipse',termination:'first-inner-cap-intersection',refracted};
}
export function sample(spec,seconds){
 const{p,t,u,hold}=context(validateSpec(spec),seconds),orbit=lerp(-p.orbit_degrees/2,p.orbit_degrees/2,u),incident=lerp(...p.light_angles,u)*Math.PI/180,
  flatten=.24+.16*Math.abs(Math.sin(orbit*Math.PI/180)),outer={rx:p.outer_radius,ry:p.outer_radius*flatten},inner={rx:p.outer_radius-p.wall_thickness,ry:(p.outer_radius-p.wall_thickness)*flatten},
  cx=420,top=760,bottom=top+p.height,cutX=cx-p.outer_radius+2*p.outer_radius*p.section_depth,ray=capRay({cx,top,outer,inner,incident,ior:p.ior});
 return{seconds:t,progress:u,hold,orbit,incident,refracted:ray.refracted,outer,inner,wallThickness:p.wall_thickness,top,bottom,cx,cutX,sectionWidth:cx+p.outer_radius-cutX,ray};
}
const ellipse=(x,y,rx,ry,fill,stroke,sw=3,opacity=1)=>`<ellipse cx="${fmt(x)}" cy="${fmt(y)}" rx="${fmt(rx)}" ry="${fmt(ry)}" fill="${fill}" stroke="${stroke}" stroke-width="${fmt(sw)}" fill-opacity="${fmt(opacity)}"/>`;
export function render(spec,seconds){const n=validateSpec(spec),p=n.parameters,s=sample(n,seconds),c=p.palette,rx=s.outer.rx,ry=s.outer.ry,curve=p.shell_geometry==='capsule'?rx:12;let shell=rect(s.cx-rx,s.top,rx*2,p.height,c.accent,curve,c.ink,3).replace('fill="'+c.accent+'"','fill="'+c.accent+'" fill-opacity="0.14"')+ellipse(s.cx,s.top,rx,ry,c.background,c.ink,3,.8)+ellipse(s.cx,s.bottom,rx,ry,'none',c.ink);let cut=rect(s.cx-s.inner.rx,s.top+p.wall_thickness,s.inner.rx*2,p.height-2*p.wall_thickness,c.background,curve,c.accent,3)+ellipse(s.cx,s.top,s.inner.rx,s.inner.ry,c.background,c.accent,3)+line(s.cutX,s.top-ry,s.cutX,s.bottom+ry,c.accent,5);const body=`<defs><clipPath id="shell-section">${rect(s.cutX,s.top-ry-5,s.sectionWidth+5,p.height+2*ry+10,'white')}</clipPath></defs>${shell}<g clip-path="url(#shell-section)">${cut}</g>`+`<line data-ray-normal="true" x1="${fmt(s.ray.entry.x)}" y1="${fmt(s.ray.entry.y-40)}" x2="${fmt(s.ray.entry.x)}" y2="${fmt(s.ray.entry.y+40)}" stroke="${c.muted}" stroke-width="2" stroke-dasharray="5 5"/>`+line(s.ray.start.x,s.ray.start.y,s.ray.entry.x,s.ray.entry.y,c.muted,5)+line(s.ray.entry.x,s.ray.entry.y,s.ray.inside.x,s.ray.inside.y,c.accent,7)+circle(s.ray.entry.x,s.ray.entry.y,8,c.ink)+numericLabels(p)+txt('Tek kapak arayüzü; ışın iç sınırda durur. Malzeme simülasyonu değil.',90,550,900,32,c.muted,2);return page(ID,p,s.seconds,body,{layout:'technical'});}
