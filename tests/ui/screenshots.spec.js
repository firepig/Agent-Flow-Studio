const { test } = require('@playwright/test');
const { waitForEditor, loadExample, saveShot } = require('./helpers');

test.describe('main editor screenshots', () => {
  test('capture core editor states', async ({ page }) => {
    await waitForEditor(page);
    await saveShot(page, '01-editor-empty.png');

    await page.getByRole('button', { name: 'Examples' }).click();
    await page.locator('#examples-modal').waitFor();
    await saveShot(page, '02-examples-modal.png');
    await page.locator('#examples-modal .modal-close').click();

    await loadExample(page, 'Research Brief With Review');
    await saveShot(page, '03-complex-example-loaded.png');

    await page.getByRole('button', { name: 'Settings' }).click();
    await page.locator('#settings-modal').waitFor();
    await saveShot(page, '04-settings-modal.png', page.locator('#settings-modal .modal-content'));
    await page.locator('#settings-modal .modal-close').click();

    await page.getByRole('button', { name: /Agent IDE/ }).click();
    await page.locator('#agent-ide-modal').waitFor();
    await saveShot(page, '05-agent-ide-overview.png', page.locator('#agent-ide-modal .modal-content'));
    await page.locator('#agent-ide-modal .modal-close').click();

    await page.getByRole('button', { name: 'Prompts' }).click();
    await page.locator('#prompt-library-modal').waitFor();
    await saveShot(page, '06-prompt-library.png', page.locator('#prompt-library-modal .modal-content'));
  });
});
