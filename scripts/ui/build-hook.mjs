import { spawnSync } from 'node:child_process';

function run(label, command, args) {
  console.log(`\n[ui-build-hook] ${label}`);
  const result = spawnSync(command, args, {
    stdio: 'inherit',
    shell: process.platform === 'win32'
  });
  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
}

run('Running Playwright UI tests', 'npx', ['playwright', 'test', 'tests/ui/editor.spec.js']);
run('Capturing Playwright UI screenshots', 'npx', ['playwright', 'test', 'tests/ui/screenshots.spec.js']);
