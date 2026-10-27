-- smoke test: run max_import.py inside 3ds Max 2027 via pymxs
python.ExecuteFile @"C:\dev\cs16db\max\max_import.py"
setEnv "MAX_IMPORT_JSON" "C:\dev\cs16db\core\tests\stub.json"
-- the script reads env at import time; re-run via python module
python.Import "max_import"
python.Execute "import sys; sys.argv=['x','--json=C:\\dev\\cs16db\\core\\tests\\stub.json','--scale=1']"
python.Execute "import max_import; max_import.build(max_import.parse_args(sys.argv[1:]))"
smoke = dotNetClass "System.IO.File"
smoke.WriteAllText @"C:\dev\cs16db\core\tests\max_smoke_ok.txt" (("objects=" + (objects.count as string)) + " cam=" + (getNodeByName "DemoCamera" != undefined as string))
