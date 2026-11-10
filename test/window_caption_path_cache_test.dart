import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:window_manager/window_manager.dart';

void main() {
  testWidgets('all four cached glyph paths render across color changes', (
    tester,
  ) async {
    final variants = <WindowCaptionButton Function(Brightness)>[
      (brightness) => WindowCaptionButton.minimize(
        brightness: brightness,
        onPressed: () {},
      ),
      (brightness) => WindowCaptionButton.maximize(
        brightness: brightness,
        onPressed: () {},
      ),
      (brightness) => WindowCaptionButton.unmaximize(
        brightness: brightness,
        onPressed: () {},
      ),
      (brightness) => WindowCaptionButton.close(
        brightness: brightness,
        onPressed: () {},
      ),
    ];

    for (final variant in variants) {
      for (final brightness in [Brightness.light, Brightness.dark]) {
        await tester.pumpWidget(
          MaterialApp(
            home: Center(
              child: RepaintBoundary(child: variant(brightness)),
            ),
          ),
        );
        await tester.pump();
        expect(find.byType(WindowCaptionButtonIcon), findsOneWidget);
        expect(tester.takeException(), isNull);
      }
    }
  });
}
