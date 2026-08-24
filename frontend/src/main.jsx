import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'
import './styles.css'

/**
 * Entry point.
 *
 * StrictMode is on in development, where it deliberately double-invokes
 * effects and renders to surface bugs that would otherwise only appear
 * intermittently - a fetch that forgets to guard against unmount, an effect
 * that is not idempotent. useFetch is written to survive that (see the
 * mounted/requestId guards there). StrictMode is stripped from production
 * builds automatically, so it costs nothing at runtime.
 */
createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
