import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import PolygonBackground from './components/PolygonBackground.jsx'

createRoot(document.getElementById('root')).render(
  <>
    <PolygonBackground />
    <App />
  </>
)