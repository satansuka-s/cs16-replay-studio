# cs16db demo toolkit - point liblist.gam gamedll at metamod
param([Parameter(Mandatory=$true)][string]$Path)
$t = [System.IO.File]::ReadAllText($Path)
$t = [regex]::Replace($t, 'gamedll[ \t]+"[^"]*"', 'gamedll "addons\metamod\dlls\metamod.dll"')
$t = [regex]::Replace($t, 'gamedll_linux[ \t]+"[^"]*"', 'gamedll_linux "addons/metamod/dlls/metamod_i386.so"')
[System.IO.File]::WriteAllText($Path, $t)
Write-Output "patched: $Path"
