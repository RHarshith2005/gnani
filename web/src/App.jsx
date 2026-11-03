import { useEffect } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import HomePage from './pages/HomePage.jsx'
import VoiceConsole from './components/VoiceConsole.jsx'
import NegotiationRoom from './components/NegotiationRoom.jsx'
import AdminApproval from './components/AdminApproval.jsx'
import Replay from './components/Replay.jsx'
import DemoBar from './components/DemoBar.jsx'
import { installEventSideEffects } from './lib/voice.js'

export default function App() {
  const location = useLocation()

  useEffect(() => {
    installEventSideEffects()
  }, [])

  return (
    <>
      <Routes location={location}>
        <Route path="/" element={<HomePage />} />
        <Route path="/console" element={<VoiceConsole />} />
        <Route path="/room" element={<NegotiationRoom />} />
        <Route path="/admin" element={<AdminApproval />} />
        <Route path="/replay" element={<Replay />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <DemoBar />
    </>
  )
}
