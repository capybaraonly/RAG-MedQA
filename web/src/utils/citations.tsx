import { RagMedQATooltip } from '@/components/ui/tooltip';
import type { ChunkRef, Reference } from '@/services/api';

export function renderWithCitations(
  content: string,
  refs?: Reference,
): React.ReactNode {
  if (!refs?.chunks?.length) return content;

  const parts = content.split(/(\[ID:\d+\])/g);
  return (
    <>
      {parts.map((part, i) => {
        const match = part.match(/\[ID:(\d+)\]/);
        if (!match) return <span key={i}>{part}</span>;
        const idx = parseInt(match[1]);
        const chunk: ChunkRef | undefined = refs.chunks[idx];
        if (!chunk) return <span key={i}>{part}</span>;
        return (
          <RagMedQATooltip
            key={i}
            tooltip={
              <div>
                <div className="font-medium text-xs">{chunk.document_name}</div>
                <div className="text-xs mt-1 opacity-80">{chunk.content}</div>
              </div>
            }
          >
            <sup className="cursor-pointer text-blue-500 hover:underline font-medium">
              [{idx + 1}]
            </sup>
          </RagMedQATooltip>
        );
      })}
    </>
  );
}
