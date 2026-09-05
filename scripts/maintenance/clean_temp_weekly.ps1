Clear-RecycleBin -Force -ErrorAction SilentlyContinue

Get-ChildItem "$env:TEMP\*" -Recurse -Force -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem "$env:SystemRoot\Temp\*" -Recurse -Force -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

Get-ChildItem "$env:SystemRoot\SoftwareDistribution\Download\*" -Recurse -Force -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

Get-ChildItem "$env:SystemRoot\ServiceProfiles\NetworkService\AppData\Local\Microsoft\Windows\DeliveryOptimization\Cache\*" -Recurse -Force -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

Get-ChildItem "$env:ProgramData\Microsoft\Windows\WER\ReportArchive\*" -Recurse -Force -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem "$env:ProgramData\Microsoft\Windows\WER\ReportQueue\*" -Recurse -Force -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

Get-ChildItem "$env:LOCALAPPDATA\Microsoft\Windows\Explorer\thumbnailcache_*.db" -Force -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue

Get-ChildItem "$env:USERPROFILE\Downloads\*" -Recurse -Force -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

ipconfig /flushdns