import { attachReferences, type Session } from '../api';

describe('attachReferences', () => {
  it('returns empty array for session with no messages', () => {
    const session: Session = {
      id: 's1',
      name: 'test',
      dialog_id: 'd1',
      message: [],
      reference: [],
    };
    expect(attachReferences(session)).toEqual([]);
  });

  it('returns empty array when message and reference are undefined', () => {
    const session: Session = {
      id: 's1',
      name: 'test',
      dialog_id: 'd1',
      message: undefined as unknown as Session['message'],
      reference: undefined as unknown as Session['reference'],
    };
    expect(attachReferences(session)).toEqual([]);
  });

  it('filters prologue (first message is assistant)', () => {
    const session: Session = {
      id: 's1',
      name: 'test',
      dialog_id: 'd1',
      message: [
        { role: 'assistant', content: 'Hello, I am a bot', id: 'prologue' },
      ],
      reference: [],
    };
    const result = attachReferences(session);
    expect(result).toHaveLength(0);
  });

  it('attaches reference to assistant message in single Q&A', () => {
    const ref = {
      total: 1,
      chunks: [
        {
          id: 'chunk1',
          content: 'Some knowledge content',
          document_id: 'doc1',
          document_name: 'test.pdf',
          similarity: 0.95,
        },
      ],
      doc_aggs: [{ doc_id: 'doc1', docnm_kwd: 'test.pdf', count: 1 }],
    };
    const session: Session = {
      id: 's1',
      name: 'test',
      dialog_id: 'd1',
      message: [
        { role: 'user', content: 'question', id: 'u1' },
        { role: 'assistant', content: 'answer [ID:0]', id: 'a1' },
      ],
      reference: [ref],
    };
    const result = attachReferences(session);
    expect(result).toHaveLength(2);
    expect(result[1].reference).toEqual(ref);
    // user message should not have reference
    expect(result[0].reference).toBeUndefined();
  });

  it('attaches references to multiple Q&A pairs', () => {
    const ref1 = {
      total: 1,
      chunks: [
        {
          id: 'c1',
          content: 'knowledge 1',
          document_id: 'd1',
          document_name: 'doc1.pdf',
        },
      ],
      doc_aggs: [],
    };
    const ref2 = {
      total: 1,
      chunks: [
        {
          id: 'c2',
          content: 'knowledge 2',
          document_id: 'd2',
          document_name: 'doc2.pdf',
        },
      ],
      doc_aggs: [],
    };
    const session: Session = {
      id: 's1',
      name: 'test',
      dialog_id: 'd1',
      message: [
        { role: 'user', content: 'Q1', id: 'u1' },
        { role: 'assistant', content: 'A1 [ID:0]', id: 'a1' },
        { role: 'user', content: 'Q2', id: 'u2' },
        { role: 'assistant', content: 'A2 [ID:0]', id: 'a2' },
      ],
      reference: [ref1, ref2],
    };
    const result = attachReferences(session);
    expect(result).toHaveLength(4);
    expect(result[1].reference).toEqual(ref1);
    expect(result[3].reference).toEqual(ref2);
    expect(result[0].reference).toBeUndefined();
    expect(result[2].reference).toBeUndefined();
  });

  it('handles more messages than references (graceful)', () => {
    const ref = {
      total: 1,
      chunks: [
        {
          id: 'c1',
          content: 'knowledge',
          document_id: 'd1',
          document_name: 'doc.pdf',
        },
      ],
      doc_aggs: [],
    };
    const session: Session = {
      id: 's1',
      name: 'test',
      dialog_id: 'd1',
      message: [
        { role: 'user', content: 'Q1', id: 'u1' },
        { role: 'assistant', content: 'A1', id: 'a1' },
        { role: 'user', content: 'Q2', id: 'u2' },
        { role: 'assistant', content: 'A2', id: 'a2' },
      ],
      reference: [ref], // only one reference for two answers
    };
    const result = attachReferences(session);
    expect(result).toHaveLength(4);
    expect(result[1].reference).toEqual(ref);
    // second assistant message should have no reference
    expect(result[3].reference).toBeUndefined();
  });

  it('handles session with prologue + Q&A pairs', () => {
    const ref = {
      total: 1,
      chunks: [
        {
          id: 'c1',
          content: 'knowledge',
          document_id: 'd1',
          document_name: 'doc.pdf',
        },
      ],
      doc_aggs: [],
    };
    const session: Session = {
      id: 's1',
      name: 'test',
      dialog_id: 'd1',
      message: [
        { role: 'assistant', content: 'Hello!', id: 'prologue' },
        { role: 'user', content: 'Q1', id: 'u1' },
        { role: 'assistant', content: 'A1 [ID:0]', id: 'a1' },
      ],
      reference: [ref],
    };
    const result = attachReferences(session);
    // prologue filtered out
    expect(result).toHaveLength(2);
    expect(result[1].reference).toEqual(ref);
  });
});
