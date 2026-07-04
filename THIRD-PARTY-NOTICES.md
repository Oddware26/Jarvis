# Third-Party Notices

Oddvark is released under the MIT License (see [LICENSE](LICENSE)). It bundles the
following third-party assets, each under its own license. The required license
texts are included in this repository.

---

## Fonts

### Rubik
- License: SIL Open Font License 1.1
- Copyright 2015 The Rubik Project Authors (https://github.com/googlefonts/rubik)
- Full license: [`frontend/assets/fonts/Rubik-OFL.txt`](frontend/assets/fonts/Rubik-OFL.txt)
- Files: `frontend/assets/fonts/rubik-*.woff2`

### OpenDyslexic
- License: SIL Open Font License 1.1
- Copyright (c) 2019, Abbie Gonzalez (https://antijingoist.itch.io/), with Reserved Font Name OpenDyslexic.
- Full license: [`frontend/assets/fonts/OpenDyslexic-OFL.txt`](frontend/assets/fonts/OpenDyslexic-OFL.txt)
- Files: `frontend/assets/fonts/opendyslexic-*.woff2`

---

## Icons

### Hugeicons Free 4.2.2
- License: MIT
- Source: https://hugeicons.com
- File: `frontend/assets/js/hugeicons.js` (SVG path data extracted from `@hugeicons/core-free-icons`)

```
MIT License

Copyright (c) Hugeicons Pro (https://hugeicons.com)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## Runtime dependencies (not bundled)

These tools run locally and are installed separately by the user; they are **not**
redistributed in this repository and remain under their own licenses:

- **Ollama** — local LLM runtime (https://ollama.com)
- **openai-whisper** — speech-to-text (MIT)
- **Coqui XTTS / TTS** — text-to-speech (model weights under the Coqui Public Model License)
- **Z-Image-Turbo** (Tongyi-MAI) — optional local image generation
