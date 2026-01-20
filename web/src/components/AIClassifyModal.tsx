import { useState } from 'react'
import { Check, Loader, Sparkles, X } from 'lucide-react'
import type { Track } from '../types'
import type { ClassificationResult } from '../api'
import * as api from '../api'
import './AIClassifyModal.css'

interface AIClassifyModalProps {
  open: boolean
  tracks: Track[]
  onClose: () => void
  onComplete: () => void
  onToast: (message: string, type: 'success' | 'error') => void
}

export function AIClassifyModal({ open, tracks, onClose, onComplete, onToast }: AIClassifyModalProps) {
  const [step, setStep] = useState<'select' | 'rule' | 'preview' | 'executing'>('select')
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [rule, setRule] = useState('')
  const [loading, setLoading] = useState(false)
  const [classification, setClassification] = useState<ClassificationResult | null>(null)

  const handleSelectAll = () => {
    if (selectedIds.size === tracks.length) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(tracks.map(t => t.id)))
    }
  }

  const toggleSelect = (id: string) => {
    const newSet = new Set(selectedIds)
    if (newSet.has(id)) {
      newSet.delete(id)
    } else {
      newSet.add(id)
    }
    setSelectedIds(newSet)
  }

  const handlePreview = async () => {
    if (selectedIds.size === 0) {
      onToast('请先选择要分类的歌曲', 'error')
      return
    }
    if (!rule.trim()) {
      onToast('请输入分类规则', 'error')
      return
    }

    setLoading(true)
    try {
      const result = await api.aiClassifyPreview(Array.from(selectedIds), rule.trim())
      setClassification(result.classification)
      setStep('preview')
    } catch (e: any) {
      onToast(e?.message || 'AI 分类失败', 'error')
    } finally {
      setLoading(false)
    }
  }

  const handleExecute = async () => {
    if (!classification) return

    setStep('executing')
    setLoading(true)
    try {
      const result = await api.aiClassifyExecute(classification)
      onToast(`已分类 ${result.moved_count} 首歌曲`, 'success')
      onComplete()
      handleClose()
    } catch (e: any) {
      onToast(e?.message || '执行分类失败', 'error')
      setStep('preview')
    } finally {
      setLoading(false)
    }
  }

  const handleClose = () => {
    setStep('select')
    setSelectedIds(new Set())
    setRule('')
    setClassification(null)
    onClose()
  }

  if (!open) return null

  return (
    <div className="modal-overlay" onClick={handleClose}>
      <div className="modal-content ai-classify-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>
            <Sparkles size={18} />
            AI 智能分类
          </h3>
          <button className="modal-close" onClick={handleClose}>
            <X size={20} />
          </button>
        </div>

        {step === 'select' && (
          <>
            <div className="modal-body">
              <p className="step-hint">第 1 步：选择要分类的歌曲</p>
              <div className="select-actions">
                <button className="btn btn-sm btn-secondary" onClick={handleSelectAll}>
                  {selectedIds.size === tracks.length ? '取消全选' : '全选'}
                </button>
                <span className="select-count">已选 {selectedIds.size} / {tracks.length}</span>
              </div>
              <div className="track-select-list">
                {tracks.map((t) => (
                  <div
                    key={t.id}
                    className={`track-select-item ${selectedIds.has(t.id) ? 'selected' : ''}`}
                    onClick={() => toggleSelect(t.id)}
                  >
                    <span className="track-name">{t.title}</span>
                    {selectedIds.has(t.id) && <Check size={16} />}
                  </div>
                ))}
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={handleClose}>取消</button>
              <button
                className="btn btn-primary"
                onClick={() => setStep('rule')}
                disabled={selectedIds.size === 0}
              >
                下一步
              </button>
            </div>
          </>
        )}

        {step === 'rule' && (
          <>
            <div className="modal-body">
              <p className="step-hint">第 2 步：输入分类规则</p>
              <textarea
                className="rule-input"
                placeholder="例如：&#10;- 按歌手分类&#10;- 按语言分类（中文、英文、日文）&#10;- 按风格分类（流行、摇滚、古风）&#10;- 将周杰伦的歌放一起，其他按语言分"
                value={rule}
                onChange={(e) => setRule(e.target.value)}
                rows={6}
              />
              <p className="rule-hint">
                提示：规则越具体，分类效果越好
              </p>
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setStep('select')}>上一步</button>
              <button
                className="btn btn-primary"
                onClick={handlePreview}
                disabled={loading || !rule.trim()}
              >
                {loading ? <Loader size={16} className="spin" /> : <Sparkles size={16} />}
                预览分类
              </button>
            </div>
          </>
        )}

        {step === 'preview' && classification && (
          <>
            <div className="modal-body">
              <p className="step-hint">第 3 步：确认分类结果</p>
              <div className="classification-preview">
                {Object.entries(classification).map(([album, songs]) => (
                  <div key={album} className="classification-group">
                    <div className="group-header">
                      <strong>{album}</strong>
                      <span className="group-count">{songs.length} 首</span>
                    </div>
                    <div className="group-songs">
                      {songs.map((s) => (
                        <span key={s.track_id} className="song-tag">{s.name}</span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setStep('rule')}>重新分类</button>
              <button className="btn btn-primary" onClick={handleExecute}>
                确认执行
              </button>
            </div>
          </>
        )}

        {step === 'executing' && (
          <div className="modal-body" style={{ textAlign: 'center', padding: '40px 20px' }}>
            <Loader size={32} className="spin" />
            <p style={{ marginTop: '16px', color: 'var(--text-secondary)' }}>正在执行分类...</p>
          </div>
        )}
      </div>
    </div>
  )
}
