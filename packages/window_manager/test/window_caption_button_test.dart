import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:window_manager/window_manager.dart';

void main() {
  testWidgets('caption icon painters repaint after changing brightness',
      (tester) async {
    Future<void> show(Brightness brightness) => tester.pumpWidget(
          MaterialApp(
            home: Center(
              child: WindowCaptionButton.close(
                brightness: brightness,
                onPressed: () {},
              ),
            ),
          ),
        );

    CustomPainter iconPainter() => tester
        .widget<CustomPaint>(
          find.descendant(
            of: find.byType(WindowCaptionButtonIcon),
            matching: find.byType(CustomPaint),
          ),
        )
        .painter!;

    await show(Brightness.light);
    final lightPainter = iconPainter();
    await show(Brightness.dark);
    final darkPainter = iconPainter();

    expect(darkPainter.shouldRepaint(lightPainter), isTrue);
    expect(darkPainter.shouldRepaint(darkPainter), isFalse);
  });

  testWidgets('custom caption icons are rendered instead of the default',
      (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Center(
          child: WindowCaptionButton(
            icon: const Text('Custom icon'),
            onPressed: () {},
          ),
        ),
      ),
    );

    expect(find.text('Custom icon'), findsOneWidget);
    expect(find.byType(WindowCaptionButtonIcon), findsNothing);
  });
}
