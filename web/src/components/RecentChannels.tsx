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
            className="flex items-center gap-2 px-3 py-2 border rounded-md text-sm hover:bg-muted transition-colors"
          >
            {c.iconUrl && (
              <img src={c.iconUrl} alt="" className="w-5 h-5 rounded" referrerPolicy="no-referrer" />
            )}
            <span>{c.name ?? c.slug}</span>
          </Link>
        ))}
      </div>
    </div>
  )
}
