import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:window_manager/window_manager.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  const channel = MethodChannel('window_manager');
  final messenger =
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;

  tearDown(() {
    messenger.setMockMethodCallHandler(channel, null);
  });

  testWidgets('caption does not query the native maximize state on rebuild',
      (tester) async {
    var reads = 0;
    messenger.setMockMethodCallHandler(channel, (call) async {
      if (call.method == 'isMaximized') {
        reads++;
        return false;
      }
      return null;
    });

    Future<void> show(String title) => tester.pumpWidget(
          MaterialApp(
            home: SizedBox(
              height: kWindowCaptionHeight,
              child: WindowCaption(title: Text(title)),
            ),
          ),
        );

    await show('one');
    await tester.pump();
    expect(reads, 1);

    await show('two');
    await tester.pump();
    expect(reads, 1);

    final response = await messenger.handlePlatformMessage(
      channel.name,
      channel.codec.encodeMethodCall(
        const MethodCall('onEvent', {'eventName': 'maximize'}),
      ),
      null,
    );
    expect(channel.codec.decodeEnvelope(response!), isNull);
    await tester.pump();

    final maximizeButton = tester.widget<WindowCaptionButton>(
      find.byType(WindowCaptionButton).at(1),
    );
    expect(maximizeButton.iconName, 'icon_chrome_unmaximize');
    expect(reads, 1);
  });
}
