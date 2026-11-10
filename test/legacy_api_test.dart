// Guards the promise of package:window_manager/legacy.dart: code written for
// window_manager 0.5.x compiles unchanged. `_surface` names every public symbol
// of 0.5.2 with its old signature; it is compiled, never run, because running
// needs the native library. The tests below cover the parts that are plain
// Dart.
// ignore_for_file: unused_local_variable, unused_element, deprecated_member_use
// ignore_for_file: deprecated_member_use_from_same_package

import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:nativeapi/nativeapi.dart' as nativeapi;
import 'package:window_manager/legacy.dart';

class _Mixed with WindowListener {}

class _Extended extends WindowListener {}

class _Implemented implements WindowListener {
  final List<String> events = <String>[];

  @override
  void onWindowEvent(String eventName) => events.add(eventName);
  @override
  void onWindowClose() {}
  @override
  void onWindowFocus() {}
  @override
  void onWindowBlur() {}
  @override
  void onWindowMaximize() {}
  @override
  void onWindowUnmaximize() {}
  @override
  void onWindowMinimize() {}
  @override
  void onWindowRestore() {}
  @override
  void onWindowResize() {}
  @override
  void onWindowResized() {}
  @override
  void onWindowMove() {}
  @override
  void onWindowMoved() {}
  @override
  void onWindowEnterFullScreen() {}
  @override
  void onWindowLeaveFullScreen() {}
  @override
  void onWindowDocked() {}
  @override
  void onWindowUndocked() {}
}

Future<void> _surface() async {
  final WindowManager manager = WindowManager.instance;
  final bool hasListeners = windowManager.hasListeners;
  final List<WindowListener> listeners = windowManager.listeners;
  windowManager.addListener(_Mixed());
  windowManager.removeListener(_Extended());

  final double ratio = windowManager.getDevicePixelRatio();
  await windowManager.ensureInitialized();
  final int id = await windowManager.getId();
  await windowManager.setAsFrameless();
  await windowManager.waitUntilReadyToShow(
    const WindowOptions(
      size: Size(800, 600),
      center: true,
      minimumSize: Size(400, 300),
      maximumSize: Size(1600, 1200),
      alwaysOnTop: false,
      fullScreen: false,
      backgroundColor: Color(0x00000000),
      skipTaskbar: false,
      title: 'window_manager',
      titleBarStyle: TitleBarStyle.hidden,
      windowButtonVisibility: false,
    ),
    () {},
  );
  await windowManager.destroy();
  await windowManager.close();
  final bool isPreventClose = await windowManager.isPreventClose();
  await windowManager.setPreventClose(true);
  await windowManager.focus();
  await windowManager.blur();
  final bool isFocused = await windowManager.isFocused();
  await windowManager.show();
  await windowManager.show(inactive: true);
  await windowManager.hide();
  final bool isVisible = await windowManager.isVisible();
  final bool isMaximized = await windowManager.isMaximized();
  await windowManager.maximize();
  await windowManager.maximize(vertically: true);
  await windowManager.unmaximize();
  final bool isMinimized = await windowManager.isMinimized();
  await windowManager.minimize();
  await windowManager.restore();
  final bool isFullScreen = await windowManager.isFullScreen();
  await windowManager.setFullScreen(true);
  final bool isDockable = await windowManager.isDockable();
  final DockSide? dockSide = await windowManager.isDocked();
  await windowManager.dock(side: DockSide.left, width: 200);
  final bool undocked = await windowManager.undock();
  await windowManager.setAspectRatio(16 / 9);
  await windowManager.setBackgroundColor(const Color(0xFF000000));
  await windowManager.setAlignment(Alignment.center, animate: true);
  await windowManager.center(animate: true);
  final Rect bounds = await windowManager.getBounds();
  await windowManager.setBounds(
    const Rect.fromLTWH(0, 0, 800, 600),
    position: Offset.zero,
    size: const Size(800, 600),
    animate: true,
  );
  final Size size = await windowManager.getSize();
  await windowManager.setSize(const Size(800, 600), animate: true);
  final Offset position = await windowManager.getPosition();
  await windowManager.setPosition(Offset.zero, animate: true);
  await windowManager.setMinimumSize(const Size(400, 300));
  await windowManager.setMaximumSize(const Size(1600, 1200));
  final bool isResizable = await windowManager.isResizable();
  await windowManager.setResizable(true);
  final bool isMovable = await windowManager.isMovable();
  await windowManager.setMovable(true);
  final bool isMinimizable = await windowManager.isMinimizable();
  await windowManager.setMinimizable(true);
  final bool isClosable = await windowManager.isClosable();
  final bool isMaximizable = await windowManager.isMaximizable();
  await windowManager.setMaximizable(true);
  await windowManager.setClosable(true);
  final bool isAlwaysOnTop = await windowManager.isAlwaysOnTop();
  await windowManager.setAlwaysOnTop(true);
  final bool isAlwaysOnBottom = await windowManager.isAlwaysOnBottom();
  await windowManager.setAlwaysOnBottom(true);
  final String title = await windowManager.getTitle();
  await windowManager.setTitle('window_manager');
  await windowManager.setTitleBarStyle(
    TitleBarStyle.normal,
    windowButtonVisibility: true,
  );
  final int titleBarHeight = await windowManager.getTitleBarHeight();
  final bool isSkipTaskbar = await windowManager.isSkipTaskbar();
  await windowManager.setSkipTaskbar(true);
  await windowManager.setProgressBar(0.5);
  await windowManager.setIcon('images/icon.ico');
  final bool onAllWorkspaces = await windowManager.isVisibleOnAllWorkspaces();
  await windowManager.setVisibleOnAllWorkspaces(
    true,
    visibleOnFullScreen: true,
  );
  await windowManager.setBadgeLabel();
  await windowManager.setBadgeLabel('4');
  final bool hasShadow = await windowManager.hasShadow();
  await windowManager.setHasShadow(true);
  final double opacity = await windowManager.getOpacity();
  await windowManager.setOpacity(1);
  await windowManager.setBrightness(Brightness.dark);
  await windowManager.setIgnoreMouseEvents(true, forward: true);
  await windowManager.popUpWindowMenu();
  await windowManager.startDragging();
  await windowManager.startResizing(ResizeEdge.bottomRight);
  final bool grabbed = await windowManager.grabKeyboard();
  final bool ungrabbed = await windowManager.ungrabKeyboard();

  final Offset calculated = await calcWindowPosition(
    const Size(800, 600),
    Alignment.topLeft,
  );

  // Constructor signature probes: non-const calls also compile when Flutter
  // instruments widgets in local path dependencies for creation tracking.
  // ignore: prefer_const_constructors
  final Widget move = DragToMoveArea(child: const SizedBox());
  // ignore: prefer_const_constructors
  final Widget resize = DragToResizeArea(
    resizeEdgeSize: 6,
    resizeEdgeColor: Color(0x00000000),
    resizeEdgeMargin: EdgeInsets.zero,
    enableResizeEdges: const [ResizeEdge.top],
    child: const SizedBox(),
  );
  // ignore: prefer_const_constructors
  final Widget frame = VirtualWindowFrame(child: const SizedBox());
  final TransitionBuilder builder = VirtualWindowFrameInit();
  // ignore: prefer_const_constructors
  final Widget caption = WindowCaption(
    title: const Text('window_manager'),
    backgroundColor: Color(0x00000000),
    brightness: Brightness.dark,
  );
  final Widget captionButton = WindowCaptionButton.close(
    brightness: Brightness.dark,
    onPressed: () {},
  );
  const double captionHeight = kWindowCaptionHeight;
}

class _RunOnClose with WindowListener {
  _RunOnClose(this.action);

  final void Function() action;

  @override
  void onWindowEvent(String eventName) {
    if (eventName == kWindowEventClose) action();
  }
}

class _Typed with WindowListener {
  final List<String> calls = <String>[];

  @override
  void onWindowFocus() => calls.add('focus');

  @override
  void onWindowBlur() => calls.add('blur');

  @override
  void onWindowMaximize() => calls.add('maximize');

  @override
  void onWindowUnmaximize() => calls.add('unmaximize');
}

class _FakeNativeWindow extends nativeapi.Window {
  _FakeNativeWindow() : super.borrowed(0);

  bool visible = false;
  bool minimized = false;
  bool maximized = false;
  bool fullscreen = false;
  bool refuseVisibilityChanges = false;
  bool rejectClose = false;
  int closeAttempts = 0;
  FutureOr<void> Function(nativeapi.WindowEvent)? _callback;

  bool get isListening => _callback != null;

  // As nativeapi on macOS, a minimized window does not count as visible.
  @override
  bool get isVisible => visible && !minimized;

  @override
  bool get isMinimized => minimized;

  @override
  bool get isMaximized => maximized;

  @override
  bool get isFullScreen => fullscreen;

  @override
  void show() => visible = visible || !refuseVisibilityChanges;

  @override
  void showInactive() => show();

  @override
  void hide() => visible = visible && refuseVisibilityChanges;

  @override
  bool close() {
    closeAttempts++;
    return !rejectClose;
  }

  @override
  void minimize() => minimized = true;

  @override
  void restore() => minimized = false;

  @override
  nativeapi.ListenerId addListener(
    FutureOr<void> Function(nativeapi.WindowEvent) listener,
  ) {
    _callback = listener;
    return 1;
  }

  @override
  bool removeListener(nativeapi.ListenerId id) {
    _callback = null;
    return true;
  }

  Future<void> fire(nativeapi.WindowEvent event) async {
    await _callback?.call(event);
  }
}

void main() {
  test('event names are still exported', () {
    expect(
      [
        kWindowEventClose,
        kWindowEventFocus,
        kWindowEventBlur,
        kWindowEventMaximize,
        kWindowEventUnmaximize,
        kWindowEventMinimize,
        kWindowEventRestore,
        kWindowEventResize,
        kWindowEventResized,
        kWindowEventMove,
        kWindowEventMoved,
        kWindowEventEnterFullScreen,
        kWindowEventLeaveFullScreen,
        kWindowEventDocked,
        kWindowEventUndocked,
      ],
      [
        'close',
        'focus',
        'blur',
        'maximize',
        'unmaximize',
        'minimize',
        'restore',
        'resize',
        'resized',
        'move',
        'moved',
        'enter-full-screen',
        'leave-full-screen',
        'docked',
        'undocked',
      ],
    );
    expect(DockSide.values, hasLength(2));
    expect(ResizeEdge.values, hasLength(8));
    expect(TitleBarStyle.values, hasLength(2));
  });

  test('preventClose turns close() into an onWindowClose report', () async {
    final listener = _Implemented();
    windowManager.addListener(listener);
    addTearDown(() => windowManager.removeListener(listener));

    await windowManager.setPreventClose(true);
    expect(await windowManager.isPreventClose(), isTrue);
    await windowManager.close();
    expect(listener.events, [kWindowEventClose]);

    await windowManager.setPreventClose(false);
    expect(await windowManager.isPreventClose(), isFalse);
  });

  test(
    'removing a listener during delivery does not starve later listeners',
    () async {
      final events = <String>[];
      late final _RunOnClose removed;
      final first = _RunOnClose(() => windowManager.removeListener(removed));
      removed = _RunOnClose(() => events.add('removed'));
      final last = _RunOnClose(() => events.add('last'));
      windowManager.addListener(first);
      windowManager.addListener(removed);
      windowManager.addListener(last);
      addTearDown(() {
        windowManager.removeListener(first);
        windowManager.removeListener(removed);
        windowManager.removeListener(last);
      });

      await windowManager.setPreventClose(true);
      addTearDown(() => windowManager.setPreventClose(false));
      await windowManager.close();
      expect(events, ['last']);
    },
  );

  test('a listener added during dispatch joins the next event only', () async {
    final received = <String>[];
    late final _RunOnClose newlyAdded;
    var added = false;
    final first = _RunOnClose(() {
      if (!added) {
        added = true;
        windowManager.addListener(newlyAdded);
      }
    });
    newlyAdded = _RunOnClose(() => received.add('new'));
    final tail = _RunOnClose(() => received.add('tail'));
    windowManager.addListener(first);
    windowManager.addListener(tail);
    addTearDown(() {
      windowManager.removeListener(first);
      windowManager.removeListener(tail);
      windowManager.removeListener(newlyAdded);
    });
    await windowManager.setPreventClose(true);
    addTearDown(() => windowManager.setPreventClose(false));

    await windowManager.close();
    expect(received, ['tail']);
    await windowManager.close();
    expect(received, ['tail', 'tail', 'new']);
  });

  test('listeners are tracked without touching the window', () {
    final listener = _Implemented();
    expect(windowManager.hasListeners, isFalse);
    windowManager.addListener(listener);
    expect(windowManager.hasListeners, isTrue);
    expect(windowManager.listeners, [listener]);
    windowManager.removeListener(listener);
    expect(windowManager.hasListeners, isFalse);
  });

  group('nativeapi bridge', () {
    late _FakeNativeWindow fake;
    late _Implemented listener;

    setUp(() {
      fake = _FakeNativeWindow();
      listener = _Implemented();
      windowManager.debugBindWindow(fake);
      windowManager.addListener(listener);
    });

    tearDown(() {
      windowManager.removeListener(listener);
      windowManager.debugBindWindow(null);
    });

    test('reports show and hide only when visibility changes', () async {
      await windowManager.show();
      await windowManager.show();
      await windowManager.hide();
      await windowManager.hide();
      await windowManager.show(inactive: true);
      expect(listener.events, ['show', 'hide', 'show']);
    });

    test('a minimized window counts as shown', () async {
      fake.visible = true;
      fake.minimized = true;
      await windowManager.hide();
      expect(listener.events, ['hide']);

      fake.visible = true;
      fake.minimized = true;
      await windowManager.show();
      expect(fake.minimized, isFalse);
      expect(listener.events, ['hide', 'show']);
    });

    test('no show or hide when the platform keeps the visibility', () async {
      fake.refuseVisibilityChanges = true;
      await windowManager.show();
      fake.visible = true;
      await windowManager.hide();
      expect(listener.events, isEmpty);
    });

    test('a vetoed native close request cannot quit the app', () async {
      fake.rejectClose = true;
      windowManager.debugCloseSupported = true;
      addTearDown(() => windowManager.debugCloseSupported = null);
      await windowManager.setPreventClose(false);
      await windowManager.close();
      expect(fake.closeAttempts, 1);
      expect(listener.events, isEmpty);
    });

    test('the last listener going away unwires the window', () {
      expect(fake.isListening, isTrue);
      windowManager.removeListener(listener);
      expect(fake.isListening, isFalse);
      windowManager.addListener(listener);
      expect(fake.isListening, isTrue);
    });

    test('a minimized maximized window coming back is not minimized', () async {
      fake.minimized = true;
      await fake.fire(const nativeapi.WindowMinimizedEvent(windowId: 1));
      fake.minimized = false;
      fake.maximized = true;
      await fake.fire(const nativeapi.WindowMaximizedEvent(windowId: 1));
      fake.maximized = false;
      await fake.fire(const nativeapi.WindowRestoredEvent(windowId: 1));

      expect(listener.events, [
        kWindowEventMinimize,
        kWindowEventMaximize,
        kWindowEventUnmaximize,
      ]);
    });

    test('restoring a minimized window keeps it maximized', () async {
      fake.maximized = true;
      await fake.fire(const nativeapi.WindowMaximizedEvent(windowId: 1));
      fake.minimized = true;
      await fake.fire(const nativeapi.WindowMinimizedEvent(windowId: 1));
      fake.minimized = false;
      await fake.fire(const nativeapi.WindowRestoredEvent(windowId: 1));
      fake.maximized = false;
      await fake.fire(const nativeapi.WindowRestoredEvent(windowId: 1));

      expect(listener.events, [
        kWindowEventMaximize,
        kWindowEventMinimize,
        kWindowEventRestore,
        kWindowEventUnmaximize,
      ]);
    });

    test('named callbacks follow onWindowEvent', () async {
      final typed = _Typed();
      windowManager.addListener(typed);
      addTearDown(() => windowManager.removeListener(typed));

      await fake.fire(const nativeapi.WindowFocusedEvent(windowId: 1));
      await fake.fire(const nativeapi.WindowBlurredEvent(windowId: 1));
      fake.maximized = true;
      await fake.fire(const nativeapi.WindowMaximizedEvent(windowId: 1));
      fake.maximized = false;
      await fake.fire(const nativeapi.WindowRestoredEvent(windowId: 1));
      await windowManager.show();

      expect(typed.calls, ['focus', 'blur', 'maximize', 'unmaximize']);
    });

    test('events without a 0.5.x counterpart are dropped', () async {
      await fake.fire(const nativeapi.WindowCreatedEvent(windowId: 1));
      await fake.fire(const nativeapi.WindowClosedEvent(windowId: 1));
      expect(listener.events, isEmpty);
    });
  });

  test('what the platform cannot do answers instead of throwing', () async {
    // Windows can report a running shell even in a test without an app window.
    if (!Platform.isWindows) {
      expect(await windowManager.isDockable(), isFalse);
    }
    expect(await windowManager.isDocked(), isNull);
    expect(await windowManager.undock(), isFalse);
    expect(await windowManager.grabKeyboard(), isFalse);
    expect(await windowManager.ungrabKeyboard(), isFalse);
    await windowManager.dock(side: DockSide.right, width: 100);
    await windowManager.popUpWindowMenu();
    await windowManager.ensureInitialized();
  });
}
