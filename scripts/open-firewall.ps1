# Allow WarehouseDB (port 8000) through Windows Firewall for ESP32 robots on your LAN.
# Run once in PowerShell as Administrator (from WarehouseDB/):
#   Set-ExecutionPolicy -Scope Process Bypass; .\scripts\open-firewall.ps1

$ruleName = "WarehouseDB port 8000"
$existing = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Firewall rule already exists: $ruleName"
} else {
    New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8000 | Out-Null
    Write-Host "Created firewall rule: $ruleName"
}
Write-Host "Done. Restart the server with: python run.py"
