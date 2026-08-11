# NeuralQuant on Oracle Cloud Free Tier

Move Hermes (and optionally the rest of the stack) to Oracle Cloud Always Free resources.

## Free tier limits (2026)

- **Ampere A1 (ARM) compute**: up to **2 OCPUs + 12 GB RAM** total per tenancy. Previously 4/24, reduced mid-2026.
- **Block Volume**: 200 GB included.
- **Object Storage**: included.
- **Outbound data**: 10 TB/month.
- **2× AMD Micro instances**: 1/8 OCPU + 1 GB each — too small for this stack.

Sources: [Oracle Cloud Free Tier](https://www.oracle.com/cloud/free/), [OCI Free Tier docs](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier.htm), [InfoQ on 2026 limit reduction](https://www.infoq.com/news/2026/07/oracle-cloud-free-tier-limits/).

## What fits for free

On a single `VM.Standard.A1.Flex` with 2 OCPU + 12 GB RAM you can run:

```
┌──────────────────────────────────────────────────────┐
│  Ubuntu 22.04 ARM VM                                  │
│  ┌─────────────┐ ┌─────────────┐ ┌──────────────────┐  │
│  │ nq-api      │ │ nq-web      │ │ hermes-trading   │  │
│  │ FastAPI     │ │ Next.js     │ │ paper-trading    │  │
│  │ ~1 GB RAM   │ │ ~0.5 GB RAM │ │ ~0.5 GB RAM      │  │
│  └─────────────┘ └─────────────┘ └──────────────────┘  │
│  ┌─────────────┐ ┌─────────────┐                       │
│  │ Postgres    │ │ Redis       │                       │
│  │ ~1 GB RAM   │ │ ~0.25 GB RAM│                       │
│  └─────────────┘ └─────────────┘                       │
│  ┌────────────────────────────────────────────────┐    │
│  │ Caddy reverse proxy + TLS                      │    │
│  └────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────┘
```

That leaves ~8 GB RAM for the kernel, build caches, and headroom. Realistic and comfortable for a lean stack.

## What is NOT practical to move

**Supabase**: The managed Supabase project (auth, row-level security, realtime, storage, edge functions) is complex to self-host in a 12 GB box. You *can* run a minimal Postgres + PostgREST + GoTrue stack, but you lose:

- Managed backups / point-in-time recovery
- Auth UI / email templates
- Realtime subscriptions (if you use them)
- Storage / edge functions
- Easy migrations

**Verdict**: keep managed Supabase for now. It has a generous free tier and is core to auth/data. Only self-host if Supabase bills become painful.

## Suggested migration strategy

### Phase 1: Hermes only (fastest, lowest risk)
1. Provision one OCI ARM instance.
2. Deploy Hermes via Docker Compose on Oracle Cloud.
3. Point Render's `nq-api` `HERMES_API_URL` at the new Oracle URL.
4. Keep everything else on Render/Vercel/Supabase.

### Phase 2: nq-api + web + worker (optional)
1. Move `nq-api`, `nq-web`, `nq-trader`, `quantastra-agent` to the same OCI VM.
2. Use managed Supabase still.
3. Update DNS / Vercel rewrite to point at Oracle public IP, or keep Vercel as CDN.

This guide currently covers **Phase 1** fully and **Phase 2** partially.
