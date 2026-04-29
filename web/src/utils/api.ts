const webAPI = `/v1`;
const restAPIv1 = `/api/v1`;

export { restAPIv1, webAPI };

export default {
  // user
  login: `${webAPI}/user/login`,
  logout: `${webAPI}/user/logout`,
  register: `${webAPI}/user/register`,
  setting: `${webAPI}/user/setting`,
  user_info: `${webAPI}/user/info`,
  tenant_info: `${webAPI}/user/tenant_info`,
  set_tenant_info: `${webAPI}/user/set_tenant_info`,
  login_channels: `${webAPI}/user/login/channels`,
  login_channel: (channel: string) => `${webAPI}/user/login/${channel}`,

  // llm model
  factories_list: `${webAPI}/llm/factories`,
  llm_list: `${webAPI}/llm/list`,
  my_llm: `${webAPI}/llm/my_llms`,
  set_api_key: `${webAPI}/llm/set_api_key`,
  add_llm: `${webAPI}/llm/add_llm`,
  delete_llm: `${webAPI}/llm/delete_llm`,
  enable_llm: `${webAPI}/llm/enable_llm`,
  deleteFactory: `${webAPI}/llm/delete_factory`,

  // knowledge base (read-only: list + detail for chat settings KB picker)
  kb_list: `${restAPIv1}/datasets`,
  get_kb_detail: `${webAPI}/kb/detail`,
  getMeta: `${webAPI}/kb/get_meta`,
  getKnowledgeBasicInfo: `${webAPI}/kb/basic_info`,
  listTag: (knowledgeId: string) => `${webAPI}/kb/${knowledgeId}/tags`,

  // chat
  createChat: `${restAPIv1}/chats`,
  listChats: `${restAPIv1}/chats`,
  getChat: (chatId: string) => `${restAPIv1}/chats/${chatId}`,
  updateChat: (chatId: string) => `${restAPIv1}/chats/${chatId}`,
  patchChat: (chatId: string) => `${restAPIv1}/chats/${chatId}`,
  deleteChat: (chatId: string) => `${restAPIv1}/chats/${chatId}`,
  bulkDeleteChats: `${restAPIv1}/chats`,
  createSession: (chatId: string) => `${restAPIv1}/chats/${chatId}/sessions`,
  listSessions: (chatId: string) => `${restAPIv1}/chats/${chatId}/sessions`,
  getSession: (chatId: string, sessionId: string) =>
    `${restAPIv1}/chats/${chatId}/sessions/${sessionId}`,
  updateSession: (chatId: string, sessionId: string) =>
    `${restAPIv1}/chats/${chatId}/sessions/${sessionId}`,
  removeSessions: (chatId: string) => `${restAPIv1}/chats/${chatId}/sessions`,
  deleteMessage: (chatId: string, sessionId: string, msgId: string) =>
    `${restAPIv1}/chats/${chatId}/sessions/${sessionId}/messages/${msgId}`,
  thumbup: (chatId: string, sessionId: string, msgId: string) =>
    `${restAPIv1}/chats/${chatId}/sessions/${sessionId}/messages/${msgId}/feedback`,
  completionUrl: (chatId: string, sessionId: string) =>
    `${restAPIv1}/chats/${chatId}/sessions/${sessionId}/completions`,
  chatsTts: `${restAPIv1}/chats/tts`,
  ask: `${restAPIv1}/chats/ask`,
  chatsMindmap: `${restAPIv1}/chats/mindmap`,
  chatsRelatedQuestions: `${restAPIv1}/chats/related_questions`,

  // next chat
  fetchExternalChatInfo: (id: string) => `${restAPIv1}/chatbots/${id}/info`,

  // system
  getSystemVersion: `${restAPIv1}/system/version`,
  getSystemConfig: `${webAPI}/system/config`,
};
