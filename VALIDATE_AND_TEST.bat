@echo off
:: VALIDATE_AND_TEST.bat - Automated validation for Book Dork Search API v2.0
:: Double-click this file to run all tests automatically
:: Requires: Docker Desktop installed and running, Windows 10+ with PowerShell

setlocal
set "TEMP_PS=%TEMP%\validate_temp_%RANDOM%.ps1"

> "%TEMP_PS%" (
# ======================
# VALIDATION SCRIPT
# ======================
Write-Host "`n=== STARTING VALIDATION OF BOOK DOCK SEARCH API v2.0 ===`n" -ForegroundColor Cyan

# Configuration
$timeoutSeconds = 60
$checkInterval = 5
$serviceName = "book_api"  # Must match container_name in docker-compose.yml

# Helper function to run docker-compose and suppress output unless error
function Invoke-DockerCompose {
    param([string]$command)
    try {
        & docker-compose $command *>$null
        if ($LASTEXITCODE -ne 0) {
            throw "docker-compose $command failed with exit code $LASTEXITCODE"
        }
    } catch {
        Write-Error "Docker command failed: $_"
        exit 1
    }
}

# Helper function for HTTP requests with retry
function Wait-For-Endpoint {
    param([string]$url, [string]$description, [int]$timeoutSec = 60, [int]$intervalSec = 5)
    Write-Host "Waiting for $description (timeout: $timeoutSec sec)..." -ForegroundColor Yellow
    $stopwatch = [Diagnostics.Stopwatch]::StartNew()
    while ($stopwatch.Elapsed.TotalSeconds -lt $timeoutSec) {
        try {
            $response = Invoke-RestMethod -Uri $uri -Method Get -ErrorAction Stop -TimeoutSec 5
            if ($response) {
                Write-Host "✅ $description is ready" -ForegroundColor Green
                return $true
            }
        } catch {
            # Silently retry on connection errors
        }
        Start-Sleep -Seconds $intervalSec
    }
    Write-Error "Timeout waiting for $description after $timeoutSec seconds"
    return $false
}

# Step 1: Clean up any existing state
Write-Host "Step 1: Cleaning up previous containers..." -ForegroundColor Cyan
try {
    Invoke-DockerCompose "down -v"
    Write-Host "✅ Cleanup complete" -ForegroundColor Green
} catch {
    Write-Error "Cleanup failed: $_"
    exit 1
}

# Step 2: Start services
Write-Host "`nStep 2: Starting services..." -ForegroundColor Cyan
try {
    Invoke-DockerCompose "up --build -d"
    Write-Host "✅ Services started in background" -ForegroundColor Green
} catch {
    Write-Error "Failed to start services: $_"
    exit 1
}

# Step 3: Wait for API to be ready
Write-Host "`nStep 3: Waiting for API to be ready..." -ForegroundColor Cyan
if (-not (Wait-For-Endpoint "http://localhost:8000/health" "Health endpoint" 60 5)) {
    # Show logs for debugging
    Write-Host "`n=== DOCKER LOGS (LAST 20 LINES) ===`n" -ForegroundColor Red
    & docker-compose logs --tail=20 2>$null | Write-Host
    exit 1
}

# Step 4: Test health endpoint
Write-Host "`nStep 4: Testing health endpoint..." -ForegroundColor Cyan
try {
    $health = Invoke-RestMethod "http://localhost:8000/health"
    if ($health.status -ne "healthy") {
        throw "Health check returned unhealthy status: $($health | ConvertTo-Json -Depth 3)"
    }
    Write-Host "✅ Health check passed: $($health.status)" -ForegroundColor Green
} catch {
    Write-Error "Health check failed: $_"
    exit 1
}

# Step 5: Test root endpoint
Write-Host "`nStep 5: Testing root endpoint..." -ForegroundColor Cyan
try {
    $root = Invoke-RestMethod "http://localhost:8000/"
    if ($root.status -ne "online") {
        throw "Root endpoint returned unexpected status: $($root | ConvertTo-Json -Depth 3)"
    }
    Write-Host "✅ Root endpoint passed: $($root.status)" -ForegroundColor Green
} catch {
    Write-Error "Root endpoint failed: $_"
    exit 1
}

# Step 6: Test search for multiple sources
Write-Host "`nStep 6: Testing search for multiple sources..." -ForegroundColor Cyan
try {
    $searchBody = @{ title = "harry potter" } | ConvertTo-Json
    $searchResult = Invoke-RestMethod -Method Post -Uri "http://localhost:8000/search" -Body $searchBody -ContentType "application/json"

    if (-not $searchResult.results) {
        throw "No results returned from search"
    }

    $sources = $searchResult.results | Select-Object -ExpandProperty source | Select-Object -Unique
    $sourceCount = $sources.Count

    if ($sourceCount -lt 2) {
        throw "Expected at least 2 different sources, but got $sourceCount: $($sources -join ', ')"
    }

    Write-Host "✅ Multiple sources check passed: Found $sourceCount sources ($($sources -join ', '))" -ForegroundColor Green
    Write-Host "   Total results: $($searchResult.total)" -ForegroundColor DarkGray
} catch {
    Write-Error "Search test failed: $_"
    exit 1
}

# Step 7: Test rate limiting
Write-Host "`nStep 7: Testing rate limiting (101 rapid requests)..." -ForegroundColor Cyan
try {
    $rateLimitCount = 0
    $totalRequests = 101
    $batchSize = 20  # Send in batches to avoid overwhelming

    for ($batchStart = 1; $batchStart -le $totalRequests; $batchStart += $batchSize) {
        $batchEnd = [math]::Min($batchStart + $batchSize - 1, $totalRequests)
        Write-Host "   Sending requests $batchStart to $batchEnd..." -ForegroundColor DarkGray

        for ($i = $batchStart; $i -le $batchEnd; $i++) {
            try {
                $response = Invoke-WebRequest -Uri "http://localhost:8000/search" -Method Post -Body (@{ title = "test" } | ConvertTo-Json) -ContentType "application/json" -ErrorAction Stop -TimeoutSec 5
                if ($response.StatusCode -eq 429) {
                    $rateLimitCount++
                }
            } catch {
                # If we get an exception, check if it's a 429
                if ($_.Exception.Response -and $_.Exception.Response.StatusCode.value__ -eq 429) {
                    $rateLimitCount++
                }
                # Other errors (like connection issues) we'll ignore for this test
            }
        }
        Start-Sleep -Milliseconds 100  # Small delay between batches
    }

    if ($rateLimitCount -eq 0) {
        throw "Rate limiting failed: 0 out of $totalRequests requests returned 429"
    }

    Write-Host "✅ Rate limiting passed: $rateLimitCount out of $totalRequests requests were throttled (429)" -ForegroundColor Green
} catch {
    Write-Error "Rate limit test failed: $_"
    exit 1
}

# Step 8: Cleanup
Write-Host "`nStep 8: Cleaning up..." -ForegroundColor Cyan
try {
    Invoke-DockerCompose "down -v"
    Write-Host "✅ Cleanup complete" -ForegroundColor Green
} catch {
    Write-Warning "Cleanup encountered issues (but continuing): $_"
}

# Final success message
Write-Host "`n" + ("="*50) -ForegroundColor Cyan
Write-Host "🎉 ALL TESTS PASSED! The system is ready for GitHub commit." -ForegroundColor Green
Write-Host ("="*50) -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. git add ."
Write-Host "  2. git commit -m ""feat: implementar melhorias de produção (cache, rate limiting, logging estruturado, validação de entrada, configuração centralizada)"" "
Write-Host "  3. git push origin main  (or your branch)"
Write-Host ""
Write-Host "Press any key to close this window..."
$null = $host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
)

# Execute the PowerShell script
powershell -NoProfile -ExecutionPolicy Bypass -File "%TEMP_PS%"

# Cleanup temp file
if exist "%TEMP_PS%" del "%TEMP_PS%"

endlocal