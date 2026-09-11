import { Navigate, Route, BrowserRouter, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { AuthProvider } from "./auth/AuthContext";
import { RequireAuth } from "./auth/RequireAuth";
import { AlertsPage } from "./routes/AlertsPage";
import { ChatPlaceholderPage } from "./routes/ChatPlaceholderPage";
import { LoginPage } from "./routes/LoginPage";
import { RegisterPage } from "./routes/RegisterPage";
import { TodayPage } from "./routes/TodayPage";

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Demo mode: login/register are still routable for manual testing,
              but the app never sends users there. AuthProvider boots straight
              into the demo session so RequireAuth always passes. */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />

          <Route
            element={
              <RequireAuth>
                <AppShell />
              </RequireAuth>
            }
          >
            <Route path="/chat" element={<ChatPlaceholderPage />} />
            <Route path="/today" element={<TodayPage />} />
            <Route path="/alerts" element={<AlertsPage />} />
          </Route>

          <Route path="/" element={<Navigate to="/chat" replace />} />
          <Route path="*" element={<Navigate to="/chat" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
