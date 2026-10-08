# Run the live demo backend on AWS EC2

Runs the guarded gutcheck server from `space/` behind Caddy, which gets and renews the HTTPS certificate on its own.

## 1. Launch the instance

- AMI: Ubuntu 24.04 LTS, type `t3.medium` (4 GB RAM; torch and the model do not fit in 1 GB), 20 GB disk.
- Security group: allow inbound 22 from your IP, and 80 and 443 from anywhere.
- Allocate an Elastic IP and attach it, so the address survives restarts.

## 2. Point a subdomain at it

Add a DNS `A` record such as `api.yourdomain.com` pointing to the Elastic IP. Wait until `dig +short api.yourdomain.com` returns that IP.

## 3. Install Docker and start the stack

```bash
ssh ubuntu@<elastic-ip>
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker ubuntu && exit
```

Log in again, then:

```bash
git clone https://github.com/16SULPHUR/gutcheck.git
cd gutcheck/deploy/ec2
cp .env.example .env && nano .env   # set DOMAIN
docker compose up -d --build
```

The first build downloads the models, so it takes several minutes. Check it:

```bash
curl https://api.yourdomain.com/healthz
```

## 4. Point the website at it

In Vercel, open the project's Settings, Environment Variables, and add `VITE_DEMO_API=https://api.yourdomain.com` for Production. Redeploy. The demo's status pill turns to live.

## Notes

- Only `/v1/decide`, `/v1/packs` and `/healthz` are reachable, inputs are capped and requests are rate limited per IP. Nothing typed is stored.
- Update: `git pull && docker compose up -d --build`.
- Logs: `docker compose logs -f`.
