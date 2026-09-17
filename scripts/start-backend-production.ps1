param(
  [string]$HostAddress = "0.0.0.0",
  [int]$Port = 5000,
  [string]$AllowedOrigin = "https://seu-frontend.com"
)

$ErrorActionPreference = "Stop"
if (-not $env:SUPABASE_URL -or (-not $env:SUPABASE_PUBLISHABLE_KEY -and -not $env:SUPABASE_ANON_KEY)) {
  throw "Configure SUPABASE_URL e SUPABASE_PUBLISHABLE_KEY no ambiente do processo."
}
$env:FLASK_ENV = "production"
$env:CLINICAL_API_REQUIRE_AUTH = "1"
$env:CLINICAL_API_ALLOWED_ORIGIN = $AllowedOrigin
Write-Host "Iniciando API HEAL+ em http://$HostAddress`:$Port"
python "heal_platform.py" --mode dashboard --host $HostAddress --port $Port
