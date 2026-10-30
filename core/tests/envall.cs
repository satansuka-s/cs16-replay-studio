using System;
using System.Runtime.InteropServices;
using System.Text;
class EnvAll {
  [DllImport("kernel32.dll")] static extern IntPtr OpenProcess(int a, bool i, int pid);
  [DllImport("kernel32.dll")] static extern bool ReadProcessMemory(IntPtr h, IntPtr addr, byte[] buf, int size, out int read);
  [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr h);
  [DllImport("ntdll.dll")] static extern int NtQueryInformationProcess(IntPtr h, int cls, byte[] info, int len, out int ret);
  static void Main(string[] args) {
    int pid = int.Parse(args[0]);
    IntPtr h = OpenProcess(0x0410, false, pid);
    byte[] pbi = new byte[24]; int ret;
    NtQueryInformationProcess(h, 0, pbi, pbi.Length, out ret);
    IntPtr peb = (IntPtr)BitConverter.ToInt32(pbi, 4);
    byte[] buf = new byte[4]; int read;
    ReadProcessMemory(h, (IntPtr)((int)peb + 0x10), buf, 4, out read);
    IntPtr pp = (IntPtr)BitConverter.ToInt32(buf, 0);
    ReadProcessMemory(h, (IntPtr)((int)pp + 0x48), buf, 4, out read);
    IntPtr env = (IntPtr)BitConverter.ToInt32(buf, 0);
    byte[] data = new byte[131072];
    ReadProcessMemory(h, env, data, data.Length, out read);
    string s = Encoding.Unicode.GetString(data, 0, Math.Max(0, read));
    int end = s.IndexOf("\0\0", StringComparison.Ordinal);
    if (end > 0) s = s.Substring(0, end);
    foreach (string kv in s.Split('\0')) {
      if (kv.Length > 0 && kv.Length < 300) Console.WriteLine(kv);
    }
    CloseHandle(h);
  }
}
