'use client';

import { useState, useRef, useCallback, memo, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { Send, X, Plus, Square } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { SkillItem } from '@/lib/api';

interface ChatInputProps {
  input: string;
  setInput: (value: string) => void;
  onSubmit: (value: string) => void;
  onStop?: () => void;
  isLoading: boolean;
  disabled: boolean;
  placeholder?: string;
  chatSkills: { id: string; name: string }[];
  selectedSkill: string | null;
  setSelectedSkill: (skill: string | null) => void;
  onCreateSkill: (name: string, action: string) => Promise<void>;
  creatingSkill: boolean;
  readyDocumentsCount: number;
}

export const ChatInput = memo(function ChatInput({
  input,
  setInput,
  onSubmit,
  onStop,
  isLoading,
  disabled,
  placeholder,
  chatSkills,
  selectedSkill,
  setSelectedSkill,
  onCreateSkill,
  creatingSkill,
  readyDocumentsCount,
}: ChatInputProps) {
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const [skillsDropdownIndex, setSkillsDropdownIndex] = useState(0);
  const [showCreateSkillModal, setShowCreateSkillModal] = useState(false);
  const [newSkillName, setNewSkillName] = useState('');
  const [newSkillAction, setNewSkillAction] = useState('');

  const slashPrefix = input.startsWith('/') ? (input.slice(1).match(/^\w*/)?.[0] ?? '') : '';
  const matchingSkills = chatSkills.filter((s) => s.id.toLowerCase().startsWith(slashPrefix.toLowerCase()));
  const showSkillsDropdown = input.startsWith('/') && readyDocumentsCount > 0;

  useEffect(() => {
    setSkillsDropdownIndex(0);
  }, [slashPrefix, matchingSkills.length]);

    const applySkillFromDropdown = useCallback(
    (skill: { id: string; name: string }) => {
      setSelectedSkill(skill.id);
      setInput(input.replace(/^\/(\w*)\s*/, '').trimStart());
      setSkillsDropdownIndex(0);
      inputRef.current?.focus();
    },
    [setInput, setSelectedSkill, input]
  );

  const openCreateSkillModal = useCallback(() => {
    setNewSkillName(slashPrefix);
    setNewSkillAction('');
    setShowCreateSkillModal(true);
  }, [slashPrefix]);

  const handleCreateSkillSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      const name = newSkillName.trim().toLowerCase().replace(/\s+/g, '_');
      const action = newSkillAction.trim();
      if (!name || !action) return;
      await onCreateSkill(name, action);
      setShowCreateSkillModal(false);
      setNewSkillName('');
      setNewSkillAction('');
      setInput(input.startsWith('/') ? '' : input);
      setSelectedSkill(name);
      setSkillsDropdownIndex(0);
    },
    [newSkillName, newSkillAction, onCreateSkill, setInput, setSelectedSkill, input]
  );

  const skillOptionCount = matchingSkills.length + 1;

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === ' ') {
        const trimmed = input.trim();
        const cmdMatch = trimmed.match(/^\/(\w+)$/i);
        if (cmdMatch) {
          const word = cmdMatch[1].toLowerCase();
          const skill = chatSkills.find((s) => s.id.toLowerCase() === word);
          if (skill) {
            e.preventDefault();
            applySkillFromDropdown(skill);
            return;
          }
        }
      }
      if (showSkillsDropdown && skillOptionCount > 0) {
        if (e.key === 'ArrowDown') {
          e.preventDefault();
          setSkillsDropdownIndex((i) => Math.min(i + 1, skillOptionCount - 1));
          return;
        }
        if (e.key === 'ArrowUp') {
          e.preventDefault();
          setSkillsDropdownIndex((i) => Math.max(0, i - 1));
          return;
        }
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          if (skillsDropdownIndex === matchingSkills.length) {
            openCreateSkillModal();
          } else {
            applySkillFromDropdown(matchingSkills[skillsDropdownIndex]);
          }
          return;
        }
        if (e.key === 'Escape') {
          e.preventDefault();
          setInput(input.startsWith('/') ? '' : input);
          setSkillsDropdownIndex(0);
          return;
        }
      }
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        if (input.trim()) onSubmit(input.trim());
      }
    },
    [
      input,
      chatSkills,
      showSkillsDropdown,
      skillOptionCount,
      skillsDropdownIndex,
      matchingSkills,
      applySkillFromDropdown,
      openCreateSkillModal,
      onSubmit,
      setInput,
    ]
  );

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      const raw = e.target.value;
      setInput(raw);
      const target = e.target;
      target.style.height = 'auto';
      target.style.height = Math.min(target.scrollHeight, 200) + 'px';
    },
    [setInput]
  );

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      if (!input.trim() || isLoading || disabled) return;
      onSubmit(input.trim());
    },
    [input, isLoading, disabled, onSubmit]
  );

  return (
    <>
      <div className="flex-shrink-0 glass p-3 sm:p-4 pb-[calc(1rem+env(safe-area-inset-bottom))]">
        <form onSubmit={handleSubmit} className="max-w-4xl mx-auto">
          {selectedSkill && (
            <div className="flex items-center gap-2 mb-2">
              <span className="chip !py-1 !px-2.5 text-xs" data-active="true">
                {chatSkills.find((s) => s.id === selectedSkill)?.name ?? selectedSkill.replace(/_/g, ' ')}
                <button
                  type="button"
                  onClick={() => setSelectedSkill(null)}
                  className="p-0.5 rounded hover:bg-sky-200/60 dark:hover:bg-sky-800/50 text-sky-600 dark:text-sky-300 hover:text-sky-800 dark:hover:text-sky-100"
                  aria-label="Clear skill"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </span>
            </div>
          )}

          <div className="field flex items-center gap-2 overflow-hidden !p-0">
            <textarea
              ref={inputRef}
              value={input}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              placeholder={placeholder}
              disabled={disabled}
              rows={1}
              aria-label="Ask a question about your documents"
              className={cn(
                'flex-1 min-h-[56px] py-3 px-4 resize-none bg-transparent text-ink',
                'placeholder:text-[var(--field-placeholder)] focus:outline-none',
                'disabled:opacity-50 disabled:cursor-not-allowed'
              )}
              style={{ maxHeight: '200px' }}
            />
            {isLoading ? (
              <button
                type="button"
                onClick={onStop}
                aria-label="Stop generating"
                title="Stop generating"
                className="icon-btn flex-shrink-0 mr-2 self-center"
              >
                <Square className="w-5 h-5" aria-hidden />
              </button>
            ) : (
              <button
                type="submit"
                disabled={!input.trim() || disabled}
                aria-label="Send message"
                title="Send message"
                className={cn(
                  'send-button flex-shrink-0 mr-2 self-center',
                  input.trim() && !disabled ? 'logo-mark !h-10 !w-10' : 'icon-btn opacity-60 cursor-not-allowed'
                )}
              >
                <Send className="w-5 h-5" aria-hidden />
              </button>
            )}
          </div>

          {showSkillsDropdown && (
            <div
              className="mt-2 rounded-xl glass border border-white/20 dark:border-white/10 overflow-hidden max-h-[240px] overflow-y-auto"
              role="listbox"
              aria-label="Available skills"
            >
              {matchingSkills.length > 0 ? (
                matchingSkills.map((skill, idx) => (
                  <button
                    key={skill.id}
                    type="button"
                    role="option"
                    aria-selected={idx === skillsDropdownIndex}
                    id={`skill-option-${skill.id}`}
                    onClick={() => applySkillFromDropdown(skill)}
                    className={cn(
                      'w-full text-left px-4 py-2.5 text-sm transition-colors duration-150',
                      idx === skillsDropdownIndex
                        ? 'glass text-slate-900 dark:text-slate-100 border-l-2 border-white/40 dark:border-white/30'
                        : 'text-slate-600 dark:text-slate-400 hover:bg-black/[0.05] dark:hover:bg-white/[0.08] hover:translate-x-1'
                    )}
                  >
                    <span className="font-medium">/{skill.id}</span>
                    <span className="ml-2 text-slate-500 dark:text-slate-400">{skill.name}</span>
                  </button>
                ))
              ) : (
                <p className="px-4 py-2.5 text-sm text-slate-500 dark:text-slate-400">No matching skill</p>
              )}
              <div className="border-t border-white/10 dark:border-white/5">
                <button
                  type="button"
                  role="option"
                  aria-selected={skillsDropdownIndex === matchingSkills.length}
                  id="skill-option-new"
                  onClick={openCreateSkillModal}
                    className={cn(
                    'w-full text-left px-4 py-2.5 text-sm transition-colors duration-150 flex items-center gap-2',
                    skillsDropdownIndex === matchingSkills.length
                      ? 'glass text-slate-900 dark:text-slate-100 border-l-2 border-white/40 dark:border-white/30'
                      : 'text-slate-600 dark:text-slate-400 hover:bg-black/[0.05] dark:hover:bg-white/[0.08] hover:translate-x-1'
                  )}
                >
                  <Plus className="w-4 h-4 shrink-0" aria-hidden />
                  <span className="font-medium">New skill...</span>
                </button>
              </div>
            </div>
          )}
        </form>
      </div>

      {showCreateSkillModal && typeof document !== 'undefined' && createPortal(
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-slate-900/25 dark:bg-black/50 backdrop-blur-md"
          role="dialog"
          aria-modal="true"
          aria-labelledby="create-skill-title"
          onClick={() => !creatingSkill && setShowCreateSkillModal(false)}
        >
          <div
            className="rounded-xl glass-modal border border-white/20 dark:border-white/10 shadow-xl w-full max-w-md p-5 space-y-4"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 id="create-skill-title" className="text-lg font-semibold text-slate-950 dark:text-white">
              Create new skill
            </h2>
            <form onSubmit={handleCreateSkillSubmit} className="space-y-3">
              <input
                type="text"
                value={newSkillName}
                onChange={(e) => setNewSkillName(e.target.value)}
                placeholder="Name"
                aria-label="Skill name (slash command)"
                className="w-full px-3 py-2 rounded-xl glass-input text-sm text-slate-950 dark:text-white placeholder-slate-700 dark:placeholder-slate-300 focus:outline-none focus:ring-1 focus:ring-slate-400/50 dark:focus:ring-slate-400/40 focus:border-slate-400 dark:focus:border-white/40"
                autoFocus
              />
              <input
                type="text"
                value={newSkillAction}
                onChange={(e) => setNewSkillAction(e.target.value)}
                placeholder="Instruction"
                aria-label="Skill instruction"
                className="w-full px-3 py-2 rounded-xl glass-input text-sm text-slate-950 dark:text-white placeholder-slate-700 dark:placeholder-slate-300 focus:outline-none focus:ring-1 focus:ring-slate-400/50 dark:focus:ring-slate-400/40 focus:border-slate-400 dark:focus:border-white/40"
              />
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => !creatingSkill && setShowCreateSkillModal(false)}
                  className="glass-interactive px-3 py-2 rounded-lg text-sm font-medium glass border border-slate-300/90 dark:border-white/25 text-slate-950 dark:text-white hover:bg-black/[0.07] dark:hover:bg-white/[0.12]"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creatingSkill || !newSkillName.trim() || !newSkillAction.trim()}
                  className="glass-interactive px-3 py-2 rounded-lg text-sm font-semibold glass border border-slate-300/90 dark:border-white/25 text-slate-950 dark:text-white hover:bg-black/[0.07] dark:hover:bg-white/[0.12] disabled:opacity-50"
                >
                  {creatingSkill ? 'Creating...' : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>,
        document.body
      )}
    </>
  );
});
