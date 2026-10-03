import { Route, Routes } from "react-router-dom"
import { AppShell } from "./components/AppShell"
import Dashboard from "./pages/Dashboard"
import Hearths from "./pages/Hearths"
import { HearthLayout } from "./pages/hearth/HearthLayout"
import Overview from "./pages/hearth/Overview"
import GraphTab from "./pages/hearth/Graph"
import Code from "./pages/hearth/Code"
import Activity from "./pages/hearth/Activity"
import Settings from "./pages/hearth/Settings"
import Library from "./pages/Library"
import System from "./pages/System"

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/hearths" element={<Hearths />} />
        <Route path="/hearths/:hearthId" element={<HearthLayout />}>
          <Route index element={<Overview />} />
          <Route path="graph" element={<GraphTab />} />
          <Route path="code" element={<Code />} />
          <Route path="activity" element={<Activity />} />
          <Route path="settings" element={<Settings />} />
        </Route>
        <Route path="/library" element={<Library />} />
        <Route path="/system" element={<System />} />
      </Route>
    </Routes>
  )
}
