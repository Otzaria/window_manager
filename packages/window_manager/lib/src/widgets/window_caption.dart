import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show MissingPluginException;

import 'package:window_manager/src/widgets/drag_to_move_area.dart';
import 'package:window_manager/src/widgets/window_caption_button.dart';
import 'package:window_manager/src/window_listener.dart';
import 'package:window_manager/src/window_manager.dart';

const double kWindowCaptionHeight = 32;

/// A widget to simulate the title bar of windows 11.
///
/// {@tool snippet}
///
/// ```dart
/// Scaffold(
///   appBar: PreferredSize(
///     child: WindowCaption(
///       brightness: Theme.of(context).brightness,
///       title: Text('window_manager_example'),
///     ),
///     preferredSize: const Size.fromHeight(kWindowCaptionHeight),
///   ),
/// )
/// ```
/// {@end-tool}
class WindowCaption extends StatefulWidget {
  const WindowCaption({
    super.key,
    this.title,
    this.backgroundColor,
    this.brightness,
  });

  final Widget? title;
  final Color? backgroundColor;
  final Brightness? brightness;

  @override
  State<WindowCaption> createState() => _WindowCaptionState();
}

class _WindowCaptionState extends State<WindowCaption> with WindowListener {
  bool _isMaximized = false;
  bool _receivedMaximizeEvent = false;

  @override
  void initState() {
    super.initState();
    windowManager.addListener(this);
    // One platform query per caption lifetime, not one per widget rebuild.
    unawaited(_readInitialMaximized());
  }

  Future<void> _readInitialMaximized() async {
    try {
      final maximized = await windowManager.isMaximized();
      // A native state event may have arrived while the query was pending.
      if (!mounted || _receivedMaximizeEvent || maximized == _isMaximized) {
        return;
      }
      setState(() => _isMaximized = maximized);
    } on MissingPluginException {
      // Widget tests do not have a native desktop window.
    }
  }

  void _setMaximized(bool value) {
    _receivedMaximizeEvent = true;
    if (!mounted || _isMaximized == value) return;
    setState(() => _isMaximized = value);
  }

  @override
  void dispose() {
    windowManager.removeListener(this);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: widget.backgroundColor ??
            (widget.brightness == Brightness.dark
                ? const Color(0xff1C1C1C)
                : Colors.transparent),
      ),
      child: Row(
        children: [
          Expanded(
            child: DragToMoveArea(
              child: SizedBox(
                height: double.infinity,
                child: Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.only(left: 16),
                      child: DefaultTextStyle(
                        style: TextStyle(
                          color: widget.brightness == Brightness.light
                              ? Colors.black.withValues(alpha: 0.8956)
                              : Colors.white,
                          fontSize: 14,
                        ),
                        child: widget.title ?? Container(),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
          WindowCaptionButton.minimize(
            brightness: widget.brightness,
            onPressed: () async {
              bool isMinimized = await windowManager.isMinimized();
              if (isMinimized) {
                windowManager.restore();
              } else {
                windowManager.minimize();
              }
            },
          ),
          _isMaximized
              ? WindowCaptionButton.unmaximize(
                  brightness: widget.brightness,
                  onPressed: () {
                    windowManager.unmaximize();
                  },
                )
              : WindowCaptionButton.maximize(
                  brightness: widget.brightness,
                  onPressed: () {
                    windowManager.maximize();
                  },
                ),
          WindowCaptionButton.close(
            brightness: widget.brightness,
            onPressed: () {
              windowManager.close();
            },
          ),
        ],
      ),
    );
  }

  @override
  void onWindowMaximize() => _setMaximized(true);

  @override
  void onWindowUnmaximize() => _setMaximized(false);
}
