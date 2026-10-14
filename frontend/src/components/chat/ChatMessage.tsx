import { GraduationCap, User } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import CitationCard from './CitationCard'
import type { Message } from '../../types'
import clsx from 'clsx'

interface Props {
  message: Message
}

export default function ChatMessage({ message }: Props) {
  const isUser = message.role === 'user'

  return (
    <div
      className={clsx(
        'flex gap-3',
        isUser ? 'flex-row-reverse' : 'flex-row'
      )}
    >
      {/* Avatar */}
      <div
        className={clsx(
          'w-8 h-8 rounded-full flex items-center justify-center shrink-0 mt-0.5',
          isUser ? 'bg-brand-600' : 'bg-gray-200'
        )}
        aria-hidden="true"
      >
        {isUser ? (
          <User className="w-4 h-4 text-white" />
        ) : (
          <GraduationCap className="w-4 h-4 text-gray-600" />
        )}
      </div>

      {/* Bubble */}
      <div className={clsx('flex flex-col gap-2 max-w-[80%]', isUser && 'items-end')}>
        <div
          className={clsx(
            'px-4 py-3 rounded-2xl text-sm leading-relaxed',
            isUser
              ? 'bg-brand-600 text-white rounded-tr-sm'
              : 'bg-white border border-gray-200 text-gray-800 rounded-tl-sm shadow-sm'
          )}
        >
          {isUser ? (
            <p>{message.content}</p>
          ) : (
            <div className="prose prose-sm max-w-none prose-p:my-1 prose-headings:my-2">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {message.content}
              </ReactMarkdown>
            </div>
          )}
        </div>

        {/* Citations */}
        {!isUser && message.citations.length > 0 && (
          <div className="w-full space-y-1">
            <p className="text-xs text-gray-400 font-medium px-1">Sources</p>
            {message.citations.map((cit, i) => (
              <CitationCard key={cit.id} citation={cit} index={i} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
