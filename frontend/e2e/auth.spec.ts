import { test, expect } from '@playwright/test';

test('register and redirect to chat', async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on('pageerror', (err) => consoleErrors.push(err.message));
  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });

  const ts = Date.now();
  const email = `user-${ts}@example.com`;
  const password = 'Test123!@#';

  await page.goto('/register');

  await page.getByLabel('Name (optional)').fill('Test User');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password', { exact: true }).fill(password);
  await page.getByLabel('Confirm password', { exact: true }).fill(password);

  const requestPromise = page.waitForRequest(
    (req) => req.url().includes('/api/auth/register') && req.method() === 'POST',
    { timeout: 15000 }
  );
  await page.getByRole('button', { name: 'Create account' }).click();

  const registerRequest = await requestPromise.catch(() => null);
  expect(registerRequest, `register request not fired. Console errors: ${consoleErrors.join(' | ')}`).not.toBeNull();

  const registerResponse = await page.waitForResponse(
    (resp) => resp.url().includes('/api/auth/register') && resp.request().method() === 'POST',
    { timeout: 15000 }
  );

  expect(registerResponse.ok(), `register failed with ${registerResponse.status()}`).toBeTruthy();

  await expect(page).toHaveURL(/\/chat/, { timeout: 15000 });
  await expect(page.getByRole('heading', { name: 'Chat' })).toBeVisible();
});
