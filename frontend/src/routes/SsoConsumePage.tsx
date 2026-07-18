import { useEffect } from "react";
import { useSearchParams } from "react-router-dom";

import { API_BASE_URL, apiUrl } from "../api";
import { ScreenState } from "../ui";

export function SsoConsumePage() {
  const [params] = useSearchParams();
  const token = params.get("token");

  useEffect(() => {
    if (token && API_BASE_URL) {
      window.location.replace(apiUrl(`/sso/consume?token=${encodeURIComponent(token)}`));
    }
  }, [token]);

  if (!token) {
    return (
      <ScreenState eyebrow="Single sign-on" title="The sign-in link is incomplete">
        <p>Return to Accumulate and open Social Media again.</p>
      </ScreenState>
    );
  }

  return (
    <ScreenState eyebrow="Single sign-on" title="Completing secure sign-in…">
      <p>
        {API_BASE_URL
          ? "Your Accumulate access is being verified."
          : "The backend must own /sso/consume on this deployment."}
      </p>
    </ScreenState>
  );
}
