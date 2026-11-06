export type Candidate = 'parallel' | 'angular';
export type Task = 'head' | 'ore' | 'store';
export const candidates = {
  parallel: { title: '平行双指', subtitle: '优先 · 直线导向与同步丝杆', description: '两指沿横向平移，指面方向不变。首版用左右旋丝杆同步驱动；短连杆可在后续轻量化时替换。', tradeoff: '释放路径直接，承力槽容易对齐；代价是横向导向宽度与重量。' },
  angular: { title: '齿轮对开', subtitle: '备选 · YUBI / RM 路线', description: '单电机经齿轮同步带动两指绕轴转动。图中采用相同接触区，便于看清圆弧开合造成的区别。', tradeoff: '传动紧凑；接触面随开合转动。当前按夹头闭合位对齐，夹矿时的接触垫需另做角度补偿。' },
};
export const tasks: Record<Task, { title: string; labels: string[]; notes: string[] }> = {
  head: { title: '夹头 → 落座', labels: ['张开对准', '闭合捕获', '提起转运', '底座承重', '松爪退出'], notes: ['头在桌面静置；夹爪从上方接近被动抓取座。', '金色承力肩进入两指槽内；下托唇承重，上限位与防转面约束姿态。', '重量经抓取座、托唇与指根传到腕部；不依赖软垫摩擦吊住头。', '车侧底座承重并完成独立锁紧，夹爪才允许释放。', '两指横向张开离开承力肩，再抬腕退出；抓取座留在头上。'] },
  ore: { title: '资源岛取矿', labels: ['轴向接近', '软垫夹紧', '沿轴拔出', '脱离支柱', '保持携带'], notes: ['从能量单元轴向接近，爪指夹其中段；此处仅显示单工位。', '青绿色软垫贴合中段；下托唇位于圆柱下方，不参与夹矿。', '沿能量单元轴线拔出，规则给出的额外磁吸阻力最高 10 N。', '内孔离开支柱后再改变姿态；相邻五个工位的完整避让待总装检查。', '维持夹紧。装配旋转的 0.3 N·m 回正力矩还需纳入摩擦力矩校核。'] },
  store: { title: '存矿 → 退爪', labels: ['携矿对准', '下降入托', '托座承重', '张开释放', '退爪完成'], notes: ['托座两侧给手指留缺口，不做包住夹持区的深筒。', '能量单元两端落在托座上，中段夹持区保持开放。', '托座先承担重量，夹爪再松开。', '从两侧缺口张开，不通过摩擦拖拽能量单元。', '向上退出；再次取矿使用相反顺序，同一副手指不更换。'] },
};
export const geometry = { openGap: 112, oreGap: 65, headGap: 80, neckWidth: 64, shoulderWidth: 86, shoulderThickness: 12, lowerLipReach: 8, wristToContact: 110 };
export interface Pose { gap: number; tool: [number, number, number]; object: [number, number, number]; captured: boolean }
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
// Piecewise keyframes in mm. These are illustrative tool translations, not arm IK.
export function poseAt(task: Task, progress: number): Pose {
  const clamp = Math.max(0, Math.min(4, progress));
  const i = Math.min(3, Math.floor(clamp)); const t = clamp - i;
  const head = [
    [112, -130, 60, 0, -130, 0, 0], [80, -130, 0, 0, -130, 0, 0],
    [80, 0, 100, 0, 0, 100, 0], [80, 130, 0, 0, 130, 0, 0], [112, 130, 100, 0, 130, 0, 0],
  ];
  const ore = [
    [112, 0, 0, 95, 0, 0, 0], [65, 0, 0, 0, 0, 0, 0],
    [65, 0, 0, 60, 0, 0, 60], [65, 0, 0, 120, 0, 0, 120], [65, 0, 35, 120, 0, 35, 120],
  ];
  const store = [
    [65, 0, 85, 0, 0, 85, 0], [65, 0, 25, 0, 0, 25, 0],
    [65, 0, 0, 0, 0, 0, 0], [112, 0, 0, 0, 0, 0, 0], [112, 0, 100, 0, 0, 0, 0],
  ];
  const frames = task === 'head' ? head : task === 'ore' ? ore : store;
  // Close only after approaching; release before retreating.
  const a = frames[i], b = frames[i + 1];
  let gt = t, mt = t;
  if ((task === 'head' || task === 'ore') && i === 0) { mt = Math.min(1, t * 2); gt = Math.max(0, t * 2 - 1); }
  if (task === 'head' && i === 3) { gt = Math.min(1, t * 2); mt = Math.max(0, t * 2 - 1); }
  return { gap: lerp(a[0], b[0], gt), tool: [1, 2, 3].map(j => lerp(a[j], b[j], mt)) as Pose['tool'], object: [4, 5, 6].map(j => lerp(a[j], b[j], t)) as Pose['object'], captured: task === 'head' ? clamp >= 1 && clamp <= 3 : task === 'ore' ? clamp >= 1 : clamp <= 2 };
}
export function budget(mass: number, offsetMm: number, friction: number) {
  const acceleration = 3, factor = 2, gravity = 9.81;
  const force = factor * mass * (gravity + acceleration);
  return { force, perJaw: force / (2 * friction), moment: force * offsetMm / 1000, payload: mass + .45, orePerJaw: factor * (.45 * (gravity + acceleration) + 10) / (2 * friction) };
}
