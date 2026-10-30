using System;
using System.Runtime.InteropServices;
using System.Text;
class Peb {
  [DllImport("kernel32.dll")] static extern IntPtr OpenProcess(int a, bool i, int pid);
  [DllImport("kernel32.dll")] static extern bool ReadProcessMemory(IntPtr h, IntPtr addr, byte[] buf, int size, out int read);
  [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr h);
  [DllImport("ntdll.dll")] static extern int NtQueryInformationProcess(IntPtr h, int cls, byte[] info, int len, out int ret);
  static void Main(string[] args) {
    int pid = int.Parse(args[0]);
    IntPtr h = OpenProcess(0x0410, false, pid);
    if (h == IntPtr.Zero) { Console.WriteLine("OpenProcess failed " + Marshal.GetLastWin32Error()); return; }
    try {
      byte[] pbi = new byte[24]; int ret;
      int st = NtQueryInformationProcess(h, 0, pbi, pbi.Length, out ret);
      IntPtr peb = (IntPtr)BitConverter.ToInt32(pbi, 4);
      byte[] buf = new byte[8]; int read;
      ReadProcessMemory(h, (IntPtr)((int)peb + 0x10), buf, 4, out read);
      IntPtr pp = (IntPtr)BitConverter.ToInt32(buf, 0);
      ReadProcessMemory(h, (IntPtr)((int)pp + 0x24), buf, 8, out read);
      int len = BitConverter.ToUInt16(buf, 0);
      IntPtr strp = (IntPtr)BitConverter.ToInt32(buf, 4);
      string s = "";
      if (len > 0 && len < 2000) { byte[] str = new byte[len]; ReadProcessMemory(h, strp, str, len, out read); s = Encoding.Unicode.GetString(str); }
      Console.WriteLine("st={0} peb=0x{1:X} pp=0x{2:X} len={3} cwd='{4}'", st, (int)peb, (int)pp, len, s);
    } finally { CloseHandle(h); }
  }
}
