import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./contexts/AuthContext";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Opportunities from "./pages/Opportunities";
import Logs from "./pages/Logs";
import Filters from "./pages/Filters";
import Admin from "./pages/Admin";
import Profile from "./pages/Profile";
import Upload from "./pages/Upload";

function PrivateRoute({ children, adminOnly = false }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="flex h-screen items-center justify-center text-gray-400">Carregando...</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (adminOnly && user.role !== "admin") return <Navigate to="/" replace />;
  return children;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            path="/"
            element={
              <PrivateRoute>
                <Layout />
              </PrivateRoute>
            }
          >
            <Route index element={<Dashboard />} />
            <Route path="oportunidades" element={<Opportunities />} />
            <Route path="filtros" element={<Filters />} />
            <Route path="logs" element={<Logs />} />
            <Route path="upload" element={<Upload />} />
            <Route path="perfil" element={<Profile />} />
            <Route
              path="admin"
              element={
                <PrivateRoute adminOnly>
                  <Admin />
                </PrivateRoute>
              }
            />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
