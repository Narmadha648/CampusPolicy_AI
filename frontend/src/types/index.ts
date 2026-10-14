export type Role = 'student' | 'admin'

export interface User {
  id: string
  email: string
  name: string
  role: Role
}

export interface Citation {
  id: string
  document_title: string
  document_version: number
  page_number: number
  excerpt: string
  similarity_score: number | null
  source_deleted: boolean
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  insufficient_evidence: boolean
  created_at: string
  citations: Citation[]
}

export interface Conversation {
  id: string
  title: string | null
  created_at: string
  updated_at: string
  message_count: number
}

export interface ConversationDetail {
  id: string
  title: string | null
  created_at: string
  updated_at: string
  messages: Message[]
}

export interface DocumentVersion {
  id: string
  version_number: number
  original_filename: string
  file_size_bytes: number
  page_count: number | null
  status: 'pending' | 'processing' | 'ready' | 'failed'
  error_message: string | null
  is_active: boolean
  uploaded_at: string
  processed_at: string | null
}

export interface Document {
  id: string
  title: string
  policy_year: string | null
  description: string | null
  created_at: string
  updated_at: string
  active_version: DocumentVersion | null
  latest_version: DocumentVersion | null
}

export interface AdminStats {
  ready_documents: number
  student_count: number
  total_questions: number
  total_conversations: number
  pending_jobs: number
  failed_jobs: number
  top_topics: Array<{ topic: string; count: number }>
}

export interface AskResponse {
  message_id: string
  answer: string
  citations: Citation[]
  insufficient_evidence: boolean
  conversation_id: string
}
