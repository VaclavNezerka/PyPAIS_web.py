# Deploying AIBAL on e-INFRA CZ (CERIT-SC Kubernetes)

AIBAL runs as one container with a slice of an NVIDIA A100 (10 GB), next to a PostgreSQL cluster run
by the platform's CloudNativePG operator, at **https://aibal.dyn.cloud.e-infra.cz** (automatic HTTPS).

| File | What it is |
|---|---|
| `../Dockerfile`, `../.dockerignore`, `requirements.txt` | the container image (PyTorch with CUDA 12.6, gunicorn on port 8080, user 1000) |
| `build_push.ps1` | builds the image and pushes it to the e-INFRA registry `cerit.io` |
| `k8s/postgres.yaml` | the database (2 instances on fast local storage) and its network policy |
| `k8s/postgres-backup.yaml` | optional daily backups of the database to S3 |
| `k8s/app.yaml` | settings, the app with the GPU slice, its Service and the HTTPS address |
| `aibal.env.example` | template of the secret settings (copy to `aibal.env`, which git ignores) |
| `restore_db.ps1` | restores a dump of the current database and applies `db_migrations/` |

Commands below are for PowerShell in the repository folder (`PyPAIS_web.py`).

## 0. Before you start

- **Terms of use.** e-INFRA CZ is free for research and education; purely commercial use is not allowed and
  partly commercial projects are assessed case by case. AIBAL is used by companies (road laboratories), so
  describe the project (research output of TAČR project CL02000145) to **k8s@ics.muni.cz** and ask whether it
  can run there.
- The platform runs on a "best effort" basis (support in working hours). Your e-INFRA (MetaCentrum)
  account expires every year on 2 February and must be renewed, or the deployment stops.
- Publications should acknowledge e-INFRA CZ (project ID 90254).

## 1. Tools on this PC

```powershell
winget install Docker.DockerDesktop     # then start Docker Desktop once
winget install Kubernetes.kubectl
```

## 2. Access to the cluster

1. Log in at **https://rancher.cloud.e-infra.cz** with your e-INFRA CZ account. The first login creates your
   personal project and namespace.
2. Create a namespace for AIBAL in the Rancher GUI (Namespaces → Create; not with kubectl, or it is not linked
   to your project). Names are unique across the cluster, e.g. `aibal-cvut`.
3. Open the cluster (drop-down in the upper left), download its **kubeconfig** and save it as
   `%USERPROFILE%\.kube\config`.
4. Use the namespace by default and check the access:

```powershell
kubectl config set-context --current --namespace=aibal-cvut
kubectl get pods
```

## 3. Build and push the image

1. Log in at **https://hub.cerit.io**, open your user profile (upper right) and copy the **CLI secret**.
2. Log in Docker to the registry (user name = your Harbor user name, password = the CLI secret), then build:

```powershell
docker login cerit.io
.\deploy\build_push.ps1 -User <your-harbor-user>
```

3. Put the printed image name (`cerit.io/<user>/aibal:<commit>`) into `deploy/k8s/app.yaml` instead of
   `cerit.io/CHANGE-ME/aibal:latest`.

The registry is readable by the whole cluster - never put secrets into the image (`.dockerignore` keeps
`.env` out).

## 4. Database

```powershell
kubectl apply -f deploy/k8s/postgres.yaml
kubectl get cluster.postgresql.cnpg.io aibal-db      # wait for "Cluster in healthy state"
```

Before that, check the size of the current database on the old server
(`SELECT pg_size_pretty(pg_database_size(current_database()));`) - photos and masks are stored in it.
If it is above ~15 GB, raise `storage.size` in `postgres.yaml` first.

## 5. Move the data from the current server

1. Stop the app on the current server (`webhost-gpu.fsv.cvut.cz`), so nothing changes after the dump.
2. On the current server, with `DB_USERNAME` / `DB_NAME` / `DB_PASSWORD` from its `.env`:

```bash
PGPASSWORD=<DB_PASSWORD> pg_dump -Fc -h localhost -U <DB_USERNAME> -d <DB_NAME> -f ~/aibal_prod.dump
```

3. Copy it to this PC and restore it into the new database. The script also applies `db_migrations/`
   (the sample designation column) and prints the number of companies, users and samples to compare:

```powershell
scp silhada2@webhost-gpu.fsv.cvut.cz:~/aibal_prod.dump .
.\deploy\restore_db.ps1 -Dump .\aibal_prod.dump
```

The restore was tested with a dump of the local database into a fresh database owned by a normal user,
as the operator creates it. Delete the dump afterwards - it contains all user data (`*.dump` is git-ignored).

## 6. Secret settings

1. Copy `deploy/aibal.env.example` to `deploy/aibal.env` and fill it in with the values of the current
   server's `.env` (SECRET_KEY, mail, admin addresses, reCAPTCHA).
2. In the reCAPTCHA admin console (https://www.google.com/recaptcha/admin), add `aibal.dyn.cloud.e-infra.cz`
   to the site's domains - otherwise logging in fails.
3. Store them in the cluster:

```powershell
kubectl create secret generic aibal-secrets --from-env-file=deploy/aibal.env
```

## 7. Start the app

```powershell
kubectl apply -f deploy/k8s/app.yaml
kubectl get pods -w                       # wait for aibal-... 1/1 Running
kubectl logs deploy/aibal
kubectl exec deploy/aibal -- python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

Then open https://aibal.dyn.cloud.e-infra.cz (the certificate takes a minute or two) and check: log in,
upload and evaluate a photo, open an old sample, export a PDF, and send a password-reset e-mail.

## 8. Backups (recommended)

The database storage (`zfs-csi`) is fast but has no backup of its own; the second instance only protects
against the loss of one node. For daily backups kept 30 days, get an S3 bucket with a read/write key pair
(e.g. CESNET's S3 storage) and follow the three steps at the top of `deploy/k8s/postgres-backup.yaml`.

## Updating the app

```powershell
.\deploy\build_push.ps1 -User <your-harbor-user>
kubectl set image deployment/aibal app=cerit.io/<user>/aibal:<new tag>
```

New database migrations: put them into `db_migrations/` and apply them before the new version starts
(e.g. through `kubectl port-forward svc/aibal-db-rw 15432:5432` and `psql`).
Changed secrets: re-create the secret (`kubectl create secret generic aibal-secrets --from-env-file=deploy/aibal.env --dry-run=client -o yaml | kubectl apply -f -`)
and `kubectl rollout restart deployment/aibal`.

## Troubleshooting

- **Pod stays Pending with "Insufficient nvidia.com/mig-1g.10gb"** - no free A100 slice. In `app.yaml`
  replace `nvidia.com/mig-1g.10gb: 1` (requests and limits) with `nvidia.com/gpu: 1` (a whole GPU).
- **Pod is rejected by a security policy** - the platform requires the security settings already in the
  manifests (non-root user 1000, no privilege escalation, all capabilities dropped, seccomp RuntimeDefault).
- **App cannot reach the database** - `kubectl get secret aibal-db-app` must exist and the network policy in
  `postgres.yaml` allows only pods of the same namespace.
- **HTTPS certificate not issued** - `kubectl describe certificate aibal-tls`; the Ingress must use the class
  `nginx-traefik` and the issuer `letsencrypt-gateway` (as in `app.yaml`).
- Rate limits are counted per gunicorn worker (2); for exact limits run a Redis-compatible store (the platform
  offers the Dragonfly operator) and set `RATELIMIT_STORAGE_URI` in `aibal.env`.

## Own domain later

To keep `aibal.fsv.cvut.cz`, CTU IT must point it to the cluster's load balancer. Because the app sends
e-mails, use an A/AAAA record to the load balancer's IP, not a CNAME (platform rule). Then add the host to the
Ingress in `app.yaml`, change `APP_BASE_URL`, and add the domain to reCAPTCHA.

Platform documentation: https://docs.cerit-sc.cz (Kubernetes, PostgreSQL operator, Harbor registry).
