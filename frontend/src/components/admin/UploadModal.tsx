import { useRef, useState } from 'react'
import { Upload, FileText, X } from 'lucide-react'
import Modal from '../ui/Modal'
import Button from '../ui/Button'
import Input from '../ui/Input'
import { documentsApi } from '../../api/documents'
import { ApiError } from '../../api/client'
import type { Document } from '../../types'

interface Props {
  open: boolean
  onClose: () => void
  onUploaded: (doc: Document) => void
  replaceDocumentId?: string
  replaceTitle?: string
}

export default function UploadModal({
  open,
  onClose,
  onUploaded,
  replaceDocumentId,
  replaceTitle,
}: Props) {
  const fileRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [title, setTitle] = useState(replaceTitle ?? '')
  const [policyYear, setPolicyYear] = useState('')
  const [description, setDescription] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const isReplace = !!replaceDocumentId

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0]
    if (!f) return
    if (!f.name.endsWith('.pdf') && f.type !== 'application/pdf') {
      setError('Only PDF files are allowed.')
      return
    }
    if (f.size > 50 * 1024 * 1024) {
      setError('File exceeds the 50 MB limit.')
      return
    }
    setError('')
    setFile(f)
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    if (!file) { setError('Please select a PDF file.'); return }
    if (!isReplace && title.trim().length < 2) { setError('Title is required.'); return }

    const form = new FormData()
    form.append('file', file)
    if (!isReplace) form.append('title', title.trim())
    if (policyYear.trim()) form.append('policy_year', policyYear.trim())
    if (description.trim()) form.append('description', description.trim())

    setLoading(true)
    try {
      const doc = isReplace
        ? await documentsApi.replace(replaceDocumentId!, form)
        : await documentsApi.upload(form)
      onUploaded(doc)
      onClose()
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'Upload failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={isReplace ? `Replace: ${replaceTitle}` : 'Upload Document'}
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Drop zone */}
        <div
          onClick={() => fileRef.current?.click()}
          onDragOver={e => e.preventDefault()}
          onDrop={e => {
            e.preventDefault()
            const f = e.dataTransfer.files[0]
            if (f) {
              const fakeEvent = { target: { files: e.dataTransfer.files } } as unknown as React.ChangeEvent<HTMLInputElement>
              handleFileChange(fakeEvent)
            }
          }}
          className="border-2 border-dashed border-gray-200 hover:border-brand-400 rounded-xl p-6 text-center cursor-pointer transition-colors"
          role="button"
          tabIndex={0}
          onKeyDown={e => e.key === 'Enter' && fileRef.current?.click()}
          aria-label="Click or drag to upload a PDF"
        >
          {file ? (
            <div className="flex items-center gap-3 justify-center text-sm text-gray-700">
              <FileText className="w-5 h-5 text-brand-600" />
              <span className="font-medium truncate max-w-xs">{file.name}</span>
              <button
                type="button"
                onClick={e => { e.stopPropagation(); setFile(null); if (fileRef.current) fileRef.current.value = '' }}
                className="text-gray-400 hover:text-red-500"
                aria-label="Remove file"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          ) : (
            <>
              <Upload className="w-8 h-8 text-gray-300 mx-auto mb-2" />
              <p className="text-sm text-gray-500">
                <span className="text-brand-600 font-medium">Click to upload</span> or drag and drop
              </p>
              <p className="text-xs text-gray-400 mt-1">PDF only · max 50 MB</p>
            </>
          )}
        </div>
        <input
          ref={fileRef}
          type="file"
          accept=".pdf,application/pdf"
          className="hidden"
          onChange={handleFileChange}
        />

        {!isReplace && (
          <Input
            label="Document title"
            value={title}
            onChange={e => setTitle(e.target.value)}
            placeholder="Student Handbook 2024-25"
            required
          />
        )}

        <Input
          label="Policy year / version (optional)"
          value={policyYear}
          onChange={e => setPolicyYear(e.target.value)}
          placeholder="2024-25"
        />

        <div className="flex flex-col gap-1">
          <label className="text-sm font-medium text-gray-700">Description (optional)</label>
          <textarea
            value={description}
            onChange={e => setDescription(e.target.value)}
            rows={2}
            className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
            placeholder="Brief description of this document…"
          />
        </div>

        {error && (
          <div role="alert" className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3">
            {error}
          </div>
        )}

        <div className="flex gap-3 justify-end pt-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" loading={loading}>
            {isReplace ? 'Replace document' : 'Upload document'}
          </Button>
        </div>
      </form>
    </Modal>
  )
}
