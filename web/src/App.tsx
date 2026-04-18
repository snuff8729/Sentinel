import { BrowserRouter, Routes, Route, Link } from 'react-router-dom'
import { ChannelInput } from '@/components/ChannelInput'
import { ChannelPage } from '@/pages/ChannelPage'
import { ArticleDetailPage } from '@/pages/ArticleDetailPage'

function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-background">
        <nav className="border-b px-6 py-3 flex items-center gap-4">
          <Link to="/" className="font-bold text-lg">Sentinel</Link>
          <Link to="/queue" className="text-muted-foreground hover:text-foreground">큐</Link>
          <Link to="/history" className="text-muted-foreground hover:text-foreground">이력</Link>
        </nav>
        <main className="p-6">
          <Routes>
            <Route path="/" element={
              <div className="space-y-6">
                <h1 className="text-2xl font-bold">채널 입력</h1>
                <ChannelInput />
              </div>
            } />
            <Route path="/channel/:slug" element={<ChannelPage />} />
            <Route path="/article/:slug/:id" element={<ArticleDetailPage />} />
            <Route path="/queue" element={<div>다운로드 큐 (TODO)</div>} />
            <Route path="/history" element={<div>백업 이력 (TODO)</div>} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}

export default App
