# Raw serial monitor for the NodeMCU on COM15.
#
#   powershell -NoProfile -File serial-monitor.ps1            74880, 20s
#   powershell -NoProfile -File serial-monitor.ps1 115200 30  ESPHome logs
#
# 74880 is the ESP8266 boot ROM's odd native baud rate. Press RST while it
# is running and look for the boot banner:
#
#   ets Jan  8 2013,rst cause:2, boot mode:(3,6)
#                                          ^
#                          3 = normal boot, 1 = flash mode
#
# Nothing at all at 74880 means the serial path itself is broken, which is
# a different problem from the board refusing to enter flash mode.

param(
    [int]$Baud = 74880,
    [int]$Seconds = 20,
    [string]$Port = "COM15"
)

try {
    $sp = New-Object System.IO.Ports.SerialPort($Port, $Baud, 'None', 8, 'One')
    $sp.ReadTimeout = 200
    $sp.Open()
} catch {
    Write-Host "Could not open $Port at $Baud : $($_.Exception.Message)"
    exit 1
}

Write-Host "--- $Port @ $Baud, listening $Seconds s. PRESS RST NOW ---"
$sw = [Diagnostics.Stopwatch]::StartNew()
$got = $false
while ($sw.Elapsed.TotalSeconds -lt $Seconds) {
    $data = $sp.ReadExisting()
    if ($data) { $got = $true; Write-Host -NoNewline $data }
    Start-Sleep -Milliseconds 100
}
$sp.Close()

Write-Host ""
if ($got) {
    Write-Host "--- done, data received ---"
} else {
    Write-Host "--- done, NOTHING received: the serial path is the problem ---"
}
