import * as C from './cfba831b446a-media-core.mjs';
export const ID='licensed-photo-depth',SOURCE_ID='src-athemeroy-style-photoreal',DEFAULT_PALETTE=C.DEFAULT_PALETTE;
export const PARAMETER_SCHEMA=C.schema({image_paths:C.arr(C.str(36),1,2),depth_paths:C.arr(C.str(36),1,2),region_masks:C.arr(C.obj({image:C.str(36),depth:C.str(36),depth_value:C.num(0,1),polygon:C.arr(C.pointSchema,3,8),label:C.str(60),light_gain:C.num(.85,1.15)}),2,5),parallax_bounds:C.obj({x_pixels:C.num(0,30),y_pixels:C.num(0,30),camera_x:C.num(-1,1),camera_y:C.num(-1,1)})});
export const METADATA=C.metadata('Maskeli Fotoğraf Derinliği · özgün edit','depth-ordered-photo-layers','caller-supplied masks and depth scalars; bounded parallax; masked relighting envelope',['depth kicker 30','headline 56','region ledger 30']);
const target=C.rect(80,430,920,1040);
// Simple convex polygon integrity. Collinear boundary vertices stay supported.
// A consistent turn sign alone also admits self-intersecting star polygons.
function maskPolygon(value){
 const polygon=C.list(value,'mask polygon',3,8).map(x=>C.point(x)),epsilon=1e-10;
 const turn=(a,b,c)=>(b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x);
 const onSegment=(a,b,p)=>Math.abs(turn(a,b,p))<=epsilon
  &&p.x>=Math.min(a.x,b.x)-epsilon&&p.x<=Math.max(a.x,b.x)+epsilon
  &&p.y>=Math.min(a.y,b.y)-epsilon&&p.y<=Math.max(a.y,b.y)+epsilon;
 const intersects=(a,b,c,d)=>{
  const abC=turn(a,b,c),abD=turn(a,b,d),cdA=turn(c,d,a),cdB=turn(c,d,b);
  if(onSegment(a,b,c)||onSegment(a,b,d)||onSegment(c,d,a)||onSegment(c,d,b))return true;
  return ((abC>epsilon&&abD< -epsilon)||(abC< -epsilon&&abD>epsilon))
   &&((cdA>epsilon&&cdB< -epsilon)||(cdA< -epsilon&&cdB>epsilon));
 };
 for(let i=0;i<polygon.length;i++)for(let j=i+1;j<polygon.length;j++){
  if(Math.hypot(polygon[i].x-polygon[j].x,polygon[i].y-polygon[j].y)<=epsilon)
   C.fail('mask vertices must be distinct');
  if((i+1)%polygon.length===j||(j+1)%polygon.length===i)continue;
  if(intersects(polygon[i],polygon[(i+1)%polygon.length],polygon[j],polygon[(j+1)%polygon.length]))
   C.fail('nonintersecting mask edges required');
 }
 let sign=0;
 for(let i=0;i<polygon.length;i++){
  const a=polygon[i],b=polygon[(i+1)%polygon.length],c=polygon[(i+2)%polygon.length],cross=(b.x-a.x)*(c.y-b.y)-(b.y-a.y)*(c.x-b.x);
  if(Math.abs(cross)<epsilon)continue;
  if(sign&&Math.sign(cross)!==sign)C.fail('convex nonintersecting mask required');
  sign=Math.sign(cross);
 }
 if(!sign||C.area(polygon)<.003)C.fail('mask area too small');
 return polygon;
}
function validateParameters(spec){const p=C.base(spec,ID,['image_paths','depth_paths','region_masks','parallax_bounds']),r=spec.parameters;p.image_paths=C.refs(r.image_paths,p,'image_paths',1,2);p.depth_paths=C.refs(r.depth_paths,p,'depth_paths',1,2);if(p.image_paths.some(id=>C.asset(p,id).kind!=='image')||p.depth_paths.some(id=>C.asset(p,id).kind!=='depth'))C.fail('image and depth handles need matching kinds');p.region_masks=C.list(r.region_masks,'region masks',2,5).map(q=>{C.keys(q,['image','depth','depth_value','polygon','label','light_gain']);if(!p.image_paths.includes(q.image)||!p.depth_paths.includes(q.depth))C.fail('mask source handles');const poly=maskPolygon(q.polygon);return {image:q.image,depth:q.depth,depth_value:C.number(q.depth_value,'region depth',0,1),polygon:poly,label:C.text(q.label,'region label',60),light_gain:C.number(q.light_gain,'light gain',.85,1.15)};});C.keys(r.parallax_bounds,['x_pixels','y_pixels','camera_x','camera_y']);p.parallax_bounds={x_pixels:C.number(r.parallax_bounds.x_pixels,'x parallax',0,30),y_pixels:C.number(r.parallax_bounds.y_pixels,'y parallax',0,30),camera_x:C.number(r.parallax_bounds.camera_x,'camera x',-1,1),camera_y:C.number(r.parallax_bounds.camera_y,'camera y',-1,1)};for(const q of p.region_masks)C.fitText(`${p.region_masks.indexOf(q)+1}. ${q.label}`,{width:440,maximum:30,minimum:30,maxLines:2});return C.assertTextLayout(p,920,56,4);}
export function sample(spec,seconds){const p=validateParameters(spec),{t,u}=C.clock(p,seconds),b=p.parallax_bounds,q=C.smooth(u),regions=[...p.region_masks].sort((a,b)=>b.depth_value-a.depth_value).map(r=>{const dx=b.x_pixels*b.camera_x*(1-r.depth_value)*q,dy=b.y_pixels*b.camera_y*(1-r.depth_value)*q,mask=r.polygon.map(pt=>({x:target.x+pt.x*target.w+dx,y:target.y+pt.y*target.h+dy}));return {...r,dx,dy,mask,light_opacity:Math.abs(r.light_gain-1)*q};}),layers=[C.layer(p,p.image_paths[0],0,C.FULL,target,{transform:{dx:0,dy:0,scale:1,rotation:0}}),...regions.map(r=>C.layer(p,r.image,0,C.FULL,target,{mask:r.mask,depth_asset_id:r.depth,depth_value:r.depth_value,light_gain:C.lerp(1,r.light_gain,q),transform:{dx:r.dx,dy:r.dy,scale:1,rotation:0}}))];return {time:t,progress:u,regions,layers};}
export function render(spec,seconds,frames){const p=validateParameters(spec),s=sample(spec,seconds),c=p.palette;const lighting=s.regions.map(r=>`<polygon points="${r.mask.map(pt=>`${C.fmt(pt.x)},${C.fmt(pt.y)}`).join(' ')}" fill="${r.light_gain>=1?'#FFFFFF':'#000000'}" opacity="${C.fmt(r.light_opacity)}"/>`).join('');return C.svg(ID,p,C.tx('BÖLGE / DERİNLİK KATMANI',80,106,920,30,c.accent,1)+C.tx(p.title,80,198,920,56,c.ink,4)+C.drawLayers(p,s.layers,'photo',frames)+lighting+s.regions.map((r,i)=>C.tx(`${i+1}. ${r.label}`,80+(i%2)*470,1515+Math.floor(i/2)*76,440,30,c.ink,2)).join('')+C.subtitle(p,s.time,1755,80,920,36)+C.proxyMark(p,1890));}

export function validateSpec(spec){return C.deepFreeze({id:ID,version:'1.0.0',parameters:validateParameters(spec)});}
