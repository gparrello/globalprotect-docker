# GlobalProtect VPN client (GUI) in a Docker container

This is an implementation of GlobalProtect VPN client (GUI), which runs in a Docker container and exposes the VPN connection to the users as a SOCKS5 proxy.

Technically, the Docker container runs a fork of [GlobalProtect-openconnect](https://github.com/yuezk/GlobalProtect-openconnect), redesigned to come as a single executable, without client-server separation.

<img src="screenshots/screenshot1.png"><img src="screenshots/screenshot2.png">

## Features

- Similar user experience as the official client in macOS.
- Supports both SAML and non-SAML authentication modes.
- Supports automatically selecting the preferred gateway from the multiple gateways.
- Supports switching gateway from the system tray menu manually.
- Memorizes credentials and authenticates automatically without a dialog.

# Docker
 
```
git clone --recurse-submodules https://github.com/dmikushin/globalprotect-docker.git
cd globalprotect-docker
docker build -t globalprotect-docker -f docker/Dockerfile .
docker-compose up -d
```
 
On the first run, navigate to `http://localhost:8083` in the web browser to provide authentication credentials. On subsequent invocations, the container will  try to use the cached credentials.

When the connection is established, configure your applications to use the provided SOCKS5 proxy. For example, Firefox:

<img src="screenshots/screenshot3.png">

## Manual Installation

Prerequisites:

```
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

```
git clone --recurse-submodules https://github.com/dmikushin/globalprotect-docker.git
cd globalprotect-docker
mkdir build
cd build
cmake -G Ninja ..
cmake --build .
sudo cmake --install .
```

Without client-server separation, the binary must be executed with elevated priviledges:

```
sudo ./gpagent
```

## Troubleshooting

Run `docker-compose logs` in the Terminal and collect the logs.

## Host Networking and Routing

When running with `network_mode: host`, the SOCKS5 proxy listens directly on port **1080** (not 8090).

### Local Network Routing

The VPN sets the default route to go through the tunnel (`tun0`). To allow clients from other local networks to reach the SOCKS proxy, you need to add static routes for those networks.

For example, if the container host is on `10.90.100.0/24` and clients are on `10.80.100.0/24`, add a route in the container host `/etc/network/interfaces`:

```
auto eth0
iface eth0 inet static
        address 10.90.100.142/24
        gateway 10.90.100.1
        post-up ip route add 10.80.100.0/24 via 10.90.100.1 dev eth0
```

This ensures response packets to local clients go via the local gateway instead of through the VPN tunnel.

### Default Route Recovery

The VPN overwrites the default route when connected. If the VPN disconnects unexpectedly, the default route is not restored, which prevents the container from reconnecting.

To automatically restore the default route, add a cron job on the container host:

```bash
echo '* * * * * root ip route add default via 10.90.100.1 dev eth0 2>/dev/null || true' | sudo tee /etc/cron.d/restore-default-route
sudo chmod 644 /etc/cron.d/restore-default-route
```

This checks every minute and restores the default route if missing.

## Healthcheck and Auto-Recovery

The container includes a healthcheck that tests the SOCKS proxy every 30 seconds. If the VPN disconnects and the proxy becomes unreachable, the container is marked unhealthy.

An `autoheal` container monitors for unhealthy containers and automatically restarts them:

- **Healthcheck interval**: 30 seconds
- **Start period**: 120 seconds (time for VPN to connect initially)
- **Retries**: 3 failed checks before marking unhealthy
- **Autoheal interval**: 60 seconds

This provides automatic recovery when the VPN connection drops.
