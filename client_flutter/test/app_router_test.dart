import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:knowlink_client/app/router/app_router.dart';
import 'package:knowlink_client/core/network/api_client.dart';
import 'package:knowlink_client/features/course_import/course_import_page.dart';
import 'package:knowlink_client/features/course_recommend/course_recommend_page.dart';
import 'package:knowlink_client/features/handout/handout_page.dart';
import 'package:knowlink_client/features/home/home_page.dart';
import 'package:knowlink_client/features/inquiry/inquiry_page.dart';
import 'package:knowlink_client/features/parse_progress/parse_progress_page.dart';
import 'package:knowlink_client/features/qa/qa_page.dart';
import 'package:knowlink_client/features/quiz/quiz_page.dart';
import 'package:knowlink_client/features/review/review_page.dart';
import 'package:knowlink_client/shared/models/inquiry_models.dart';
import 'package:knowlink_client/shared/models/pipeline_status.dart';
import 'package:knowlink_client/shared/models/resource_upload_models.dart';
import 'package:knowlink_client/shared/providers/course_flow_providers.dart';
import 'package:knowlink_client/shared/providers/course_recommend_provider.dart';

void main() {
  testWidgets('frozen routes resolve to expected pages', (tester) async {
    final router = AppRouter.createRouter();
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(_RouterFakeApiClient()),
      ],
    );
    addTearDown(container.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp.router(
          routerConfig: router,
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.byType(HomePage), findsOneWidget);

    final routes = <String, Finder>{
      '/import': find.byType(CourseImportPage),
      '/recommend': find.byType(CourseRecommendPage),
      '/courses/101/progress': find.byType(ParseProgressPage),
      '/courses/101/inquiry': find.byType(InquiryPage),
      '/courses/101/handout': find.byType(HandoutPage),
      '/quizzes/8001': find.byType(QuizPage),
      '/courses/101/review': find.byType(ReviewPage),
    };

    for (final entry in routes.entries) {
      router.go(entry.key);
      await tester.pumpAndSettle();
      expect(
        entry.value,
        findsOneWidget,
        reason: 'route ${entry.key} should resolve',
      );
    }

    router.go('/courses/205/qa/9876');
    await tester.pumpAndSettle();
    expect(find.byType(QaPage), findsOneWidget);
    expect(find.textContaining('QA'), findsOneWidget);
    expect(find.textContaining('205'), findsOneWidget);
    expect(find.textContaining('9876'), findsOneWidget);

    router.go('/quizzes/8001');
    await tester.pumpAndSettle();
    expect(find.byType(QuizPage), findsOneWidget);
    expect(find.textContaining('8001'), findsOneWidget);

    router.go('/');
    await tester.pumpAndSettle();
  });

  testWidgets('course routes sync URL courseId into course flow', (
    tester,
  ) async {
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(_RouterFakeApiClient()),
      ],
    );
    final router = AppRouter.createRouter();
    addTearDown(container.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp.router(
          routerConfig: router,
        ),
      ),
    );
    await tester.pumpAndSettle();

    router.go('/import');
    await tester.pumpAndSettle();
    expect(find.byType(CourseImportPage), findsOneWidget);
    expect(container.read(courseFlowProvider).courseId, isNull);

    router.go('/import?courseId=101');
    await tester.pumpAndSettle();
    expect(find.byType(CourseImportPage), findsOneWidget);
    expect(find.textContaining('101'), findsOneWidget);
    expect(container.read(courseFlowProvider).courseId, '101');

    router.go('/courses/205/progress');
    await tester.pumpAndSettle();
    expect(find.byType(ParseProgressPage), findsOneWidget);
    expect(container.read(courseFlowProvider).courseId, '205');

    router.go('/courses/306/qa/9876');
    await tester.pumpAndSettle();
    expect(find.byType(QaPage), findsOneWidget);
    expect(container.read(courseFlowProvider).courseId, '306');
  });
}

class _RouterFakeApiClient extends ApiClient {
  @override
  Future<List<CourseResourceModel>> fetchCourseResources(
      String courseId) async {
    return const [];
  }

  @override
  Future<PipelineStatusModel> fetchPipelineStatus(String courseId) async {
    return PipelineStatusModel.fromJson({
      'courseStatus': {
        'lifecycleStatus': 'resource_ready',
        'pipelineStage': 'parse',
        'pipelineStatus': 'queued',
      },
      'progressPct': 0,
      'steps': [],
      'activeParseRunId': null,
      'activeHandoutVersionId': null,
      'nextAction': 'poll',
    });
  }

  @override
  Future<InquiryQuestionsModel> fetchInquiryQuestions(String courseId) async {
    return InquiryQuestionsModel.fromJson({
      'version': 1,
      'questions': [],
    });
  }
}
