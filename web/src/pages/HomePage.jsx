import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import Hero from '../components/Hero.jsx'
import Logo from '../components/Logo.jsx'
import { useSession, LANGUAGES } from '../state/session.js'
import { voice } from '../lib/voice.js'

const ease = [0.22, 1, 0.36, 1]

const STEPS = [
  {
    n: '01',
    title: 'Listen',
    body: 'A resident speaks their weekly need in Kannada, Hindi, English or a code-mix. NegoAI reads the quantity back in words and only counts it once confirmed.',
  },
  {
    n: '02',
    title: 'Negotiate',
    body: 'The engine sets every counter. The LLM only speaks them. Three suppliers, three rounds, free delivery asked once — and no offer ever accepted by the agent.',
  },
  {
    n: '03',
    title: 'Save',
    body: 'The committee sees verified demand, the best eligible quote, weekly savings and the risks — then approves once, instead of 120 families haggling alone.',
  },
]

const SCENE_ROUTES = ['/console', '/room', '/admin']

export default function HomePage() {
  const orb = useSession((s) => s.orb)
  const level = useSession((s) => s.level)
  const language = useSession((s) => s.language)
  const micOn = useSession((s) => s.micOn)
  const [langOpen, setLangOpen] = useState(false)
  const [scene, setScene] = useState(0)
  const navigate = useNavigate()

  const step = (dir) => {
    const next = (scene + dir + SCENE_ROUTES.length) % SCENE_ROUTES.length
    setScene(next)
    navigate(SCENE_ROUTES[next])
  }

  return (
    <div className="home">
      <Hero
        orbState={orb}
        level={level}
        scene={scene}
        language={language}
        languageOpen={langOpen}
        micOn={micOn}
        onMic={() => {
          voice.startLive(language)
          navigate('/console')
        }}
        onCta={() => {
          voice.startLive(language)
          navigate('/console')
        }}
        onPhone={() => {}}
        onLanguage={() => setLangOpen((v) => !v)}
        onStep={step}
      />

      <section className="how" id="how">
        <header className="how__head">
          <Logo compact />
          <p className="how__eyebrow">How it works</p>
          <h2 className="how__title">
            One AI negotiates. <br />
            The whole society benefits.
          </h2>
          <p className="how__lede">
            Why should 120 families haggle alone over the same water cans? NegoAI aggregates demand,
            negotiates like a procurement desk, and hands the committee one decision instead of a
            hundred chats.
          </p>
        </header>

        <div className="how__grid">
          {STEPS.map((stepItem, i) => (
            <motion.article
              key={stepItem.n}
              className="how__card"
              initial={{ opacity: 0, y: 22 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.4 }}
              transition={{ duration: 0.6, delay: i * 0.08, ease }}
            >
              <span className="how__n">{stepItem.n}</span>
              <h3>{stepItem.title}</h3>
              <p>{stepItem.body}</p>
            </motion.article>
          ))}
        </div>

        <div className="how__actions">
          <Link className="btn-solid" to="/console">
            Try the voice console
          </Link>
          <Link className="btn-outline" to="/room?demo=1">
            Watch the negotiation
          </Link>
          <button
            type="button"
            className="how__lang"
            onClick={() => {
              const index = LANGUAGES.findIndex((l) => l.id === language)
              voice.setLanguage(LANGUAGES[(index + 1) % LANGUAGES.length].id)
            }}
          >
            Language: {LANGUAGES.find((l) => l.id === language)?.name} →
          </button>
        </div>

        <p className="how__note">
          Synthetic data only. Every supplier is simulated and labelled on screen. Prices and
          savings are computed by the negotiation engine; Gnani Prisma (STT) and Timbre (TTS) power
          the voice loop, with a scripted fallback when keys are absent.
        </p>
      </section>
    </div>
  )
}
