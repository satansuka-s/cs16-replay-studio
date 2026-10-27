-- atomic smoke: write a marker file immediately (no pymxs)
try (
    dotNetClass "System.IO.File" .WriteAllText @"C:\dev\cs16db\core\tests\max_marker.txt" "hello-from-max"
    ok = true
) catch (
    dotNetClass "System.IO.File" .WriteAllText @"C:\dev\cs16db\core\tests\max_marker.txt" ("ERROR: " + (getCurrentException() as string))
)
