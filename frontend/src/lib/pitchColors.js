// Pitch type color scheme matching Baseball Savant conventions
export const PITCH_COLORS = {
  FF: '#D62728',  // 4-seam fastball  — red
  FA: '#D62728',  // fastball (generic)
  SI: '#FF7F0E',  // sinker           — orange
  FT: '#FF7F0E',  // 2-seam
  FC: '#8C564B',  // cutter           — brown
  SL: '#17BECF',  // slider           — cyan
  ST: '#9EDAE5',  // sweeper          — light cyan
  SV: '#AEC7E8',  // slurve
  CU: '#2CA02C',  // curveball        — green
  KC: '#98DF8A',  // knuckle-curve    — light green
  CH: '#9467BD',  // changeup         — purple
  FS: '#E377C2',  // splitter         — pink
  FO: '#F7B6D2',  // forkball
  KN: '#FFBB78',  // knuckleball      — light orange
  EP: '#C5B0D5',  // eephus
  SC: '#C49C94',  // screwball
  CS: '#DBDB8D',  // slow curve
}

export const PITCH_LABEL = {
  FF: '4-Seam Fastball',
  FA: 'Fastball',
  SI: 'Sinker',
  FT: '2-Seam Fastball',
  FC: 'Cutter',
  SL: 'Slider',
  ST: 'Sweeper',
  SV: 'Slurve',
  CU: 'Curveball',
  KC: 'Knuckle Curve',
  CH: 'Changeup',
  FS: 'Splitter',
  FO: 'Forkball',
  KN: 'Knuckleball',
  EP: 'Eephus',
  SC: 'Screwball',
  CS: 'Slow Curve',
}

export function pitchColor(type) {
  return PITCH_COLORS[type] || '#888888'
}
