"""Swagger UI customization for previewing binary audio responses."""

from __future__ import annotations

import html
import json

from fastapi.responses import HTMLResponse


_SWAGGER_UI_VERSION = "5.32.6"


def get_audio_swagger_ui_html(*, openapi_url: str, title: str) -> HTMLResponse:
    """Render Swagger UI with POST audio responses backed by Blob URLs.

    Swagger UI's built-in audio response component points the player at the
    request URL. That only works for GET endpoints; speech synthesis is POST.
    """

    page = r"""<!DOCTYPE html>
<html>
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@__VERSION__/swagger-ui.css">
  <link rel="shortcut icon" href="https://fastapi.tiangolo.com/img/favicon.png">
  <title>__TITLE__</title>
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@__VERSION__/swagger-ui-bundle.js"></script>
  <script>
    const AudioResponsePlugin = function() {
      return {
        wrapComponents: {
          responseBody: (Original, system) => {
            const React = system.React;

            return class AudioResponseBody extends React.Component {
              constructor(props) {
                super(props);
                this.state = { audioUrl: this.createAudioUrl(props) };
              }

              createAudioUrl(props) {
                if (!/^audio\//i.test(props.contentType || "")) return null;
                const blob = props.content instanceof Blob
                  ? props.content
                  : new Blob([props.content], { type: props.contentType });
                return URL.createObjectURL(blob);
              }

              componentDidUpdate(previousProps) {
                if (previousProps.content !== this.props.content ||
                    previousProps.contentType !== this.props.contentType) {
                  if (this.state.audioUrl) URL.revokeObjectURL(this.state.audioUrl);
                  this.setState({ audioUrl: this.createAudioUrl(this.props) });
                }
              }

              componentWillUnmount() {
                if (this.state.audioUrl) URL.revokeObjectURL(this.state.audioUrl);
              }

              render() {
                if (!/^audio\//i.test(this.props.contentType || "")) {
                  return React.createElement(Original, this.props);
                }

                return React.createElement(
                  "div",
                  null,
                  React.createElement("h5", null, "Response body"),
                  React.createElement(
                    "pre",
                    { className: "microlight" },
                    React.createElement("audio", {
                      controls: true,
                      src: this.state.audioUrl,
                    })
                  )
                );
              }
            };
          },
        },
      };
    };

    const ui = SwaggerUIBundle({
      url: __OPENAPI_URL__,
      dom_id: "#swagger-ui",
      layout: "BaseLayout",
      deepLinking: true,
      showExtensions: true,
      showCommonExtensions: true,
      presets: [
        SwaggerUIBundle.presets.apis,
        SwaggerUIBundle.SwaggerUIStandalonePreset,
      ],
      plugins: [AudioResponsePlugin],
    });
  </script>
</body>
</html>
"""
    page = page.replace("__VERSION__", _SWAGGER_UI_VERSION)
    page = page.replace("__TITLE__", html.escape(title))
    page = page.replace("__OPENAPI_URL__", json.dumps(openapi_url))
    return HTMLResponse(page)
