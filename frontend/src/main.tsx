import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { PwaSetup } from './components/PwaSetup.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <PwaSetup />
    <App />
  </StrictMode>,
)
