import { readFile, writeFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { layout } from '../src/layout.ts';
import { packing } from '../src/state.ts';
import { assertResolvedDownload } from './check-lfs.ts';
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const names = ['wheel-left', 'wheel-right', 'm3508-body', 'sm11', 'c620', 'vision-v2'];
const models = [];
for (const name of names) {
  const b = await readFile(resolve(root, 'public/models', `${name}.glb`));
  if (b.readUInt32LE(0) !== 0x46546c67 || b.readUInt32LE(4) !== 2 || b.readUInt32LE(8) !== b.length) throw new Error(`Invalid GLB: ${name}`);
  const jsonLength = b.readUInt32LE(12);
  const gltf = JSON.parse(b.subarray(20, 20 + jsonLength).toString());
  const binaryStart = 20 + jsonLength + 8;
  for (const mesh of gltf.meshes) for (const primitive of mesh.primitives) {
    const positions = gltf.accessors[primitive.attributes.POSITION];
    const indices = gltf.accessors[primitive.indices];
    const view = gltf.bufferViews[indices.bufferView];
    for (let i = 0; i < indices.count; i++) if (b.readUInt32LE(binaryStart + view.byteOffset + i * 4) >= positions.count) throw new Error(`Invalid index: ${name}`);
  }
  models.push({ name, path: `models/${name}.glb`, bytes: b.length, parts: gltf.meshes.length,
    triangles: gltf.accessors.filter((x: { type: string }) => x.type === 'SCALAR').reduce((sum: number, x: { count: number }) => sum + x.count / 3, 0), ...gltf.extras });
}
const downloads = ['c620.step', 'm3508-official.stp', 'sm11-2020.step', 'camera-lbc3-v2.FCStd', 'camera-lbc3-v2.step', 'jiao-long-launcher-reference.FCStd'];
for (const path of downloads) await assertResolvedDownload(resolve(root, 'public/downloads', path), path);
await writeFile(resolve(root, 'public/models/manifest.json'), JSON.stringify({
  units: 'mm', sourceFrame: 'X forward, Y left, Z up', permission: 'User confirmed public display of supplied manufacturer models on 2026-11-05',
  models, notes: ['SM11 original cable route omitted; C620 flexible wires omitted.', 'M3508 displayed without gearbox; wheel/shaft adaptation remains to be designed.', 'Vision V2 contains actual CAD structures and dimensional references.'],
}, null, 2) + '\n');
await writeFile(resolve(root, 'public/downloads/design-parameters.json'), JSON.stringify({
  revision: 'layout-v0.2', units: 'mm', coordinateFrame: 'X forward, Y left, Z up', layout,
  storage: [10, 12].map(capacity => ({ capacity, ...packing(capacity), loadingPort: [-149, 0, 2 * packing(capacity).radius] })),
  pusherStroke: layout.pusherEnd - layout.pusherRest, pitchRange: [-15, 45],
  semantics: { payload: 'No ammunition or magazine on detachable head', camera: 'Camera and LBC3 above SM11 on common rigid frame', motor: 'Jiao Long wheel geometry + M3508 body reference; new hub/mount adaptation unresolved', actuatorModels: 'Layout placeholders, not selected hardware', mass: 'Not measured; no derived uniform-density mass', animation: 'Kinematic illustration, not contact or force simulation', chassis: 'No actual chassis or arm geometry; no stowage/reachability conclusion' },
}, null, 2) + '\n');
console.log(`${models.length} GLB assets checked; manifest and layout parameters prepared.`);
