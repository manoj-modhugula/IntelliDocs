import { test, expect } from '@playwright/test';

test.describe('Home page', () => {
  test('renders product heading and primary actions', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/IntelliDocs/);
    await expect(page.locator('#main-content').getByRole('heading', { level: 1 })).toBeVisible();
    await expect(page.locator('#main-content').getByRole('link', { name: /Open chat/i })).toBeVisible();
    await expect(page.locator('#main-content').getByRole('link', { name: /Upload documents/i })).toBeVisible();
  });

  test('navigates to chat', async ({ page }) => {
    await page.goto('/');
    await page.locator('#main-content').getByRole('link', { name: /Open chat/i }).click();
    await expect(page).toHaveURL(/\/chat/);
  });

  test('navigates to documents', async ({ page }) => {
    await page.goto('/');
    await page.locator('#main-content').getByRole('link', { name: /Upload documents/i }).click();
    await expect(page).toHaveURL(/\/documents/);
  });
});
