import { useCallback, useEffect, useState } from 'react'
import {
  GraduationCap,
  LogOut,
  FileText,
  Users,
  MessageSquare,
  RefreshCw,
  Plus,
  AlertCircle,
  BarChart2,
  Loader2,
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { documentsApi } from '../api/documents'
import { ApiError } from '../api/client'
import DocumentTable from '../components/admin/DocumentTable'
import UploadModal from '../components/admin/UploadModal'
import Button from '../components/ui/Button'
import type { Document, AdminStats } from '../types'

interface StatCardProps {
  label: string
  value: number | string
  icon: React.ReactNode
  color: string
}

function StatCard({ label, value, icon, color }: StatCardProps) {
  return (
    <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5 flex items-center gap-4">
      <div className={`w-11 h-11 rounded-xl flex items-center justify-center ${color}`}>
        {icon}
      </div>
      <div>
        <p className="text-2xl font-bold text-gray-900">{value}</p>
        <p className="text-sm text-gray-500">{label}</p>
      </div>
    </div>
  )
}

export default function AdminDashboard() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const [documents, setDocuments] = useState<Document[]>([])
  const [stats, setStats] = useState<AdminStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [uploadOpen, setUploadOpen] = useState(false)
  const [refreshing, setRefreshing] = useState(false)

  const loadAll = useCallback(async () => {
    setError('')
    try {
      const [docsRes, statsRes] = await Promise.all([
        documentsApi.adminList(),
        documentsApi.stats(),
      ])
      setDocuments(docsRes.items)
      setStats(statsRes)
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'Failed to load data')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    void loadAll()
    // Poll every 8 seconds while there are pending/processing jobs
    const id = setInterval(() => {
      if (documents.some(d => ['pending', 'processing'].includes(d.latest_version?.status ?? ''))) {
        void loadAll()
      }
    }, 8000)
    return () => clearInterval(id)
  }, [loadAll, documents])

  async function handleLogout() {
    await logout()
    navigate('/login')
  }

  function handleRefresh() {
    setRefreshing(true)
    void loadAll()
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* ── Top nav ── */}
      <nav className="bg-white border-b border-gray-100 px-6 py-3 flex items-center gap-4">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-brand-600 rounded-lg flex items-center justify-center">
            <GraduationCap className="w-5 h-5 text-white" />
          </div>
          <span className="font-semibold text-gray-900">CampusPolicy AI</span>
          <span className="text-xs bg-brand-100 text-brand-700 px-2 py-0.5 rounded-full font-medium">
            Admin
          </span>
        </div>
        <div className="ml-auto flex items-center gap-3 text-sm text-gray-500">
          <span>{user?.name}</span>
          <button
            onClick={handleLogout}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg hover:bg-gray-100 transition-colors"
          >
            <LogOut className="w-4 h-4" />
            Sign out
          </button>
        </div>
      </nav>

      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8 space-y-8">
        {/* Error */}
        {error && (
          <div role="alert" className="flex items-start gap-2 bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl px-4 py-3">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            {error}
          </div>
        )}

        {/* Stats cards */}
        {loading ? (
          <div className="flex justify-center py-8">
            <Loader2 className="w-8 h-8 animate-spin text-brand-600" />
          </div>
        ) : (
          <>
            <section aria-label="Summary statistics">
              <h2 className="text-lg font-semibold text-gray-800 mb-4">Overview</h2>
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <StatCard
                  label="Ready documents"
                  value={stats?.ready_documents ?? 0}
                  icon={<FileText className="w-5 h-5 text-green-600" />}
                  color="bg-green-50"
                />
                <StatCard
                  label="Student accounts"
                  value={stats?.student_count ?? 0}
                  icon={<Users className="w-5 h-5 text-blue-600" />}
                  color="bg-blue-50"
                />
                <StatCard
                  label="Questions asked"
                  value={stats?.total_questions ?? 0}
                  icon={<MessageSquare className="w-5 h-5 text-purple-600" />}
                  color="bg-purple-50"
                />
                <StatCard
                  label="Conversations"
                  value={stats?.total_conversations ?? 0}
                  icon={<BarChart2 className="w-5 h-5 text-orange-600" />}
                  color="bg-orange-50"
                />
              </div>
            </section>

            {/* Top topics */}
            {stats && stats.top_topics.length > 0 && (
              <section aria-label="Frequently asked topics">
                <h2 className="text-lg font-semibold text-gray-800 mb-4">Top question topics</h2>
                <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
                  <div className="space-y-3">
                    {stats.top_topics.map(t => {
                      const max = stats.top_topics[0].count
                      const pct = max > 0 ? (t.count / max) * 100 : 0
                      return (
                        <div key={t.topic} className="flex items-center gap-3">
                          <span className="text-sm text-gray-600 w-36 shrink-0">{t.topic}</span>
                          <div className="flex-1 bg-gray-100 rounded-full h-2">
                            <div
                              className="bg-brand-500 h-2 rounded-full transition-all"
                              style={{ width: `${pct}%` }}
                            />
                          </div>
                          <span className="text-sm font-medium text-gray-700 w-8 text-right">
                            {t.count}
                          </span>
                        </div>
                      )
                    })}
                  </div>
                </div>
              </section>
            )}

            {/* Documents table */}
            <section aria-label="Document management">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-gray-800">Documents</h2>
                <div className="flex items-center gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={handleRefresh}
                    loading={refreshing}
                  >
                    <RefreshCw className="w-3.5 h-3.5" />
                    Refresh
                  </Button>
                  <Button size="sm" onClick={() => setUploadOpen(true)}>
                    <Plus className="w-4 h-4" />
                    Upload PDF
                  </Button>
                </div>
              </div>

              <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
                <DocumentTable documents={documents} onRefresh={loadAll} />
              </div>

              {/* Job status callout */}
              {(stats?.pending_jobs ?? 0) > 0 && (
                <p className="text-xs text-gray-400 mt-2">
                  {stats?.pending_jobs} job(s) pending or processing. The table refreshes automatically.
                </p>
              )}
              {(stats?.failed_jobs ?? 0) > 0 && (
                <p className="text-xs text-red-400 mt-1">
                  {stats?.failed_jobs} job(s) failed. Click "details" in the table for more information.
                </p>
              )}
            </section>
          </>
        )}
      </div>

      {/* Upload modal */}
      <UploadModal
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        onUploaded={() => { setUploadOpen(false); void loadAll() }}
      />
    </div>
  )
}
