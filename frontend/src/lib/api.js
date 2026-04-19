import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || ''

const api = axios.create({ baseURL: API_URL })

export const mlb = {
  pitches: (params)          => api.get('/api/mlb/pitches', { params }),
  pitchers: (params)         => api.get('/api/mlb/pitchers', { params }),
  pitcherSummary: (id, p)      => api.get(`/api/mlb/pitchers/${id}/summary`, { params: p }),
  pitcherPitches: (id, p)      => api.get(`/api/mlb/pitchers/${id}/pitches`, { params: p }),
  pitcherGames: (id, p)        => api.get(`/api/mlb/pitchers/${id}/games`, { params: p }),
  pitcherGameSummary: (id, pk) => api.get(`/api/mlb/pitchers/${id}/game-summary`, { params: { game_pk: pk } }),
  pitchTypeNorms: (p)          => api.get('/api/mlb/pitch-type-norms', { params: p }),
  gameDates: (p)               => api.get('/api/mlb/game-dates', { params: p }),
  pitchersByDate: (p)          => api.get('/api/mlb/pitchers-by-date', { params: p }),
  leaderboardPitching: (p)   => api.get('/api/mlb/leaderboards/pitching', { params: p }),
  leaderboardHitting: (p)    => api.get('/api/mlb/leaderboards/hitting', { params: p }),
  teams: (p)                 => api.get('/api/mlb/teams', { params: p }),
  pitchTypes: ()             => api.get('/api/mlb/pitch-types'),
  dataStatus: ()             => api.get('/api/mlb/data-status'),
}

export const fairValue = {
  stuffPlusLeaderboard: (params) => api.get('/api/fair-value/stuff-plus/leaderboard', { params }),
}

export const hrFairValue = {
  games: (params) => api.get('/api/hr-fair-value/games', { params }),
  game: (gamePk) => api.get(`/api/hr-fair-value/games/${gamePk}`),
  run: (params) => api.post('/api/hr-fair-value/run', null, { params }),
}

export default api
