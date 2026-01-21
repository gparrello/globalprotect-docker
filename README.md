# GlobalProtect VPN Docker Container with SOCKS5 Proxy

A Docker container that runs the GlobalProtect VPN client with **automated SAML/MFA authentication** and exposes the connection as a SOCKS5 proxy.

Based on a fork of [GlobalProtect-openconnect](https://github.com/yuezk/GlobalProtect-openconnect), redesigned as a single executable without client-server separation.

## Features

- **Automated SAML Authentication**: Supports Okta → OneLogin SSO flow with automatic credential entry
- **MFA Support**: Automatic TOTP code generation for Google Authenticator
- **SOCKS5 Proxy**: Exposes VPN connection on port 1080 for easy application routing
- **Headless Operation**: Runs without a display using Xvfb (ideal for servers/LXC containers)
- **Auto-Recovery**: Healthcheck and autoheal automatically restart on VPN disconnection
- **Gateway Selection**: Supports multiple gateways with automatic or manual selection

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Docker Container                                            │
│                                                             │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐  │
│  │  Xvfb   │───▶│ gpagent │───▶│  tun0   │───▶│ danted  │  │
│  │ :99     │    │  (VPN)  │    │ (tunnel)│    │ :1080   │  │
│  └─────────┘    └────┬────┘    └─────────┘    └────┬────┘  │
│                      │                             │        │
│                      ▼                             ▼        │
│               ┌─────────────┐               SOCKS5 Proxy    │
│               │  autofill   │                               │
│               │  (CDP:9222) │                               │
│               └─────────────┘                               │
│                                                             │
│  Managed by: supervisord                                    │
└─────────────────────────────────────────────────────────────┘
```

**Components:**
- **Xvfb**: Virtual X server for headless GUI operation
- **gpagent**: GlobalProtect client with embedded Chromium browser for SAML
- **autofill**: Python script using Chrome DevTools Protocol (CDP) to automate login
- **danted**: SOCKS5 proxy server bound to the VPN tunnel interface
- **supervisord**: Process manager ensuring correct startup order

## Quick Start

### 1. Clone and Configure

```bash
git clone --recurse-submodules https://github.com/gparrello/globalprotect-docker.git
cd globalprotect-docker
```

### 2. Create Environment File

Create a `.env` file with your credentials:

```bash
GP_PORTAL=your-portal.company.com  # Your GlobalProtect portal address
GP_USERNAME=your.email@company.com
GP_PASSWORD=your_password
GP_TOTP_SECRET=JBSWY3DPEHPK3PXP    # Your Google Authenticator secret key
STEP_DELAY=3                        # Delay between automation steps (seconds)
USE_XVFB=1                          # Enable for headless/LXC environments
```

### 3. Build and Run

```bash
docker compose build
docker compose up -d
```

### 4. Use the Proxy

Once connected, route traffic through the SOCKS5 proxy:

```bash
# Test connection
curl -x socks5h://localhost:1080 https://ipinfo.io

# Firefox: Settings → Network → Manual proxy → SOCKS Host: localhost, Port: 1080
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GP_PORTAL` | Yes* | GlobalProtect portal address (e.g., `vpn.company.com`) |
| `GP_USERNAME` | Yes | SSO username (email) |
| `GP_PASSWORD` | Yes | SSO password |
| `GP_TOTP_SECRET` | Yes | Base32 secret for TOTP generation |
| `GP_GATEWAY` | No | Preferred gateway name (auto-selected if not set) |
| `STEP_DELAY` | No | Delay between automation steps in seconds (default: 5) |
| `USE_XVFB` | No | Build arg: set to `1` for headless environments |

*\*Either set `GP_PORTAL` or mount a config file (see Advanced Configuration)*

## Portal Configuration

The container needs to know your GlobalProtect portal address. You have two options:

### Option 1: Environment Variable (Recommended)

Set `GP_PORTAL` in your `.env` file:

```bash
GP_PORTAL=vpn.company.com
```

The config file is generated automatically at container startup. Gateways are discovered from the portal on first connection.

### Option 2: Mount Config File

For advanced configuration (pre-configured gateways, custom settings), mount a `GPClient.conf` file:

```yaml
# docker-compose.yml
volumes:
  - ./config/com.yuezk.qt/GPClient.conf:/root/.config/com.yuezk.qt/GPClient.conf
```

Example `GPClient.conf`:

```ini
[General]
portal=vpn.company.com
vpn.company.com_selectedGateway=eu-gateway
vpn.company.com_gateways="[\n    {\"address\": \"gw-eu.company.com\", \"name\": \"eu-gateway\"},\n    {\"address\": \"gw-us.company.com\", \"name\": \"us-gateway\"}\n]"
```

**Note:** If you mount a config file, `GP_PORTAL` is ignored.

## Authentication Flow

The `autofill-cdp.py` script automates the following SAML flow:

1. **Okta Login** → Enters username, submits form
2. **OneLogin Redirect** → Waits for page load, handles certificate verification
3. **Password Entry** → Fills password, submits
4. **MFA Selection** → Clicks "Google Authenticator" if factor selection appears
5. **TOTP Entry** → Generates code using `oathtool`, submits
6. **VPN Connected** → ESP tunnel established, SOCKS proxy starts

## Healthcheck and Auto-Recovery

The container includes automatic recovery for VPN disconnections:

| Setting | Value | Description |
|---------|-------|-------------|
| Healthcheck interval | 30s | Tests proxy connectivity to google.com |
| Start period | 120s | Grace period for initial VPN connection |
| Retries | 3 | Failed checks before marking unhealthy |
| Autoheal interval | 60s | How often autoheal checks for unhealthy containers |

When the VPN drops, the container is marked unhealthy and the `autoheal` sidecar container automatically restarts it.

## Host Networking and Routing

The container uses `network_mode: host` for direct network access. The SOCKS5 proxy listens on port **1080**.

### Local Network Routing

The VPN sets the default route through the tunnel. To allow clients from other networks to reach the proxy, add static routes on the container host:

```bash
# /etc/network/interfaces
auto eth0
iface eth0 inet static
    address 10.90.100.142/24
    gateway 10.90.100.1
    post-up ip route add 10.80.100.0/24 via 10.90.100.1 dev eth0
```

### Default Route Recovery

The VPN doesn't restore the default route on disconnect. Add a cron job to ensure recovery:

```bash
echo '* * * * * root ip route add default via 10.90.100.1 dev eth0 2>/dev/null || true' | sudo tee /etc/cron.d/restore-default-route
sudo chmod 644 /etc/cron.d/restore-default-route
```

## Manual Installation (Without Docker)

Prerequisites:

```bash
sudo apt-get install -y \
    build-essential \
    qtbase5-dev \
    libqt5websockets5-dev \
    qtwebengine5-dev \
    qttools5-dev \
    qt5keychain-dev \
    openconnect
```

Building:

```bash
git clone --recurse-submodules https://github.com/gparrello/globalprotect-docker.git
cd globalprotect-docker
mkdir build && cd build
cmake -G Ninja ..
cmake --build .
sudo cmake --install .
```

Run with elevated privileges:

```bash
sudo ./gpagent
```

## Troubleshooting

**View logs:**
```bash
docker compose logs -f globalprotect
```

**Check VPN status:**
```bash
docker exec globalprotect-docker-globalprotect-1 ip addr show tun0
```

**Test proxy from inside container:**
```bash
docker exec globalprotect-docker-globalprotect-1 curl -x socks5h://localhost:1080 https://ipinfo.io
```

**Check health status:**
```bash
docker ps --format 'table {{.Names}}\t{{.Status}}'
```

**Common issues:**
- **DevTools not available**: gpagent GUI didn't start. Check Xvfb is running and `DISPLAY=:99` is set.
- **Host not found**: DNS broken after VPN disconnect. Ensure default route recovery cron is configured.
- **TOTP invalid**: Clock skew or wrong secret. Verify `GP_TOTP_SECRET` matches your authenticator app.

## License

See [LICENSE](LICENSE) for details.
