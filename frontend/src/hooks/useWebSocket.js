import { useEffect, useRef, useCallback, useState } from 'react'
import { WS_URL } from '../utils/constants'

/**
 * Hook para mantener una conexión WebSocket con reconexión automática.
 * @param {function} onMessage - callback(parsedMessage) llamado por cada mensaje recibido
 */
export function useWebSocket(onMessage) {
  const wsRef        = useRef(null)
  const onMsgRef     = useRef(onMessage)
  const unmountedRef = useRef(false)
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
      console.log('[WS] Desconectado — reconectando en 3s...')
      if (!unmountedRef.current) {
        setReconnecting(true)
        setTimeout(connect, 3000)
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
      wsRef.current?.close()
    }
  }, [connect])

  return { isConnected, reconnecting }
}
