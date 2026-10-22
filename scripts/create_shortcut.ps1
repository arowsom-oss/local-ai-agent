param(
    [Parameter(Mandatory=$true)][string]$Pythonw,
    [string]$Destination = [Environment]::GetFolderPath('Desktop')
)
$ErrorActionPreference = 'Stop'
$appFolder = (Resolve-Path -LiteralPath (Split-Path -Parent $PSScriptRoot)).Path
$runtimePath = (Resolve-Path -LiteralPath $Pythonw).Path
$shortcutFolder = (Resolve-Path -LiteralPath $Destination).Path
$sourcePath = Join-Path $appFolder 'chat_window.py'
$iconPath = Join-Path $appFolder 'assets\local-studio.ico'
if ((Split-Path -Leaf $runtimePath) -ne 'pythonw.exe') { throw 'Choose the existing app runtime pythonw.exe.' }
if (!(Test-Path -LiteralPath $sourcePath) -or !(Test-Path -LiteralPath $iconPath)) { throw 'App source or icon missing.' }
$shortcutPath = Join-Path $shortcutFolder 'Local Studio.lnk'
$shellObject = New-Object -ComObject WScript.Shell
$shortcutObject = $shellObject.CreateShortcut($shortcutPath)
$sourceArgument = '"' + $sourcePath + '"'
if ((Test-Path -LiteralPath $shortcutPath) -and
    ($shortcutObject.TargetPath -ne $runtimePath -or $shortcutObject.Arguments -ne $sourceArgument)) {
    throw 'An unrelated Local Studio shortcut exists; choose another destination.'
}
$shortcutObject.TargetPath = $runtimePath
$shortcutObject.Arguments = $sourceArgument
$shortcutObject.WorkingDirectory = $appFolder
$shortcutObject.IconLocation = $iconPath + ',0'
$shortcutObject.Description = 'Local Studio - private local AI assistant'
$shortcutObject.Save()
[pscustomobject]@{ shortcut=$shortcutPath; target=$runtimePath; source=$sourcePath; icon=$iconPath } | ConvertTo-Json
