import { useRef, useState, type KeyboardEvent } from 'react'
import { SendHorizontal } from 'lucide-react'
import clsx from 'clsx'

interface Props {
  onSend: (text: string) => void
  disabled?: boolean
  placeholder?: string
}

export default function ChatInput({ onSend, disabled, placeholder }: Props) {
  const [value, setValue] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  function submit() {
    const q = value.trim()
    if (!q || disabled) return
    onSend(q)
    setValue('')
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  function handleInput() {
    const ta = textareaRef.current
    if (ta) {
      ta.style.height = 'auto'
      ta.style.height = Math.min(ta.scrollHeight, 160) + 'px'
    }
  }

  return (
    <div className="flex items-end gap-2 bg-white border border-gray-200 rounded-2xl px-4 py-3 shadow-sm focus-within:ring-2 focus-within:ring-brand-500 focus-within:border-brand-500 transition-all">
      <textarea
        ref={textareaRef}
        rows={1}
        value={value}
        onChange={e => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        onInput={handleInput}
        disabled={disabled}
        placeholder={placeholder ?? 'Ask about a college policy…'}
        className="flex-1 resize-none bg-transparent text-sm text-gray-800 placeholder:text-gray-400 focus:outline-none disabled:opacity-50 leading-relaxed"
        aria-label="Message input"
      />
      <button
        onClick={submit}
        disabled={!value.trim() || disabled}
        className={clsx(
          'w-8 h-8 rounded-xl flex items-center justify-center transition-colors shrink-0',
          value.trim() && !disabled
            ? 'bg-brand-600 text-white hover:bg-brand-700'
            : 'bg-gray-100 text-gray-400 cursor-not-allowed'
        )}
        aria-label="Send message"
      >
        <SendHorizontal className="w-4 h-4" />
      </button>
    </div>
  )
}
