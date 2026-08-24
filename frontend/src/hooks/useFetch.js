import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * Fetch-on-mount with refetch, built around one specific UI requirement:
 * a refetch must NOT clear the data it already has.
 *
 * A dashboard that blanks to skeletons every 30 seconds is unusable - the
 * layout jumps, the thing you were reading disappears, and the eye has to
 * re-find its place. So the hook keeps three pieces of state:
 *
 *   data     - the last successful payload, held across refetches
 *   loading  - true only for the FIRST load, when there is nothing to hold
 *   stale    - true while a background refetch is in flight
 *
 * Components render `data` continuously and dim it with the .is-stale class
 * while `stale` is true. The frame never moves.
 *
 * @param {() => Promise<any>} fetcher  must be stable (useCallback at the
 *   call site), since it is this hook's dependency for re-running.
 * @param {{enabled?: boolean}} [options]
 */
export function useFetch(fetcher, { enabled = true } = {}) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(enabled)
  const [stale, setStale] = useState(false)

  // Guards against two races that would otherwise show wrong data:
  //  - setting state after the component unmounted
  //  - a slow request for "30 days" resolving after a fast one for "7 days"
  //    and overwriting it. Only the most recent request may commit.
  const mounted = useRef(true)
  const requestId = useRef(0)

  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])

  const run = useCallback(
    async ({ background = false } = {}) => {
      const id = ++requestId.current
      if (background) setStale(true)
      else setLoading(true)

      try {
        const result = await fetcher()
        if (!mounted.current || id !== requestId.current) return
        setData(result)
        setError(null)
      } catch (err) {
        if (!mounted.current || id !== requestId.current) return
        setError(err)
      } finally {
        if (mounted.current && id === requestId.current) {
          setLoading(false)
          setStale(false)
        }
      }
    },
    [fetcher],
  )

  useEffect(() => {
    if (!enabled) return
    // Data already on screen? Treat the change as a background refresh so
    // the previous render is held instead of flashing away.
    run({ background: data !== null })
    // `data` is intentionally NOT a dependency - including it would make
    // every successful fetch schedule another one.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [run, enabled])

  const refetch = useCallback(() => run({ background: true }), [run])

  return { data, error, loading, stale, refetch }
}
