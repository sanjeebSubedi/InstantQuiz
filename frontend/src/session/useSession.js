import { useRef, useSyncExternalStore } from 'react'
import { createSessionController } from './controller.js'

export function useSession() {
  const controllerRef = useRef(null)
  if (controllerRef.current === null) {
    controllerRef.current = createSessionController()
  }
  const { getState, subscribe, actions } = controllerRef.current
  const state = useSyncExternalStore(subscribe, getState)
  return { state, actions }
}