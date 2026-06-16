import 'dart:ui';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:knowlink_client/core/widgets/knowlink_widgets.dart';

void main() {
  testWidgets('HoverLift floats its child on mouse hover', (tester) async {
    const targetKey = Key('hover-target');

    await tester.pumpWidget(
      const MaterialApp(
        home: Center(
          child: HoverLift(
            child: SizedBox(
              key: targetKey,
              width: 80,
              height: 40,
            ),
          ),
        ),
      ),
    );

    final before = tester.getTopLeft(find.byKey(targetKey));
    final gesture = await tester.createGesture(kind: PointerDeviceKind.mouse);
    await gesture.addPointer(location: before + const Offset(8, 8));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 200));

    final after = tester.getTopLeft(find.byKey(targetKey));
    expect(after.dy, lessThan(before.dy));

    await gesture.removePointer();
  });
}
