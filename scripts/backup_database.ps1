# NeuralQuant Database Backup — Windows PowerShell Script
# Creates a compressed SQL dump of the entire Supabase PostgreSQL database.
#
# Requires: PostgreSQL client tools (pg_dump). Install via:
#   choco install postgresql
#   OR download from https://www.postgresql.org/download/windows/
#
# Usage:
#   .\scripts\backup_database.ps1
#
# Output:
#   backups\nq_backup_YYYY-MM-DD_HHMMSS.sql.gz

param(
    [string]$DbUrl = "postgresql://postgres:Thomasarthurpolly08%23@db.ajkhyayrbqiuvnsmqrdz.supabase.co:5432/postgres",
    [string]$BackupDir = ".\backups"
)

$ErrorActionPreference = "Stop"

# ── Create backup directory ──────────────────────────────────────────────────
$dir = Resolve-Path $BackupDir -ErrorAction SilentlyContinue
if (-not $dir) {
    New-Item -ItemType Directory -Path $BackupDir | Out-Null
    $dir = Resolve-Path $BackupDir
}

# ── Timestamped filename ────────────────────────────────────────────────────
$ts = (Get-Date -Format "yyyy-MM-dd_HHmmss")
$outFile = Join-Path $dir "nq_backup_${ts}.sql.gz"

# ── Check pg_dump ────────────────────────────────────────────────────────────
$pgDump = Get-Command pg_dump -ErrorAction SilentlyContinue
if (-not $pgDump) {
    Write-Host "ERROR: pg_dump not found in PATH." -ForegroundColor Red
    Write-Host ""
    Write-Host "Install one of these:"
    Write-Host "  1. PostgreSQL tools:  choco install postgresql"
    Write-Host "  2. Docker fallback:   docker run --rm postgres:17-alpine pg_dump ..."
    Write-Host ""
    exit 1
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "NeuralQuant Database Backup"
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Database: $($DbUrl.Split('@')[-1])"
Write-Host "Output:   $outFile"
Write-Host ""

# ── Run pg_dump piped to gzip ────────────────────────────────────────────────
$env:PGPASSWORD = "Thomasarthurpolly08#"

try {
    # pg_dump writes SQL to stdout; we pipe to gzip
    & pg_dump `
        --dbname "$DbUrl" `
        --format plain `
        --verbose `
        --no-owner `
        --no-privileges `
        2>$null |
        & gzip -c > "$outFile"

    $sizeMB = (Get-Item $outFile).Length / 1MB
    Write-Host "Backup complete!" -ForegroundColor Green
    Write-Host "   File: $outFile"
    Write-Host "   Size: $($sizeMB.ToString('F2')) MB"
    Write-Host ""
    Write-Host "IMPORTANT: Keep this file safe. It contains ALL production data." -ForegroundColor Yellow
    Write-Host "Store in a password manager or encrypted drive." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "To restore later:"
    Write-Host "   gunzip < $outFile | psql '$DbUrl'"
} catch {
    Write-Host "ERROR: Backup failed — $_" -ForegroundColor Red
    if (Test-Path $outFile) { Remove-Item $outFile -Force }
    exit 1
}
