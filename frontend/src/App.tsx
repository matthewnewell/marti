import { Route, Routes } from 'react-router-dom'
import AppLayout from './components/AppLayout'
import ProjectDetailPage from './pages/ProjectDetailPage'
import ProjectsPage from './pages/ProjectsPage'
import SplashPage from './pages/SplashPage'
import './App.css'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<ProjectsPage />} />
      <Route path="/about" element={<SplashPage />} />
      <Route path="/projects/:projectId" element={<AppLayout />}>
        <Route index element={<ProjectDetailPage />} />
      </Route>
    </Routes>
  )
}
