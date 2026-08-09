import { useEffect } from "react";
import { useSearchParams } from "../routing";

import { apiUrl } from "../api";
import { ScreenState } from "../ui";

export function SsoConsumePage() {
  const [params] = useSearchParams();
  const token = params.get("token");

  useEffect(() => {
    if (token) {
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
      <p>Your Accumulate access is being verified.</p>
    </ScreenState>
  );
}
