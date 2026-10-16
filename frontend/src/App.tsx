import { Navigate, Route, BrowserRouter, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { AuthProvider } from "./auth/AuthContext";
import { RequireAuth } from "./auth/RequireAuth";
import { AlertsPage } from "./routes/AlertsPage";
import { ChatScreen } from "./chat/ChatScreen";
import { LoginPage } from "./routes/LoginPage";
import { RegisterPage } from "./routes/RegisterPage";
import { SettingsPage } from "./routes/SettingsPage";
import { TodayPage } from "./routes/TodayPage";

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* There is no demo session. AuthProvider boots unauthenticated and
              RequireAuth sends you here, so /login is the only place a token
              can be obtained. See AuthContext.tsx for why the fake session was
              removed. */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />

          <Route
            element={
              <RequireAuth>
                <AppShell />
              </RequireAuth>
            }
          >
            <Route path="/chat" element={<ChatScreen />} />
            <Route path="/today" element={<TodayPage />} />
            <Route path="/alerts" element={<AlertsPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            {/* `/profile` was the settings screen's old name. Redirect rather
                than delete the route: an installed PWA and any saved bookmark
                still request it, and without this it would fall through to the
                catch-all and land on Chat. */}
            <Route path="/profile" element={<Navigate to="/settings" replace />} />
          </Route>

          <Route path="/" element={<Navigate to="/chat" replace />} />
          <Route path="*" element={<Navigate to="/chat" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
