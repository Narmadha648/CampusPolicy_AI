import { useState } from 'react'
import {
  Trash2,
  RotateCcw,
  AlertCircle,
  CheckCircle,
  Clock,
  Loader2,
  Upload,
} from 'lucide-react'
import Badge from '../ui/Badge'
import Button from '../ui/Button'
import Modal from '../ui/Modal'
import UploadModal from './UploadModal'
import { documentsApi } from '../../api/documents'
import { ApiError } from '../../api/client'
import type { Document } from '../../types'

interface Props {
  documents: Document[]
  onRefresh: () => void
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { label: string; variant: 'success' | 'warning' | 'error' | 'info' | 'neutral' }> = {
    ready:      { label: 'Ready',      variant: 'success' },
    processing: { label: 'Processing', variant: 'info' },
    pending:    { label: 'Pending',    variant: 'warning' },
    failed:     { label: 'Failed',     variant: 'error' },
  }
  const { label, variant } = map[status] ?? { label: status, variant: 'neutral' }
  return <Badge variant={variant}>{label}</Badge>
}

function StatusIcon({ status }: { status: string }) {
  if (status === 'ready')      return <CheckCircle className="w-4 h-4 text-green-500" />
  if (status === 'processing') return <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />
  if (status === 'pending')    return <Clock className="w-4 h-4 text-yellow-500" />
  return <AlertCircle className="w-4 h-4 text-red-500" />
}

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

export default function DocumentTable({ documents, onRefresh }: Props) {
  const [replaceTarget, setReplaceTarget] = useState<Document | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<Document | null>(null)
  const [errorTarget, setErrorTarget] = useState<Document | null>(null)
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [actionError, setActionError] = useState('')

  async function handleDelete(doc: Document) {
    setActionLoading(doc.id)
    setActionError('')
    try {
      await documentsApi.delete(doc.id)
      setDeleteTarget(null)
      onRefresh()
    } catch (err) {
      setActionError(err instanceof ApiError ? err.detail : 'Delete failed')
    } finally {
      setActionLoading(null)
    }
  }

  async function handleRetry(doc: Document) {
    setActionLoading(doc.id)
    setActionError('')
    try {
      await documentsApi.retry(doc.id)
      onRefresh()
    } catch (err) {
      setActionError(err instanceof ApiError ? err.detail : 'Retry failed')
    } finally {
      setActionLoading(null)
    }
  }

  if (documents.length === 0) {
    return (
      <div className="text-center py-16 text-gray-400">
        <Upload className="w-10 h-10 mx-auto mb-3 opacity-40" />
        <p className="font-medium">No documents yet</p>
        <p className="text-sm mt-1">Upload your first PDF to get started</p>
      </div>
    )
  }

  return (
    <>
      {actionError && (
        <div role="alert" className="mb-4 bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3">
          {actionError}
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 text-xs text-gray-500 uppercase tracking-wide">
              <th className="text-left py-3 pr-4 font-medium">Document</th>
              <th className="text-left py-3 pr-4 font-medium">Year</th>
              <th className="text-left py-3 pr-4 font-medium">Version</th>
              <th className="text-left py-3 pr-4 font-medium">Size</th>
              <th className="text-left py-3 pr-4 font-medium">Pages</th>
              <th className="text-left py-3 pr-4 font-medium">Status</th>
              <th className="text-left py-3 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {documents.map(doc => {
              const ver = doc.active_version ?? doc.latest_version
              const isBusy = actionLoading === doc.id
              return (
                <tr
                  key={doc.id}
                  className="border-b border-gray-50 hover:bg-gray-50 transition-colors"
                >
                  <td className="py-3 pr-4">
                    <div className="flex items-center gap-2">
                      <StatusIcon status={ver?.status ?? 'pending'} />
                      <div>
                        <p className="font-medium text-gray-900 max-w-[200px] truncate">
                          {doc.title}
                        </p>
                        <p className="text-xs text-gray-400 truncate max-w-[200px]">
                          {ver?.original_filename}
                        </p>
                      </div>
                    </div>
                  </td>
                  <td className="py-3 pr-4 text-gray-600">{doc.policy_year ?? '—'}</td>
                  <td className="py-3 pr-4 text-gray-600">v{ver?.version_number ?? 1}</td>
                  <td className="py-3 pr-4 text-gray-600">
                    {ver ? formatBytes(ver.file_size_bytes) : '—'}
                  </td>
                  <td className="py-3 pr-4 text-gray-600">{ver?.page_count ?? '—'}</td>
                  <td className="py-3 pr-4">
                    <StatusBadge status={ver?.status ?? 'pending'} />
                    {ver?.status === 'failed' && (
                      <button
                        onClick={() => setErrorTarget(doc)}
                        className="ml-1.5 text-xs text-red-600 hover:underline"
                      >
                        details
                      </button>
                    )}
                  </td>
                  <td className="py-3">
                    <div className="flex items-center gap-1">
                      {/* Replace */}
                      <button
                        onClick={() => setReplaceTarget(doc)}
                        disabled={isBusy}
                        title="Replace with new version"
                        className="p-1.5 rounded-lg text-gray-400 hover:text-brand-600 hover:bg-brand-50 transition-colors disabled:opacity-40"
                        aria-label="Replace document"
                      >
                        <Upload className="w-4 h-4" />
                      </button>

                      {/* Retry (failed only) */}
                      {ver?.status === 'failed' && (
                        <button
                          onClick={() => handleRetry(doc)}
                          disabled={isBusy}
                          title="Retry processing"
                          className="p-1.5 rounded-lg text-gray-400 hover:text-green-600 hover:bg-green-50 transition-colors disabled:opacity-40"
                          aria-label="Retry processing"
                        >
                          {isBusy ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                          ) : (
                            <RotateCcw className="w-4 h-4" />
                          )}
                        </button>
                      )}

                      {/* Delete */}
                      <button
                        onClick={() => setDeleteTarget(doc)}
                        disabled={isBusy}
                        title="Delete document"
                        className="p-1.5 rounded-lg text-gray-400 hover:text-red-600 hover:bg-red-50 transition-colors disabled:opacity-40"
                        aria-label="Delete document"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Replace modal */}
      {replaceTarget && (
        <UploadModal
          open
          onClose={() => setReplaceTarget(null)}
          onUploaded={() => { setReplaceTarget(null); onRefresh() }}
          replaceDocumentId={replaceTarget.id}
          replaceTitle={replaceTarget.title}
        />
      )}

      {/* Delete confirm */}
      {deleteTarget && (
        <Modal open onClose={() => setDeleteTarget(null)} title="Delete document" size="sm">
          <p className="text-sm text-gray-600 mb-6">
            Are you sure you want to delete{' '}
            <strong className="text-gray-900">{deleteTarget.title}</strong>? This will remove it
            from all future searches. Historical citations will be marked as unavailable.
          </p>
          <div className="flex gap-3 justify-end">
            <Button variant="secondary" onClick={() => setDeleteTarget(null)}>
              Cancel
            </Button>
            <Button
              variant="danger"
              loading={actionLoading === deleteTarget.id}
              onClick={() => handleDelete(deleteTarget)}
            >
              Delete
            </Button>
          </div>
        </Modal>
      )}

      {/* Error details */}
      {errorTarget && (
        <Modal open onClose={() => setErrorTarget(null)} title="Processing error" size="sm">
          <div className="bg-red-50 border border-red-100 rounded-lg px-4 py-3 text-sm text-red-700">
            {errorTarget.latest_version?.error_message ?? 'Unknown error'}
          </div>
          <div className="flex justify-end mt-4">
            <Button variant="secondary" onClick={() => setErrorTarget(null)}>Close</Button>
          </div>
        </Modal>
      )}
    </>
  )
}
