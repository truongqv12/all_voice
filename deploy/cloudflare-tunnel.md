# Public exposure — Cloudflare Tunnel (free)

Expose all-voice to the internet with **no inbound ports open** and **no public IP**.
`cloudflared` makes an outbound connection to Cloudflare's edge and forwards a
hostname to your local nginx. All of this is on Cloudflare's free plan.

```
internet → Cloudflare edge → cloudflared (outbound) → nginx 127.0.0.1:8123 → API 127.0.0.1:8124
```

Do the nginx + systemd setup first (`docs/deployment.md`, `deploy/install-service.sh`,
`deploy/nginx.conf.example`). Confirm `curl http://localhost:8123/v1/models` works
locally before wiring the tunnel — the tunnel only forwards to nginx.

You need a domain whose nameservers point at Cloudflare (adding a site to Cloudflare
is free). The steps below run **on the box**.

## 1. Install cloudflared

```bash
# Debian/Ubuntu
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o cloudflared.deb
sudo dpkg -i cloudflared.deb
cloudflared --version
```

## 2. Log in and create the tunnel

```bash
cloudflared tunnel login                 # opens a browser; pick your domain/zone
cloudflared tunnel create all-voice      # prints a Tunnel ID + writes ~/.cloudflared/<ID>.json
```

## 3. Config file

Create `~/.cloudflared/config.yml` (replace the ID, the credentials filename, and
the hostname):

```yaml
tunnel: <TUNNEL-ID>
credentials-file: /home/<user>/.cloudflared/<TUNNEL-ID>.json

ingress:
  - hostname: voice.example.com
    service: http://localhost:8123      # nginx (which fronts the loopback API)
  - service: http_status:404            # catch-all (required last rule)
```

> **Token-managed tunnel** (how this box runs): if you start cloudflared with
> `tunnel run --token …`, the ingress lives in the Cloudflare **Zero Trust dashboard**,
> not this `config.yml`. Set the hostname's Service to `http://localhost:<nginx-port>`
> there; nginx must listen on that same port (deploy/nginx.conf.example).

## 4. Route DNS and run

```bash
cloudflared tunnel route dns all-voice voice.example.com   # creates the proxied CNAME
cloudflared tunnel run all-voice                           # foreground test
```

Open `https://voice.example.com` — the test UI should load and read text aloud.

Run it as a service so it survives reboots:

```bash
sudo cloudflared service install
sudo systemctl enable --now cloudflared
```

## 5. Cloudflare dashboard checklist (do this — the app gate is not the only layer)

The app already self-protects by real cost (characters / audio-seconds per IP), but
the edge stops junk before it ever reaches the box. In the Cloudflare dashboard for
this zone:

- [ ] **Rate limiting rule** on `/v1/audio/*` — e.g. cap requests per IP per minute
      (Security → WAF → Rate limiting rules). One free custom rule is included.
- [ ] **WAF custom rules** to block obvious abuse: unknown/scanner User-Agents,
      requests to paths other than `/` and `/v1/*`, and non-GET/POST methods.
- [ ] **Bot Fight Mode** ON (Security → Bots) — challenges cheap automated traffic.
- [ ] **Always Use HTTPS** ON; **SSL/TLS mode = Full** (nginx is plain HTTP on
      loopback, but the hop is inside the tunnel, so Full is correct here).
- [ ] Confirm the DNS record for the hostname is **Proxied** (orange cloud), not
      DNS-only — grey cloud would bypass the edge protections above.

> The per-IP gate in the app keys off `CF-Connecting-IP`, which Cloudflare sets to the
> true visitor IP. nginx forwards it and the app trusts it only on the loopback hop,
> so the budget/rate limits apply per real visitor even behind the tunnel.

## Troubleshooting

- **502/404 from the edge:** nginx isn't up or the ingress `service:` port is wrong.
  Test `curl http://localhost:8123/v1/models` on the box.
- **524 timeout on long reads:** streaming got buffered somewhere. Ensure
  `proxy_buffering off` in nginx (it is in the example) and that you're calling
  `/v1/audio/stream` for long text.
- **Gate limits look global, not per-visitor:** the DNS record is grey-clouded
  (DNS-only) so `CF-Connecting-IP` is absent — set it back to Proxied.
