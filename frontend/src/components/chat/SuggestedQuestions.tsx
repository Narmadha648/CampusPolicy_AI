const SUGGESTIONS = [
  'What are the attendance rules?',
  'How do I apply for an examination revaluation?',
  'What does the handbook say about leave?',
  'What is the minimum attendance percentage required?',
  'What are the late fee rules?',
  'How are internal marks calculated?',
]

interface Props {
  onSelect: (q: string) => void
}

export default function SuggestedQuestions({ onSelect }: Props) {
  return (
    <div className="flex flex-wrap gap-2 justify-center">
      {SUGGESTIONS.map(q => (
        <button
          key={q}
          onClick={() => onSelect(q)}
          className="px-3 py-2 text-xs bg-white border border-gray-200 rounded-xl text-gray-600 hover:bg-brand-50 hover:border-brand-300 hover:text-brand-700 transition-colors shadow-sm"
        >
          {q}
        </button>
      ))}
    </div>
  )
}
