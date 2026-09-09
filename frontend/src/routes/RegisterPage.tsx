import { useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";

export function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      let latitude: number | undefined;
      let longitude: number | undefined;
      if ("geolocation" in navigator) {
        try {
          const position = await new Promise<GeolocationPosition>((resolve, reject) =>
            navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 3000 }),
          );
          latitude = position.coords.latitude;
          longitude = position.coords.longitude;
        } catch {
          // location is optional — proceed without it
        }
      }
      await register({ email, password, latitude, longitude });
      navigate("/chat", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not create your account.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="auth-screen">
      <div>
        <h2 className="vt">Create your account</h2>
        <p className="vsub">We use your location to show local pollen, air quality and nearby care.</p>
      </div>
      <form className="auth-form" onSubmit={onSubmit}>
        <div className="field">
          <label htmlFor="register-email">Email</label>
          <input
            id="register-email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="register-password">Password</label>
          <input
            id="register-password"
            type="password"
            autoComplete="new-password"
            required
            minLength={8}
            maxLength={72}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        {error && <p className="form-error">{error}</p>}
        <button className="btn-primary" type="submit" disabled={submitting}>
          {submitting ? "Creating account…" : "Create account"}
        </button>
      </form>
      <p className="vsub">
        Already have an account?{" "}
        <Link className="btn-link" to="/login">
          Sign in
        </Link>
      </p>
    </div>
  );
}
