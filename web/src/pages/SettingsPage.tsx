import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { settingsApi } from '@/api/client'
import { ConfirmDialog } from '@/components/ConfirmDialog'

export function SettingsPage() {
  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">설정</h1>
      <DataPathCard />
      <EmbeddingSettingsCard />
    </div>
  )
}

function DataPathCard() {
  const [path, setPath] = useState('')
  const [info, setInfo] = useState<{ path: string; exists: boolean; total_size_mb: number; file_count: number } | null>(null)
  const [saving, setSaving] = useState(false)
  const [saveResult, setSaveResult] = useState('')

  useEffect(() => {
    settingsApi.getDataPath().then(data => {
      setPath(data.path)
      setInfo(data)
    })
  }, [])

  const handleSave = async () => {
    setSaving(true)
    setSaveResult('')
    try {
      const result = await settingsApi.updateDataPath(path)
      if (result.error) {
        setSaveResult(`오류: ${result.error}`)
      } else {
        setSaveResult('저장되었습니다. 서버를 재시작하면 적용됩니다.')
        settingsApi.getDataPath().then(setInfo)
      }
    } catch {
      setSaveResult('저장 실패')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">데이터 저장 경로</CardTitle>
        <p className="text-sm text-muted-foreground">
          백업 HTML, 미디어, 다운로드 파일이 저장되는 경로입니다.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-1.5">
          <label className="text-sm font-medium">경로</label>
          <Input
            value={path}
            onChange={e => setPath(e.target.value)}
            placeholder="예: /Volumes/External/sentinel-data, D:\sentinel-data"
          />
        </div>

        {info && (
          <div className="text-sm text-muted-foreground space-y-1">
            <p>현재 경로: <span className="font-mono text-xs">{info.path}</span></p>
            <p>파일 {info.file_count}개 · {info.total_size_mb}MB</p>
            {!info.exists && <p className="text-yellow-600">⚠ 경로가 존재하지 않습니다.</p>}
          </div>
        )}

        <div className="flex gap-2">
          <Button onClick={handleSave} disabled={saving}>
            {saving ? '저장 중...' : '저장'}
          </Button>
        </div>

        {saveResult && (
          <div className={`text-sm p-3 rounded border ${
            saveResult.includes('오류') || saveResult.includes('실패')
              ? 'bg-red-50 border-red-200 text-red-700'
              : 'bg-yellow-50 border-yellow-200 text-yellow-700'
          }`}>
            {saveResult}
            {saveResult.includes('재시작') && (
              <p className="mt-1 text-xs">⚠ 기존 데이터는 자동으로 이동되지 않습니다. 파일을 직접 옮겨주세요.</p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function EmbeddingSettingsCard() {
  const [baseUrl, setBaseUrl] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [model, setModel] = useState('')
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [recalculating, setRecalculating] = useState(false)
  const [saveResult, setSaveResult] = useState('')
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null)
  const [status, setStatus] = useState<{ stale: boolean; embedded_count: number; total_articles: number } | null>(null)
  const [recalcResult, setRecalcResult] = useState('')

  const loadStatus = () => {
    settingsApi.getEmbeddingStatus().then(setStatus)
  }

  useEffect(() => {
    settingsApi.getEmbedding().then(s => {
      setBaseUrl(s.base_url)
      setApiKey(s.api_key)
      setModel(s.model)
    })
    loadStatus()
  }, [])

  const handleRecalculate = async () => {
    setRecalculating(true)
    setRecalcResult('')
    try {
      const result = await settingsApi.recalculateEmbeddings()
      setRecalcResult(`완료: ${result.success}개 성공, ${result.failed}개 실패 (총 ${result.total}개)`)
      loadStatus()
    } catch (e) {
      setRecalcResult(`오류: ${e}`)
    } finally {
      setRecalculating(false)
    }
  }

  const handleSave = async () => {
    setSaving(true)
    setSaveResult('')
    try {
      const result = await settingsApi.updateEmbedding({ base_url: baseUrl, api_key: apiKey, model })
      setSaveResult(result.model_changed ? '저장되었습니다. 모델이 변경되어 임베딩 재계산이 필요합니다.' : '저장되었습니다.')
      loadStatus()
    } catch {
      setSaveResult('저장 실패')
    } finally {
      setSaving(false)
    }
  }

  const handleTest = async () => {
    setTesting(true)
    setTestResult(null)
    try {
      const result = await settingsApi.testEmbedding({ base_url: baseUrl, api_key: apiKey, model })
      if (result.success) {
        setTestResult({ success: true, message: `연결 성공: ${result.dimensions}차원` })
      } else {
        setTestResult({ success: false, message: `연결 실패: ${result.error}` })
      }
    } catch (e) {
      setTestResult({ success: false, message: `오류: ${e}` })
    } finally {
      setTesting(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">임베딩 설정</CardTitle>
        <p className="text-sm text-muted-foreground">
          게시글 버전 감지에 사용할 임베딩 모델을 설정합니다. 백업 시 제목 임베딩을 생성하여 유사 게시글을 찾습니다.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-1.5">
          <label className="text-sm font-medium">Base URL</label>
          <Input
            value={baseUrl}
            onChange={e => setBaseUrl(e.target.value)}
            placeholder="예: http://localhost:11434/v1, https://api.openai.com/v1"
          />
          <p className="text-xs text-muted-foreground">
            Ollama: http://localhost:11434/v1 · OpenAI: https://api.openai.com/v1
          </p>
        </div>

        <div className="space-y-1.5">
          <label className="text-sm font-medium">API Key</label>
          <Input
            type="password"
            value={apiKey}
            onChange={e => setApiKey(e.target.value)}
            placeholder="로컬이면 비워두세요"
          />
        </div>

        <div className="space-y-1.5">
          <label className="text-sm font-medium">Model</label>
          <Input
            value={model}
            onChange={e => setModel(e.target.value)}
            placeholder="예: nomic-embed-text, text-embedding-3-small"
          />
        </div>

        <div className="flex gap-2">
          <Button onClick={handleSave} disabled={saving}>
            {saving ? '저장 중...' : '저장'}
          </Button>
          <Button variant="outline" onClick={handleTest} disabled={testing || !baseUrl}>
            {testing ? '테스트 중...' : '연결 테스트'}
          </Button>
        </div>

        {saveResult && <p className="text-sm text-green-600">{saveResult}</p>}
        {testResult && (
          <div className={`text-sm p-3 rounded border ${
            testResult.success
              ? 'bg-green-50 border-green-200 text-green-700'
              : 'bg-red-50 border-red-200 text-red-700'
          }`}>
            {testResult.message}
          </div>
        )}

        {/* 임베딩 상태 */}
        {status && (
          <div className="border-t pt-4 space-y-3">
            <div className="text-sm">
              <span className="text-muted-foreground">임베딩 현황: </span>
              <span className="font-medium">{status.embedded_count}</span>
              <span className="text-muted-foreground"> / {status.total_articles}개 게시글</span>
            </div>

            {status.stale && (
              <div className="text-sm p-3 rounded border bg-yellow-50 border-yellow-200 text-yellow-700">
                ⚠ 모델이 변경되어 기존 임베딩이 유효하지 않습니다. 재계산이 필요합니다.
              </div>
            )}

            <div className="flex gap-2">
              <ConfirmDialog
                trigger={
                  <Button variant="outline" size="sm" disabled={recalculating || !baseUrl}>
                    {recalculating ? '재계산 중...' : '임베딩 전체 재계산'}
                  </Button>
                }
                title="임베딩 재계산"
                description="모든 백업 게시글의 임베딩을 재계산합니다. 시간이 걸릴 수 있습니다. 계속할까요?"
                onConfirm={handleRecalculate}
                confirmText="재계산"
              />
            </div>

            {recalcResult && <p className="text-sm text-green-600">{recalcResult}</p>}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
