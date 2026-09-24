import { DepotBackBar } from '@conways/drawer'
import { Navigate, Route, Routes, useParams } from 'react-router-dom'
import Layout from './components/Layout'
import { PersonaProvider } from './lib/persona'
import { ScopeProvider } from './lib/scope'
import ConstraintsPage from './pages/ConstraintsPage'
import HotFlagsPage from './pages/HotFlagsPage'
import MaterialPage from './pages/MaterialPage'
import RoutingPage from './pages/RoutingPage'
import SplashPage from './pages/SplashPage'
import TriagePage from './pages/TriagePage'
import './App.css'

/** Old per-project links (Depot tiles, bookmarks) land on Routing scoped to that project. */
function ProjectRedirect() {
  const { projectId } = useParams<{ projectId: string }>()
  return <Navigate to={`/routing?project=${projectId}`} replace />
}

export default function App() {
  return (
    <PersonaProvider>
      <ScopeProvider>
        <DepotBackBar />
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Navigate to="/material" replace />} />
            <Route path="/material" element={<MaterialPage />} />
            <Route path="/routing" element={<RoutingPage />} />
            <Route path="/triage" element={<TriagePage />} />
            <Route path="/constraints" element={<ConstraintsPage />} />
            <Route path="/hot-flags" element={<HotFlagsPage />} />
            <Route path="/about" element={<SplashPage />} />
          </Route>
          <Route path="/tradeoffs" element={<Navigate to="/triage" replace />} />
          <Route path="/projects" element={<Navigate to="/routing" replace />} />
          <Route path="/projects/:projectId" element={<ProjectRedirect />} />
        </Routes>
      </ScopeProvider>
    </PersonaProvider>
  )
}
