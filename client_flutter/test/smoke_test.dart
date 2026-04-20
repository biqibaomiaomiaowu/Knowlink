import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:knowlink_client/app/app.dart';
import 'package:knowlink_client/app/router/app_router.dart';

void main() {
  testWidgets('app boots to KnowLink home', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        child: KnowLinkApp(routerConfig: AppRouter.createRouter()),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('KnowLink'), findsWidgets);
  });
}
