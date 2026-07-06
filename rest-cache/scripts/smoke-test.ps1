param(
    [string]$BaseUrl = "http://127.0.0.1:8080"
)

$ErrorActionPreference = "Stop"

function Invoke-LabRequest {
    param(
        [ValidateSet("GET", "POST", "PUT", "PATCH", "DELETE")]
        [string]$Method,
        [string]$Path,
        [string]$Body = ""
    )

    $uri = "$BaseUrl$Path"
    $parameters = @{
        UseBasicParsing = $true
        Uri = $uri
        Method = $Method
    }

    if ($Body) {
        $parameters.ContentType = "application/json"
        $parameters.Body = $Body
    }

    try {
        Invoke-WebRequest @parameters
    } catch {
        if ($_.Exception.Response) {
            return $_.Exception.Response
        }
        throw
    }
}

function Get-HeaderValue {
    param(
        [object]$Response,
        [string]$Name
    )

    $value = $Response.Headers[$Name]
    if ($value -is [array]) {
        return $value[0]
    }
    return $value
}

function Assert-Status {
    param(
        [object]$Response,
        [int]$Expected,
        [string]$Label
    )

    if ([int]$Response.StatusCode -ne $Expected) {
        throw "$Label expected HTTP $Expected, got $([int]$Response.StatusCode)."
    }
}

function Assert-XCache {
    param(
        [object]$Response,
        [string]$Expected,
        [string]$Label
    )

    $actual = Get-HeaderValue -Response $Response -Name "X-Cache"
    if ($actual -ne $Expected) {
        throw "$Label expected X-Cache: $Expected, got '$actual'."
    }
}

function Write-Pass {
    param([string]$Message)

    Write-Host "[PASS] $Message"
}

Write-Host "Testing Varnish REST cache at $BaseUrl"

$reset = Invoke-LabRequest -Method "PUT" -Path "/api/v1/resources/123" -Body '{"name":"resource-123"}'
Assert-Status -Response $reset -Expected 200 -Label "reset resource"
Write-Pass "reset resources/123 to seed value"

$first = Invoke-LabRequest -Method "GET" -Path "/api/v1/resources/123"
Assert-Status -Response $first -Expected 200 -Label "first resource read"
Assert-XCache -Response $first -Expected "MISS" -Label "first resource read"

$second = Invoke-LabRequest -Method "GET" -Path "/api/v1/resources/123"
Assert-Status -Response $second -Expected 200 -Label "second resource read"
Assert-XCache -Response $second -Expected "HIT" -Label "second resource read"
Write-Pass "resource GET caches: MISS then HIT"

$queryFirst = Invoke-LabRequest -Method "GET" -Path "/api/v1/resources?b=2&a=1"
Assert-Status -Response $queryFirst -Expected 200 -Label "first normalized query read"
Assert-XCache -Response $queryFirst -Expected "MISS" -Label "first normalized query read"

$querySecond = Invoke-LabRequest -Method "GET" -Path "/api/v1/resources?a=1&b=2"
Assert-Status -Response $querySecond -Expected 200 -Label "second normalized query read"
Assert-XCache -Response $querySecond -Expected "HIT" -Label "second normalized query read"
Write-Pass "query normalization shares cache key"

$mutate = Invoke-LabRequest -Method "PUT" -Path "/api/v1/resources/123" -Body '{"name":"resource-123-after-ban"}'
Assert-Status -Response $mutate -Expected 200 -Label "resource mutation"

$afterMutation = Invoke-LabRequest -Method "GET" -Path "/api/v1/resources/123"
Assert-Status -Response $afterMutation -Expected 200 -Label "resource read after mutation"
Assert-XCache -Response $afterMutation -Expected "MISS" -Label "resource read after mutation"
Write-Pass "resource mutation invalidates cached resource"

$permissionsWarm = Invoke-LabRequest -Method "GET" -Path "/api/v1/permissions"
Assert-Status -Response $permissionsWarm -Expected 200 -Label "permissions warm"

$permissionsHit = Invoke-LabRequest -Method "GET" -Path "/api/v1/permissions"
Assert-Status -Response $permissionsHit -Expected 200 -Label "permissions hit"
Assert-XCache -Response $permissionsHit -Expected "HIT" -Label "permissions hit"

$userMutation = Invoke-LabRequest -Method "PUT" -Path "/api/v1/users/1" -Body '{"name":"user-1"}'
Assert-Status -Response $userMutation -Expected 200 -Label "user mutation"

$permissionsAfterUserMutation = Invoke-LabRequest -Method "GET" -Path "/api/v1/permissions"
Assert-Status -Response $permissionsAfterUserMutation -Expected 200 -Label "permissions after user mutation"
Assert-XCache -Response $permissionsAfterUserMutation -Expected "MISS" -Label "permissions after user mutation"
Write-Pass "dependency ban invalidates permissions collection when users mutate"

$resetAgain = Invoke-LabRequest -Method "PUT" -Path "/api/v1/resources/123" -Body '{"name":"resource-123"}'
Assert-Status -Response $resetAgain -Expected 200 -Label "final resource reset"
Write-Pass "reset resources/123 back to original seed value"

Write-Host ""
Write-Host "Smoke test passed."
