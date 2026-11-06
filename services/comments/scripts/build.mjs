import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const root = fileURLToPath(new URL('..', import.meta.url));
const upstream = fileURLToPath(new URL('../.upstream', import.meta.url));
export const revision = 'b13ef7c018b0cb1bb4b9ac82d98728322ae5e79b'; // Official tag 2.0.17, matches browser SDK.
function run(command, args, cwd = root) {
  const result = spawnSync(command, args, { cwd, stdio: 'inherit', env: { ...process.env, MONGOMS_DISABLE_POSTINSTALL: '1' } });
  if (result.status !== 0) throw new Error(`${command} failed (${result.status}): ${result.error?.message || args.join(' ')}`);
}
if (!existsSync(upstream)) run('git', ['clone', '--depth', '1', '--branch', '2.0.17', 'https://github.com/twikoojs/twikoo.git', upstream]);
const actual = spawnSync('git', ['rev-parse', 'HEAD'], { cwd: upstream, encoding: 'utf8' });
if (actual.status !== 0 || actual.stdout.trim() !== revision) throw new Error('Unexpected upstream revision; use the pinned 2.0.17 checkout.');
run('pnpm', ['--filter', '@twikoojs/cloudflare...', 'install', '--frozen-lockfile'], upstream);
// Upstream source intentionally uses 0.0.0; use its release script to stamp the pinned release version.
const version = JSON.parse(readFileSync(`${upstream}/packages/shared/package.json`, 'utf8')).version;
if (version === '0.0.0') run('node', ['scripts/release-set-version.mjs', '2.0.17'], upstream);
else if (version !== '2.0.17') throw new Error('Unexpected shared package version');
run('pnpm', ['-r', '--filter', '@twikoojs/cloudflare...', 'build'], upstream);
