import { useState } from 'react'
import { useSession, LANGUAGES } from '../state/session.js'
import { voice } from '../lib/voice.js'
import { ROLE_LABEL } from '../lib/format.js'
import { DESIGN_FLAGS } from './flags.js'
import './design.css'

const SCRIPT_PREVIEW = {
  'kn-IN': 'ನಮಸ್ಕಾರ · ಕನ್ನಡ ಲಿಪಿ',
  'hi-IN': 'नमस्ते · देवनागरी लिपि',
  'en-IN': 'Hello · Latin script',
}

function ChatBubble({ line, newest }) {
  const role = line.role === 'agent' ? 'NegoAI' : line.role === 'vendor' ? line.vendor || 'Simulated vendor' : ROLE_LABEL[line.role] || line.role
  return (
    <article className={`design-chat design-chat--${line.role}`} aria-label={`${role} message`}>
      <div className="design-chat__meta">
        <strong>{role}</strong>
        {line.role === 'vendor' ? <span>Simulated</span> : null}
        {line.lang ? <span>{line.lang}</span> : null}
        {newest ? <span>Latest</span> : null}
      </div>
      <p lang={line.lang}>{line.text}</p>
      {line.subtitle && line.subtitle !== line.text ? <small>{line.subtitle}</small> : null}
    </article>
  )
}

export function ConsoleLine({ line, newest }) {
  if (!DESIGN_FLAGS.console) return null
  return <ChatBubble line={line} newest={newest} />
}

export function ConsoleReadback({ confirm }) {
  if (!DESIGN_FLAGS.console || !confirm) return null
  return (
    <section className="console-readback" aria-label="Quantity read-back">
      <span>Read back for confirmation</span>
      <p>{confirm.text}</p>
      <small>NegoAI will only record this request after you confirm.</small>
    </section>
  )
}

export function ConsoleStatus({ status, hasLines, error }) {
  if (!DESIGN_FLAGS.console) return null
  if (status === 'connecting' && !hasLines) {
    return <p className="console-status" role="status">Connecting to NegoAI… Your conversation will appear here.</p>
  }
  if (status === 'error' || error) {
    return <p className="console-status console-status--error" role="alert">{error || 'Could not connect. Your saved conversation remains on screen.'}</p>
  }
  if (status === 'ready' && !hasLines) {
    return <p className="console-status" role="status">You’re connected. Tell NegoAI what your household needs this week.</p>
  }
  return null
}

export function ScriptPreview({ language }) {
  if (!DESIGN_FLAGS.console) return null
  return (
    <div className="script-preview" aria-live="polite">
      <span>{LANGUAGES.find((item) => item.id === language)?.name || language}</span>
      <small lang={language}>{SCRIPT_PREVIEW[language] || ''}</small>
    </div>
  )
}

export function MobileMicSheet() {
  const micOn = useSession((state) => state.micOn)
  const [open, setOpen] = useState(false)
  if (!DESIGN_FLAGS.console) return null
  return (
    <div className="mobile-mic">
      <button type="button" className="mobile-mic__trigger" onClick={() => setOpen(true)}>
        {micOn ? 'Microphone on · controls' : 'Open microphone controls'}
      </button>
      {open ? (
        <div className="mobile-mic__scrim" onClick={() => setOpen(false)}>
          <section className="mobile-mic__sheet" role="dialog" aria-modal="true" aria-labelledby="mobile-mic-title"
            onClick={(event) => event.stopPropagation()}>
            <h3 id="mobile-mic-title">Voice controls</h3>
            <p>Speak naturally. NegoAI reads the request back before recording it.</p>
            <button type="button" className="btn-solid" onClick={() => voice.toggleMic()}>
              {micOn ? 'Turn microphone off' : 'Turn microphone on'}
            </button>
            <button type="button" className="btn-outline" onClick={() => setOpen(false)}>Close</button>
          </section>
        </div>
      ) : null}
    </div>
  )
}
