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
winget install Docker.DockerDesktop     # then start Docker Desktop once; it brings kubectl too
```

Open a new terminal afterwards, so `docker` and `kubectl` are on the PATH. Windows blocks `.ps1` scripts by
default, so the scripts below are started with `powershell -ExecutionPolicy Bypass -File ...` (this allows
just that one script and changes no setting).

## 2. Access to the cluster

1. Log in at **https://rancher.cloud.e-infra.cz** with your e-INFRA CZ account. The first login creates your
   personal project and namespace `<surname>-ns` (AIBAL runs in `nezerka-ns`).
2. On the Home page, click the cluster **kuba-cluster**, then the **Download KubeConfig** icon in the upper
   right, and save the file as `%USERPROFILE%\.kube\config`.
3. Use the namespace by default and check the access:

```powershell
kubectl config set-context --current --namespace=nezerka-ns
kubectl get pods
```

A separate namespace is possible too: create it in the Rancher GUI (Namespaces → Create), not with kubectl,
or it is not linked to your project and its quota.

## 3. Build and push the image

1. Log in at **https://hub.cerit.io**, open your user profile (upper right) and copy the **CLI secret**.
2. Log in Docker to the registry (user name = your Harbor user name, password = the CLI secret), then build:

```powershell
docker login cerit.io
powershell -ExecutionPolicy Bypass -File deploy\build_push.ps1 -User <your-harbor-user>
```

The image has about 17 GB (PyTorch with CUDA alone is 8 GB): the first build and push take long, later
ones only send the changed app layer. Keep the VPN off for them.

3. Put the printed image name (`cerit.io/<user>/aibal:<commit>`) into `deploy/k8s/app.yaml`
   (`cerit.io/nezervac/aibal:5136f09` is the first deployed version).

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

The current app runs on `webhost-03.fsv.cvut.cz` in `/var/www/sites/aibal.fsv.cvut.cz/app/` (reached over
the CTU VPN, e.g. with WinSCP; its database accepts only local connections).

1. Stop the app on the current server, so nothing changes after the dump.
2. Dump the database there with the login from the app's `.env` - in WinSCP: Commands → Open Terminal:

```bash
cd /var/www/sites/aibal.fsv.cvut.cz/app && v() { sed -n "s/^$1=//p" .env | tr -d "\r\"'"; } && PGPASSWORD="$(v DB_PASSWORD)" pg_dump -Fc -h "$(v DB_HOST)" -U "$(v DB_USERNAME)" -d "$(v DB_NAME)" -f ~/aibal_prod.dump && ls -lh ~/aibal_prod.dump
```

3. Download `~/aibal_prod.dump` to this PC, outside synced folders. Restore it into the new database. The
   script copies the dump into the database pod, restores it there, applies `db_migrations/` and prints the
   number of companies, users and samples to compare:

```powershell
powershell -ExecutionPolicy Bypass -File deploy\restore_db.ps1 -Dump C:\path\aibal_prod.dump
```

The October 2026 dump (84 MB; 3 companies, 9 users, 41 samples) restored in under 2 minutes. The script only
restores into an empty database and prints how to empty it otherwise. Delete the dump from the old server
and this PC afterwards - it contains all user data (`*.dump` is git-ignored).

## 6. Secret settings

1. Copy `deploy/aibal.env.example` to `aibal.env` and fill it in with the values of the current server's
   `.env` (SECRET_KEY, mail, admin addresses). Keep it outside synced folders (OneDrive, ownCloud) - it holds
   the mail password; AIBAL's lives in `C:\Users\vacla\pgsql\dumps\aibal.env`. The server's `.env` is a hidden
   file: `ls -a` lists it, and WinSCP shows it after Ctrl+Alt+H.
2. reCAPTCHA: the new address has its own reCAPTCHA v3 site (registered in October 2026 at
   https://www.google.com/recaptcha/admin, domain `aibal.dyn.cloud.e-infra.cz`), so its two keys differ from
   the old server's. Without a matching secret key nobody can log in.
3. Store them in the cluster (and after a change, `kubectl rollout restart deployment/aibal`):

```powershell
kubectl create secret generic aibal-secrets --from-env-file=C:\Users\vacla\pgsql\dumps\aibal.env --dry-run=client -o yaml | kubectl apply -f -
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
powershell -ExecutionPolicy Bypass -File deploy\build_push.ps1 -User <your-harbor-user>
kubectl set image deployment/aibal app=cerit.io/<user>/aibal:<new tag>
```

New database migrations: put them into `db_migrations/` (the folder's `*.sql` files are git-ignored, add
them with `git add -f`) and apply them in the database pod, as the app's database user:

```powershell
$pod = kubectl get cluster.postgresql.cnpg.io aibal-db -o "jsonpath={.status.currentPrimary}"
Get-Content db_migrations\<file>.sql -Raw | kubectl exec -i $pod -c postgres -- psql -d aibal -v ON_ERROR_STOP=1 -X -c "SET ROLE aibal" -f -
```
Changed secrets: re-run the command of step 6.3 and `kubectl rollout restart deployment/aibal`.

## Developer accounts and the activity report

Every request is recorded in the table `activity_log` (migration `2026-10-29_developer_activity_log.sql`);
developers see the report at `/developer` (link in the user menu) with the event log and a CSV download.
The role is granted only in the database, never in the app - in the database pod:

```powershell
kubectl exec -i $pod -c postgres -- psql -d aibal -X -c "SET ROLE aibal" -c "UPDATE users SET is_developer = true WHERE username = '<username>'"
```

The user sees the link after the next login. No IP addresses or cookies are stored (see `activity.py`); rows
older than `ACTIVITY_RETENTION_DAYS` (default 400) are deleted. `ACTIVITY_LOG=0` in `aibal.env` turns the
recording off. A fresh dump of the old server has no activity log and no developers: `restore_db.ps1` applies
the migration, the role has to be granted again.

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
