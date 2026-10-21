Clear-RecycleBin -Force -ErrorAction SilentlyContinue
Get-ChildItem "$env:TEMP\*" -Recurse -Force -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem "$env:SystemRoot\Temp\*" -Recurse -Force -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue