/* =====================================================================
 *  genvoice.js  -  renders the pet's fixed voice lines with meSpeak
 *  (a JS port of eSpeak, i.e. formant synthesis - the same family of
 *  algorithm a 1992 talking toy would have used).
 *
 *  Output: art/voice/NN_name.wav  (16-bit mono, whatever rate eSpeak gives)
 *  tools/mkvoice.py then folds them into VOICE.DAT: 8 kHz, 8-bit unsigned.
 *
 *  run:  NODE_PATH=<workspace>/node_modules node tools/genvoice.js
 * ===================================================================== */
const fs = require('fs');
const path = require('path');
const meSpeak = require('mespeak');

const root = path.join(process.env.NODE_PATH || '', 'mespeak');
meSpeak.loadConfig(JSON.parse(fs.readFileSync(path.join(root, 'src', 'mespeak_config.json'), 'utf8')));

const outDir = path.join(__dirname, '..', 'art', 'voice');
fs.mkdirSync(outDir, { recursive: true });

const VOICES = {
  'en/en-us': path.join(root, 'voices', 'en', 'en-us.json'),
  'zh':       path.join(root, 'voices', 'zh.json')
};
const loaded = {};

function loadVoice(v) {
  if (!loaded[v]) {
    meSpeak.loadVoice(JSON.parse(fs.readFileSync(VOICES[v], 'utf8')));
    loaded[v] = true;
  }
}

/* index order is the phrase number the 16-bit app uses - do not reorder */
const LINES = [
  ['00_hello',      'en/en-us', 'Hello!'],
  ['01_whale',      'en/en-us', 'I am a deep sea whale.'],
  ['02_think',      'en/en-us', 'Let us think step by step.'],
  ['03_nice',       'en/en-us', 'Nice to meet you.'],
  ['04_sleepy',     'en/en-us', 'I am sleepy. Good night.'],
  ['05_ni_hao',     'zh', '你好，我是深海鲸鱼。'],
  ['06_think_zh',   'zh', '让我想一想。']
];

const OPTS = { speed: 150, pitch: 62, amplitude: 180, wordgap: 0 };

for (const [name, lang, text] of LINES) {
  loadVoice(lang);
  const buf = meSpeak.speak(text, Object.assign({ rawdata: 'ArrayBuffer', voice: lang }, OPTS));
  if (!buf) { console.error('FAILED', name); continue; }
  const p = path.join(outDir, name + '.wav');
  fs.writeFileSync(p, Buffer.from(buf));
  console.log('%-12s %-3s %6d bytes  %s', name, lang, buf.byteLength, text);
}
