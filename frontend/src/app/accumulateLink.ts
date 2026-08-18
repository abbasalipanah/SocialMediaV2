/**
 * Where "Back to Accumulate" and the signed-out screen send the user.
 *
 * Social Media V2 is launched from Accumulate through signed SSO, so the way
 * back is a plain link to the Accumulate shell rather than any V2 route.
 */
export const accumulateUrl =
  (import.meta.env.VITE_ACCUMULATE_URL as string | undefined)?.trim() ||
  "https://app.theaccumulate.com";
