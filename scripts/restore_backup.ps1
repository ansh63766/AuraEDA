# Windows PowerShell Restore Script
$BackupDir = "v2.0_backup"
if (Test-Path $BackupDir) {
    Copy-Item -Path "$BackupDir\*" -Destination ".\" -Recurse -Force
    Write-Host "Backup successfully restored!" -ForegroundColor Green
} else {
    Write-Warning "Backup directory $BackupDir not found."
}
