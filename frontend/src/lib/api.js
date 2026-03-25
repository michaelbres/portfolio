import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || ''

const api = axios.create({ baseURL: API_URL })

export const mlb = {
  pitches: (params)          => api.get('/api/mlb/pitches', { params }),
  pitchers: (params)         => api.get('/api/mlb/pitchers', { params }),
  pitcherSummary: (id, p)    => api.get(`/api/mlb/pitchers/${id}/summary`, { params: p }),
  pitcherPitches: (id, p)    => api.get(`/api/mlb/pitchers/${id}/pitches`, { params: p }),
  leaderboardPitching: (p)   => api.get('/api/mlb/leaderboards/pitching', { params: p }),
  leaderboardHitting: (p)    => api.get('/api/mlb/leaderboards/hitting', { params: p }),
  teams: (p)                 => api.get('/api/mlb/teams', { params: p }),
  pitchTypes: ()             => api.get('/api/mlb/pitch-types'),
  dataStatus: ()             => api.get('/api/mlb/data-status'),
}

export default api
