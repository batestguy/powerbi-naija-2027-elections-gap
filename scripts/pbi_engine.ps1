<#
.SYNOPSIS
  Talk to the local Analysis Services engine inside a running Power BI Desktop: refresh the model, run DAX checks.

.DESCRIPTION
  Uses the ADOMD client that ships with Desktop (no install). Finds the engine (msmdsrv) started by the Desktop
  process, its port, and its single database. Runs in Windows PowerShell 5.1 (the DLLs target .NET Framework).

  Refresh: sends a TMSL full refresh of the database (same effect as Home > Refresh).
  Query:   runs one DAX query and writes the rows as JSON (stdout, or -Out file).

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts/pbi_engine.ps1 -Action Refresh
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts/pbi_engine.ps1 -Action Query -Dax "EVALUATE dim_party"
#>
param(
  [Parameter(Mandatory = $true)][ValidateSet('Refresh', 'Query', 'Info')][string]$Action,
  [string]$Dax,
  [string]$DaxFile,
  [string]$Out,
  [int]$DesktopPid = 0,
  [int]$TimeoutSec = 300,
  [int]$DialogWaitSec = 180
)
$ErrorActionPreference = 'Stop'

$desk = if ($DesktopPid) { Get-Process -Id $DesktopPid } else { Get-Process PBIDesktop -ErrorAction SilentlyContinue }
if (-not $desk) { throw 'Power BI Desktop is not running.' }
if (@($desk).Count -gt 1) { throw "More than one Desktop is running ($(@($desk).Id -join ', ')); pass -DesktopPid." }
# Refuse to work while Desktop shows a dialog: it blocks the bridge and can leave the model half-refreshed.
Add-Type @"
using System; using System.Runtime.InteropServices;
public class PbiWin {
  public delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc f, IntPtr l);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
  public static int Count(uint p) { int n = 0;
    EnumWindows((h, l) => { uint q; GetWindowThreadProcessId(h, out q); RECT r;
      if (q == p && IsWindowVisible(h) && GetWindowRect(h, out r) && r.R - r.L > 50 && r.B - r.T > 50) n++; return true; }, IntPtr.Zero);
    return n; }
}
"@
# Desktop may be running its own "Load" (after opening or a model change). Wait until no dialog has been seen for
# 3 checks in a row (2 s apart); give up after $DialogWaitSec with a clear message.
$quiet = 0; $waited = 0
while ($quiet -lt 3) {
  $dialogs = [PbiWin]::Count([uint32]$desk.Id) - 1
  if ($dialogs -gt 0) { $quiet = 0 } else { $quiet++ }
  if ($quiet -lt 3) {
    if ($waited -ge $DialogWaitSec) { throw "Power BI Desktop (pid $($desk.Id)) still has $dialogs dialog(s) open after $DialogWaitSec s - not proceeding." }
    Start-Sleep 2; $waited += 2
  }
}

$bin = Split-Path $desk.Path
Add-Type -Path (Join-Path $bin 'Microsoft.PowerBI.AdomdClient.dll')

$engine = Get-CimInstance Win32_Process -Filter "Name = 'msmdsrv.exe' AND ParentProcessId = $($desk.Id)"
if (-not $engine) { throw "No msmdsrv engine under Desktop pid $($desk.Id) (is a file open?)." }
$port = (Get-NetTCPConnection -OwningProcess $engine.ProcessId -State Listen | Where-Object LocalAddress -in '127.0.0.1', '::1' |
         Select-Object -First 1).LocalPort
if (-not $port) { throw 'Engine listening port not found.' }

$conn = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection "Data Source=localhost:$port"
$conn.Open()
try {
  $cmd = $conn.CreateCommand()
  $cmd.CommandTimeout = $TimeoutSec   # never hang silently; ADOMD raises a timeout error instead
  $cmd.CommandText = 'SELECT [CATALOG_NAME] FROM $SYSTEM.DBSCHEMA_CATALOGS'
  $r = $cmd.ExecuteReader(); $dbs = @(); while ($r.Read()) { $dbs += $r.GetString(0) }; $r.Close()
  if ($dbs.Count -ne 1) { throw "Expected one database, found $($dbs.Count)." }
  $db = $dbs[0]

  switch ($Action) {
    'Info' { [pscustomobject]@{ desktopPid = $desk.Id; enginePid = $engine.ProcessId; port = $port; database = $db } | ConvertTo-Json }
    'Refresh' {
      $t0 = Get-Date
      $cmd.CommandText = (@{ refresh = @{ type = 'full'; objects = @(@{ database = $db }) } } | ConvertTo-Json -Depth 5)
      [void]$cmd.ExecuteNonQuery()
      [pscustomobject]@{ action = 'refresh'; database = $db; seconds = [math]::Round(((Get-Date) - $t0).TotalSeconds, 1); status = 'ok' } | ConvertTo-Json
    }
    'Query' {
      if ($DaxFile) { $Dax = Get-Content -Raw $DaxFile }
      if (-not $Dax) { throw 'Query needs -Dax or -DaxFile.' }
      $conn.ChangeDatabase($db)
      $cmd.CommandText = $Dax
      $r = $cmd.ExecuteReader()
      $rows = @()
      while ($r.Read()) {
        $o = [ordered]@{}
        for ($i = 0; $i -lt $r.FieldCount; $i++) { $o[$r.GetName($i)] = if ($r.IsDBNull($i)) { $null } else { $r.GetValue($i) } }
        $rows += [pscustomobject]$o
      }
      $r.Close()
      $json = ConvertTo-Json -InputObject @($rows) -Depth 4
      if ($Out) { Set-Content -Path $Out -Value $json -Encoding UTF8 } else { $json }
    }
  }
}
finally { $conn.Close() }
