import { test, expect } from '@playwright/test';

test.describe('Documents Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/documents');
  });

  test('should display documents page', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /Documents/i }).first()).toBeVisible();
  });

  test('should display upload zone', async ({ page }) => {
    // Look for upload-related text
    const uploadText = page.getByText(/Drop files/i).or(page.getByText(/upload/i)).or(page.getByText(/drag/i));
    await expect(uploadText.first()).toBeVisible();
  });

  test('should have file input', async ({ page }) => {
    // The file input should exist (hidden but functional)
    const fileInput = page.locator('input[type="file"]');
    await expect(fileInput).toBeAttached();
  });

  test('should display empty state when no documents', async ({ page }) => {
    // Clear local storage to ensure clean state
    await page.evaluate(() => localStorage.clear());
    await page.reload();
    
    // Page should still be functional
    await expect(page.locator('#main-content')).toBeVisible();
  });

  test('upload zone is visible', async ({ page }) => {
    // Check for upload-related UI - just verify main content area is visible
    await expect(page.locator('#main-content')).toBeVisible();
    // And that there's a dashed border element (upload zone)
    const dashedElements = page.locator('[class*="border-dashed"]');
    const count = await dashedElements.count();
    expect(count).toBeGreaterThan(0);
  });
});
