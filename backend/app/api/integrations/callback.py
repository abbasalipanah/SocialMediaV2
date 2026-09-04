"""Provider-neutral OAuth callback page for channel integrations."""

from __future__ import annotations

import json

from fastapi.responses import HTMLResponse

from app.domain.platforms import PlatformId


def oauth_channel_callback_page(
    *,
    platform: PlatformId,
    brand_id: str,
    connection_id: int | None = None,
    discovered_count: int = 0,
    error_code: str = "",
    status_code: int = 200,
) -> HTMLResponse:
    callback_status = "error" if error_code else "success"
    payload = json.dumps(
        {
            "type": f"social-media:{platform.value}-oauth",
            "status": callback_status,
            "brandId": brand_id,
            "platform": platform.value,
            "connectionId": connection_id,
            "discoveredCount": discovered_count,
            "connectionState": "pending_verification" if not error_code else "error",
            "errorCode": error_code,
        },
        separators=(",", ":"),
    ).replace("<", "\\u003c")
    fallback_path = f"/integrations?{platform.value}_oauth={callback_status}"
    if error_code:
        fallback_path = f"{fallback_path}&error={error_code}"
    fallback_json = json.dumps(fallback_path)
    title = "Authorization complete" if not error_code else "Connection failed"
    message = (
        "Authorization completed. Return to the application to select the account."
        if not error_code
        else "Authorization could not be completed. Return to Integrations and try again."
    )
    content = f"""<!doctype html>
<html lang="en">
  <head><meta charset="utf-8" /><meta name="viewport" content="width=device-width" />
    <title>{title}</title></head>
  <body><main><h1>{title}</h1><p>{message}</p>
    <a href="{fallback_path}">Return to Integrations</a></main>
    <script>
      (() => {{
        const payload = {payload};
        if (window.opener && !window.opener.closed) {{
          window.opener.postMessage(payload, window.location.origin);
          window.setTimeout(() => window.close(), 350);
          return;
        }}
        window.setTimeout(() => window.location.replace({fallback_json}), 900);
      }})();
    </script>
  </body>
</html>"""
    return HTMLResponse(
        content=content,
        status_code=status_code,
        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
    )


__all__ = ["oauth_channel_callback_page"]
