param(
    [string]$Images = "",

    [string]$Workspace = "",

    [int]$TargetHuman = 100,

    [int]$PseudoReviewCount = 20,

    [int]$TeacherEpochs = 15,

    [int]$StudentEpochs = 15,

    [ValidateSet("auto", "cpu", "cuda")]
    [string]$Device = "auto"
)

$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $Workspace) {
    $Workspace = Join-Path $projectRoot "ml\outputs\guided_wound_workflow"
}

$arguments = @(
    "ml/scripts/run_guided_semisupervised_wound.py",
    "--workspace", $Workspace,
    "--target-human", $TargetHuman,
    "--pseudo-review-count", $PseudoReviewCount,
    "--teacher-epochs", $TeacherEpochs,
    "--student-epochs", $StudentEpochs,
    "--device", $Device,
    "--confirm-authorized-data"
)

if ($Images) {
    $arguments += @("--images", $Images)
}

Push-Location $projectRoot
try {
    & python @arguments
    $workflowExitCode = $LASTEXITCODE
}
finally {
    Pop-Location
}

if ($workflowExitCode -ne 0) {
    throw "O fluxo terminou com código $workflowExitCode."
}
