import 'package:flutter_riverpod/flutter_riverpod.dart';

final handoutRequestStateProvider = StateProvider<AsyncValue<void>>(
  (ref) => const AsyncData<void>(null),
);

final quizRequestStateProvider = StateProvider<AsyncValue<void>>(
  (ref) => const AsyncData<void>(null),
);

final reviewRequestStateProvider = StateProvider<AsyncValue<void>>(
  (ref) => const AsyncData<void>(null),
);
