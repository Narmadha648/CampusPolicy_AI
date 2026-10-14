import { api } from './client'
import type { AskResponse, Conversation, ConversationDetail } from '../types'

export const conversationsApi = {
  list: () =>
    api.get<{ items: Conversation[]; total: number }>('/conversations'),

  create: () =>
    api.post<Conversation>('/conversations'),

  get: (id: string) =>
    api.get<ConversationDetail>(`/conversations/${id}`),

  delete: (id: string) =>
    api.delete<{ message: string }>(`/conversations/${id}`),

  ask: (conversationId: string, question: string) =>
    api.post<AskResponse>(`/conversations/${conversationId}/messages`, { question }),
}
