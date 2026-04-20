import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:knowlink_client/shared/providers/feature_request_providers.dart';

void main() {
  test('feature request providers default to idle async state', () {
    final container = ProviderContainer();
    addTearDown(container.dispose);

    final handoutState = container.read(handoutRequestStateProvider);
    final quizState = container.read(quizRequestStateProvider);
    final reviewState = container.read(reviewRequestStateProvider);

    expect(handoutState, const AsyncData<void>(null));
    expect(quizState, const AsyncData<void>(null));
    expect(reviewState, const AsyncData<void>(null));
  });
}
