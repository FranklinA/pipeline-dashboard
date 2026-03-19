import { NavLink, Outlet } from 'react-router-dom'
import styles from './App.module.css'
import { usePipelineContext } from './context/PipelineContext'

function WsIndicator() {
  const { isConnected, reconnecting } = usePipelineContext()
  let label = 'Connected'
  let cls   = styles.wsConnected
  if (reconnecting)      { label = 'Reconnecting...'; cls = styles.wsReconnecting }
  else if (!isConnected) { label = 'Disconnected';   cls = styles.wsDisconnected }
  return <span className={`${styles.wsIndicator} ${cls}`}>{label}</span>
}

export default function App() {
  return (
    <div className={styles.app}>
      <header className={styles.header}>
        <span className={styles.brand}>Pipeline Dashboard</span>
        <nav className={styles.nav}>
          <NavLink to="/" end className={({ isActive }) => isActive ? styles.active : ''}>
            Dashboard
          </NavLink>
          <NavLink to="/pipelines" className={({ isActive }) => isActive ? styles.active : ''}>
            Pipelines
          </NavLink>
        </nav>
        <WsIndicator />
      </header>
      <main className={styles.main}>
        <Outlet />
      </main>
    </div>
  )
}
