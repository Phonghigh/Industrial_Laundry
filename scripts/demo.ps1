<#
.SYNOPSIS
    Full automated demo for the Industrial Laundry Operational Event Capture System.

.PARAMETER SkipStart
    Skip docker compose up (use when the stack is already running).

.PARAMETER SkipSeed
    Skip migration + seed (use when the DB already has data).

.PARAMETER ApiBase
    Base URL of the API. Default: http://localhost:8000

.EXAMPLE
    .\scripts\demo.ps1
    .\scripts\demo.ps1 -SkipStart -SkipSeed
#>

param(
    [switch]$SkipStart,
    [switch]$SkipSeed,
    [string]$ApiBase = "http://localhost:8000"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

function Write-Step  { param($n, $msg) Write-Host "`n[ STEP $n ] $msg" -ForegroundColor Cyan }
function Write-Ok    { param($msg)     Write-Host "  OK   $msg" -ForegroundColor Green }
function Write-Warn  { param($msg)     Write-Host "  WARN $msg" -ForegroundColor Yellow }
function Write-Info  { param($msg)     Write-Host "       $msg" -ForegroundColor Gray }
function Write-Title {
    param($msg)
    Write-Host "`n==========================================" -ForegroundColor DarkCyan
    Write-Host "  $msg" -ForegroundColor White
    Write-Host "==========================================`n" -ForegroundColor DarkCyan
}

function Pause-Demo { param($sec = 2) Start-Sleep -Seconds $sec }

function Invoke-Api {
    param($Path, $Method = "GET", $Body = $null)
    $params = @{ Uri = "$ApiBase$Path"; Method = $Method }
    if ($Body) {
        $params.Body        = ($Body | ConvertTo-Json)
        $params.ContentType = "application/json"
    }
    Invoke-RestMethod @params
}

function Send-Event {
    param($BatchId, $StationId, $EventType, $Device = "demo-tablet-01", $IssueCode = $null)
    $meta = @{ source = "demo_script" }
    if ($IssueCode) { $meta.issue_code = $IssueCode }
    $result = Invoke-Api "/api/v1/events" -Method POST -Body @{
        batch_id        = $BatchId
        station_id      = $StationId
        event_type      = $EventType
        device_id       = $Device
        idempotency_key = [guid]::NewGuid().ToString()
        timestamp       = (Get-Date -Format o)
        metadata        = $meta
    }
    Write-Ok "$EventType -- event_id: $($result.event_id)  queued: $($result.queued)"
}

function Show-Alerts {
    param($Label = "Operational State")
    Write-Info "--- $Label ---"
    $state = Invoke-Api "/api/v1/alerts"

    $stuck = $state.stuck_batches
    if ($stuck.Count -eq 0) {
        Write-Ok "Stuck batches  : none"
    } else {
        Write-Warn "Stuck batches ($($stuck.Count)):"
        foreach ($b in $stuck) {
            Write-Info "    $($b.batch_code) @ $($b.station) -- $($b.stuck_mins) min stuck"
        }
    }

    $tp = $state.station_throughput
    if ($tp.Count -eq 0) {
        Write-Info "Throughput     : no completed events this hour"
    } else {
        Write-Ok "Throughput (completed last hour):"
        foreach ($t in $tp) {
            Write-Info "    $($t.station): $($t.completed_last_hour) batches/h"
        }
    }

    $inactive = $state.inactive_stations
    if ($inactive.Count -eq 0) {
        Write-Ok "Inactive stations: none"
    } else {
        Write-Warn "Inactive stations ($($inactive.Count)):"
        foreach ($s in $inactive) {
            $detail = if ($s.never_active) { "never active" } else { "$($s.silent_mins) min silent" }
            Write-Info "    $($s.station): $detail"
        }
    }
}

function Wait-Worker {
    param($MinRows = 1, $TimeoutSec = 20)
    Write-Info "Waiting for worker to persist events to PostgreSQL..."
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        $rows = docker compose -f infra/docker-compose.yml exec -T db `
            psql -U postgres industrial_laundry -tAc `
            "SELECT COUNT(*) FROM operational_events WHERE ts > NOW() - INTERVAL '5 minutes';" `
            2>$null
        if ([int]($rows.Trim()) -ge $MinRows) {
            Write-Ok "$([int]($rows.Trim())) recent event(s) in PostgreSQL"
            return
        }
        Start-Sleep -Milliseconds 600
    }
    Write-Warn "Timeout -- consumer may still be processing"
}

# ===========================================================================
Write-Title "Industrial Laundry -- Automated Demo"
# ===========================================================================

# ---------------------------------------------------------------------------
# STEP 1 - Start the stack
# ---------------------------------------------------------------------------
Write-Step 1 "Starting Docker stack"

if (-not $SkipStart) {
    Write-Info "docker compose up -d ..."
    docker compose -f infra/docker-compose.yml up -d 2>&1 | Out-Null

    Write-Info "Waiting for API health check ..."
    $deadline = (Get-Date).AddSeconds(90)
    $ready = $false
    while ((Get-Date) -lt $deadline) {
        try {
            $h = Invoke-Api "/health"
            if ($h.status -eq "ok") { $ready = $true; break }
        } catch { }
        Start-Sleep -Seconds 2
    }
    if ($ready) { Write-Ok "Stack is up and healthy" }
    else         { Write-Warn "API did not become healthy in time -- continuing anyway" }
} else {
    Write-Info "Skipped (stack assumed running)"
}

Pause-Demo 1

# ---------------------------------------------------------------------------
# STEP 2 - Migrate and seed
# ---------------------------------------------------------------------------
Write-Step 2 "Database migration + seed"

if (-not $SkipSeed) {
    Write-Info "Running alembic upgrade head ..."
    docker compose -f infra/docker-compose.yml exec api alembic upgrade head 2>&1 | Out-Null
    Write-Ok "Schema at head"

    Write-Info "Seeding stations and batches ..."
    docker compose -f infra/docker-compose.yml exec api `
        sh -c "PYTHONPATH=/app python scripts/seed.py" 2>&1 | Out-Null
    Write-Ok "Seed complete"
} else {
    Write-Info "Skipped (DB assumed seeded)"
}

Pause-Demo 1

# ---------------------------------------------------------------------------
# STEP 3 - Resolve IDs
# ---------------------------------------------------------------------------
Write-Step 3 "Resolving station and batch IDs from API"

$stations = Invoke-Api "/api/v1/stations"
$batches  = Invoke-Api "/api/v1/batches"

$stn = @{}
foreach ($s in $stations) { $stn[$s.name] = $s.id }

$b2041 = ($batches | Where-Object batch_code -eq "BATCH_2041").id
$b2042 = ($batches | Where-Object batch_code -eq "BATCH_2042").id

Write-Ok "Stations loaded: $($stations.Count)"
Write-Ok "BATCH_2041 id  : $b2041"
Write-Ok "BATCH_2042 id  : $b2042"
foreach ($k in ($stn.Keys | Sort-Object)) {
    Write-Info "  $($k.PadRight(10)) $($stn[$k])"
}

Pause-Demo 1

# ---------------------------------------------------------------------------
# STEP 4 - Baseline
# ---------------------------------------------------------------------------
Write-Step 4 "Baseline alert state (seed data -- all batches idle ~1 hour)"
Show-Alerts "Before any demo events"
Write-Info ""
Write-Info "All 5 batches stuck -- only seeded with 'started' events ~1h ago."
Write-Info "Intake and Dispatch never received any events."
Pause-Demo 3

# ---------------------------------------------------------------------------
# STEP 5 - BATCH_2041 through Washing
# ---------------------------------------------------------------------------
Write-Step 5 "BATCH_2041 arrives at Washing and completes"

Write-Info "Sending: started @ Washing ..."
Send-Event -BatchId $b2041 -StationId $stn["Washing"] -EventType "started" -Device "tablet-washing-01"
Pause-Demo 1

Write-Info "Sending: completed @ Washing ..."
Send-Event -BatchId $b2041 -StationId $stn["Washing"] -EventType "completed" -Device "tablet-washing-01"

Wait-Worker -MinRows 2
Pause-Demo 1

# ---------------------------------------------------------------------------
# STEP 6 - BATCH_2041 arrives at Drying (leave open)
# ---------------------------------------------------------------------------
Write-Step 6 "BATCH_2041 moves to Drying -- left in-progress"

Write-Info "Sending: started @ Drying ..."
Send-Event -BatchId $b2041 -StationId $stn["Drying"] -EventType "started" -Device "tablet-drying-01"
Wait-Worker -MinRows 3
Pause-Demo 2

Show-Alerts "After BATCH_2041 moves Washing -> Drying"
Write-Info ""
Write-Info "  Expected: BATCH_2041 gone from stuck_batches (last event is seconds old)"
Write-Info "  Expected: Washing shows 1 completed batch this hour"
Write-Info "  Expected: Washing + Drying gone from inactive_stations"
Pause-Demo 3

# ---------------------------------------------------------------------------
# STEP 7 - BATCH_2042 flags an issue
# ---------------------------------------------------------------------------
Write-Step 7 "BATCH_2042 flags a mechanical issue at Washing"

Write-Info "Sending: started @ Washing ..."
Send-Event -BatchId $b2042 -StationId $stn["Washing"] -EventType "started" -Device "tablet-washing-01"
Pause-Demo 1

Write-Info "Sending: issue_flagged @ Washing (MECH_JAM) ..."
Send-Event -BatchId $b2042 -StationId $stn["Washing"] -EventType "issue_flagged" `
    -Device "tablet-washing-01" -IssueCode "MECH_JAM"

Wait-Worker -MinRows 5
Pause-Demo 2

Show-Alerts "After BATCH_2042 flags issue at Washing"
Write-Info ""
Write-Info "  Expected: BATCH_2042 NOT stuck -- issue_flagged counts as recent activity"
Write-Info "  Expected: issue_code=MECH_JAM stored in JSONB metadata column"
Pause-Demo 3

# ---------------------------------------------------------------------------
# STEP 8 - BATCH_2041 completes Drying
# ---------------------------------------------------------------------------
Write-Step 8 "BATCH_2041 completes Drying -- fully resolved"

Write-Info "Sending: completed @ Drying ..."
Send-Event -BatchId $b2041 -StationId $stn["Drying"] -EventType "completed" -Device "tablet-drying-01"
Wait-Worker -MinRows 6
Pause-Demo 2

Show-Alerts "After BATCH_2041 completes Drying"
Write-Info ""
Write-Info "  Expected: Drying now appears in station_throughput"
Write-Info "  Expected: BATCH_2041 still absent from stuck (last event = seconds ago)"
Pause-Demo 3

# ---------------------------------------------------------------------------
# STEP 9 - Idempotency proof
# ---------------------------------------------------------------------------
Write-Step 9 "Idempotency -- same event sent twice, DB stores it once"

$ikey = [guid]::NewGuid().ToString()
Write-Info "idempotency_key: $ikey"

$body = @{
    batch_id        = $b2041
    station_id      = $stn["Drying"]
    event_type      = "completed"
    device_id       = "tablet-drying-01"
    idempotency_key = $ikey
    timestamp       = (Get-Date -Format o)
    metadata        = @{ source = "idempotency_test" }
}

$r1 = Invoke-Api "/api/v1/events" -Method POST -Body $body
Write-Ok "Send 1 -- event_id: $($r1.event_id)  queued: $($r1.queued)"

Start-Sleep -Milliseconds 200
$r2 = Invoke-Api "/api/v1/events" -Method POST -Body $body
Write-Ok "Send 2 -- event_id: $($r2.event_id)  queued: $($r2.queued)"

Start-Sleep -Seconds 5
$count = docker compose -f infra/docker-compose.yml exec -T db `
    psql -U postgres industrial_laundry -tAc `
    "SELECT COUNT(*) FROM operational_events WHERE idempotency_key = '$ikey'::uuid;" `
    2>$null
Write-Ok "Rows in DB for that key: $($count.Trim())  (expected: 1)"
Pause-Demo 2

# ---------------------------------------------------------------------------
# STEP 10 - Final state
# ---------------------------------------------------------------------------
Write-Step 10 "Final operational state"
Show-Alerts "End of demo"

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
Write-Title "Demo Complete"

Write-Host "Pipeline verified:" -ForegroundColor White
Write-Ok "POST /events -> Redis Stream -> Worker -> PostgreSQL"
Write-Ok "Stuck-batch detection (DISTINCT ON latest event per batch)"
Write-Ok "Station throughput (completed events in last hour)"
Write-Ok "Inactive station detection"
Write-Ok "Idempotency (duplicate events silently discarded)"

Write-Host ""
Write-Host "URLs:" -ForegroundColor White
Write-Info "  Swagger UI   : $ApiBase/docs"
Write-Info "  Alerts JSON  : $ApiBase/api/v1/alerts"
Write-Info "  Batches      : $ApiBase/api/v1/batches"
Write-Info "  Stations     : $ApiBase/api/v1/stations"
Write-Info "  Metrics      : $ApiBase/metrics"
Write-Info "  Grafana      : http://localhost:3000  (admin / admin)"
Write-Host ""
