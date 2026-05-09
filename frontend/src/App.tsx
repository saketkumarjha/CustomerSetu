import { BrowserRouter, Routes, Route } from 'react-router-dom'
import LandingPage from './components/home/LandingPage'
import { MainApp } from './components/home/MainApp'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/"          element={<LandingPage />} />
        <Route path="/complaint" element={<MainApp />} />
      </Routes>
    </BrowserRouter>
  )
}
