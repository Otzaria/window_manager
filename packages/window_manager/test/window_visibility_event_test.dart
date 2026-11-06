import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:window_manager/window_manager.dart';

class _Listener with WindowListener {
  final events = <String>[];
  final dedicated = <String>[];

  @override
  void onWindowEvent(String eventName) => events.add(eventName);

  @override
  void onWindowFocus() => dedicated.add('focus');

  @override
  void onWindowBlur() => dedicated.add('blur');

  @override
  void onWindowMinimize() => dedicated.add('minimize');

  @override
  void onWindowRestore() => dedicated.add('restore');
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  const channel = MethodChannel('window_manager');
  final messenger =
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;
  final manager = WindowManager.instance;

  Future<void> nativeEvent(String name) async {
    final response = await messenger.handlePlatformMessage(
      channel.name,
      channel.codec.encodeMethodCall(
        MethodCall('onEvent', {'eventName': name}),
      ),
      null,
    );
    expect(channel.codec.decodeEnvelope(response!), isNull);
  }

  tearDown(() {
    for (final listener in manager.listeners) {
      manager.removeListener(listener);
    }
  });

  test('visibility events reach every generic listener in native order',
      () async {
    final first = _Listener();
    final second = _Listener();
    manager.addListener(first);
    manager.addListener(second);

    for (final event in ['show', 'hide', 'show']) {
      await nativeEvent(event);
    }

    expect(first.events, ['show', 'hide', 'show']);
    expect(second.events, first.events);
    expect(first.dedicated, isEmpty);
    expect(second.dedicated, isEmpty);
  });

  test('focus and minimized state keep their existing dedicated callbacks',
      () async {
    final listener = _Listener();
    manager.addListener(listener);
    for (final event in [
      'show',
      'focus',
      'minimize',
      'restore',
      'blur',
      'hide',
    ]) {
      await nativeEvent(event);
    }

    expect(
      listener.events,
      ['show', 'focus', 'minimize', 'restore', 'blur', 'hide'],
    );
    expect(listener.dedicated, ['focus', 'minimize', 'restore', 'blur']);
  });

  test('a detached listener cannot receive later visibility events', () async {
    final removed = _Listener();
    final survivor = _Listener();
    manager.addListener(removed);
    manager.addListener(survivor);
    await nativeEvent('show');
    manager.removeListener(removed);
    await nativeEvent('hide');
    expect(removed.events, ['show']);
    expect(survivor.events, ['show', 'hide']);
  });
}
