# 14 — AWS Deployment Deep-Dive

## Topology, end to end

```
Namecheap DNS (A record) ──▶ Elastic IP (static) ──▶ EC2 instance (t3.micro, Ubuntu 24.04)
                                                          │
                                          Security Group: 22 (SSH), 80 (HTTP), 443 (HTTPS) only
                                                          │
                                          ┌───────────────┴───────────────┐
                                          │        Docker network         │
                                          │  nginx (TLS, :80→:443 redir)  │
                                          │        ↓ api:8000             │
                                          │  api (FastAPI, no host port)  │
                                          └────────────────────────────────┘
```

## IAM — credential scoping, done deliberately

Rather than using root AWS credentials, a dedicated IAM user was created with **only** the `AmazonEC2FullAccess` managed policy attached — enough to provision EC2 instances, security groups, key pairs, and Elastic IPs, and nothing else (no S3, no IAM management, no billing access). This is the principle of least privilege in practice: if these access keys were ever leaked, the blast radius is bounded to EC2 resources in this account, not the entire AWS account.

## Networking: VPC & Security Group

The default VPC (created automatically by AWS in every account/region) was used rather than a custom one — appropriate for a single-instance deployment; a custom VPC with public/private subnet separation would be the right next step for a multi-tier production system (see the "when this doesn't scale" note below).

A security group was created with exactly three inbound rules:

| Port | Protocol | Purpose |
|---|---|---|
| 22 | TCP | SSH administration |
| 80 | TCP | HTTP (redirects to HTTPS) |
| 443 | TCP | HTTPS (the only port real traffic should use) |

No other ports are open — critically, **port 8000 (the API's own port) is never exposed to the internet**, matching the `docker-compose.yml` decision in `13_Docker.md`.

## Compute: the EC2 instance itself

- **Instance type**: `t3.micro` — 2 vCPUs (burstable), 1GB RAM. Chosen for free-tier eligibility, with a known, accepted trade-off: 1GB is tight for torch + sentence-transformers + ChromaDB running together.
- **Mitigation**: a 2GB swap file was added on first boot (`fallocate`, `mkswap`, `swapon`, plus an `/etc/fstab` entry so it survives reboots) specifically to absorb memory pressure spikes rather than the kernel's OOM-killer terminating the process.
- **AMI**: the latest Ubuntu 24.04 LTS image, found programmatically (`aws ec2 describe-images` filtered to Canonical's owner ID, sorted by creation date) rather than hand-picking an AMI ID that would go stale.
- **Storage**: a 16GB gp3 EBS root volume — bumped up from the AMI's smaller default specifically to comfortably fit the ~2.6GB application image plus OS and Docker layer overhead.
- **Key pair**: an RSA key pair generated via the AWS CLI at provisioning time; the private key was saved locally (never committed to git, never transmitted except directly to the person who needed it) and used for all subsequent SSH administration and for the `EC2_SSH_KEY` GitHub secret.

## Static addressing: Elastic IP

EC2 instances get a new public IP on every stop/start by default — fine for initial testing, but disastrous the moment DNS or a CI/CD secret depends on that IP staying constant. An **Elastic IP** was allocated and associated with the instance specifically to fix this: it's free while attached to a running instance, and once associated, both the DNS A record and the `EC2_HOST` GitHub secret could be set once and never need updating again for the life of that instance.

## Server bootstrap

1. Docker Engine installed via the official convenience script (`get.docker.com`), which also installs the `docker compose` plugin.
2. The `ubuntu` user added to the `docker` group, so `docker` commands don't require `sudo` for routine operations.
3. Swap file added (above).
4. The repository cloned directly onto the host at `/opt/rag-chatbot` — the deploy pipeline only ever updates the running *image*, so this clone mainly exists to hold `docker-compose.yml`, the nginx config, and the deploy script itself.

## Reverse proxy & TLS

NGINX terminates TLS and reverse-proxies to `api:8000` over the internal Docker network (full detail in `16_Security.md`'s HTTPS section and `13_Docker.md`). **Let's Encrypt** issues the certificate via Certbot's HTTP-01 challenge — Certbot proves domain ownership by having NGINX serve a specific file at `http://<domain>/.well-known/acme-challenge/<token>`, which only the actual server behind that domain's DNS record could serve, hence "proof of control." Certificates are valid 90 days and must be renewed (`deploy/nginx/init-letsencrypt.sh` documents the renewal command; automating it is an open follow-up, noted in `18_Debugging.md`).

## DNS

A single **A record** at the domain registrar (Namecheap) maps `akashwork.website` → the Elastic IP. No CDN or DNS-level proxy sits in front (a proxying DNS provider, like Cloudflare's default mode, would break the Let's Encrypt HTTP-01 challenge unless proxying was temporarily disabled for that record).

## Deployment commands, concretely (`deploy/ec2/deploy.sh`)

```bash
docker pull "$IMAGE"                                  # fetch the new image from GHCR
docker tag "$IMAGE" rag-chatbot-api:latest             # retag to what docker-compose.yml expects
docker compose up -d --no-build                        # recreate only the containers whose image changed
docker image prune -f                                  # reclaim disk space from now-unused old layers
# then poll http://localhost/health (through nginx) until it responds, or fail loudly
```

This script is what the CD pipeline runs over SSH on every push to `main` — see `15_GitHub_Actions.md` for the trigger side, and `18_Debugging.md` for the three real bugs found while getting this exact script to work correctly.

## Monitoring & log management, honestly assessed

What exists today: Docker's built-in healthcheck, `docker compose logs`, and the deploy script's own health-check polling loop. What does **not** exist: centralized log aggregation, metrics/alerting, or uptime monitoring from outside the instance itself. For a demo deployment this is an acceptable and clearly named gap — a real production system would ship logs to something queryable (CloudWatch Logs, or a hosted log platform) and add an external uptime check (so an outage is discovered by monitoring, not by a user complaint).

## Scaling considerations — what would have to change

This is a single instance with no redundancy — if it goes down, the service is down. Scaling this properly would mean: an Application Load Balancer in front of multiple instances (or an ECS/EKS-managed fleet) instead of one EC2 box; the SQLite database replaced with managed Postgres (RDS) so multiple app instances can share state; the vector store moved to a managed or clustered service instead of a single Docker volume; and session/JWT validation kept stateless (already true here) so any instance can serve any request. None of this was needed for a single-user demo deployment, but it's the honest answer to "how would you scale this."
