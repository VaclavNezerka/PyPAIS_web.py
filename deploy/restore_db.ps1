# Restores a dump of the current AIBAL database into the PostgreSQL cluster on e-INFRA and applies
# the pending migrations. Run it after "kubectl apply -f deploy/k8s/postgres.yaml" and before the app starts.
#   .\deploy\restore_db.ps1 -Dump C:\path\aibal_prod.dump
# The dump comes from the current server (see deploy/README.md, step 5):
#   pg_dump -Fc -h localhost -U <DB_USERNAME> -d <DB_NAME> -f aibal_prod.dump
param(
    [Parameter(Mandatory = $true)][string]$Dump,
    # PostgreSQL client tools (17 or newer); the portable installation of this PC by default
    [string]$PgBin = "C:\Users\vacla\pgsql\pgsql\bin",
    [int]$LocalPort = 15432
)
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path $Dump)) { throw "Dump not found: $Dump" }

function Get-SecretValue([string]$key) {
    $b64 = kubectl get secret aibal-db-app -o "jsonpath={.data.$key}"
    if ($LASTEXITCODE -ne 0 -or -not $b64) { throw "Cannot read secret aibal-db-app ($key) - is the database cluster running?" }
    [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($b64))
}

$dbUser = Get-SecretValue "username"
$dbName = Get-SecretValue "dbname"
$env:PGPASSWORD = Get-SecretValue "password"

# the database is not reachable from outside the cluster - forward it to this PC for the restore
$forward = Start-Process kubectl -ArgumentList "port-forward", "svc/aibal-db-rw", "$($LocalPort):5432" -PassThru -WindowStyle Hidden
try {
    Start-Sleep -Seconds 4
    $conn = @("-h", "127.0.0.1", "-p", "$LocalPort", "-U", $dbUser, "-d", $dbName)

    Write-Host "Restoring $Dump into $dbName ..."
    # objects get the app user as owner; grants of the old server's roles are not needed
    & "$PgBin\pg_restore.exe" @conn --no-owner --no-privileges --exit-on-error $Dump
    if ($LASTEXITCODE -ne 0) { throw "pg_restore failed" }

    foreach ($sql in Get-ChildItem "$repo\db_migrations\*.sql" | Sort-Object Name) {
        Write-Host "Applying migration $($sql.Name)"
        & "$PgBin\psql.exe" @conn -v ON_ERROR_STOP=1 -f $sql.FullName
        if ($LASTEXITCODE -ne 0) { throw "migration $($sql.Name) failed" }
    }

    Write-Host "Rows after the restore (compare with the current server):"
    & "$PgBin\psql.exe" @conn -c "SELECT (SELECT count(*) FROM companies) AS companies, (SELECT count(*) FROM users) AS users, (SELECT count(*) FROM experiments) AS samples, pg_size_pretty(pg_database_size(current_database())) AS size;"
}
finally {
    Stop-Process -Id $forward.Id -ErrorAction SilentlyContinue
    Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
}
