import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'

export function ChannelInput() {
  const [url, setUrl] = useState('')
  const navigate = useNavigate()

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const match = url.match(/arca\.live\/b\/([^/?]+)/)
    const slug = match ? match[1] : url.trim()
    if (slug) navigate(`/channel/${slug}`)
  }

  return (
    <form onSubmit={handleSubmit} className="flex gap-2 max-w-xl">
      <Input
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        placeholder="채널 URL 또는 slug 입력 (예: characterai)"
        className="flex-1"
      />
      <Button type="submit">이동</Button>
    </form>
  )
}
