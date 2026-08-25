import { BrowserRouter, Route, Routes } from 'react-router-dom'
import Home from './pages/Home/Home'
import NewTicket from './pages/NewTicket/NewTicket'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<NewTicket />} />
        <Route path="/home" element={<Home />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
