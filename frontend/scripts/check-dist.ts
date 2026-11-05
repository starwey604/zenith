import { readFile, stat, readdir } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', 'dist');
for (const entry of ['index.html', 'gripper.html']) {
  const index = await readFile(resolve(root, entry), 'utf8');
  for (const path of [...index.matchAll(/(?:src|href)="\/(assets\/[^"?#]+)"/g)].map(m => m[1])) {
    await stat(resolve(root, path));
  }
}
const manifest = JSON.parse(await readFile(resolve(root, 'models/manifest.json'), 'utf8'));
for (const model of manifest.models) {
  const path = resolve(root, model.path); const info = await stat(path);
  if (info.size !== model.bytes) throw new Error(`Wrong asset size: ${model.path}`);
}
const parameters = JSON.parse(await readFile(resolve(root, 'downloads/design-parameters.json'), 'utf8'));
if (parameters.storage.map((p: { capacity: number }) => p.capacity).join(',') !== '10,12') throw new Error('Missing capacity layouts');
await stat(resolve(root, '_headers'));
// Workers Static Assets allows a maximum of 25 MiB per file.
let count = 0;
async function inspect(dir: string) {
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const path = resolve(dir, entry.name);
    if (entry.isDirectory()) await inspect(path);
    else {
      const info = await stat(path); count++;
      if (info.size > 25 * 1024 * 1024) throw new Error(`Asset exceeds Workers 25 MiB limit: ${path}`);
    }
  }
}
await inspect(root);
console.log(`dist verified: ${count} files, ${manifest.models.length} models, 10/12-round layouts.`);
