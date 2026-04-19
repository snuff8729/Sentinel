import { BrowserRouter, Routes, Route, Link } from 'react-router-dom'
import { Toaster } from '@/components/ui/sonner'
import { ChannelInput } from '@/components/ChannelInput'
import { RecentChannels } from '@/components/RecentChannels'
import { ChannelPage } from '@/pages/ChannelPage'
import { ArticleDetailPage } from '@/pages/ArticleDetailPage'
import { QueuePage } from '@/pages/QueuePage'
import { HistoryPage } from '@/pages/HistoryPage'
import { BackupDetailPage } from '@/pages/BackupDetailPage'
import { SettingsPage } from '@/pages/SettingsPage'
import { VersionsPage } from '@/pages/VersionsPage'

function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-background">
        <nav className="border-b px-6 py-3 flex items-center gap-4">
          <Link to="/" className="font-bold text-lg">Sentinel</Link>
          <Link to="/queue" className="text-muted-foreground hover:text-foreground">큐</Link>
          <Link to="/history" className="text-muted-foreground hover:text-foreground">이력</Link>
          <Link to="/versions" className="text-muted-foreground hover:text-foreground">버전</Link>
          <Link to="/settings" className="text-muted-foreground hover:text-foreground">설정</Link>
        </nav>
        <main className="p-6">
          <Routes>
            <Route path="/" element={
              <div className="space-y-6">
                <h1 className="text-2xl font-bold">채널 입력</h1>
                <ChannelInput />
                <RecentChannels />
              </div>
            } />
            <Route path="/channel/:slug" element={<ChannelPage />} />
            <Route path="/article/:slug/:id" element={<ArticleDetailPage />} />
            <Route path="/queue" element={<QueuePage />} />
            <Route path="/history" element={<HistoryPage />} />
            <Route path="/backup/:id" element={<BackupDetailPage />} />
            <Route path="/versions" element={<VersionsPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Routes>
        </main>
      </div>
      <Toaster />
    </BrowserRouter>
  )
}

export default App
