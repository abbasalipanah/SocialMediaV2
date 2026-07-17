import { ArrowRight, ShieldCheck } from "lucide-react";
import { Navigate } from "react-router-dom";

import { useAuth } from "../auth";
import { ScreenState } from "../ui";

const accumulateUrl =
  (import.meta.env.VITE_ACCUMULATE_URL as string | undefined)?.trim() ||
  "https://app.theaccumulate.com";

export function LoginPage() {
  const { status, retry } = useAuth();
  if (status === "signed_in") return <Navigate replace to="/overview" />;
  if (status === "checking") {
    return (
      <ScreenState eyebrow="ACCUMULATE" title="Checking your session…">
        <p>Secure single sign-on status is loading.</p>
      </ScreenState>
    );
  }
  if (status === "error") {
    return (
      <ScreenState eyebrow="Connection error" title="Sign-in status is unavailable">
        <p>Retry before starting another single sign-on handoff.</p>
        <button className="primary-button" onClick={retry} type="button">Try again</button>
      </ScreenState>
    );
  }

  return (
    <main className="login-page">
      <section className="login-card">
        <img alt="Accumulate" className="login-logo" src="/accumulate-logo.svg" />
        <p className="eyebrow">ACCUMULATE</p>
        <h1>Social Media</h1>
        <p>Open this workspace from Accumulate to continue with your Brand access and permissions.</p>
        <a className="primary-button login-action" href={accumulateUrl}>
          Continue with Accumulate <ArrowRight size={18} />
        </a>
        <div className="login-security">
          <ShieldCheck size={18} />
          <span>Single sign-on · No local password</span>
        </div>
      </section>
    </main>
  );
}
