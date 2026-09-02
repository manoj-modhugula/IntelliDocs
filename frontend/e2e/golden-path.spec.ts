import { test, expect } from '@playwright/test';
import path from 'path';

const FIXTURE = path.join(__dirname, 'fixtures', 'acme_refund_policy.pdf');

test('upload PDF, ask, open cited page', async ({ page }) => {
  test.setTimeout(120_000);
  const health = await fetch('http://127.0.0.1:8000/health').catch(() => null);
  test.skip(!health || !health.ok, 'backend is not running on :8000');

  const email = `golden-${Date.now()}@example.com`;
  const password = 'Test123!@#';

  await page.goto('/register');
  await page.getByLabel('Name (optional)').fill('Golden Path');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password', { exact: true }).fill(password);
  await page.getByLabel('Confirm password').fill(password);
  await page.getByRole('button', { name: 'Create account' }).click();
  await expect(page).toHaveURL(/\/chat/, { timeout: 20000 });

  await page.goto('/documents');
  await page.locator('input[type="file"]').first().setInputFiles(FIXTURE);
  await expect(page.getByText('Ready').first()).toBeVisible({ timeout: 90000 });

  await page.goto('/chat');
  const input = page.locator('textarea').first();
  await expect(input).toBeEnabled({ timeout: 15000 });
  await input.fill('How long is the refund window after purchase?');
  await page.getByRole('button', { name: 'Send message' }).click();

  const cited = page.getByRole('button', { name: /passage cited/i }).first();
  await expect(cited).toBeVisible({ timeout: 45000 });
  await cited.click();
  const openPage = page.getByRole('button', { name: /Open page/i }).first();
  await expect(openPage).toBeVisible({ timeout: 10000 });
  await openPage.click();
  const viewer = page.getByRole('dialog');
  await expect(viewer).toBeVisible();
  await expect(viewer.getByText(/acme_refund_policy/i)).toBeVisible();
  await expect(viewer.getByText(/PAGE 1/i)).toBeVisible();
});
