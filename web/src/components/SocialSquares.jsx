import { AnimatePresence, motion } from 'framer-motion'

function MicIcon() {
  return (
    <svg viewBox="0 0 24 24" width="55%" height="55%" fill="none" stroke="currentColor" strokeWidth="1.6">
      <rect x="9" y="3" width="6" height="11" rx="3" />
      <path d="M5.5 11.5a6.5 6.5 0 0 0 13 0M12 18v3" strokeLinecap="round" />
    </svg>
  )
}

function PhoneIcon() {
  return (
    <svg viewBox="0 0 24 24" width="55%" height="55%" fill="none" stroke="currentColor" strokeWidth="1.6">
      <path
        d="M5 4h3l1.6 4-2 1.4a12 12 0 0 0 5 5l1.4-2 4 1.6v3a2 2 0 0 1-2.2 2A16 16 0 0 1 3 6.2 2 2 0 0 1 5 4Z"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function GlobeIcon() {
  return (
    <svg viewBox="0 0 24 24" width="55%" height="55%" fill="none" stroke="currentColor" strokeWidth="1.6">
      <circle cx="12" cy="12" r="8.5" />
      <path d="M3.5 12h17M12 3.5c2.6 2.4 2.6 14.6 0 17-2.6-2.4-2.6-14.6 0-17Z" />
    </svg>
  )
}

/**
 * The three outlined squares bottom-right: mic starts the web conversation,
 * phone stays disabled until telephony genuinely works, globe opens the
 * language chips (blueprint §1.4).
 */
export default function SocialSquares({ onMic, onPhone, onLanguage, languageOpen, micOn, language }) {
  return (
    <div className="socials" role="group" aria-label="Conversation actions">
      <button
        type="button"
        className={`social ${micOn ? 'is-live' : ''}`}
        onClick={onMic}
        aria-label={micOn ? 'Stop microphone' : 'Start voice conversation'}
        title="Talk to NegoAI"
      >
        <MicIcon />
      </button>

      <button
        type="button"
        className="social social--disabled"
        onClick={onPhone}
        aria-label="Phone calls coming soon"
        aria-disabled="true"
        title="Phone calls — coming soon"
      >
        <PhoneIcon />
        <span className="social__tooltip" role="tooltip">
          Phone line — coming soon
        </span>
      </button>

      <button
        type="button"
        className={`social ${languageOpen ? 'is-active' : ''}`}
        onClick={onLanguage}
        aria-label={`Language: ${language}. Change language`}
        aria-expanded={languageOpen}
        title="Change language"
      >
        <GlobeIcon />
      </button>
    </div>
  )
}

export function LanguageChips({ open, value, onChange, align = 'right' }) {
  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className={`lang-chips lang-chips--${align}`}
          initial={{ opacity: 0, y: 8, filter: 'blur(4px)' }}
          animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
          exit={{ opacity: 0, y: 6, filter: 'blur(4px)' }}
          transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
        >
          {[
            { id: 'kn-IN', label: 'ಕನ್ನಡ' },
            { id: 'hi-IN', label: 'हिन्दी' },
            { id: 'en-IN', label: 'English' },
          ].map((lang) => (
            <button
              key={lang.id}
              type="button"
              className={`chip ${value === lang.id ? 'is-active' : ''}`}
              onClick={() => onChange(lang.id)}
            >
              {lang.label}
              <span className="chip__code">{lang.id.split('-')[0].toUpperCase()}</span>
            </button>
          ))}
        </motion.div>
      )}
    </AnimatePresence>
  )
}
