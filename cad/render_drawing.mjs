import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import sharp from 'sharp'

const here = path.dirname(fileURLToPath(import.meta.url))

const svg = fs.readFileSync(path.join(here, 'engineering-drawing.svg'))
await sharp(svg, { density: 144 })
  .png()
  .toFile(path.join(here, 'output', 'engineering-drawing.png'))

console.log(path.join(here, 'output', 'engineering-drawing.png'))
