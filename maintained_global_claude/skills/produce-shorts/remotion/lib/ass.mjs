// Minimal, strict Advanced SubStation Alpha (.ass) reader.
//
// The .ass emitted by scripts/align_subtitles.py is the TIMING TRUTH for the
// render — props.json subtitle events are derived from it, never from the
// design-time ranges in clip.yaml. Anything this parser does not understand is
// an error: a silently dropped override tag is a silently wrong render.

/** Override tags that carry no information this renderer needs (documented no-ops). */
const IGNORED_TAGS = [
  'fad', 'fade', 'blur', 'be', 'fsp', 'fn', 'fs', 'bord', 'shad', 'xbord', 'ybord',
  'xshad', 'yshad', '3c', '4c', '2c', 'alpha', '1a', '2a', '3a', '4a', 'q', 'k', 'K',
  'kf', 'ko', 't', 'move', 'org', 'clip', 'iclip', 'p', 'pbo', 'fr', 'frx', 'fry',
  'frz', 'fax', 'fay', 'fscx', 'fscy', 'u', 's',
];

const fail = (msg) => {
  throw new Error(`.ass parse error: ${msg}`);
};

/** `&HAABBGGRR` / `&HBBGGRR&` -> `#RRGGBB` (+ alpha when the file sets one). */
export const assColor = (raw) => {
  const hex = String(raw).trim().replace(/^&H/i, '').replace(/&$/, '');
  if (!/^[0-9a-f]{1,8}$/i.test(hex)) fail(`not a colour: ${JSON.stringify(raw)}`);
  const padded = hex.padStart(8, '0').toUpperCase();
  const [aa, bb, gg, rr] = [padded.slice(0, 2), padded.slice(2, 4), padded.slice(4, 6), padded.slice(6, 8)];
  const rgb = `#${rr}${gg}${bb}`;
  const inverseAlpha = parseInt(aa, 16);
  return inverseAlpha === 0 ? rgb : `rgba(${parseInt(rr, 16)}, ${parseInt(gg, 16)}, ${parseInt(bb, 16)}, ${((255 - inverseAlpha) / 255).toFixed(3)})`;
};

/** `H:MM:SS.cc` -> seconds. */
export const assTime = (raw) => {
  const m = /^(\d+):(\d{2}):(\d{2})\.(\d{2})$/.exec(String(raw).trim());
  if (m === null) fail(`not a timestamp: ${JSON.stringify(raw)} (expected H:MM:SS.cc)`);
  const [, h, mm, ss, cc] = m;
  return Number(h) * 3600 + Number(mm) * 60 + Number(ss) + Number(cc) / 100;
};

const splitFormat = (line, section) => {
  const idx = line.indexOf(':');
  if (idx === -1) fail(`malformed Format line in ${section}: ${line}`);
  return line
    .slice(idx + 1)
    .split(',')
    .map((f) => f.trim());
};

/**
 * Split a Dialogue text field into styled spans, honouring the override tags
 * this renderer supports and throwing on any tag it does not.
 */
const parseDialogueText = (raw, style) => {
  const base = { color: style.primaryColour, bold: style.bold, italic: style.italic };
  let current = { ...base };
  let override = { align: null, posX: null, posY: null };
  const spans = [];

  const push = (text) => {
    if (text === '') return;
    const last = spans[spans.length - 1];
    if (last !== undefined && last.color === current.color && last.bold === current.bold && last.italic === current.italic) {
      last.text += text;
      return;
    }
    spans.push({ text, ...current });
  };

  const applyTag = (tag) => {
    if (tag === '') return;
    if (tag === 'r') {
      current = { ...base };
      return;
    }
    if (/^r.+/.test(tag)) fail(`style-reset-to-named-style (\\${tag}) is not supported`);

    let m;
    if ((m = /^b(\d+)$/.exec(tag)) !== null) {
      current = { ...current, bold: Number(m[1]) !== 0 };
      return;
    }
    if ((m = /^i([01])$/.exec(tag)) !== null) {
      current = { ...current, italic: m[1] === '1' };
      return;
    }
    if ((m = /^(?:1?c)(&H[0-9a-f]+&?)$/i.exec(tag)) !== null) {
      current = { ...current, color: assColor(m[1]) };
      return;
    }
    if ((m = /^an?(\d)$/.exec(tag)) !== null) {
      override = { ...override, align: Number(m[1]) };
      return;
    }
    if ((m = /^pos\(\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*\)$/.exec(tag)) !== null) {
      override = { ...override, posX: Number(m[1]), posY: Number(m[2]) };
      return;
    }
    const name = /^([a-zA-Z0-9]+)/.exec(tag)?.[1] ?? tag;
    if (IGNORED_TAGS.includes(name)) return;
    fail(`unsupported override tag \\${tag} — teach lib/ass.mjs about it or drop it from align_subtitles.py`);
  };

  for (const chunk of raw.split(/(\{[^}]*\})/)) {
    if (chunk === '') continue;
    if (chunk.startsWith('{') && chunk.endsWith('}')) {
      const body = chunk.slice(1, -1);
      if (body.startsWith('\\')) {
        for (const tag of body.slice(1).split('\\')) applyTag(tag.trim());
      }
      // A `{...}` block without a leading backslash is an .ass comment.
      continue;
    }
    push(chunk.replace(/\\N/g, '\n').replace(/\\n/g, '\n').replace(/\\h/g, ' '));
  }

  if (spans.length === 0) fail(`dialogue event has no visible text: ${JSON.stringify(raw)}`);
  return { spans, override };
};

/**
 * @param {string} content raw .ass file text
 * @returns {{playResX: number, playResY: number, styles: Map<string, object>, events: object[]}}
 */
export function parseAss(content) {
  const lines = content.split(/\r?\n/);
  let section = null;
  const info = {};
  const styles = new Map();
  const events = [];
  let styleFormat = null;
  let eventFormat = null;

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (line === '' || line.startsWith(';')) continue;
    if (line.startsWith('[') && line.endsWith(']')) {
      section = line.slice(1, -1).toLowerCase();
      continue;
    }

    if (section === 'script info') {
      const [key, ...rest] = line.split(':');
      info[key.trim().toLowerCase()] = rest.join(':').trim();
      continue;
    }

    if (section !== null && section.includes('styles')) {
      if (line.startsWith('Format:')) {
        styleFormat = splitFormat(line, '[V4+ Styles]');
        continue;
      }
      if (!line.startsWith('Style:')) continue;
      if (styleFormat === null) fail('a Style line appeared before the Format line');
      const values = line.slice('Style:'.length).split(',').map((v) => v.trim());
      if (values.length !== styleFormat.length) {
        fail(`Style line has ${values.length} fields, Format declares ${styleFormat.length}: ${line}`);
      }
      const row = Object.fromEntries(styleFormat.map((f, i) => [f.toLowerCase(), values[i]]));
      for (const required of ['name', 'fontname', 'fontsize', 'primarycolour', 'alignment', 'marginv']) {
        if (row[required] === undefined) fail(`[V4+ Styles] Format is missing the ${required} column`);
      }
      styles.set(row.name, {
        name: row.name,
        fontName: row.fontname,
        fontSize: Number(row.fontsize),
        primaryColour: assColor(row.primarycolour),
        outlineColour: row.outlinecolour === undefined ? '#000000' : assColor(row.outlinecolour),
        outline: row.outline === undefined ? 0 : Number(row.outline),
        shadow: row.shadow === undefined ? 0 : Number(row.shadow),
        bold: row.bold !== undefined && Number(row.bold) !== 0,
        italic: row.italic !== undefined && Number(row.italic) !== 0,
        alignment: Number(row.alignment),
        marginL: Number(row.marginl ?? 0),
        marginR: Number(row.marginr ?? 0),
        marginV: Number(row.marginv),
      });
      continue;
    }

    if (section === 'events') {
      if (line.startsWith('Format:')) {
        eventFormat = splitFormat(line, '[Events]');
        continue;
      }
      if (!line.startsWith('Dialogue:')) continue;
      if (eventFormat === null) fail('a Dialogue line appeared before the Format line');
      const body = line.slice('Dialogue:'.length);
      // The Text field is last and may itself contain commas.
      const parts = body.split(',');
      const head = parts.slice(0, eventFormat.length - 1).map((v) => v.trim());
      const text = parts.slice(eventFormat.length - 1).join(',');
      const row = Object.fromEntries(eventFormat.map((f, i) => [f.toLowerCase(), i === eventFormat.length - 1 ? text : head[i]]));
      const style = styles.get(row.style);
      if (style === undefined) fail(`Dialogue references unknown style ${JSON.stringify(row.style)}`);
      const { spans, override } = parseDialogueText(row.text, style);
      events.push({
        start: assTime(row.start),
        end: assTime(row.end),
        style,
        spans,
        marginV: Number(row.marginv ?? 0),
        alignment: override.align ?? style.alignment,
        posX: override.posX,
        posY: override.posY,
        text: spans.map((s) => s.text).join(''),
      });
    }
  }

  if (styles.size === 0) fail('no [V4+ Styles] Style lines found');
  if (events.length === 0) fail('no [Events] Dialogue lines found');

  const playResX = Number(info.playresx ?? 0);
  const playResY = Number(info.playresy ?? 0);
  if (!Number.isFinite(playResX) || playResX <= 0) fail('[Script Info] PlayResX missing or not positive');
  if (!Number.isFinite(playResY) || playResY <= 0) fail('[Script Info] PlayResY missing or not positive');

  return {
    playResX,
    playResY,
    styles,
    events: events.sort((a, b) => a.start - b.start),
  };
}
