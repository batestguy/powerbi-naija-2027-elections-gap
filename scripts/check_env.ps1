# Phase 0 environment check. Re-runnable; writes reports/env_check.json and exits 1 if a required check fails.
# Usage (from repo root):  pwsh -File scripts/check_env.ps1
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$results = [ordered]@{ checked_at = (Get-Date).ToString('s'); checks = @() }

function Add-Check($name, $pass, $detail, $required = $true) {
    $script:results.checks += [ordered]@{ name = $name; pass = [bool]$pass; required = $required; detail = "$detail" }
}

# Power BI Desktop: Store edition or installer edition
$pbiVersion = $null
$store = Get-AppxPackage Microsoft.MicrosoftPowerBIDesktop -ErrorAction SilentlyContinue
if ($store) { $pbiVersion = [version]$store.Version; $pbiKind = 'Store' }
else {
    $exe = Get-Item 'C:\Program Files\Microsoft Power BI Desktop\bin\PBIDesktop.exe' -ErrorAction SilentlyContinue
    if ($exe) { $pbiVersion = [version]($exe.VersionInfo.ProductVersion -replace '[^\d\.].*$', ''); $pbiKind = 'Installer' }
}
Add-Check 'powerbi_desktop_installed' ($null -ne $pbiVersion) "$pbiKind $pbiVersion"

# Feature availability by version, per Microsoft release notes:
#   Shape map GA in June 2026 update (2.155); PBIP GA in September 2026 update (assumed 2.158).
#   Version thresholds are taken from release-note summaries, not verified against each build.
if ($pbiVersion) {
    Add-Check 'shape_map_ga_by_version' ($pbiVersion -ge [version]'2.155.0.0') 'Shape map GA from 2.155 (June 2026)'
    Add-Check 'pbip_ga_by_version' ($pbiVersion -ge [version]'2.158.0.0') 'PBIP GA from Sept 2026 update (assumed 2.158)'
}

# Preview toggles the user has changed (read-only copy of Desktop's settings archive)
$userZip = Join-Path $env:USERPROFILE 'Microsoft\Power BI Desktop Store App\User.zip'
if (-not (Test-Path $userZip)) { $userZip = Join-Path $env:LOCALAPPDATA 'Microsoft\Power BI Desktop\User.zip' }
if (Test-Path $userZip) {
    $tmp = Join-Path ([IO.Path]::GetTempPath()) ("pbiuser_" + [guid]::NewGuid())
    Expand-Archive $userZip $tmp
    $xml = [xml](Get-Content (Join-Path $tmp 'UserInterface\Settings.xml') -Raw)
    $types = $xml.UISettingsConfig.Entries.Entry | ForEach-Object Type
    Remove-Item $tmp -Recurse -Force
    $preview = $types | Where-Object { $_ -match 'Preview|Pbip|Pbir|ShapeMap' }
    Add-Check 'desktop_settings_readable' $true ("preview-related entries: " + ($(if ($preview) { $preview -join ', ' } else { 'none (all defaults)' }))) $false
} else { Add-Check 'desktop_settings_readable' $false 'User.zip not found (Desktop never run?)' $false }

# Pinned Python env
$py = Join-Path $root '.venv\Scripts\python.exe'
$pinned = (Get-Content (Join-Path $root '.python-version') -Raw).Trim()
if (Test-Path $py) {
    $v = (& $py -c "import platform; print(platform.python_version())").Trim()
    Add-Check 'python_pinned_env' ($v -eq $pinned) "venv=$v pinned=$pinned"
} else { Add-Check 'python_pinned_env' $false '.venv missing: run uv sync' }

# Network: a real host must answer and an impossible host must fail
try { $r = Invoke-WebRequest https://www.example.com -TimeoutSec 20; Add-Check 'network_real_host' ($r.StatusCode -eq 200) "HTTP $($r.StatusCode)" }
catch { Add-Check 'network_real_host' $false $_.Exception.Message }
try { Invoke-WebRequest https://no-such-host-zz9.invalid -TimeoutSec 10 | Out-Null; Add-Check 'network_impossible_host_fails' $false 'unexpectedly succeeded' }
catch { Add-Check 'network_impossible_host_fails' $true $_.Exception.Message }

# Screen recorder for the walkthrough video
$rec = @('Microsoft.ScreenSketch', 'Microsoft.XboxGamingOverlay') | ForEach-Object { Get-AppxPackage $_ -ErrorAction SilentlyContinue } | ForEach-Object { "$($_.Name) $($_.Version)" }
Add-Check 'screen_recorder_available' ($rec.Count -gt 0) ($rec -join '; ')

# Resources
$freeGB = [math]::Round((Get-PSDrive (Split-Path $root -Qualifier).TrimEnd(':')).Free / 1GB, 1)
Add-Check 'disk_free_gb_over_10' ($freeGB -gt 10) "$freeGB GB"
$ramGB = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 1)
Add-Check 'ram_gb_over_8' ($ramGB -gt 8) "$ramGB GB"

$out = Join-Path $root 'reports\env_check.json'
$results | ConvertTo-Json -Depth 5 | Set-Content $out -Encoding utf8
$results.checks | ForEach-Object { '{0,-32} {1,-5} {2}' -f $_.name, $(if ($_.pass) { 'PASS' } else { 'FAIL' }), $_.detail }
$failed = @($results.checks | Where-Object { $_.required -and -not $_.pass })
"`n$($results.checks.Count) checks, $($failed.Count) required failures. Written to reports/env_check.json"
if ($failed.Count) { exit 1 }
