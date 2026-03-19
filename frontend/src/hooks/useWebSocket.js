import { useEffect, useRef, useCallback, useState } from 'react'
import { WS_URL } from '../utils/constants'

/**
 * Hook para mantener una conexión WebSocket con reconexión automática.
 * @param {function} onMessage - callback(parsedMessage) llamado por cada mensaje recibido
 */
const BACKOFF_INITIAL = 1000
const BACKOFF_MAX     = 30000

export function useWebSocket(onMessage) {
  const wsRef        = useRef(null)
  const onMsgRef     = useRef(onMessage)
  const unmountedRef = useRef(false)
  const backoffRef   = useRef(BACKOFF_INITIAL)
  const timerRef     = useRef(null)
  const [isConnected,  setIsConnected]  = useState(false)
  const [reconnecting, setReconnecting] = useState(false)

  // Mantener la referencia al callback actualizada sin reabrir la conexión
  useEffect(() => { onMsgRef.current = onMessage }, [onMessage])

  const connect = useCallback(() => {
    if (unmountedRef.current) return

    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const url = `${protocol}://${window.location.host}${WS_URL}`
    const ws  = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      setIsConnected(true)
      setReconnecting(false)
      backoffRef.current = BACKOFF_INITIAL  // reset backoff on successful connection
      console.log('[WS] Conectado')
    }

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        onMsgRef.current?.(msg)
      } catch {
        console.warn('[WS] Mensaje no parseable:', event.data)
      }
    }

    ws.onclose = () => {
      setIsConnected(false)
      if (!unmountedRef.current) {
        const delay = backoffRef.current
        backoffRef.current = Math.min(delay * 2, BACKOFF_MAX)
        console.log(`[WS] Desconectado — reconectando en ${delay / 1000}s...`)
        setReconnecting(true)
        timerRef.current = setTimeout(connect, delay)
      }
    }

    ws.onerror = (err) => {
      console.error('[WS] Error:', err)
      ws.close()
    }
  }, [])

  useEffect(() => {
    unmountedRef.current = false
    connect()
    return () => {
      unmountedRef.current = true
      clearTimeout(timerRef.current)
      wsRef.current?.close()
    }
  }, [connect])

  return { isConnected, reconnecting }
}
