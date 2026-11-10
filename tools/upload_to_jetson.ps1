param(
    [string]$HostName = "jetson",
    [string]$Destination = "/home/jetson/syf/vision_code",
    [string]$PackagePath = ""
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
if (-not $PackagePath) {
    $PackagePath = Join-Path $env:TEMP "r2_gripper_vision_runtime.tar.gz"
}

if (Test-Path $PackagePath) {
    Remove-Item -LiteralPath $PackagePath -Force
}

tar -czf $PackagePath -C $Root configs docs head_rack_align models tools README.md requirements.txt
scp $PackagePath "${HostName}:/tmp/r2_gripper_vision_runtime.tar.gz"

$remote = @"
set -e
DEST="$Destination"
PARENT=`$(dirname "`$DEST")
mkdir -p "`$PARENT"
if [ -d "`$DEST" ]; then
  BACKUP="`$DEST.backup.`$(date +%Y%m%d_%H%M%S)"
  mv "`$DEST" "`$BACKUP"
  echo "Backed up old vision_code to `$BACKUP"
fi
mkdir -p "`$DEST"
tar -xzf /tmp/r2_gripper_vision_runtime.tar.gz -C "`$DEST"
chmod +x "`$DEST/tools/run_r2_gripper_v5_jetson.sh"
mkdir -p "`$DEST/logs"
echo "Uploaded vision runtime to `$DEST"
"@

ssh $HostName $remote
