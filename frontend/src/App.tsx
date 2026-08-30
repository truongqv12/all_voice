import { RouterProvider } from 'react-router-dom'
import { ApiProvider } from './api/api-context'
import { router } from './app/router'
import { ThemeProvider } from './theme/theme-provider'
import { SelectionProvider } from './store/selection'

export default function App() {
  return (
    <ApiProvider>
      <ThemeProvider>
        <SelectionProvider><RouterProvider router={router} /></SelectionProvider>
      </ThemeProvider>
    </ApiProvider>
  )
}
