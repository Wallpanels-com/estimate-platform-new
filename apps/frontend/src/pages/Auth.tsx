import { LanguageSwitch, useI18n } from "../lib/i18n";
import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { post, errorMessage } from "../lib/api";
import { useAuth } from "../lib/auth";
import { Button, Field, ErrorNotice } from "../components/ui";
import { Brand } from "../components/Shell";
import { useQuery } from "@tanstack/react-query";
import { request } from "../lib/api";
export default function Auth({ register = false }: { register?: boolean }) {
  const { t } = useI18n();

  const { token, signIn } = useAuth();
  const settings = useQuery({
    queryKey: ["auth-settings"],
    queryFn: () => request<{ self_registration: boolean }>("/auth/settings"),
  });
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    setBusy(true);
    setError("");
    try {
      const data = await post<{ access_token: string }>(
        register ? "/auth/register" : "/auth/login",
        Object.fromEntries(form),
      );
      signIn(data.access_token);
      navigate(register ? "/onboarding" : "/");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }
  if (token) return <Navigate to="/" replace />;
  if (register && !settings.data?.self_registration)
    return <Navigate to="/login" replace />;
  return (
    <main className="auth-page">
      <div className="auth-story">
        <Brand />
        <div>
          <div className="panel-lines" aria-hidden="true" />
          <p className="auth-statement">
            {t("Thoughtful spaces.")}
            <br />
            {t("Considered estimates.")}
          </p>
          <p>{t("From the first idea to the final detail.")}</p>
        </div>
        <small>WallPanels.com · By Verona Home</small>
      </div>
      <section className="auth-form">
        <div className="auth-language">
          <LanguageSwitch />
        </div>
        <Brand />
        <div>
          <h1>{register ? t("Create your account") : t("Welcome back")}</h1>
          <p>
            {register
              ? t("Prepare estimates with your team.")
              : t("Sign in to your estimate workspace.")}
          </p>
        </div>
        {error ? <ErrorNotice>{error}</ErrorNotice> : null}
        <form onSubmit={submit}>
          {register ? (
            <Field label={t("Name")}>
              <input name="name" autoComplete="name" required maxLength={120} />
            </Field>
          ) : null}
          <Field label={t("Email")}>
            <input
              type="email"
              name="email"
              autoComplete="email"
              spellCheck={false}
              required
            />
          </Field>
          <Field label={t("Password")}>
            <input
              type="password"
              name="password"
              autoComplete={register ? "new-password" : "current-password"}
              required
              minLength={register ? 8 : 1}
            />
          </Field>
          <Button type="submit" variant="primary" busy={busy}>
            {register ? t("Create account") : t("Sign in")}
          </Button>
        </form>
        {settings.data?.self_registration ? (
          <p className="auth-switch">
            {register ? t("Already have an account?") : t("New to WallPanels?")}{" "}
            <Link to={register ? "/login" : "/register"}>
              {register ? t("Sign in") : t("Create account")}
            </Link>
          </p>
        ) : (
          <p className="auth-switch">
            {t("Ask a team member to create your account.")}
          </p>
        )}
      </section>
    </main>
  );
}
