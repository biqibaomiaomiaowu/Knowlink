import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:knowlink_client/app/app.dart';

void main() {
  testWidgets('app boots to KnowLink home', (tester) async {
    await tester.pumpWidget(const ProviderScope(child: KnowLinkApp()));
    await tester.pumpAndSettle();

    expect(find.text('KnowLink'), findsWidgets);
  });
}
