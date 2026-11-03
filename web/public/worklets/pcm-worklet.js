/**
 * NegoAI capture worklet.
 *
 * The browser mic runs at 44.1/48 kHz; Gnani Prisma expects 16 kHz mono PCM16
 * in 1024-byte frames (blueprint §0). This worklet does the linear resample and
 * the float -> int16 conversion on the audio thread, then posts ~50 ms chunks.
 */
class NegoAIPcmProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super()
    const opts = options?.processorOptions || {}
    this.targetRate = opts.targetRate || 16000
    this.frameMs = opts.frameMs || 50
    this.ratio = sampleRate / this.targetRate
    this.pos = 0
    this.carry = null
    this.buffer = new Float32Array(Math.round((this.targetRate * this.frameMs) / 1000))
    this.filled = 0
  }

  process(inputs) {
    const input = inputs[0]
    if (!input || input.length === 0) return true
    const channel = input[0]
    if (!channel) return true

    // Prepend the previous block's tail so interpolation is seamless.
    let data = channel
    if (this.carry) {
      data = new Float32Array(this.carry.length + channel.length)
      data.set(this.carry, 0)
      data.set(channel, this.carry.length)
    }

    while (this.pos + 1 < data.length) {
      const i = Math.floor(this.pos)
      const frac = this.pos - i
      const sample = data[i] * (1 - frac) + data[i + 1] * frac
      this.buffer[this.filled++] = sample
      this.pos += this.ratio

      if (this.filled === this.buffer.length) {
        const pcm = new Int16Array(this.buffer.length)
        for (let s = 0; s < this.buffer.length; s++) {
          const v = Math.max(-1, Math.min(1, this.buffer[s]))
          pcm[s] = v < 0 ? v * 0x8000 : v * 0x7fff
        }
        this.port.postMessage(pcm, [pcm.buffer])
        this.filled = 0
      }
    }

    const consumed = Math.floor(this.pos)
    this.pos -= consumed
    this.carry = data.slice(consumed)
    return true
  }
}

registerProcessor('negoai-pcm', NegoAIPcmProcessor)
