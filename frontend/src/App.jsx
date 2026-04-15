import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Landing from './pages/Landing'
import SportsAnalytics from './pages/sports/SportsAnalytics'
import MLBDashboard from './pages/sports/mlb/MLBDashboard'
import PitcherDetail from './pages/sports/mlb/PitcherDetail'
import FairValue from './pages/sports/mlb/FairValue'
import StuffPlusLeaderboard from './pages/sports/mlb/StuffPlusLeaderboard'
import Betting from './pages/Betting'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/"                          element={<Landing />} />
        <Route path="/sports"                    element={<SportsAnalytics />} />
        <Route path="/sports/mlb"                element={<MLBDashboard />} />
        <Route path="/sports/mlb/pitcher/:id"    element={<PitcherDetail />} />
        <Route path="/sports/mlb/fair-value"     element={<FairValue />} />
        <Route path="/sports/mlb/stuff-plus"     element={<StuffPlusLeaderboard />} />
        <Route path="/betting"                   element={<Betting />} />
      </Routes>
    </BrowserRouter>
  )
}
