import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth";
import { ToastProvider } from "./toast";
import { Layout } from "./components/Layout";
import { BootFilm } from "./components/BootFilm";
import { LoginPage } from "./pages/Login";
import { HomePage } from "./pages/Home";
import { DevicePage } from "./pages/Device";
import { MissionsPage } from "./pages/Missions";
import { MissionDetailPage } from "./pages/MissionDetail";
import { MemoryPage } from "./pages/Memory";
import { RoutinesPage } from "./pages/Routines";
import { ProvidersPage } from "./pages/Providers";
import { ChatPage } from "./pages/Chat";
import { DiscoverPage } from "./pages/Discover";
import { PairPage } from "./pages/Pair";
import { SettingsPage } from "./pages/Settings";
import { JournalPage } from "./pages/Journal";
import { PresentationPage } from "./pages/Presentation";

function Splash() {
  return (
    <main className="splash" role="status">
      <span className="spinner" aria-hidden="true" />
      <p>Ouverture de la session locale…</p>
    </main>
  );
}

function Protected({ children }: { children: React.ReactNode }) {
  const { me, loading } = useAuth();
  const location = useLocation();
  if (loading) return <Splash />;
  if (!me) {
    // La racine présente le produit ; les autres pages renvoient à la connexion.
    if (location.pathname === "/") return <PresentationPage />;
    return <Navigate to="/connexion" replace state={{ from: location.pathname }} />;
  }
  return <>{children}</>;
}

function NotFound() {
  return (
    <main className="login-page">
      <section className="login-card">
        <p className="eyebrow">404</p>
        <h1>Page introuvable</h1>
        <p className="page-lead">Cette route ne correspond à aucune vue du site.</p>
        <a className="btn btn-primary" href="/">
          Revenir à l'accueil
        </a>
      </section>
    </main>
  );
}

export function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          <BootFilm />
          <Routes>
            <Route path="/connexion" element={<LoginPage />} />
            <Route path="/presentation" element={<PresentationPage />} />
            <Route path="/appairer" element={<PairPage />} />
            <Route
              element={
                <Protected>
                  <Layout />
                </Protected>
              }
            >
              <Route index element={<HomePage />} />
              <Route path="/boitier" element={<DevicePage />} />
              <Route path="/missions" element={<MissionsPage />} />
              <Route path="/missions/:id" element={<MissionDetailPage />} />
              <Route path="/memoire" element={<MemoryPage />} />
              <Route path="/routines" element={<RoutinesPage />} />
              <Route path="/ia" element={<ProvidersPage />} />
              <Route path="/miles" element={<ChatPage />} />
              <Route path="/decouvrir" element={<DiscoverPage />} />
              <Route path="/reglages" element={<SettingsPage />} />
              <Route path="/journal" element={<JournalPage />} />
            </Route>
            <Route path="*" element={<NotFound />} />
          </Routes>
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
