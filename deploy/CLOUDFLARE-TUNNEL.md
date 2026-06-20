# Cloudflare Tunnel (optional)

Installed during `./install.sh`. Use this when you want a public domain instead of a raw LAN IP (e.g. for `WAREHOUSE_HOST` on robots or `WAREHOUSE_URL` on store/scan).

## One-time setup

```bash
cloudflared tunnel login
cloudflared tunnel create warehouse
cloudflared tunnel route dns warehouse cloud.yourdomain.com
```

## Run the tunnel

```bash
cloudflared tunnel run warehouse
```

Point your app at the tunnel hostname:

- **WarehouseDB** — `WAREHOUSE_HOST` in Arduino `config.h`, or store/scan `WAREHOUSE_URL=https://cloud.yourdomain.com`
- **Store / Scan** — set `WAREHOUSE_URL` to your warehouse tunnel URL

For a persistent tunnel service, see [Cloudflare systemd docs](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/configure-tunnels/local-management/as-a-service/linux/).
