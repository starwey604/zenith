import { open, stat } from 'node:fs/promises';
export async function assertResolvedDownload(target: string, label: string) {
  const info = await stat(target);
  if (!info.size) throw new Error(`Empty download: ${label}`);
  const file = await open(target, 'r');
  const prefix = Buffer.alloc(160);
  try { await file.read(prefix, 0, prefix.length, 0); } finally { await file.close(); }
  if (prefix.toString('utf8').startsWith('version https://git-lfs.github.com/spec/v1')) {
    throw new Error(`Unfetched Git LFS download: ${label}. Run git lfs pull --include='frontend/public/downloads/*.FCStd' --exclude='' from the repository root.`);
  }
}
