const { test, expect } = require('@playwright/test');
const { waitForEditor, loadExample } = require('./helpers');

test.describe('main editor UI', () => {
  test('loads the editor shell and node palette', async ({ page }) => {
    await waitForEditor(page);

    await expect(page.locator('#toolbar')).toBeVisible();
    await expect(page.locator('#flow-name')).toHaveValue('Untitled Flow');
    await expect(page.locator('#node-palette')).toContainText('Nodes');
    await expect(page.locator('#node-palette')).toContainText('LLM Call');
    await expect(page.locator('#node-palette')).toContainText('Vector Store');
  });

  test('lists tracked example flows and imports one into the canvas', async ({ page }) => {
    await waitForEditor(page);

    await page.getByRole('button', { name: 'Examples' }).click();
    const modal = page.locator('#examples-modal');
    await expect(modal).toBeVisible();
    await expect(modal).toContainText('Support Triage Router');
    await expect(modal).toContainText('Research Brief With Review');

    await modal.locator('.flow-item').filter({ hasText: 'Support Triage Router' }).getByRole('button', { name: 'Load' }).click();

    await expect(page.locator('#flow-name')).toHaveValue('Support Triage Router');
    await expect(page.locator('#drawflow .drawflow-node')).toHaveCount(6);
  });

  test('opens settings and agent ide after importing a complex example', async ({ page }) => {
    await waitForEditor(page);
    await loadExample(page, 'Research Brief With Review');

    await page.getByRole('button', { name: 'Settings' }).click();
    await expect(page.locator('#settings-modal')).toBeVisible();
    await expect(page.locator('#setting-default-provider')).toBeVisible();
    await page.locator('#settings-modal .modal-close').click();

    await page.getByRole('button', { name: /Agent IDE/ }).click();
    await expect(page.locator('#agent-ide-modal')).toBeVisible();
    await expect(page.locator('#agent-ide-overview-cards')).toContainText('Persona');
  });
});
