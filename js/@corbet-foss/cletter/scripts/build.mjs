// Build runnable packages; consumers never need a TypeScript loader.
import { copyFileSync, cpSync, mkdirSync, readFileSync, readdirSync, rmSync } from 'node:fs';
import { spawnSync } from 'node:child_process';

mkdirSync('dist', { recursive: true });
const types = spawnSync('node', ['node_modules/typescript/bin/tsc', '-p', 'tsconfig.build.json'], { stdio: 'inherit' });
if (types.status !== 0) process.exit(types.status ?? 1);
copyFileSync('dist/types/index.d.ts', 'dist/types/index.d.cts');
for (const [file, format, packages] of [
    ['index.js', 'esm', 'external'],
    ['index.cjs', 'cjs', 'external'],
    ['browser.js', 'esm', 'bundle'],
]) {
    const result = await Bun.build({
        entrypoints: ['src/index.ts'],
        target: 'browser', format, packages,
        minify: false,
    });
    if (!result.success) throw new AggregateError(result.logs, `Failed to build ${file}`);
    if (result.outputs.length !== 1) throw new Error(`Unexpected outputs for ${file}`);
    await Bun.write(`dist/${file}`, result.outputs[0]);
}
rmSync('LICENSES', { recursive: true, force: true });
mkdirSync('LICENSES', { recursive: true });
// This directory is generated; replace it so retired license texts cannot ship.
for (const file of readdirSync('../../../LICENSES')) {
    copyFileSync(`../../../LICENSES/${file}`, `LICENSES/${file}`);
}
// The standalone browser module embeds the sibling implementations.
for (const name of ['cgreet', 'cfarewell', 'cink', 'cdate']) {
    cpSync(`node_modules/@corbet-foss/${name}/LICENSES`, `LICENSES/vendor/${name}`, { recursive: true });
}
// Keep the registry page and the GitHub product page in sync.
copyFileSync('../../../README.md', 'README.md');
const pkg = JSON.parse(readFileSync('package.json', 'utf8'));
console.log(`Built ${pkg.name}@${pkg.version}: ESM, CommonJS, declarations, browser`);
