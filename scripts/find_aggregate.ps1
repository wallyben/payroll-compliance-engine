$repo = Get-Location

Write-Host "Searching for aggregate_severity_summary..."

Get-ChildItem -Recurse -Include *.py |
    Select-String -Pattern "aggregate_severity_summary" |
    ForEach-Object {
        Write-Host "Found in:" $_.Path
    }