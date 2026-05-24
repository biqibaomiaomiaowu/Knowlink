import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'course_progress_models.dart';
import 'course_summary.dart';
import 'home_dashboard_models.dart';

class HomeState {
  const HomeState({
    required this.dashboard,
    required this.progressByCourseId,
    required this.progressSave,
    required this.currentCourseSwitch,
  });

  factory HomeState.initial() {
    return const HomeState(
      dashboard: AsyncData<HomeDashboardModel?>(null),
      progressByCourseId: <int, AsyncValue<CourseProgressModel>>{},
      progressSave: AsyncData<CourseProgressModel?>(null),
      currentCourseSwitch: AsyncData<CourseSummaryModel?>(null),
    );
  }

  final AsyncValue<HomeDashboardModel?> dashboard;
  final Map<int, AsyncValue<CourseProgressModel>> progressByCourseId;
  final AsyncValue<CourseProgressModel?> progressSave;
  final AsyncValue<CourseSummaryModel?> currentCourseSwitch;

  HomeDashboardModel? get dashboardValue => dashboard.valueOrNull;

  HomeState copyWith({
    AsyncValue<HomeDashboardModel?>? dashboard,
    Map<int, AsyncValue<CourseProgressModel>>? progressByCourseId,
    AsyncValue<CourseProgressModel?>? progressSave,
    AsyncValue<CourseSummaryModel?>? currentCourseSwitch,
  }) {
    return HomeState(
      dashboard: dashboard ?? this.dashboard,
      progressByCourseId: progressByCourseId ?? this.progressByCourseId,
      progressSave: progressSave ?? this.progressSave,
      currentCourseSwitch: currentCourseSwitch ?? this.currentCourseSwitch,
    );
  }
}
