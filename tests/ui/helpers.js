const path = require('node:path');
const fs = require('node:fs/promises');

const SCREENSHOT_DIR = path.resolve(process.cwd(), 'output', 'ui-snapshots');

async function waitForEditor(page) {
  await page.goto('/');
  await page.waitForLoadState('domcontentloaded');
  await page.locator('#toolbar').waitFor();
  await page.locator('#drawflow').waitFor();
  await page.locator('#node-palette').waitFor();
}

async function loadExample(page, exampleName) {
  await page.getByRole('button', { name: 'Examples' }).click();
  const modal = page.locator('#examples-modal');
  await modal.waitFor();
  await modal.getByRole('button', { name: 'Load' }).first().waitFor();
  await modal.locator('.flow-item').filter({ hasText: exampleName }).getByRole('button', { name: 'Load' }).click();
  await page.locator('#flow-name').waitFor();
}

async function ensureScreenshotDir() {
  await fs.mkdir(SCREENSHOT_DIR, { recursive: true });
}

async function saveShot(page, fileName, locator = null) {
  await ensureScreenshotDir();
  const target = locator || page;
  await target.screenshot({
    path: path.join(SCREENSHOT_DIR, fileName),
    fullPage: !locator
  });
}

module.exports = {
  SCREENSHOT_DIR,
  waitForEditor,
  loadExample,
  saveShot
};
