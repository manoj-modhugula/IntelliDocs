export function exportConversationToMarkdown(
  messages: { role: string; content: string; citations?: { documentName: string; pageNumber?: number }[] }[],
  title: string
): string {
  const lines: string[] = [`# ${title || 'Chat export'}\n`];
  for (const msg of messages) {
    const heading = msg.role === 'user' ? '## User' : '## Assistant';
    lines.push(`${heading}\n\n${msg.content.trim()}\n\n`);
    if (msg.role === 'assistant' && msg.citations && msg.citations.length > 0) {
      lines.push('**Sources:**\n');
      msg.citations.forEach((c, i) => {
        const page = c.pageNumber != null ? `, p.${c.pageNumber}` : '';
        lines.push(`- [${i + 1}] ${c.documentName}${page}\n`);
      });
      lines.push('\n');
    }
  }
  return lines.join('');
}
