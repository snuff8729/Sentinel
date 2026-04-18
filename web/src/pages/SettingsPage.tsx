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
              placeholder="비워두면 기본 프롬프트를 사용합니다."
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
    </div>
  )
}
