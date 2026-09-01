'use client';

import { useEffect } from 'react';

interface UseChatKeyboardOptions {
  onNewChat: () => void;
  onToggleSidebar: () => void;
  onToggleFullFocus: () => void;
  onSwitchPanel: () => void;
  inputRef: React.RefObject<HTMLTextAreaElement | null>;
}

export function useChatKeyboard({
  onNewChat,
  onToggleSidebar,
  onToggleFullFocus,
  onSwitchPanel,
  inputRef,
}: UseChatKeyboardOptions) {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      const inEditable = target.tagName === 'TEXTAREA' || target.tagName === 'INPUT' || target.tagName === 'SELECT';
      const isMetaKey = e.metaKey || e.ctrlKey;

      // Cmd+K - toggle sidebar
      if (isMetaKey && e.key === 'k') {
        e.preventDefault();
        if (e.shiftKey) {
          onToggleFullFocus();
        } else {
          onToggleSidebar();
        }
        return;
      }

      // Cmd+M - switch left panel (chats ↔ documents)
      if (isMetaKey && e.key === 'm') {
        e.preventDefault();
        onSwitchPanel();
        return;
      }

      // Cmd+N - new chat
      if (isMetaKey && e.key === 'n') {
        e.preventDefault();
        onNewChat();
        inputRef.current?.focus();
        return;
      }

      // Escape - close dropdowns/modals, clear skills dropdown selection, return focus to input
      if (e.key === 'Escape') {
        // Close any visible listbox dropdown
        const listbox = document.querySelector('[role="listbox"]:not([hidden])') as HTMLElement | null;
        if (listbox) {
          listbox.blur();
          return;
        }
        // Close any open modals (by pressing Escape outside of inputs)
        const modal = document.querySelector('[role="dialog"]:not([hidden])') as HTMLElement | null;
        if (modal && !inEditable) {
          return; // Let the modal handle its own Escape
        }
        // Return focus to input if not already there
        if (inEditable && document.activeElement !== inputRef.current) {
          return;
        }
        inputRef.current?.focus();
      }

      // Cmd+Shift+C - focus chat input
      if (isMetaKey && e.shiftKey && e.key === 'C') {
        e.preventDefault();
        inputRef.current?.focus();
      }

      // Cmd+/ - show keyboard shortcuts help (prevent browser default)
      if (isMetaKey && e.key === '/') {
        e.preventDefault();
        // Dispatch a custom event that any component can listen to
        window.dispatchEvent(new CustomEvent('intellidocs:show-shortcuts'));
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onNewChat, onToggleSidebar, onToggleFullFocus, onSwitchPanel, inputRef]);
}
