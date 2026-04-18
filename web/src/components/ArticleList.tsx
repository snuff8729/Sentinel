import { Link } from 'react-router-dom'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'
import type { ArticleRow } from '@/api/types'

interface Props {
  slug: string
  articles: ArticleRow[]
  selected: Set<number>
  onToggle: (id: number) => void
  onToggleAll: () => void
}

export function ArticleList({ slug, articles, selected, onToggle, onToggleAll }: Props) {
  const allSelected = articles.length > 0 && articles.every(a => selected.has(a.id))

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-10">
            <Checkbox checked={allSelected} onCheckedChange={onToggleAll} />
          </TableHead>
          <TableHead>제목</TableHead>
          <TableHead className="w-24">작성자</TableHead>
          <TableHead className="w-28">작성일</TableHead>
          <TableHead className="w-16 text-right">조회</TableHead>
          <TableHead className="w-16 text-right">추천</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {articles.map((article) => (
          <TableRow key={article.id}>
            <TableCell>
              <Checkbox
                checked={selected.has(article.id)}
                onCheckedChange={() => onToggle(article.id)}
              />
            </TableCell>
            <TableCell>
              <Link
                to={`/article/${slug}/${article.id}`}
                className="hover:underline"
              >
                {article.is_best && (
                  <span className="text-yellow-500 mr-1">★</span>
                )}
                {article.category && (
                  <Badge variant="secondary" className="mr-1.5 text-xs">
                    {article.category}
                  </Badge>
                )}
                {article.title}
                {article.comment_count > 0 && (
                  <span className="text-muted-foreground ml-1">[{article.comment_count}]</span>
                )}
              </Link>
            </TableCell>
            <TableCell className="text-sm">{article.author}</TableCell>
            <TableCell className="text-sm text-muted-foreground">
              {new Date(article.created_at).toLocaleDateString('ko-KR')}
            </TableCell>
            <TableCell className="text-right text-sm">{article.view_count}</TableCell>
            <TableCell className="text-right text-sm">{article.vote_count}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
