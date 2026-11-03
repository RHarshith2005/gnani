import { motion } from 'framer-motion'

const COLUMNS = [2, 4, 5, 3, 5, 4, 2, 4, 3]
const ROWS = 5
const DOT = 4
const GAP = 5

/**
 * Dot-matrix waveform mark from the reference frame. Nine columns, each a
 * run of dots centred on the middle row — a compressed audio waveform.
 */
export default function Logo({ compact = false, tone = 'light' }) {
  const width = COLUMNS.length * (DOT + GAP)
  const height = ROWS * (DOT + GAP)

  return (
    <div className={`logo ${tone === 'dark' ? 'logo--dark' : ''}`}>
      <motion.svg
        width={compact ? 26 : 34}
        height={compact ? 18 : 24}
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label="NegoAI"
        initial={{ opacity: 0, y: -4 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
      >
        {COLUMNS.map((filled, col) => {
          const start = Math.floor((ROWS - filled) / 2)
          return Array.from({ length: filled }).map((_, row) => (
            <circle
              key={`${col}-${row}`}
              cx={col * (DOT + GAP) + DOT / 2}
              cy={(start + row) * (DOT + GAP) + DOT / 2}
              r={DOT / 2}
              fill="currentColor"
            />
          ))
        })}
      </motion.svg>
      {!compact && <span className="logo__word">negoai</span>}
    </div>
  )
}
