import { motion } from 'framer-motion'
import { Link } from 'react-router-dom'
import FurTorus from './FurTorus.jsx'
import Logo from './Logo.jsx'
import SocialSquares, { LanguageChips } from './SocialSquares.jsx'
import './Hero.css'

const SCENES = ['Resident', 'Negotiation', 'Savings']
const ease = [0.22, 1, 0.36, 1]

const lineVariants = {
  hidden: { opacity: 0, y: '0.42em', filter: 'blur(10px)' },
  show: (i) => ({
    opacity: 1,
    y: 0,
    filter: 'blur(0px)',
    transition: { duration: 0.85, delay: 0.14 + i * 0.09, ease },
  }),
}

function Chevron({ dir }) {
  return (
    <svg viewBox="0 0 24 24" width="60%" height="60%" fill="none" stroke="currentColor" strokeWidth="1.4">
      <path d={dir === 'left' ? 'M15 5 8 12l7 7' : 'M9 5l7 7-7 7'} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

export default function Hero({
  orbState = 'idle',
  level = 0,
  onMic,
  onPhone,
  onLanguage,
  onStep,
  onCta,
  scene = 0,
  language = 'kn-IN',
  languageOpen = false,
  micOn = false,
}) {
  return (
    <section className="canvas">
      <div className="card hero-card">
        <div className="orb-slot">
          <FurTorus state={orbState} level={level} />
        </div>

        <div className="glass" aria-hidden="true" />

        <div className="brand">
          <Logo />
        </div>

        <nav className="nav" aria-label="Primary">
          <Link className="nav__link" to="/">
            Home
          </Link>
          <a className="nav__link" href="#how">
            How it works
          </a>
          <Link className="nav__link" to="/console">
            Live demo
          </Link>
          <button type="button" className="burger" aria-label="Open menu">
            <span />
            <span />
            <span />
          </button>
        </nav>

        <div className="arrows" role="group" aria-label="Step through demo scenes">
          <motion.button
            type="button"
            className="chev"
            onClick={() => onStep?.(-1)}
            aria-label="Previous scene"
            whileHover={{ scale: 1.12 }}
            whileTap={{ scale: 0.94 }}
          >
            <Chevron dir="left" />
          </motion.button>
          <motion.button
            type="button"
            className="chev"
            onClick={() => onStep?.(1)}
            aria-label="Next scene"
            whileHover={{ scale: 1.12 }}
            whileTap={{ scale: 0.94 }}
          >
            <Chevron dir="right" />
          </motion.button>
        </div>

        <div className="scene-rail" aria-hidden="true">
          {SCENES.map((label, i) => (
            <span key={label} className={i === scene ? 'is-active' : ''}>
              {label}
            </span>
          ))}
        </div>

        <div className="hero-copy">
          <h1>
            {['Your Society.', 'One AI.', 'Better Deals.'].map((line, i) => (
              <motion.span
                key={line}
                custom={i}
                variants={lineVariants}
                initial="hidden"
                animate="show"
              >
                {line}
              </motion.span>
            ))}
          </h1>
          <motion.p
            className="sub"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.5, duration: 0.8, ease }}
          >
            We Listen <span>|</span> We Negotiate <span>|</span> We Save.
          </motion.p>
          <motion.button
            type="button"
            className="cta"
            onClick={onCta}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.62, duration: 0.7, ease }}
            whileHover={{ y: -2 }}
            whileTap={{ scale: 0.985 }}
          >
            Try voice demo
            <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="1.8">
              <path d="M5 12h13M13 6l6 6-6 6" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </motion.button>
        </div>

        <SocialSquares
          onMic={onMic}
          onPhone={onPhone}
          onLanguage={onLanguage}
          languageOpen={languageOpen}
          micOn={micOn}
          language={language}
        />

        <LanguageChips
          open={languageOpen}
          value={language}
          onChange={(lang) => {
            onLanguage?.(lang)
          }}
          align="right"
        />

        <div className="grain" />
      </div>

      <p className="powered">
        Voice in Kannada · हिन्दी · English — engine-decided prices, simulated vendors
      </p>
    </section>
  )
}
