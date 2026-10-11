# Prepared only. Requires approval for browser/driver internal temporary cleanup.
$ErrorActionPreference = 'Stop'
$taskRoot = [IO.Path]::GetFullPath($PSScriptRoot)
$runtimeRoot = [IO.Path]::GetFullPath((Join-Path $taskRoot 'browser-runtime-01'))
if (-not $runtimeRoot.StartsWith($taskRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Unexpected runtime target' }
if (Test-Path -LiteralPath $runtimeRoot) { throw 'Refusing to reuse an existing browser runtime directory' }
if (Get-NetTCPConnection -LocalPort 9227 -State Listen -ErrorAction SilentlyContinue) { throw 'Debug port 9227 already in use' }
$profileRoot = Join-Path $runtimeRoot 'profile'
$temporaryRoot = Join-Path $runtimeRoot 'temp'
$dumpRoot = Join-Path $runtimeRoot 'crash-dumps'
New-Item -ItemType Directory -Path $runtimeRoot,$profileRoot,$temporaryRoot,$dumpRoot | Out-Null
$taskPreviousTemp = $env:TEMP
$taskPreviousTmp = $env:TMP
try {
    $env:TEMP = $temporaryRoot
    $env:TMP = $temporaryRoot
    $browserArguments = @('--headless=new','--remote-debugging-address=127.0.0.1','--remote-debugging-port=9227',"--user-data-dir=$profileRoot", "--crash-dumps-dir=$dumpRoot",'--no-first-run','--no-default-browser-check','--disable-background-networking','--disable-component-update','--disable-sync','--disable-extensions','--disable-breakpad','--disable-crash-reporter','--disable-gpu','--metrics-recording-only','about:blank')
    $browserProcess = Start-Process -FilePath 'C:\Program Files\Google\Chrome\Application\chrome.exe' -ArgumentList $browserArguments -WindowStyle Hidden -PassThru
    $record = @{pid=$browserProcess.Id;debug_endpoint='http://127.0.0.1:9227';profile=$profileRoot;temporary=$temporaryRoot;artifact_cleanup='No explicit profile/artifact deletion';launch_scope='New synthetic local browser only'} | ConvertTo-Json
    $recordPath = Join-Path $runtimeRoot 'launch.json'
    $recordStream = [IO.File]::Open($recordPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
    $recordWriter = [IO.StreamWriter]::new($recordStream)
    try { $recordWriter.Write($record) } finally { $recordWriter.Dispose() }
    Write-Output $record
} finally {
    $env:TEMP = $taskPreviousTemp
    $env:TMP = $taskPreviousTmp
}
