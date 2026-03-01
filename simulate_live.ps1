# ===================================================================
#  ChronoTrace - Live Monitor Simulation Script
#  Run this in an ELEVATED (Administrator) PowerShell terminal
#  while the Live Monitor is active on drive C:
#
#  This script performs REAL anti-forensic actions on temp files
#  to trigger the USN Journal + Process Watcher sensors.
# ===================================================================

$ErrorActionPreference = "SilentlyContinue"
$TestDir = "C:\ChronoTrace_SimTest"

Write-Host ""
Write-Host "  +==================================================+" -ForegroundColor Cyan
Write-Host "  |   ChronoTrace - Live Monitor Simulator           |" -ForegroundColor Cyan
Write-Host "  |   Generates REAL NTFS events to trigger alerts   |" -ForegroundColor Cyan
Write-Host "  +==================================================+" -ForegroundColor Cyan
Write-Host ""

# -- Setup ------------------------------------------------------------------
Write-Host "[*] Creating test directory: $TestDir" -ForegroundColor Yellow
New-Item -Path $TestDir -ItemType Directory -Force | Out-Null

# ===================================================================
#  SCENARIO 1: Timestamp Manipulation (PowerShell)
#  Triggers:
#    - USN Journal: BASIC_INFO_CHANGE events
#    - ProcessWatcher: TOOL_POWERSHELL_SETTIME (detects .CreationTime = ...)
#    - Rules: RULE_01 (SI/FN divergence), RULE_10 (rapid metadata rewrite),
#             RULE_20 (SetMACE fingerprint if all 4 set identical)
# ===================================================================

Write-Host ""
Write-Host "-- SCENARIO 1: Timestamp Manipulation ----------------------" -ForegroundColor Magenta
Write-Host "[1] Creating test files..." -ForegroundColor Yellow

$file1 = "$TestDir\quarterly_report_2024.docx"
$file2 = "$TestDir\meeting_notes_draft.txt"
$file3 = "$TestDir\project_budget.xlsx"

Set-Content -Path $file1 -Value "Fake document content - quarterly report"
Set-Content -Path $file2 -Value "Fake document content - meeting notes"
Set-Content -Path $file3 -Value "Fake document content - budget spreadsheet"

Start-Sleep -Seconds 2

Write-Host "[1] Backdating timestamps (timestomping)..." -ForegroundColor Red
Write-Host "    Setting $file1 to 2022-03-15..." -ForegroundColor DarkGray

# Backdate all 3 timestamps to a date far in the past
# This generates BASIC_INFO_CHANGE in USN and triggers SI/FN divergence
$fakeDate = Get-Date "2022-03-15 09:30:00"
(Get-Item $file1).CreationTime   = $fakeDate
(Get-Item $file1).LastWriteTime  = $fakeDate
(Get-Item $file1).LastAccessTime = $fakeDate

Start-Sleep -Milliseconds 500

Write-Host "    Setting $file2 to 2021-11-01..." -ForegroundColor DarkGray
$fakeDate2 = Get-Date "2021-11-01 14:22:00"
(Get-Item $file2).CreationTime   = $fakeDate2
(Get-Item $file2).LastWriteTime  = $fakeDate2
(Get-Item $file2).LastAccessTime = $fakeDate2

Start-Sleep -Milliseconds 500

# SetMACE fingerprint: set ALL FOUR timestamps to the exact same value
# Triggers RULE_20 specifically
Write-Host "    Setting $file3 - all 4 timestamps IDENTICAL (SetMACE fingerprint)..." -ForegroundColor Red
$fakeDate3 = Get-Date "2023-06-01 00:00:00"
(Get-Item $file3).CreationTime   = $fakeDate3
(Get-Item $file3).LastWriteTime  = $fakeDate3
(Get-Item $file3).LastAccessTime = $fakeDate3
# The 4th timestamp ($MFT modified) cannot be set from user mode, but the
# USN Journal will still record the BASIC_INFO_CHANGE events.

Write-Host "[OK] Scenario 1 complete - check for CRITICAL alerts" -ForegroundColor Green

# ===================================================================
#  SCENARIO 2: Rapid Metadata Rewrite (Tool Fingerprint)
#  Triggers:
#    - USN Journal: Multiple BASIC_INFO_CHANGE within <2 seconds
#    - Rules: RULE_10 (rapid metadata rewrite)
# ===================================================================

Write-Host ""
Write-Host "-- SCENARIO 2: Rapid Metadata Rewrite ----------------------" -ForegroundColor Magenta
Write-Host "[2] Rapidly changing timestamps on a single file..." -ForegroundColor Yellow

$rapidFile = "$TestDir\rapid_rewrite_test.txt"
Set-Content -Path $rapidFile -Value "This file will be timestomped rapidly"

Start-Sleep -Seconds 1

Write-Host "[2] Firing rapid timestamp changes..." -ForegroundColor Red
# Change timestamps multiple times in quick succession - mimics SetMACE/timestomp
for ($i = 1; $i -le 5; $i++) {
    $dt = Get-Date "2019-0$i-15 08:00:00"
    (Get-Item $rapidFile).CreationTime  = $dt
    (Get-Item $rapidFile).LastWriteTime = $dt
    Start-Sleep -Milliseconds 100  # very fast - triggers rapid-event detection
}

Write-Host "[OK] Scenario 2 complete - check for RULE_10 rapid rewrite alerts" -ForegroundColor Green

# ===================================================================
#  SCENARIO 3: Secure Delete Pattern (overwrite then delete)
#  Triggers:
#    - USN Journal: DATA_OVERWRITE followed by FILE_DELETE
#    - Rules: RULE_21 (secure delete pattern)
# ===================================================================

Write-Host ""
Write-Host "-- SCENARIO 3: Secure Delete Pattern -----------------------" -ForegroundColor Magenta

$secureFile = "$TestDir\evidence_to_destroy.log"
Write-Host "[3] Creating file, overwriting content, then deleting..." -ForegroundColor Yellow

Set-Content -Path $secureFile -Value "Original sensitive content here"
Start-Sleep -Seconds 1

# Overwrite content (generates DATA_OVERWRITE in USN)
Write-Host "[3] Overwriting file content (wiping)..." -ForegroundColor Red
Set-Content -Path $secureFile -Value ("X" * 1024)  # overwrite with junk
Start-Sleep -Milliseconds 200

# Delete immediately after overwrite (generates FILE_DELETE in USN)
Write-Host "[3] Deleting file immediately after overwrite..." -ForegroundColor Red
Remove-Item -Path $secureFile -Force

Write-Host "[OK] Scenario 3 complete - check for RULE_21 secure deletion alert" -ForegroundColor Green

# ===================================================================
#  SCENARIO 4: Prefetch Wiping Simulation
#  Triggers:
#    - USN Journal: FILE_DELETE on .pf files
#    - Rules: RULE_19 (prefetch wiping)
#  NOTE: We create FAKE .pf files in our test dir rather than
#  touching the real Prefetch folder.
# ===================================================================

Write-Host ""
Write-Host "-- SCENARIO 4: Prefetch-Style Deletion ---------------------" -ForegroundColor Magenta
Write-Host "[4] Creating and deleting fake .pf files..." -ForegroundColor Yellow

for ($i = 1; $i -le 5; $i++) {
    $pf = "$TestDir\FAKE_APP_$i.pf"
    Set-Content -Path $pf -Value "fake prefetch data $i"
}
Start-Sleep -Seconds 1

Write-Host "[4] Mass-deleting .pf files..." -ForegroundColor Red
Get-ChildItem "$TestDir\*.pf" | Remove-Item -Force

Write-Host "[OK] Scenario 4 complete - check for RULE_19 prefetch wipe alert" -ForegroundColor Green

# ===================================================================
#  SCENARIO 5: Batch file creation + timestomping (mimics evidence planting)
#  Triggers a burst of USN events + multiple BASIC_INFO_CHANGE
# ===================================================================

Write-Host ""
Write-Host "-- SCENARIO 5: Evidence Planting Simulation ----------------" -ForegroundColor Magenta
Write-Host "[5] Creating a batch of files and backdating them..." -ForegroundColor Yellow

$plantDir = "$TestDir\planted_evidence"
New-Item -Path $plantDir -ItemType Directory -Force | Out-Null

$names = @("contract_v2_final.pdf", "invoice_00482.pdf", "email_export.eml",
           "screenshot_desktop.png", "bank_statement_jan.pdf")

foreach ($name in $names) {
    $path = "$plantDir\$name"
    Set-Content -Path $path -Value "Planted evidence file: $name"
}

Start-Sleep -Seconds 1

Write-Host "[5] Backdating all planted files to same date..." -ForegroundColor Red
$plantDate = Get-Date "2023-01-10 08:15:00"
foreach ($name in $names) {
    $path = "$plantDir\$name"
    (Get-Item $path).CreationTime   = $plantDate
    (Get-Item $path).LastWriteTime  = $plantDate
    (Get-Item $path).LastAccessTime = $plantDate
    Start-Sleep -Milliseconds 50
}

Write-Host "[OK] Scenario 5 complete - check for multiple CRITICAL alerts" -ForegroundColor Green

# ===================================================================
#  CLEANUP (optional - uncomment to auto-remove test files)
# ===================================================================

Write-Host ""
Write-Host "-- DONE ----------------------------------------------------" -ForegroundColor Cyan
Write-Host ""
Write-Host "  All 5 scenarios executed. Check the ChronoTrace Live Monitor UI" -ForegroundColor White
Write-Host "  for alerts. You should see:" -ForegroundColor White
Write-Host "    - CRITICAL: SI/FN divergence, backdating, SetMACE fingerprint" -ForegroundColor Red
Write-Host "    - HIGH:     Rapid metadata rewrite, secure deletion" -ForegroundColor DarkYellow
Write-Host "    - HIGH:     PowerShell timestomping tool detection" -ForegroundColor DarkYellow
Write-Host "    - HIGH:     Prefetch wiping pattern" -ForegroundColor DarkYellow
Write-Host ""
Write-Host "  Test files are in: $TestDir" -ForegroundColor Gray
Write-Host "  To clean up:  Remove-Item -Recurse -Force $TestDir" -ForegroundColor Gray
Write-Host ""

# Uncomment the next line to auto-cleanup:
# Remove-Item -Recurse -Force $TestDir
