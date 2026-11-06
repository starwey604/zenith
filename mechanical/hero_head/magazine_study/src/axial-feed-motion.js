// Illustrative sequence. Limit/ball/speed confirmations are assumed milestones;
// this function is neither real control firmware nor a contact simulation.
const smooth=t=>{t=Math.max(0,Math.min(1,t));return t*t*(3-2*t);};
export const feedPhases=[
 ['分度到位并锁止','推头在后限位板之后，出口止弹片常闭。画面假设本格到位反馈已经确认；各格还需要轻弹性保持，避免搬运时球前窜。'],
 ['打开常闭止弹片','仅在分度锁止、摩擦轮就绪后打开。止弹片位于转盘前端，闭合时限制球前窜；保持力与滑片间隙仍需样件验证。'],
 ['沿炮口方向主动推出','电机经丝杆驱动一级，内部同步带带动二级。推头先接触球，再穿过格位和短直导路，连续推到摩擦轮接管位置。'],
 ['摩擦轮接管，确认出球','球心推进至X=−8 mm，已越过理想圆轮的首次接触位置。画面按出球已确认隐藏球；不代表已经仿真了接触和发射。'],
 ['推头退回','分度保持锁止，止弹片保持打开。推头必须完全退到转盘后方，再允许下一个动作。'],
 ['关闭止弹片','画面假设出球和推头回零均已确认，再关闭止弹片。缺反馈时应停机，不能按时间强行进入下一格。'],
 ['允许下一格分度','推头已退净、止弹片已关，才解除分度锁止。示意中下一颗球转到入口，不依赖后弹顶推。']
];
export function feedFrame(progress,c,cfg){
 const d=c.axial_metrics,t=Math.max(0,Math.min(1,progress/100));
 let stroke=0,gate=0,angle=0,phase=0,present=true;
 if(t<.12)angle=-72*(1-smooth(t/.12));
 else if(t<.23){phase=1;gate=smooth((t-.12)/.11);}
 else if(t<.61){phase=2;gate=1;stroke=d.stroke_mm*smooth((t-.23)/.38);}
 else if(t<.70){phase=3;gate=1;stroke=d.stroke_mm;present=t<.67;}
 else if(t<.88){phase=4;gate=1;present=false;stroke=d.stroke_mm*(1-smooth((t-.70)/.18));}
 else if(t<.94){phase=5;present=false;gate=1-smooth((t-.88)/.06);}
 else{phase=6;present=false;angle=72*smooth((t-.94)/.06);}
 return {progress,phase,stroke_mm:stroke,gate_open_fraction:gate,rotor_angle_deg:angle,ball_present:present,
  ball_center_x_mm:Math.max(c.rotor_center_mm[0],d.home_face_x_mm+stroke+cfg.ball_diameter_mm/2),
  pusher_home:stroke<=1e-8,gate_closed:gate<=1e-8,indexing_allowed:stroke<=1e-8&&gate<=1e-8};
}
