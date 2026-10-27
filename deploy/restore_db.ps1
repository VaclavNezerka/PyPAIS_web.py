# Restores a dump of the current AIBAL database into the PostgreSQL cluster on e-INFRA and applies
# the pending migrations. Run it after "kubectl apply -f deploy/k8s/postgres.yaml" and before the app starts.
#   powershell -ExecutionPolicy Bypass -File deploy\restore_db.ps1 -Dump C:\path\aibal_prod.dump
# The dump comes from the current server (see deploy/README.md, step 5):
#   pg_dump -Fc -h localhost -U <DB_USERNAME> -d <DB_NAME> -f aibal_prod.dump
# The restore runs inside the database pod, so only the compressed dump crosses the network; through
# "kubectl port-forward" the uncompressed photos and masks go through Rancher's proxy and take hours.
param(
    [Parameter(Mandatory = $true)][string]$Dump,
    # the database to restore into (it must have no tables yet); the app's database by default
    [string]$Database = ""
)
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$Dump = (Resolve-Path $Dump).Path

function Get-SecretValue([string]$key) {
    $b64 = kubectl get secret aibal-db-app -o "jsonpath={.data.$key}"
    if ($LASTEXITCODE -ne 0 -or -not $b64) { throw "Cannot read secret aibal-db-app ($key) - is the database cluster running?" }
    [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($b64))
}

$owner = Get-SecretValue "username"
if (-not $Database) { $Database = Get-SecretValue "dbname" }
$pod = kubectl get cluster.postgresql.cnpg.io aibal-db -o "jsonpath={.status.currentPrimary}"
if ($LASTEXITCODE -ne 0 -or -not $pod) { throw "Database cluster aibal-db not found - apply deploy/k8s/postgres.yaml first" }

# the superuser connects through the pod's local socket; SET ROLE makes the app user the owner of everything
function Invoke-Psql([string[]]$arguments) {
    kubectl exec $pod -c postgres -- psql -d $Database -v ON_ERROR_STOP=1 -X -q -c "SET ROLE $owner" @arguments
    if ($LASTEXITCODE -ne 0) { throw "psql failed: $arguments" }
}

$tables = kubectl exec $pod -c postgres -- psql -d $Database -X -At -c "SELECT count(*) FROM pg_tables WHERE schemaname = 'public'"
if ($LASTEXITCODE -ne 0) { throw "Cannot connect to database $Database in pod $pod" }
if ([int]$tables -gt 0) {
    throw "Database $Database already has $tables tables - the restore needs an empty database. To start over:`n" +
          "  kubectl exec $pod -c postgres -- dropdb --force $Database`n" +
          "  kubectl exec $pod -c postgres -- createdb -O $owner $Database"
}

# files are copied next to the data directory (the pod's root file system is read-only)
$remote = "/var/lib/postgresql/data/aibal-restore"
try {
    kubectl exec $pod -c postgres -- mkdir -p "$remote/migrations"
    Write-Host "Copying $Dump to $pod ..."
    # kubectl cp reads "C:" as a pod name - copy by relative paths
    Push-Location (Split-Path -Parent $Dump)
    try { kubectl cp -c postgres (Split-Path -Leaf $Dump) "$($pod):$remote/restore.dump" } finally { Pop-Location }
    if ($LASTEXITCODE -ne 0) { throw "Copying the dump failed" }
    Push-Location "$repo\db_migrations"
    try { foreach ($sql in Get-ChildItem *.sql) { kubectl cp -c postgres $sql.Name "$($pod):$remote/migrations/$($sql.Name)" } } finally { Pop-Location }

    Write-Host "Restoring into $Database ..."
    # objects get the app user as owner; grants of the old server's roles are not needed
    kubectl exec $pod -c postgres -- pg_restore -d $Database --role=$owner --no-owner --no-privileges --exit-on-error "$remote/restore.dump"
    if ($LASTEXITCODE -ne 0) { throw "pg_restore failed" }

    foreach ($sql in Get-ChildItem "$repo\db_migrations\*.sql" | Sort-Object Name) {
        Write-Host "Applying migration $($sql.Name)"
        Invoke-Psql @("-f", "$remote/migrations/$($sql.Name)")
    }

    Write-Host "Rows after the restore (compare with the current server):"
    kubectl exec $pod -c postgres -- psql -d $Database -X -c "SELECT (SELECT count(*) FROM companies) AS companies, (SELECT count(*) FROM users) AS users, (SELECT count(*) FROM experiments) AS samples, pg_size_pretty(pg_database_size(current_database())) AS size"
}
finally {
    # the dump holds all user data - do not leave it in the pod
    kubectl exec $pod -c postgres -- rm -rf $remote
}
