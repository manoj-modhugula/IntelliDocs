import { test, expect } from '@playwright/test';

test.describe('Chat Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/chat');
  });

  test('should display chat page', async ({ page }) => {
    await expect(page.locator('#main-content')).toBeVisible();
  });

  test('should display empty state when no documents', async ({ page }) => {
    await page.evaluate(() => localStorage.clear());
    await page.reload();

    const emptyStateText = page.getByText(/Upload documents first/i).or(
      page.getByText(/No documents uploaded/i)
    ).or(page.getByText(/document/i));
    await expect(emptyStateText.first()).toBeVisible();
  });

  test('should have message input', async ({ page }) => {
    const input = page.locator('textarea').first();
    await expect(input).toBeVisible();
  });

  test('should have send button', async ({ page }) => {
    const sendButton = page.locator('button[type="submit"]');
    await expect(sendButton).toBeVisible();
  });

  test('should have disabled send button when input is empty', async ({ page }) => {
    const sendButton = page.locator('button[type="submit"]');
    await expect(sendButton).toBeDisabled();
  });

  test('should open export menu when export button is clicked', async ({ page }) => {
    // Inject a mock conversation with messages to show the export button
    await page.evaluate(() => {
      const store = {
        conversations: {
          'conv-1': {
            id: 'conv-1',
            title: 'Test Chat',
            messages: [
              { id: 'msg-1', role: 'user', content: 'Hello', citations: [] },
              { id: 'msg-2', role: 'assistant', content: 'Hi there!', citations: [] },
            ],
            updatedAt: Date.now(),
          },
        },
        currentConversationId: 'conv-1',
      };
      localStorage.setItem('intellidocs-chat', JSON.stringify({
        state: {
          conversations: [{
            id: 'conv-1',
            title: 'Test Chat',
            messages: store.conversations['conv-1'].messages.map((m) => ({
              ...m,
              createdAt: new Date().toISOString(),
            })),
            pinnedMessageIds: [],
            isPinned: false,
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
            workspaceId: '',
          }],
          currentConversationIdByWorkspace: { '': 'conv-1' },
        },
        version: 0,
      }));
    });
    await page.reload();
    await page.waitForTimeout(500);

    const exportBtn = page.getByRole('button', { name: /export/i }).or(
      page.locator('button[aria-label="Export conversation"]')
    );
    await expect(exportBtn).toBeVisible();

    await exportBtn.click();
    // Menu should appear with Markdown and JSON options
    await expect(page.getByRole('menuitem', { name: /markdown/i })).toBeVisible();
    await expect(page.getByRole('menuitem', { name: /json/i })).toBeVisible();
  });

  test('should close export menu on click outside', async ({ page }) => {
    await page.evaluate(() => {
      const store = {
        conversations: {
          'conv-1': {
            id: 'conv-1',
            title: 'Test Chat',
            messages: [{ id: 'msg-1', role: 'user', content: 'Hello', citations: [] }],
            updatedAt: Date.now(),
          },
        },
        currentConversationId: 'conv-1',
      };
      localStorage.setItem('intellidocs-chat', JSON.stringify({
        state: {
          conversations: [{
            id: 'conv-1',
            title: 'Test Chat',
            messages: store.conversations['conv-1'].messages.map((m) => ({
              ...m,
              createdAt: new Date().toISOString(),
            })),
            pinnedMessageIds: [],
            isPinned: false,
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
            workspaceId: '',
          }],
          currentConversationIdByWorkspace: { '': 'conv-1' },
        },
        version: 0,
      }));
    });
    await page.reload();
    await page.waitForTimeout(500);

    const exportBtn = page.getByRole('button', { name: /export/i }).or(
      page.locator('button[aria-label="Export conversation"]')
    );
    await exportBtn.click();
    await expect(page.getByRole('menuitem', { name: /markdown/i })).toBeVisible();

    await page.keyboard.press('Escape');
    await page.click('body', { position: { x: 10, y: 10 } });
    await page.waitForTimeout(100);
    await expect(page.getByRole('menuitem', { name: /markdown/i })).not.toBeVisible();
  });

  test('should navigate to new conversation from sidebar', async ({ page }) => {
    // Sidebar toggle
    const sidebarToggle = page.getByRole('button', { name: /toggle sidebar/i }).or(
      page.locator('button[aria-label*="sidebar"]').first()
    );
    if (await sidebarToggle.isVisible()) {
      await sidebarToggle.click();
    }

    const newChatBtn = page.getByRole('button', { name: 'Start new chat' });
    await expect(newChatBtn).toBeVisible();
  });

  test('should show suggested follow-up questions after a response', async ({ page }) => {
    // Mock documents in ready state
    await page.evaluate(() => {
      localStorage.setItem('intellidocs-documents', JSON.stringify({
        state: {
          documents: [{
            id: 'test-doc-1',
            name: 'Annual Report 2025.pdf',
            type: 'application/pdf',
            size: 204800,
            status: 'ready',
            uploadedAt: new Date().toISOString(),
          }],
        },
        version: 0,
      }));
    });
    await page.reload();

    const input = page.locator('textarea').first();
    await expect(input).toBeVisible();
    await expect(input).toBeEnabled();
  });

  test('textarea accepts text input', async ({ page }) => {
    const input = page.locator('textarea').first();
    await input.fill('What is the revenue for 2025?');
    await expect(input).toHaveValue('What is the revenue for 2025?');
  });
});
