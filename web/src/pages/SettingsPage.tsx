import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { settingsApi } from '@/api/client'

export function SettingsPage() {
  const [baseUrl, setBaseUrl] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [model, setModel] = useState('')
  const [prompt, setPrompt] = useState('')
  const [defaultPrompt, setDefaultPrompt] = useState('')
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null)
  const [saveResult, setSaveResult] = useState('')

  useEffect(() => {
    settingsApi.getLLM().then(s => {
      setBaseUrl(s.base_url)
      setApiKey(s.api_key)
      setModel(s.model)
      setPrompt(s.prompt)
    })
    settingsApi.getDefaultPrompt().then(d => setDefaultPrompt(d.prompt))
  }, [])

  const handleSave = async () => {
    setSaving(true)
    setSaveResult('')
    try {
      await settingsApi.updateLLM({ base_url: baseUrl, api_key: apiKey, model, prompt })
      setSaveResult('저장되었습니다.')
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
      const result = await settingsApi.testLLM({ base_url: baseUrl, api_key: apiKey, model, prompt })
      if (result.success) {
        setTestResult({ success: true, message: `연결 성공: ${result.response}` })
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
    <div className="max-w-2xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">설정</h1>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">LLM 설정</CardTitle>
          <p className="text-sm text-muted-foreground">
            게시글 링크 분석에 사용할 LLM을 설정합니다. OpenAI 호환 API를 지원하는 모든 서비스를 사용할 수 있습니다.
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
              Ollama: http://localhost:11434/v1 · LM Studio: http://localhost:1234/v1 · OpenAI: https://api.openai.com/v1
            </p>
          </div>

          <div className="space-y-1.5">
            <label className="text-sm font-medium">API Key</label>
            <Input
              type="password"
              value={apiKey}
              onChange={e => setApiKey(e.target.value)}
              placeholder="로컬 LLM이면 비워두세요"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-sm font-medium">Model</label>
            <Input
              value={model}
              onChange={e => setModel(e.target.value)}
              placeholder="예: llama3, gpt-4o-mini, claude-haiku-4-5-20251001"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-sm font-medium">분석 프롬프트</label>
            <textarea
              className="flex min-h-[160px] w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-xs placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              value={prompt}
              onChange={e => setPrompt(e.target.value)}
              placeholder={defaultPrompt || "비워두면 기본 프롬프트를 사용합니다."}
            />
            <p className="text-xs text-muted-foreground">
              게시글 링크 분류에 사용할 시스템 프롬프트입니다. JSON 형식으로 응답하도록 지시해야 합니다.
            </p>
          </div>

          <div className="flex gap-2">
            <Button onClick={handleSave} disabled={saving}>
              {saving ? '저장 중...' : '저장'}
            </Button>
            <Button variant="outline" onClick={handleTest} disabled={testing || !baseUrl}>
              {testing ? '테스트 중...' : '연결 테스트'}
            </Button>
          </div>

          {saveResult && (
            <p className="text-sm text-green-600">{saveResult}</p>
          )}

          {testResult && (
            <div className={`text-sm p-3 rounded border ${
              testResult.success
                ? 'bg-green-50 border-green-200 text-green-700'
                : 'bg-red-50 border-red-200 text-red-700'
            }`}>
              {testResult.message}
            </div>
          )}
        </CardContent>
      </Card>

      <EmbeddingSettingsCard />
    </div>
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
    if (!confirm('모든 백업 게시글의 임베딩을 재계산합니다. 시간이 걸릴 수 있습니다. 계속할까요?')) return
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
              <Button
                variant="outline"
                size="sm"
                onClick={handleRecalculate}
                disabled={recalculating || !baseUrl}
              >
                {recalculating ? '재계산 중...' : '임베딩 전체 재계산'}
              </Button>
            </div>

            {recalcResult && <p className="text-sm text-green-600">{recalcResult}</p>}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
