import { Link } from 'react-router-dom'
import { getRecentChannels } from '@/lib/recentChannels'

export function RecentChannels() {
  const channels = getRecentChannels()

  if (channels.length === 0) return null

  return (
    <div className="space-y-2">
      <h2 className="text-sm font-medium text-muted-foreground">최근 접속 채널</h2>
      <div className="flex flex-wrap gap-2">
        {channels.map(c => (
          <Link
            key={c.slug}
            to={`/channel/${c.slug}`}
            className="px-3 py-1.5 border rounded-md text-sm hover:bg-muted transition-colors"
          >
            {c.slug}
          </Link>
        ))}
      </div>
    </div>
  )
}
