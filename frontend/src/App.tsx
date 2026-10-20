import { Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import Chat from "./pages/Chat";
import Dashboard from "./pages/Dashboard";
import Library from "./pages/Library";
import Quiz from "./pages/Quiz";
import SearchPage from "./pages/SearchPage";
import Topics from "./pages/Topics";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="library" element={<Library />} />
        <Route path="search" element={<SearchPage />} />
        <Route path="chat" element={<Chat />} />
        <Route path="topics" element={<Topics />} />
        <Route path="quiz" element={<Quiz />} />
        <Route path="*" element={<p className="text-ink-soft">Page not found.</p>} />
      </Route>
    </Routes>
  );
}
