import 'dart:ffi';
import 'dart:io';

import 'package:ffi/ffi.dart';

const _gwOwner = 4;

/// The `HWND` of this process's only top-level window that hosts a Flutter
/// view, or 0 when there is none, more than one, or the platform is not
/// Windows.
///
/// nativeapi finds the current window on Windows through `GetActiveWindow()`,
/// which knows nothing of a window that is still hidden. A Flutter runner
/// parents the engine's view (window class `FLUTTERVIEW`) to its top-level
/// window, visible or not; when that identifies a single window of this
/// process, it is the app's window. With several such windows the answer
/// would be a guess, so there is none.
int findSoleFlutterHostWindow() {
  if (!Platform.isWindows) return 0;
  final user32 = DynamicLibrary.open('user32.dll');
  final kernel32 = DynamicLibrary.open('kernel32.dll');
  final findWindowEx = user32
      .lookupFunction<
        IntPtr Function(IntPtr, IntPtr, Pointer<Utf16>, Pointer<Utf16>),
        int Function(int, int, Pointer<Utf16>, Pointer<Utf16>)
      >('FindWindowExW');
  final getWindowThreadProcessId = user32
      .lookupFunction<
        Uint32 Function(IntPtr, Pointer<Uint32>),
        int Function(int, Pointer<Uint32>)
      >('GetWindowThreadProcessId');
  final getWindow = user32
      .lookupFunction<IntPtr Function(IntPtr, Uint32), int Function(int, int)>(
        'GetWindow',
      );
  final getCurrentProcessId = kernel32
      .lookupFunction<Uint32 Function(), int Function()>('GetCurrentProcessId');

  final viewClass = 'FLUTTERVIEW'.toNativeUtf16();
  final processId = calloc<Uint32>();
  try {
    final self = getCurrentProcessId();
    var found = 0;
    var hwnd = 0;
    // Every top-level window of the desktop, hidden ones included. The bound
    // only guards against a z-order that keeps changing under the walk.
    for (var i = 0; i < 1 << 16; i++) {
      hwnd = findWindowEx(0, hwnd, nullptr, nullptr);
      if (hwnd == 0) break;
      getWindowThreadProcessId(hwnd, processId);
      if (processId.value != self) continue;
      if (getWindow(hwnd, _gwOwner) != 0) continue;
      if (findWindowEx(hwnd, 0, viewClass, nullptr) == 0) continue;
      if (found != 0 && found != hwnd) return 0;
      found = hwnd;
    }
    return found;
  } finally {
    calloc.free(viewClass);
    calloc.free(processId);
  }
}
