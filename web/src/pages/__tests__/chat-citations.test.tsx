import { TooltipProvider } from '@/components/ui/tooltip';
import type { Reference } from '@/services/api';
import { renderWithCitations } from '@/utils/citations';
import { render } from '@testing-library/react';

function Wrapper({ children }: { children: React.ReactNode }) {
  return <TooltipProvider>{children}</TooltipProvider>;
}

const makeRef = (
  chunks: {
    id: string;
    content: string;
    document_name: string;
    document_id: string;
  }[],
): Reference => ({
  total: chunks.length,
  chunks: chunks.map((c) => ({ ...c, similarity: 0.9 })),
  doc_aggs: [],
});

describe('renderWithCitations', () => {
  it('returns plain text when no reference provided', () => {
    const { container } = render(
      <Wrapper>{renderWithCitations('Hello [ID:0] world', undefined)}</Wrapper>,
    );
    expect(container.textContent).toBe('Hello [ID:0] world');
  });

  it('returns plain text when reference has empty chunks', () => {
    const ref: Reference = { total: 0, chunks: [], doc_aggs: [] };
    const { container } = render(
      <Wrapper>{renderWithCitations('Hello [ID:0] world', ref)}</Wrapper>,
    );
    expect(container.textContent).toBe('Hello [ID:0] world');
  });

  it('renders [ID:0] as superscript badge with index 1', () => {
    const ref = makeRef([
      {
        id: 'c0',
        content: 'some text',
        document_name: 'doc.pdf',
        document_id: 'd1',
      },
    ]);
    const { container } = render(
      <Wrapper>{renderWithCitations('Answer [ID:0] end', ref)}</Wrapper>,
    );
    // Should have superscript badge [1]
    const sup = container.querySelector('sup');
    expect(sup).not.toBeNull();
    expect(sup!.textContent).toBe('[1]');
  });

  it('renders multiple [ID:N] marks as separate badges', () => {
    const ref = makeRef([
      {
        id: 'c0',
        content: 'text 0',
        document_name: 'doc0.pdf',
        document_id: 'd0',
      },
      {
        id: 'c1',
        content: 'text 1',
        document_name: 'doc1.pdf',
        document_id: 'd1',
      },
      {
        id: 'c2',
        content: 'text 2',
        document_name: 'doc2.pdf',
        document_id: 'd2',
      },
    ]);
    const { container } = render(
      <Wrapper>{renderWithCitations('[ID:0] middle [ID:2] end', ref)}</Wrapper>,
    );
    const sups = container.querySelectorAll('sup');
    expect(sups).toHaveLength(2);
    expect(sups[0].textContent).toBe('[1]');
    expect(sups[1].textContent).toBe('[3]');
  });

  it('keeps [ID:N] as plain text when index out of bounds', () => {
    const ref = makeRef([
      {
        id: 'c0',
        content: 'only one',
        document_name: 'doc.pdf',
        document_id: 'd1',
      },
    ]);
    const { container } = render(
      <Wrapper>
        {renderWithCitations('Valid [ID:0] missing [ID:5]', ref)}
      </Wrapper>,
    );
    const sups = container.querySelectorAll('sup');
    expect(sups).toHaveLength(1);
    expect(sups[0].textContent).toBe('[1]');
    expect(container.textContent).toContain('[ID:5]');
  });

  it('handles text without any [ID:N] markers', () => {
    const ref = makeRef([
      {
        id: 'c0',
        content: 'text',
        document_name: 'doc.pdf',
        document_id: 'd1',
      },
    ]);
    const { container } = render(
      <Wrapper>{renderWithCitations('Plain text no markers', ref)}</Wrapper>,
    );
    expect(container.querySelector('sup')).toBeNull();
    expect(container.textContent).toBe('Plain text no markers');
  });

  it('renders correct badge number (1-indexed)', () => {
    const ref = makeRef([
      { id: 'c0', content: 't0', document_name: 'd0.pdf', document_id: 'd0' },
      { id: 'c1', content: 't1', document_name: 'd1.pdf', document_id: 'd1' },
      { id: 'c2', content: 't2', document_name: 'd2.pdf', document_id: 'd2' },
    ]);
    const { container } = render(
      <Wrapper>{renderWithCitations('[ID:0] [ID:1] [ID:2]', ref)}</Wrapper>,
    );
    const sups = container.querySelectorAll('sup');
    expect(sups).toHaveLength(3);
    expect(sups[0].textContent).toBe('[1]');
    expect(sups[1].textContent).toBe('[2]');
    expect(sups[2].textContent).toBe('[3]');
  });

  it('renders non-consecutive IDs correctly', () => {
    const ref = makeRef([
      { id: 'c0', content: 't0', document_name: 'd0.pdf', document_id: 'd0' },
      { id: 'c1', content: 't1', document_name: 'd1.pdf', document_id: 'd1' },
    ]);
    const { container } = render(
      <Wrapper>{renderWithCitations('Ref [ID:1] and [ID:0]', ref)}</Wrapper>,
    );
    const sups = container.querySelectorAll('sup');
    expect(sups).toHaveLength(2);
    expect(sups[0].textContent).toBe('[2]');
    expect(sups[1].textContent).toBe('[1]');
  });
});
