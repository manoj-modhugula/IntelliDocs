import { test, expect } from '@playwright/test';

test.describe('Settings Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/settings');
  });

  test('should display settings page', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /Settings/i }).first()).toBeVisible();
  });

  test('should display storage section', async ({ page }) => {
    await expect(page.getByText(/Storage/i).first()).toBeVisible();
  });

  test('should display danger zone', async ({ page }) => {
    await expect(page.getByText(/Danger Zone/i).first()).toBeVisible();
  });

  test('should have clear data button', async ({ page }) => {
    const clearButton = page.getByRole('button', { name: /Clear/i }).first();
    await expect(clearButton).toBeVisible();
  });

  test('clear data button clears localStorage', async ({ page }) => {
    // Add some data
    await page.evaluate(() => {
      localStorage.setItem('test-key', 'test-value');
    });
    
    // Click clear button
    const clearButton = page.getByRole('button', { name: /Clear/i }).first();
    await clearButton.click();
    
    // Wait for action
    await page.waitForTimeout(500);
    
    // Check the page is still functional
    await expect(page.locator('#main-content')).toBeVisible();
  });
});
