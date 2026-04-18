import { useEffect, useRef } from 'react'

type EventHandlers = Record<string, (data: unknown) => void>

export function useSSE(url: string, handlers: EventHandlers) {
  const handlersRef = useRef(handlers)
  handlersRef.current = handlers

  useEffect(() => {
    const source = new EventSource(url)

    const listeners: [string, (e: MessageEvent) => void][] = []
    for (const eventType of Object.keys(handlersRef.current)) {
      const listener = (e: MessageEvent) => {
        try {
          const data = JSON.parse(e.data)
          handlersRef.current[eventType]?.(data)
        } catch {
          // ignore parse errors
        }
      }
      source.addEventListener(eventType, listener)
      listeners.push([eventType, listener])
    }

    return () => {
      for (const [type, listener] of listeners) {
        source.removeEventListener(type, listener)
      }
      source.close()
    }
  }, [url])
}
