import { BrowserRouter, Routes, Route, Link } from 'react-router-dom'

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
            <Route path="/" element={<div>채널 URL을 입력하세요</div>} />
            <Route path="/channel/:slug" element={<div>채널 페이지</div>} />
            <Route path="/article/:slug/:id" element={<div>게시글 상세</div>} />
            <Route path="/queue" element={<div>다운로드 큐</div>} />
            <Route path="/history" element={<div>백업 이력</div>} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}

export default App
