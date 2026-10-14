import { api } from './client'
import type { Document, AdminStats } from '../types'

export const documentsApi = {
  adminList: () =>
    api.get<{ items: Document[]; total: number }>('/admin/documents'),

  upload: (form: FormData) =>
    api.postForm<Document>('/admin/documents', form),

  replace: (documentId: string, form: FormData) =>
    api.postForm<Document>(`/admin/documents/${documentId}/replace`, form),

  delete: (documentId: string) =>
    api.delete<{ message: string }>(`/admin/documents/${documentId}`),

  retry: (documentId: string) =>
    api.post<Document>(`/admin/documents/${documentId}/retry`),

  stats: () =>
    api.get<AdminStats>('/admin/stats'),

  fileUrl: (documentId: string) =>
    `/api/documents/${documentId}/file`,
}
