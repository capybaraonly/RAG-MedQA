// Stub: agent-related hooks are not needed in the simplified RAG-MedQA.
// These remain as no-ops for components that still import them.

export const useFetchAgentList = () => ({ data: [] as any[], loading: false });
export const useFetchAgentListByPage = () => ({
  data: { items: [] as any[], total: 0 },
  loading: false,
});
export const useFetchExternalAgentInputs = () => ({
  data: {} as any,
  loading: false,
});
export const useFetchFlowSSE = () => ({
  data: null,
  loading: false,
  sendMessage: async () => {},
});
