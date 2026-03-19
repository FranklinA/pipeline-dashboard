import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import './index.css'
import App from './App.jsx'
import { PipelineProvider } from './context/PipelineContext.jsx'
import { Dashboard } from './components/Dashboard.jsx'
import { PipelineList } from './components/PipelineList.jsx'
import { PipelineDetail } from './components/PipelineDetail.jsx'

const router = createBrowserRouter([
  {
    path: '/',
    element: (
      <PipelineProvider>
        <App />
      </PipelineProvider>
    ),
    children: [
      { index: true,           element: <Dashboard /> },
      { path: 'pipelines',     element: <PipelineList /> },
      { path: 'pipelines/:id', element: <PipelineDetail /> },
    ],
  },
])

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
)
