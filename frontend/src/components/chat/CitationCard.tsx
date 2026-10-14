import { useState } from 'react'
import { ChevronDown, ChevronUp, FileText, AlertTriangle } from 'lucide-react'
import type { Citation } from '../../types'

interface Props {
  citation: Citation
  index: number
}

export default function CitationCard({ citation, index }: Props) {
  const [expanded, setExpanded] = useState(false)

  if (citation.source_deleted) {
    return (
      <div className="flex items-start gap-2 px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-xs text-gray-500">
        <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5 text-amber-500" />
        <span>
          [{index + 1}] <span className="italic">{citation.document_title}</span> — original
          source has been removed
        </span>
      </div>
    )
  }

  // Extract document ID from the citation. The backend includes it via chunk metadata;
  // we derive a document file URL using the document title as fallback display.
  // The real document_id isn't in CitationOut, so we open the file search page.
  // For direct PDF access, admins should open the admin panel.

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden text-xs">
      <button
        onClick={() => setExpanded(v => !v)}
        className="w-full flex items-center justify-between px-3 py-2 bg-gray-50 hover:bg-gray-100 transition-colors text-left"
        aria-expanded={expanded}
      >
        <span className="flex items-center gap-2 font-medium text-gray-700">
          <FileText className="w-3.5 h-3.5 text-brand-500 shrink-0" />
          [{index + 1}]{' '}
          <span className="truncate max-w-[220px]">{citation.document_title}</span>
          <span className="text-gray-400 font-normal whitespace-nowrap">
            · v{citation.document_version}, p.{citation.page_number}
          </span>
          {citation.similarity_score !== null && (
            <span className="text-gray-400 font-normal">
              · {(citation.similarity_score * 100).toFixed(0)}% match
            </span>
          )}
        </span>
        {expanded ? (
          <ChevronUp className="w-3.5 h-3.5 text-gray-400 shrink-0" />
        ) : (
          <ChevronDown className="w-3.5 h-3.5 text-gray-400 shrink-0" />
        )}
      </button>

      {expanded && (
        <div className="px-3 py-2 bg-white border-t border-gray-100">
          <p className="text-gray-600 leading-relaxed whitespace-pre-line">{citation.excerpt}</p>
        </div>
      )}
    </div>
  )
}
