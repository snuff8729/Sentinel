import { useEffect, useRef } from 'react'

type EventHandlers = Record<string, (data: unknown) => void>

export function useSSE(url: string, handlers: EventHandlers) {
  const handlersRef = useRef(handlers)
  handlersRef.current = handlers

  useEffect(() => {
    let source: EventSource | null = null
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null

    function connect() {
      source = new EventSource(url)

      for (const eventType of Object.keys(handlersRef.current)) {
        source.addEventListener(eventType, (e: MessageEvent) => {
          try {
            const data = JSON.parse(e.data)
            handlersRef.current[eventType]?.(data)
          } catch {
            // ignore parse errors
          }
        })
      }

      source.onerror = () => {
        source?.close()
        // 재연결 시도
        reconnectTimer = setTimeout(connect, 3000)
      }
    }

    connect()

    return () => {
      source?.close()
      if (reconnectTimer) clearTimeout(reconnectTimer)
    }
  }, [url])
}
