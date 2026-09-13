// Windows inbox kernel32 only, used by diagnostic PowerShell, never by MQL5.
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;
public static class QrosNativeFileIdentity {
    [StructLayout(LayoutKind.Sequential)]
    private struct Info {
        public uint Attributes;
        public System.Runtime.InteropServices.ComTypes.FILETIME Creation;
        public System.Runtime.InteropServices.ComTypes.FILETIME Access;
        public System.Runtime.InteropServices.ComTypes.FILETIME Write;
        public uint Volume;
        public uint SizeHigh;
        public uint SizeLow;
        public uint Links;
        public uint IndexHigh;
        public uint IndexLow;
    }
    [DllImport("kernel32.dll", SetLastError=true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool GetFileInformationByHandle(SafeFileHandle h, out Info info);
    public static string Read(SafeFileHandle h) {
        Info info;
        if (!GetFileInformationByHandle(h, out info))
            throw new Win32Exception(Marshal.GetLastWin32Error());
        return info.Volume.ToString("X8") + ":" + info.IndexHigh.ToString("X8") + info.IndexLow.ToString("X8");
    }
}
