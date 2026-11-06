export const mountingSchemes = {
  integrated: { title: '一体板 · 推荐', detail: 'R1–R4 接触件直接接入载板，保护器件布在背面。输入端不再焊四根短线；拆侧盖后，触点与保护板作为一个组件更换。' },
  castellated: { title: '邮票口子板 · 对比', detail: '触点载板背面焊一块半孔保护子板，仍然不需要输入短线。多一层 PCB 与焊接高度；可独立改版，但更换子板需要返焊，不能直接拔下。' },
} as const;
export type Mounting = keyof typeof mountingSchemes;
export function isMounting(value: string | null): value is Mounting { return value !== null && Object.hasOwn(mountingSchemes, value); }
export function mountingDiagram(mode: Mounting) {
  const stacked = mode === 'castellated', boardTop = stacked ? 208 : 232, deviceY = boardTop - 39;
  return `<svg xmlns="http://www.w3.org/2000/svg" id="mounting-svg" viewBox="0 0 960 470" role="img" aria-labelledby="mount-title mount-desc">
<title id="mount-title">${mountingSchemes[mode].title}安装剖面</title><desc id="mount-desc">头侧触点盒位于头下侧边。车侧弹针向上接触 R1 至 R4；触点背面直接连接保护电路，输入无短线。绝缘支座承托触点载板；保护后四芯输出线通向 SM11。</desc>
<defs><marker id="mount-force" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10Z" fill="#567d6c"/></marker></defs>
<rect width="960" height="470" fill="white"/>
<text x="28" y="35" class="mount-heading">头侧：接触面朝下，元件朝内</text><text x="28" y="60" class="mount-muted">安装关系示意 · 非尺寸图</text>
<path d="M240 100H640V322H240Z" class="mount-housing"/>
<text x="265" y="122" class="mount-muted">侧盖打开后取出整个组件</text>
<g data-layer="support"><path d="M240 135H265V254H310V280H240Z M640 135H615V254H570V280H640Z" class="mount-support"/>
<path d="M310 265H218V309H28" class="mount-leader"/><text x="28" y="332">绝缘承托＋固定点</text><text x="28" y="355" class="mount-muted">触点压力传给支座</text></g>
<g data-layer="carrier"><rect x="280" y="232" width="320" height="22" class="mount-pcb"/>
${[340,405,470,535].map((x,i)=>`<path d="M${x} 244V270" class="mount-pin"/><rect x="${x-18}" y="265" width="36" height="8" rx="2" class="mount-contact"/><text x="${x}" y="300" text-anchor="middle">R${i+1}</text>`).join('')}</g>
${stacked ? `<g data-layer="daughter"><rect x="310" y="208" width="260" height="20" class="mount-pcb"/><path d="M320 228V232 M560 228V232" class="mount-solder"/><path d="M323 208v20 M557 208v20" class="mount-solder"/><path d="M320 230H200V195H28" class="mount-leader"/><text x="28" y="176">半孔焊接到载板焊盘</text><text x="28" y="218" class="mount-muted">增加板厚与焊接高度</text></g>` : `<path d="M340 244H200V188H28" class="mount-leader"/><text x="28" y="170">触点焊脚 / 板内铜连接</text><text x="28" y="211" class="mount-muted">省去输入四芯短线</text>`}
<g data-layer="protection"><rect x="350" y="${deviceY}" width="70" height="39" rx="3" class="mount-device"/><rect x="440" y="${deviceY}" width="112" height="39" rx="3" class="mount-device"/><text x="385" y="${deviceY+25}" text-anchor="middle" class="mount-device-label">电源保护</text><text x="496" y="${deviceY+25}" text-anchor="middle" class="mount-device-label">TMUX7462F</text></g>
<path d="M554 ${deviceY+16}H690V102H930" class="mount-leader"/><text x="700" y="83">保护器件在接触面背后</text>
<g data-layer="output"><rect x="565" y="${deviceY+13}" width="42" height="26" rx="3" class="mount-connector"/>
${['#8e6145','#d78335','#c54b4b','#c4a42e'].map((color,i)=>`<path d="M607 ${deviceY+18+i*5}H655Q675 ${deviceY+18+i*5} 675 ${deviceY+38+i*5}V${310+i*5}Q675 ${330+i*5} 705 ${330+i*5}H760" fill="none" stroke="${color}" stroke-width="3"/>`).join('')}
<rect x="760" y="307" width="170" height="60" rx="5" class="mount-module"/><text x="845" y="333" text-anchor="middle">去大测速 SM11</text><text x="845" y="355" text-anchor="middle" class="mount-muted">保留原插接方式</text>
<text x="710" y="235">保护后四芯输出</text><text x="710" y="260" class="mount-muted">保留插拔与服务弯空间</text></g>
<g data-layer="car"><rect x="300" y="388" width="280" height="24" rx="4" class="mount-car"/>
${[340,405,470,535].map(x=>`<rect x="${x-8}" y="341" width="16" height="47" rx="4" class="mount-pin-body"/><path d="M${x} 341V319" class="mount-pin"/><circle cx="${x}" cy="319" r="6" class="mount-contact"/>`).join('')}
<text x="440" y="440" text-anchor="middle">车侧弹针与背后线束保留</text></g>
<path d="M230 404V350" class="mount-force" marker-end="url(#mount-force)"/><text x="28" y="408">对接方向</text>
</svg>`;
}
export const mountingLocator = `<svg viewBox="0 0 420 200" role="img" aria-label="头部俯视定位：保护一体板位于头下侧边触点盒，避开中央弹路"><rect x="100" y="25" width="220" height="115" rx="12" fill="#edf3f6" stroke="#9bb3c3"/><path d="M35 82H370" stroke="#a6bac5" stroke-width="24"/><text x="210" y="88" text-anchor="middle" fill="#294e5b">中央弹路 / 发射机构</text><path d="M110 140V155 M265 140V155" stroke="#9bb3c3" stroke-width="6"/><rect x="100" y="153" width="180" height="30" rx="4" fill="#e5eaf0" stroke="#9bb3c3"/><rect x="188" y="153" width="92" height="30" rx="4" fill="#39877c"/><text x="234" y="174" text-anchor="middle" fill="white">裁判保护板</text><text x="27" y="35" fill="#58776c">后方供弹</text><text x="344" y="35" fill="#58776c">炮口</text></svg>`;

export function mountingDimensions() {
  return `<section class="p-dimensions" aria-label="首版触点与半孔尺寸"><h2>首版尺寸：接触面和邮票半孔是两套尺寸</h2><p>以下为本项目打样建议，单位 mm。底座三维沿用 12 mm 裁判触点中心距；一体板不需要邮票半孔。</p>
<div class="p-dimension-columns"><section><h3>车头盲插接触面</h3><svg viewBox="0 0 430 180" role="img" aria-label="四个6乘6毫米接触面，中心距12毫米，弹针头径不大于2毫米"><rect x="20" y="40" width="390" height="105" rx="7" fill="#edf5f1" stroke="#8aa99e"/>${[70,166,262,358].map((x,i)=>`<rect x="${x-24}" y="64" width="48" height="48" rx="3" fill="#d5a049"/><circle cx="${x}" cy="88" r="8" fill="#f5f8fa" stroke="#536f80"/><text x="${x}" y="134" text-anchor="middle">R${i+1}</text>`).join('')}<path d="M70 55V22H166V55" fill="none" stroke="#536f80"/><text x="118" y="16" text-anchor="middle">12</text><text x="215" y="172" text-anchor="middle">金色：6 × 6 接触面 · 圆圈：Ø2 针头包络</text></svg>
<dl><dt>有效接触面</dt><dd>6 × 6 / 每点；四点同尺寸</dd><dt>中心距</dt><dd>12；四点接触面总跨度 42</dd><dt>配对弹针头径</dt><dd>目标 ≤2；不是弹针本体直径</dd><dt>载板厚度</dt><dd>1.6，接触件附近设绝缘承托</dd><dt>电源触点选型目标</dt><dd>R1 / R3 单点额定电流 ≥3 A，再校核启动电流、温升与压降</dd></dl><p>按 Ø2 针头、落座后单轴残余偏移 0.8 估算，单侧接触面几何余量为 (6−2)/2−0.8 = <strong>1.2 mm</strong>；这不含定位、装配和磨损公差，也不把浮动行程当作已达到的精度。</p><p>优先用耐磨镀金接触片；若直接用 PCB 接触面，应与板厂确认接触区硬金工艺。工作压缩量按弹针型号确定，底座动画中的 2 mm 不是选型值。</p></section>
<section><h3>仅邮票口子板方案使用</h3><svg viewBox="0 0 430 180" role="img" aria-label="板边半孔标称孔径0.8毫米，铜焊盘外径1.6毫米，中心距2.54毫米"><defs><clipPath id="half-hole-clip"><rect x="35" y="40" width="360" height="80"/></clipPath></defs><rect x="35" y="40" width="360" height="80" fill="#edf5f1" stroke="#8aa99e"/>${[80,170,260,350].map(x=>`<rect x="${x-28}" y="92" width="56" height="56" fill="#ead8ac"/><g clip-path="url(#half-hole-clip)"><circle cx="${x}" cy="120" r="28" fill="#d5a049"/><circle cx="${x}" cy="120" r="14" fill="white"/></g>`).join('')}<path d="M80 53V20H170V53 M25 120H405" fill="none" stroke="#536f80" stroke-dasharray="4 3"/><text x="125" y="15" text-anchor="middle">2.54</text><text x="215" y="75" text-anchor="middle">子板 · 标称板厚 1.0</text><text x="215" y="172" text-anchor="middle">虚线：板边穿过孔中心 · 浅金：载板焊盘</text></svg>
<dl><dt>半孔标称孔径</dt><dd>Ø0.8，金属化，板边过孔中心</dd><dt>子板铜焊盘外径</dt><dd>Ø1.6；名义铜环宽 0.4</dd><dt>半孔中心距</dt><dd>2.54；相邻铜焊盘名义净距 0.94</dd><dt>载板焊盘起始尺寸</dt><dd>1.6 宽 × 2.4 长，长边垂直子板边；向外露出约 0.8，供焊脚检视</dd><dt>子板 / 载板厚度</dt><dd>1.0 / 1.6；叠高另加焊料与元件</dd></dl><p>半孔采用专用加工，上下铜层与阻焊均开窗。12 V / GND 路径需按孔铜、连接铜皮和焊点校核载流；孔径不能直接换算为额定电流。四个输入通过载板汇接到子板，不按 12 mm 盲插间距排半孔。</p><p><a href="https://jlcpcb.com/help/article/what-is-castellated-holes" target="_blank" rel="noreferrer">板厂半孔加工要求</a> · <a href="https://www.harwin.com/products/S70-332002045R" target="_blank" rel="noreferrer">耐磨接触片形式参考</a>（不指定该商品尺寸作为本方案料号）</p></section></div></section>`;
}
