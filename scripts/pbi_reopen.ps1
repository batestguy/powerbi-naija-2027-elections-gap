<#
.SYNOPSIS
  Close Power BI Desktop (only if it has no unsaved changes), reopen the project, wait for the bridge, refresh data.
  Needed after semantic-model (TMDL) changes: `powerbi-desktop reload` re-reads report files only.
  -Force closes Desktop even with unsaved changes (kills the process). Use only when the window is driven by scripts:
  a data refresh alone marks the file unsaved, and the data cache is rebuilt from data/staging on reopen anyway.

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts/pbi_reopen.ps1
#>
param([string]$Pbip = (Join-Path $PSScriptRoot '..\pbip\NaijaElectionsGap.pbip'), [int]$TimeoutSec = 300, [switch]$Force)
$ErrorActionPreference = 'Stop'
$Pbip = (Resolve-Path $Pbip).Path

function Status { (powerbi-desktop status | Out-String) | ConvertFrom-Json }

$desk = Get-Process PBIDesktop -ErrorAction SilentlyContinue
if ($desk) {
  # Act only on THIS project's window. Any other Desktop (another file, or one whose bridge state is unknown)
  # stops the script, so another project's work can never be closed or killed.
  $inst = @((Status).instances)
  $ours = @($inst | Where-Object { $_.currentFilePath -eq $Pbip })
  $unknown = @($desk | Where-Object { $_.Id -notin $inst.pid })
  $others = @($inst | Where-Object { $_.currentFilePath -ne $Pbip })
  if ($others.Count -or $unknown.Count) {
    throw "Another Power BI Desktop is running (pids: $(@($others.pid) + @($unknown.Id) -join ', ')) - close it first; not touching it."
  }
  $dirty = [bool]($ours | Where-Object { $_.hasUnsavedChanges -ne $false })
  if ($dirty -and -not $Force) { throw 'Desktop has unsaved (or unknown) changes - not closing it (use -Force if only scripts drive it).' }
  $mine = $desk | Where-Object { $_.Id -in $ours.pid }
  if ($dirty) { $mine | Stop-Process -Force } else { foreach ($p in @($mine)) { [void]$p.CloseMainWindow() } }
  $t = 0; while ((Get-Process PBIDesktop -ErrorAction SilentlyContinue) -and $t -lt 60) { Start-Sleep 2; $t += 2 }
  if (Get-Process PBIDesktop -ErrorAction SilentlyContinue) { throw 'Desktop did not close within 60 s (a dialog may be open).' }
}

if (-not $env:PBI_DESKTOP_PATH) {
  $pkg = Get-AppxPackage -Name Microsoft.MicrosoftPowerBIDesktop -ErrorAction SilentlyContinue
  if ($pkg) { $env:PBI_DESKTOP_PATH = Join-Path $pkg.InstallLocation 'bin\pbidesktop.exe' }
}
# Start Desktop detached. (Capturing `powerbi-desktop open` output hangs: Desktop inherits the pipe, so the
# capture waits until Desktop exits.)
if (-not $env:PBI_DESKTOP_PATH) { throw 'Power BI Desktop executable not found; set PBI_DESKTOP_PATH.' }
Write-Host "opening $Pbip"
Start-Process -FilePath $env:PBI_DESKTOP_PATH -ArgumentList "`"$Pbip`""

$t = 0
do {
  Start-Sleep 5; $t += 5
  $i = (Status).instances | Where-Object { $_.bridgeStatus -eq 'connected' -and $_.currentFilePath -eq $Pbip }
} until ($i -or $t -ge $TimeoutSec)
if (-not $i) { throw "Desktop did not open $Pbip within $TimeoutSec s." }
Write-Host "bridge connected (pid $($i.pid)); refreshing data"

# The engine can lag the bridge. Wait until it answers a harmless Info call, then refresh ONCE.
# (Retrying the refresh while the engine starts up left "Could not find a PackageSession" dialogs that block Desktop.)
$engine = Join-Path $PSScriptRoot 'pbi_engine.ps1'
# Desktop may run its own "Load" refresh on open (e.g. after new tables were added); pbi_engine.ps1 refuses while
# any dialog is showing, so this loop also waits for that Load window to close.
$t = 0
do {
  Start-Sleep 5; $t += 5
  $info = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $engine -Action Info 2>&1 | Out-String
} until ($info -match '"database"' -or $t -ge $TimeoutSec)
if ($info -notmatch '"database"') { throw "Local engine not ready within $TimeoutSec s (a dialog may still be open): $info" }
$r = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $engine -Action Refresh 2>&1 | Out-String
if ($r -notmatch '"ok"') { throw "Refresh through the local engine did not succeed: $r" }
[pscustomobject]@{ pid = $i.pid; file = $Pbip; refreshed = $true } | ConvertTo-Json
