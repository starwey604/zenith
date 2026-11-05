import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { assertResolvedDownload } from '../scripts/check-lfs.ts';

test('构建拒绝Git LFS指针和空下载件，并接受已拉取的文件', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'zenith-lfs-'));
  const file = join(dir, 'reference.FCStd');
  try {
    await writeFile(file, 'version https://git-lfs.github.com/spec/v1\n');
    await assert.rejects(assertResolvedDownload(file, 'reference.FCStd'), /Unfetched Git LFS download/);
    await writeFile(file, '');
    await assert.rejects(assertResolvedDownload(file, 'reference.FCStd'), /Empty download/);
    await writeFile(file, Buffer.from([0x50, 0x4b, 0x03, 0x04, 0x01]));
    await assert.doesNotReject(assertResolvedDownload(file, 'reference.FCStd'));
  } finally { await rm(dir, { recursive: true, force: true }); }
});
