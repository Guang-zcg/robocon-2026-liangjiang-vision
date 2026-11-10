param(
    [int]$Camera = 1,
    [string]$Device = "cpu",
    [switch]$Show = $true,
    [string]$JsonOut = ""
)

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$env:PYTHONPATH = $Root
$env:YOLO_CONFIG_DIR = Join-Path $Root "Ultralytics"
$env:MPLCONFIGDIR = Join-Path $Root "matplotlib_cache"

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    $Python = "python"
}

$Model = "models\rack_connector_v5_single_slot_best.pt"
$Config = "configs\r2_gripper.yaml"

$Args = @(
    "-m", "head_rack_align.app",
    "--model", $Model,
    "--camera", "$Camera",
    "--device", $Device,
    "--conf", "0.40",
    "--iou", "0.25",
    "--config", $Config
)

if ($JsonOut) {
    $Args += @("--json-out", $JsonOut)
}

if ($Show) {
    $Args += @("--draw-detections", "--show")
}

& $Python @Args
